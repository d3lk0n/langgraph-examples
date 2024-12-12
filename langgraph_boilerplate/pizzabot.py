from typing import TypedDict
import requests
from os import environ
from openai import OpenAI
from dotenv import load_dotenv
import json

from fuzzywuzzy import fuzz
from langdetect import detect

from langgraph.graph import END, StateGraph
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
)
from enum import Enum


class ChatbotState(TypedDict):
    """
    Messages have the type "list". The `add_messages` function
    in the annotation defines how this state key should be updated
    (in this case, it appends messages to the list, rather than overwriting them)
    """
    input: str
    slots: dict
    messages: list
    active_order: bool
    confirm_order: bool
    additional_information: bool
    invalid: bool
    ended: bool
    pizza_id: str
    customer_address: tuple[str]
    order_id: str
    user_language: str

class Nodes(Enum):
    ENTRY = "entry"
    CHECKER = "checker"
    ORDER_FORM = "order_form"
    RETRIEVAL = "retrieval"
    END = "end"

class OrderSlots(Enum):
    PIZZA_NAME = "pizza_name"
    CUSTOMER_ADDRESS = "customer_address"
    ORDER_ID = "order_id"
    ADDITIONAL_INFORMATION = "additional_information"
    CUSTOMER_TEL_NUMBER = "customer_tel_number"
    DELIVERY_TIME = "delivery_time"

class SupportedLanguages(Enum):
    ENGLISH = "english"
    GERMAN = "german"

class LanguageNode:
    """
    Detects language of user input.
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> str:
        """
        Returns fallback message
        """
        _input = state['input']
        detected_language = detect(_input)
        if detect=='de':
            state["user_language"] = SupportedLanguages.GERMAN.name
        elif detect=='en':
            state["user_language"] = SupportedLanguages.ENGLISH.name
        #default
        else:                       
            state["user_language"] = SupportedLanguages.ENGLISH.name

             


class CheckerNode:
    """
    This node checks whether user input is valid
    """
    
    def __init__(self, order_keywords: list = ["order"], confirm_keywords: list = ["yes", "Yes"]):
        self.order_keywords = order_keywords
        self.confirm_keywords = confirm_keywords
        

    def invoke(self, state: ChatbotState) -> str:
        """
        Checks whether the input is a valid request for pizza order
        """
        _input = state['input']
        
        ## current idea:
        ## state __ missing -> ask for it -> and so on, only in active order
        ## after active order, confirm order
        
        if state['confirm_order']:
            if not any(keyword in _input for keyword in self.confirm_keywords):
                #customer provides no further information
                state["confirm_order"] = False
                return {
                    "messages": state["messages"],
                    "confirm_order": state["confirm_order"]
                }
            else:
                #customer provides further contact/delivery information
                state["additional_information"] = True
                return {
                    "messages": state["messages"],
                    "additional_information": state["additional_information"]
                }
                
        # add constraints for additional info
        
        if state['active_order']:
            #TODO instead check whether states pizza_id, customer_address... are valid
            if OrderSlots.PIZZA_NAME.value in state["messages"][-1].content:
                pizza_id = check_pizzas(_input)
                if pizza_id is not None:
                    #found pizza type
                    state['pizza_id'] = pizza_id
                    return {
                        "messages": state["messages"],
                        "pizza_id": state["pizza_id"]
                    }
                else:
                    state["invalid"] = True
                    state['messages'].append(AIMessage(content="Invalid pizza type. Please specify a valid type (e.g. a pizza Pepperoni)'."))
                    return {
                        "messages": state["messages"],
                        "invalid": state["invalid"]
                    }
                    
            elif OrderSlots.CUSTOMER_ADDRESS.value in state["messages"][-1].content:
                customer_address = check_customer_address(_input)
                if customer_address is not None:
                    state['customer_address'] = customer_address
                    return {
                        "messages": state["messages"],
                        "customer_address": state["customer_address"]
                    }
                else:
                    state["invalid"] = True
                    state['messages'].append(AIMessage(content="Invalid customer address. Please keep in mind, we only deliver to Halle, Leipzig and Dresden."))
                    return {
                        "messages": state["messages"],
                        "invalid": state["invalid"]
                    }
        
        if not all(keyword in _input for keyword in self.order_keywords):
            state['messages'].append(AIMessage(content="Invalid order. Please specify a pizza order. Try writing 'I want to order a pizza'."))
            return {
                "messages": state["messages"]
            }
        else:
            state['active_order'] = True
            # state['messages'].append(AIMessage(content="Your pizza order is valid."))
            return {
                "messages": state["messages"],
                "active_order": state["active_order"]
            }
    
    def route(self, state: ChatbotState) -> str:
        """
        Routes to the next node
        """
        if state['active_order']:
            return Nodes.RETRIEVAL.value
        else:
            return END

def check_pizzas(input):
    threshold = 80
    response = requests.get("https://demos.swe.htwk-leipzig.de/pizza-api/pizza")
    menu = response.json()
    for item in menu:
        current_ratio = fuzz.partial_ratio(input, list(item.values())[1])
        if(current_ratio >= threshold):
            #print("debugging: " + str(list(item.values())[1]) + " was determined type")
            return str(list(item.values())[0])
    return None

def check_customer_address(input):
    
    #TODO move somewhere else
    #get open api key from .env file
    load_dotenv()
    openai_api_key = environ.get('OPENAI_API_KEY')
    openai_api_base = "http://gpu01.imn.htwk-leipzig.de:8081/v1"
    
    #get model from http://gpu01.imn.htwk-leipzig.de:8081/v1/models
    

    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    
    #TODO give instruciton on expected return types etc
    #TODO use in all/most api calls or verification

    #use in-context-learning
    example_string = "My address is Gustav-Freytag Straße 12A in Leipzig."
    assistant_docstring = """[{"Leipzig": "CITY"}, {"Gustav-Freytag Straße": "STREET"}, {"12A": "HOUSE_NUMBER"}]"""
    chat_response = client.chat.completions.create(
        model="Qwen/Qwen2.5-72B-Instruct-AWQ",
        messages=[
            {"role": "system", "content": """You are a Named Entity Recognition Tool.
