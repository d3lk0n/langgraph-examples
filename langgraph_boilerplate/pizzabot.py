from typing import TypedDict
import requests
from re import search, split, findall

from fuzzywuzzy import fuzz

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
    address: str
    order_id: str

class Nodes(Enum):
    ENTRY = "entry"
    CHECKER = "checker"
    ORDER_FORM = "order_form"
    RETRIEVAL = "retrieval"
    END = "end"

class OrderSlots(Enum):
    PIZZA_NAME = "pizza_name"
    CUSTOMER_ADDRESS = "customer_address"
    ADDITIONAL_INFORMATION = "additional_information"
    CUSTOMER_TEL_NUMBER = "customer_tel_number"
    DELIVERY_TIME = "delivery_time"

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
                    "slots": state["slots"],
                    "active_order": state["active_order"],
                    "confirm_order": state["confirm_order"],
                    "additional_information": state["additional_information"],
                    "ended": state["ended"]
                }
            else:
                #customer provides further contact/delivery information
                state["additional_information"] = True
                return {
                    "messages": state["messages"],
                    "slots": state["slots"],
                    "active_order": state["active_order"],
                    "confirm_order": state["confirm_order"],
                    "additional_information": state["additional_information"],
                    "ended": state["ended"]
                }
                
        # add constraints for additional info
        
        if state['active_order']:
            if OrderSlots.PIZZA_NAME.value in state["messages"][-1].content:
                pizza_id = check_pizzas(_input)
                if pizza_id is not None:
                    #found pizza type
                    state['pizza_id'] = True
                    return {
                        "messages": state["messages"],
                        "slots": state["slots"],
                        "active_order": state["active_order"],
                        "confirm_order": state["confirm_order"],
                        "additional_information": state["additional_information"],
                        "pizza_id": state["pizza_id"],
                        "ended": state["ended"]
                    }
                else:
                    print("pizza type not found")
                    state["invalid"] = True
                    state['messages'].append(AIMessage(content="Invalid pizza type. Please specify a valid type (e.g. a pizza Pepperoni)'."))
                    return {
                        "messages": state["messages"],
                        "slots": state["slots"],
                        "active_order": state["active_order"],
                        "confirm_order": state["confirm_order"],
                        "additional_information": state["additional_information"],
                        "invalid": state["invalid"],
                        "ended": state["ended"]
                    }
                    
            elif OrderSlots.CUSTOMER_ADDRESS.value in state["messages"][-1].content:
                customer_address = check_customer_address(_input)
                if customer_address is not None:
                    state['customer address'] = True
                    return {
                        "messages": state["messages"],
                        "slots": state["slots"],
                        "active_order": state["active_order"],
                        "confirm_order": state["confirm_order"],
                        "additional_information": state["additional_information"],
                        "customer address": state["customer address"],
                        "ended": state["ended"]
                    }
                else:
                    state["invalid"] = True
                    state['messages'].append(AIMessage(content="Invalid customer address. Please specify a valid address."))
                    return {
                        "messages": state["messages"],
                        "slots": state["slots"],
                        "active_order": state["active_order"],
                        "confirm_order": state["confirm_order"],
                        "additional_information": state["additional_information"],
                        "invalid": state["invalid"],
                        "ended": state["ended"]
                    }   
            #TODO elif for post order
        
        if not all(keyword in _input for keyword in self.order_keywords):
            state['messages'].append(AIMessage(content="Invalid order. Please specify a pizza order. Try writing 'I want to order a pizza'."))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "active_order": state["active_order"],
                "confirm_order": state["confirm_order"],
                "additional_information": state["additional_information"],
                "ended": state["ended"]
            }
        else:
            state['active_order'] = True
            # state['messages'].append(AIMessage(content="Your pizza order is valid."))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "active_order": state["active_order"],
                "confirm_order": state["confirm_order"],
                "additional_information": state["additional_information"],
                "ended": state["ended"]
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
    threshold = 75
    response = requests.get("https://demos.swe.htwk-leipzig.de/pizza-api/pizza")
    menu = response.json()
    for item in menu:
        current_ratio = fuzz.partial_ratio(input, list(item.values())[1])
        if(current_ratio >= threshold):
            print("debugging: " + str(list(item.values())[1]) + " was determined type")
            return str(list(item.values())[0])
    return None

