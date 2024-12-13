from typing import TypedDict
import requests
from os import environ
from openai import OpenAI
from dotenv import load_dotenv
import json

from fuzzywuzzy import fuzz

from langgraph.graph import END, StateGraph
from langchain_core.messages import (
    AIMessage,
    FunctionMessage,
)
from enum import Enum

client = None

def load_llm():
    
    load_dotenv()
    openai_api_key = environ.get('OPENAI_API_KEY')
    openai_api_base = environ.get('OPENAI_API_BASE')
    
    #get model from http://gpu01.imn.htwk-leipzig.de:8081/v1/models

    #TODO probably a hack
    global client 
    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )

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
    give_description: bool
    invalid: bool
    ended: bool
    pizza_id: str
    customer_address: tuple[str]
    order_id: str

class Nodes(Enum):
    ENTRY = "entry"
    CHECKER = "checker"
    DESCRIPTION = "description"
    ORDER_FORM = "order_form"
    RETRIEVAL = "retrieval"
    END = "end"

class OrderSlots(Enum):
    PIZZA_NAME = "pizza_name"
    CUSTOMER_ADDRESS = "customer_address"
    ORDER_ID = "order_id"

class CheckerNode:
    """
    This node checks whether user input is valid
    """
    
    def __init__(self, order_keywords: list = ["order"]):
        self.order_keywords = order_keywords

    def invoke(self, state: ChatbotState) -> str:
        """
        Checks whether the input is a valid request for pizza order
        """
        _input = state['input']
        
        if state['active_order']:
            if OrderSlots.PIZZA_NAME.value in state["messages"][-1].content:
                if check_description_intention(_input):
                    state["give_description"] = True
                    return {
                        "messages": state["messages"],
                        "give_description": state["give_description"]
                    }
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
        
        #no other dialogue state -> implicit begin of conversation
        if check_order_intention(_input):
            state['active_order'] = True
            # state['messages'].append(AIMessage(content="Your pizza order is valid."))
            return {
                "messages": state["messages"],
                "active_order": state["active_order"]
            }
        else:
            state['messages'].append(AIMessage(content="Invalid order. Please specify a pizza order. Try writing 'I want to order a pizza'."))
            return {
                "messages": state["messages"]
            }
    
    def route(self, state: ChatbotState) -> str:
        """
        Routes to the next node
        """
        #TODO add condition to route into description node
        if state['give_description']:
            return Nodes.DESCRIPTION.value
        if state['active_order']:
            return Nodes.RETRIEVAL.value
        else:
            return END