Recognize named entities and output the structured data as a JSON. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
            {"role": "user", "content": example_string},
            {"role": "assistant", "content": assistant_docstring},
            {"role": "user", "content": input}
        ]
    )
    
    receivedMessage = chat_response.choices[0].message.content
    #receivedMessage = """[{"Leipzig": "CITY"}, {"Gustav-Freytag Straße": "STREET"}, {"12A": "HOUSE_NUMBER"}]"""
    print(receivedMessage)
    
    response_dictionary = {}
    for d in json.loads(receivedMessage):
        response_dictionary.update(d)
        
    city = [k for(k , v) in response_dictionary.items() if v == "CITY"][0]
    street = [k for (k , v) in response_dictionary.items() if v == "STREET"][0]
    house_number = [k for (k , v) in response_dictionary.items() if v == "HOUSE_NUMBER"][0]

    post = {"city":city, "street":street, "house_number":house_number}
    response = requests.post("https://demos.swe.htwk-leipzig.de/pizza-api/address/validate", json=post) 

    if response.status_code != 200:
        return None

    #print("debugging: Potential Address found: " + str((city, street, house_number)))
    return (city, street, house_number)

class OrderNode:
    """
    Collects the slots for the pizza order
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> str:
        """
        Returns fallback message
        """

        #use for additional information dialogue (not in correct order with order_id)
        #required_slots = [..., OrderSlots.ADDITIONAL_INFORMATION, OrderSlots.ORDER_ID]
        
        required_slots = [OrderSlots.PIZZA_NAME, OrderSlots.CUSTOMER_ADDRESS, OrderSlots.ORDER_ID]
        missing_slots = [slot.value for slot in required_slots if slot.value not in state['slots'].keys()]
        optional_slots = [OrderSlots.CUSTOMER_TEL_NUMBER, OrderSlots.DELIVERY_TIME]
        optional_missing_slots = [slot.value for slot in optional_slots if slot.value not in state['slots'].keys()]
        
        #don't override invalidation ai messages
        if state["invalid"]:
            last_function_message = [m for m in outputs["messages"] if isinstance(m, FunctionMessage) ][-1]
            state["invalid"] = False
            state["messages"].append(last_function_message)
            return {
                "messages": state["messages"],
                "invalid": state["invalid"]
            }

        next_slot = missing_slots[0] if missing_slots else optional_missing_slots[0]
        
        #try to end dialogue
        if next_slot == OrderSlots.ORDER_ID.value and not state['additional_information']:
            order_id = post_order(state["pizza_id"], state["customer_address"])
            if order_id is not None:
                state['order_id'] = order_id
                state['messages'].append(AIMessage(content="Thank you for providing all the details. Your order is being processed! "
                    + "Keep your order id ready incase you have further inquiries: " + state["order_id"] + " ."))
                state['ended'] = True
                return {
                    "messages": state["messages"],
                    "order_id": state["order_id"],
                    "ended": state["ended"]
                }
            else:
                #TODO properly set states for user to re-submit information  
                state['messages'].append(AIMessage(content="Something went wrong while submitting your order, please try again."))
                state['ended'] = True
                return {
                    "messages": state["messages"],
                    "invalid": state["invalid"]
                } 


        if next_slot == OrderSlots.PIZZA_NAME.value:
            state['messages'].append(AIMessage("What pizza would you like to order?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.PIZZA_NAME, name=OrderSlots.PIZZA_NAME.value))
            return {
                "messages": state["messages"]
            }
        
        elif next_slot == OrderSlots.CUSTOMER_ADDRESS.value:
            state['messages'].append(AIMessage("What is your delivery address?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.CUSTOMER_ADDRESS, name=OrderSlots.CUSTOMER_ADDRESS.value))
            return {
                "messages": state["messages"]
            }
        
        elif next_slot == OrderSlots.ADDITIONAL_INFORMATION.value:
            state['messages'].append(AIMessage("Would you like to add additional information to your oder (e.g. telephone number / specific delivery time)"))
            state["messages"].append(FunctionMessage(content=OrderSlots.ADDITIONAL_INFORMATION, name=OrderSlots.ADDITIONAL_INFORMATION.value))
            state["confirm_order"] = True
            return {
                "messages": state["messages"],
                "confirm_order" : state["confirm_order"]
            }
        
        # is only being asked within the confirm_order path
        elif state['additional_information']:
            if next_slot == OrderSlots.CUSTOMER_TEL_NUMBER.value:
                state['messages'].append(AIMessage("What telephone number would you like to be reached at?"))
                state["messages"].append(FunctionMessage(content=OrderSlots.CUSTOMER_TEL_NUMBER, name=OrderSlots.CUSTOMER_TEL_NUMBER.value))
                return {
                    "messages": state["messages"]
                }
            elif next_slot == OrderSlots.DELIVERY_TIME.value:
                state['messages'].append(AIMessage("What delivery time would you prefer?"))
                state["messages"].append(FunctionMessage(content=OrderSlots.DELIVERY_TIME, name=OrderSlots.DELIVERY_TIME.value))
                state["additional_information"] = False
                return {
                    "messages": state["messages"],
                    "additional_information": state["additional_information"]
                }
            

def post_order(pizza_id, address):
    city, street, house_number = address
    post = {"pizza_id":pizza_id, "city":city, "street":street, "house_number":house_number}
    response = requests.post("https://demos.swe.htwk-leipzig.de/pizza-api/order", json=post)

    if response.status_code != 200:
        return None
    
    order_id = response.json()["order_id"]
    status = response.json()["status"]

    if status != "received":
        return None
    
    return order_id
    

    
def get_order(order_id):
    response = requests.get("https://demos.swe.htwk-leipzig.de/pizza-api/address/validate/" + order_id)
    order = response.json()
    #TODO return order information if asked




# TODO Question:
# Do the RetrievalNode and CheckerNode have to do the same kind of "verification" of user input? 
# The CheckerNode checks whether the original user input is valid by transforming it (i.e. by regex)
# The RetrievalNode would also get the original, untransformed user input (and thus would also need to transform it, to correctly extract relevant information)
# 
# Currently I'm using the RetrievalNode as a List of valid user input with the corresponding context (function message)
# This List is never queried though...

class RetrievalNode:
    """
    This node extracts the information from user input
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> str:
        """
        Extracts the information from user input
        """
        last_message = state["messages"][-1] if len(state["messages"]) > 0 else "No message"

        if not state['active_order'] or not isinstance(last_message, FunctionMessage):
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        
        _input = state['input'].lower()

        #TODO move input saving into here

        if last_message.content == OrderSlots.PIZZA_NAME.value:
            state['slots'][OrderSlots.PIZZA_NAME.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        elif last_message.content == OrderSlots.CUSTOMER_ADDRESS.value:
            state['slots'][OrderSlots.CUSTOMER_ADDRESS.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        elif last_message.content == OrderSlots.ADDITIONAL_INFORMATION.value:
            state['slots'][OrderSlots.ADDITIONAL_INFORMATION.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        elif last_message.content == OrderSlots.CUSTOMER_TEL_NUMBER.value:
            state['slots'][OrderSlots.CUSTOMER_TEL_NUMBER.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        elif last_message.content == OrderSlots.DELIVERY_TIME.value:
            state['slots'][OrderSlots.DELIVERY_TIME.value] = _input
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        

if __name__ == "__main__":
    # Initialize nodes
    order_node = OrderNode()
    checker_node = CheckerNode()
    retrieval_node = RetrievalNode()

    workflow = StateGraph(ChatbotState)
    #TODO set entrypoint as language detection-node
    #either use it to set a state (enum)
    #or route to language dependant nodes
    workflow.add_node(Nodes.CHECKER.value, checker_node.invoke)
    workflow.add_node(Nodes.RETRIEVAL.value, retrieval_node.invoke)
    workflow.add_node(Nodes.ORDER_FORM.value, order_node.invoke)

    workflow.add_conditional_edges(
        Nodes.CHECKER.value,
        checker_node.route,
        {
            Nodes.RETRIEVAL.value: Nodes.RETRIEVAL.value,
            END: END,
        }
    )
    workflow.add_edge(Nodes.RETRIEVAL.value, Nodes.ORDER_FORM.value)
    workflow.add_edge(Nodes.ORDER_FORM.value, END)
    
    workflow.set_entry_point(Nodes.CHECKER.value)
    graph = workflow.compile()

    # START DIALOGUE: first message
    print("-- Chatbot: ", "Hi! I am a pizza bot. I can help you order a pizza. What would you like to order?")
    user_input = input("-> Your response: ")
    outputs = graph.invoke({"input": user_input, "slots": {}, "messages": [], "active_order": False, "confirm_order":False, "additional_information":False, "pizza_id":None, "customer_address":None, "invalid":False, "ended": False})

    while True:
        print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
        user_input = input("-> Your response: ")

        outputs = graph.invoke({"input": user_input, "slots": outputs["slots"], "messages": outputs["messages"], "active_order": outputs["active_order"], "confirm_order":outputs["confirm_order"], "additional_information":outputs["additional_information"], "pizza_id":outputs["pizza_id"], "customer_address":outputs["customer_address"], "invalid":outputs["invalid"], "ended": outputs["ended"]})

        # check if the conversation has ended
        if outputs["ended"]:
            print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
            break