def check_customer_address(input):
    match = "^\w+(\w| |\.)* \d+ \w+(\w| )*$"

    # no address match found
    if not findall(match, input):
        return None
    
    street, city = split("\d+", input)
    street = street[:-1]
    city = city[1:]
    house_number = findall("\d+", input)[0]

    post = {"city":city, "street":street, "house_number":house_number}
    
    
    response = requests.post("https://demos.swe.htwk-leipzig.de/pizza-api/address/validate", json=post) 
    if response.status_code != 200:
        return None

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

        #uncomment for additional information dialogue
        #required_slots = [OrderSlots.PIZZA_NAME, OrderSlots.CUSTOMER_ADDRESS, OrderSlots.ADDITIONAL_INFORMATION]
        
        required_slots = [OrderSlots.PIZZA_NAME, OrderSlots.CUSTOMER_ADDRESS]
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
                "slots": state["slots"],
                "invalid": state["invalid"],
                "ended": state["ended"]
            }


        if not missing_slots and not state['additional_information']:
            state['messages'].append(AIMessage("Thank you for providing all the details. Your order is being processed!"))
            state['ended'] = True
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }

        next_slot = missing_slots[0] if missing_slots else optional_missing_slots[0]
        if next_slot == OrderSlots.PIZZA_NAME.value:
            state['messages'].append(AIMessage("What pizza would you like to order?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.PIZZA_NAME, name=OrderSlots.PIZZA_NAME.value))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        
        elif next_slot == OrderSlots.CUSTOMER_ADDRESS.value:
            state['messages'].append(AIMessage("What is your delivery address?"))
            state["messages"].append(FunctionMessage(content=OrderSlots.CUSTOMER_ADDRESS, name=OrderSlots.CUSTOMER_ADDRESS.value))
            return {
                "messages": state["messages"],
                "slots": state["slots"],
                "confirm_order": state["confirm_order"],
                "ended": state["ended"]
            }
        
        elif next_slot == OrderSlots.ADDITIONAL_INFORMATION.value:
            state['messages'].append(AIMessage("Would you like to add additional information to your oder (e.g. telephone number / specific delivery time)"))
            state["messages"].append(FunctionMessage(content=OrderSlots.ADDITIONAL_INFORMATION, name=OrderSlots.ADDITIONAL_INFORMATION.value))
            state["confirm_order"] = True
            return {
                "messages": state["messages"],
                "confirm_order" : state["confirm_order"],
                "slots": state["slots"],
                "ended": state["ended"]
            }
        
        elif state['additional_information']:
            if next_slot == OrderSlots.CUSTOMER_TEL_NUMBER.value:
                state['messages'].append(AIMessage("What telephone number would you like to be reached at?"))
                state["messages"].append(FunctionMessage(content=OrderSlots.CUSTOMER_TEL_NUMBER, name=OrderSlots.CUSTOMER_TEL_NUMBER.value))
                return {
                    "messages": state["messages"],
                    "slots": state["slots"],
                    "ended": state["ended"]
                }
            elif next_slot == OrderSlots.DELIVERY_TIME.value:
                state['messages'].append(AIMessage("What delivery time would you prefer?"))
                state["messages"].append(FunctionMessage(content=OrderSlots.DELIVERY_TIME, name=OrderSlots.DELIVERY_TIME.value))
                state["additional_information"] = False
                return {
                    "messages": state["messages"],
                    "slots": state["slots"],
                    "additional_information": state["additional_information"],
                    "ended": state["ended"]
                }
            
    
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
    outputs = graph.invoke({"input": user_input, "slots": {}, "messages": [], "active_order": False, "confirm_order":False, "additional_information":False, "invalid":False, "ended": False})

    while True:
        print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
        user_input = input("-> Your response: ")

        outputs = graph.invoke({"input": user_input, "slots": outputs["slots"], "messages": outputs["messages"], "active_order": outputs["active_order"], "confirm_order":outputs["confirm_order"], "additional_information":outputs["additional_information"], "invalid":outputs["invalid"], "ended": outputs["ended"]})

        # check if the conversation has ended
        if outputs["ended"]:
            print("-- Chatbot: ", [m.content for m in outputs["messages"] if isinstance(m, AIMessage) ][-1]) # print chatbot response
            break