def check_order_intention(_input):
    example_string_1 = "I wanna order a pizza."
    assistant_docstring_1 = """{"intention": True}"""

    example_string_2 = "How are you doing today?"
    assistant_docstring_2 = """{"intention": False}"""

    chat_response = client.chat.completions.create(
        model=environ.get("OPENAI_MODEL"),
        messages=[
            {"role": "system", "content": """You are an Input Validation Tools.
Recognize whether the user wants to order a pizza or he/she has another intention and output the structured data as a JSON. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
            {"role": "user", "content": example_string_1},
            {"role": "assistant", "content": assistant_docstring_1},
            {"role": "user", "content": example_string_2},
            {"role": "assistant", "content": assistant_docstring_2},
            {"role": "user", "content": _input}
        ]
    )
    
    received_message = chat_response.choices[0].message.content
    
    #TODO use actual logging while in debug
    #logger.info(received_message)
    
    return eval(received_message)["intention"]

def check_description_intention(_input):
    example_string_1 = "What is a Pizza Hawaiian?"
    assistant_docstring_1 = """{"intention": True}"""

    example_string_2 = "I want to order a pizza Pepperoni?"
    assistant_docstring_2 = """{"intention": False}"""

    chat_response = client.chat.completions.create(
        model=environ.get("OPENAI_MODEL"),
        messages=[
            {"role": "system", "content": """You are an Input Validation Tools.
Recognize whether the user wants receive further information about a specific pizza or he/she has another intention and output the structured data as a JSON. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
            {"role": "user", "content": example_string_1},
            {"role": "assistant", "content": assistant_docstring_1},
            {"role": "user", "content": example_string_2},
            {"role": "assistant", "content": assistant_docstring_2},
            {"role": "user", "content": _input}
        ]
    )
    
    received_message = chat_response.choices[0].message.content
    
    return eval(received_message)["intention"]
    
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
    load_dotenv()
    openai_api_key = environ.get('OPENAI_API_KEY')
    openai_api_base = environ.get('OPENAI_API_BASE')

    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    
    #TODO give instruciton on expected return types etc
    #TODO use in all/most api calls or verification

    #use in-context-learning
    example_string = "My address is Gustav-Freytag Straße 12A in Leipzig."
    assistant_docstring = """[{"Leipzig": "CITY"}, {"Gustav-Freytag Straße": "STREET"}, {"12A": "HOUSE_NUMBER"}]"""
    
    #get current model from http://gpu01.imn.htwk-leipzig.de:8081/v1/models
    chat_response = client.chat.completions.create(
        model=environ.get('OPENAI_MODEL'),
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
    
    necessary_fields = ["CITY", "STREET", "HOUSE_NUMBER"]    
    #TODO do proper logging of errors
    if not response_dictionary or not all(value in set(necessary_fields) for value in response_dictionary.values()):
        return None

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
        
        #don't override invalidation ai messages
        if state["invalid"]:
            last_function_message = [m for m in outputs["messages"] if isinstance(m, FunctionMessage) ][-1]
            state["invalid"] = False
            state["messages"].append(last_function_message)
            return {
                "messages": state["messages"],
                "invalid": state["invalid"]
            }

        next_slot = missing_slots[0]
        
        #try to end dialogue
        if next_slot == OrderSlots.ORDER_ID.value:
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
                #TODO better to properly set states for user to re-submit information  
                state['messages'].append(AIMessage(content="Something went wrong while submitting your order, please try again."))
                state['ended'] = True
                return {
                    "messages": state["messages"],
                    "invalid": state["invalid"]
                } 

        if next_slot == OrderSlots.PIZZA_NAME.value:
            
            #TODO also give possibility to ask for pizza description
            if not state["give_description"]:    
                response = requests.get("https://demos.swe.htwk-leipzig.de/pizza-api/pizza")
                menu = response.json()
                menu_str = ""
                
                for item in menu:
                    menu_str += item["name"] + ", "
                menu_str = menu_str[:-2]    
            
                state['messages'].append(AIMessage("What pizza would you like to order? We are currently delivering the following items: " + menu_str + 
                                                   ".\n We can also provide further information about a pizza item, if you any questions."))
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
            

def post_order(pizza_id, address):
    city, street, house_number = address
    post = {"pizza_id":pizza_id, "city":city, "street":street, "house_number":house_number}
    #TODO extract base URL into .env
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

        #TODO instead don't enter RetrievalNode in case of inactive Order move into routing
        if not state['active_order'] or not isinstance(last_message, FunctionMessage):
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        
        _input = state['input'].lower()

        #'slots' used to handle missing<->required fields
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

class DescriptionNode:
    """
    This node collects information about pizza's
    """
    
    def __init__(self):
        pass

    def invoke(self, state: ChatbotState) -> str:
        """
        Resolves additional information about pizza items
        """
        
        _input = state['input'].lower()

        #determine which pizza user want to get information for
        
        pizza_name = resolve_pizza(_input)
        pizza_description = resolve_description(pizza_name)
        
        state['messages'].append(AIMessage("Further Information about Pizza " + pizza_name + ": " + pizza_description))
        state["messages"].append(FunctionMessage(content=OrderSlots.PIZZA_NAME, name=OrderSlots.PIZZA_NAME.value))
        state["give_description"] = False
        return {
            "messages": state["messages"],
            "give_description": state["give_description"]
        }
        
    #def route(self, state: ChatbotState) -> str:
    #TODO necessary?

def resolve_pizza(_input):
    #TODO resolve pizza name
    return "Standard"

def resolve_description(_input):
    #TODO resolve pizza description through sparql
    return "Standard Description"

if __name__ == "__main__":
    # Initialize nodes
    order_node = OrderNode()
    checker_node = CheckerNode()
    retrieval_node = RetrievalNode()
    description_node = DescriptionNode()

    workflow = StateGraph(ChatbotState)
    #TODO set entrypoint as language detection-node
    #either use it to set a state (enum)
    #or route to language dependant nodes
    workflow.add_node(Nodes.CHECKER.value, checker_node.invoke)
    #TODO try removing retrieval node -> input saving is already done within dialogue state
    workflow.add_node(Nodes.RETRIEVAL.value, retrieval_node.invoke)
    workflow.add_node(Nodes.ORDER_FORM.value, order_node.invoke)
    workflow.add_node(Nodes.DESCRIPTION.value, description_node.invoke)

    workflow.add_conditional_edges(
        Nodes.CHECKER.value,
        checker_node.route,
        {
            Nodes.RETRIEVAL.value: Nodes.RETRIEVAL.value,
            Nodes.DESCRIPTION.value: Nodes.DESCRIPTION.value,
            END: END,
        }
    )

    #don't enter retrieval node from description -> "missing slots" doesn't get updated
    workflow.add_edge(Nodes.DESCRIPTION.value, END)
    workflow.add_edge(Nodes.RETRIEVAL.value, Nodes.ORDER_FORM.value)
    workflow.add_edge(Nodes.ORDER_FORM.value, END)
    
    workflow.set_entry_point(Nodes.CHECKER.value)
    graph = workflow.compile()
    
    # load llm
    load_llm()
    
    # START DIALOGUE: first message
    print("-- Chatbot: ", "Hi! I am a pizza bot. I can help you order a pizza. What would you like to order?")
    user_input = input("-> Your response: ")
    outputs = graph.invoke({"input": user_input, "slots": {}, "messages": [], "active_order": False, "give_description":False, "pizza_id":None, "customer_address":None, "invalid":False, "ended": False})

    while True:
        print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
        user_input = input("-> Your response: ")

        outputs = graph.invoke({"input": user_input, "slots": outputs["slots"], "messages": outputs["messages"], "active_order": outputs["active_order"], "give_description":outputs["give_description"], "pizza_id":outputs["pizza_id"], "customer_address":outputs["customer_address"], "invalid":outputs["invalid"], "ended": outputs["ended"]})

        # check if the conversation has ended
        if outputs["ended"]:
            print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
            break