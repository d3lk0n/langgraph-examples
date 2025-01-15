import streamlit as st 
from langchain_core.messages import AIMessage, HumanMessage 
from pizzabot import * # Unsere Datei, die wir für den konsolenbasierten Chat verwendet haben


# Initialisiere Nodes
order_node = OrderNode()
checker_node = CheckerNode()
retrieval_node = RetrievalNode()
description_node = DescriptionNode()

workflow = StateGraph(ChatbotState)
# Nodes im Workflow einrichten
workflow.add_node(Nodes.CHECKER.value, checker_node.invoke)
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
workflow.add_edge(Nodes.RETRIEVAL.value, Nodes.ORDER_FORM.value)
workflow.add_edge(Nodes.DESCRIPTION.value, END)
workflow.add_edge(Nodes.ORDER_FORM.value, END)

workflow.set_entry_point(Nodes.CHECKER.value)
graph = workflow.compile()

def create_chat_app():
    # Initialisiere Session-Variablen, falls sie noch nicht existieren
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "streamlit_messages" not in st.session_state:
        st.session_state.streamlit_messages = []
    if "initialized" not in st.session_state:
        st.session_state.initialized = False
    if "slots" not in st.session_state:
        st.session_state.slots = {}
    if "active_order" not in st.session_state:
        st.session_state.active_order = False
    if "give_description" not in st.session_state:
        st.session_state.give_description = False
    if "pizza_id" not in st.session_state:
        st.session_state.pizza_id = None
    if "customer_address" not in st.session_state:
        st.session_state.customer_address = None
    if "order_id" not in st.session_state:
        st.session_state.order_id = None
    if "invalid" not in st.session_state:
        st.session_state.invalid = False
    if "ended" not in st.session_state:
        st.session_state.ended = False
        
    # Chat-Titel anzeigen
    st.title("Pizza Ordering Chatbot")

    #Initialisieren der im Pizzabot genutzten LLM
    load_llm()

    # Anzeige der ersten Nachricht, wenn noch nicht initialisiert
    if not st.session_state.initialized:
        initial_message = "Hi! I am a pizza bot. I can help you order a pizza. What would you like to order?"
        st.session_state.streamlit_messages.append(AIMessage(content=initial_message))
        st.session_state.initialized = True

    # Chat-Nachrichten anzeigen
    for message in st.session_state.streamlit_messages:
        if isinstance(message, AIMessage):
            with st.chat_message("assistant"):
                st.write(message.content)
        elif isinstance(message, HumanMessage):
            with st.chat_message("user"):
                st.write(message.content)
                
    # Eingabefeld für den Benutzer
    if not st.session_state.ended:
        user_input = st.chat_input("Schreibe deine Nachricht...")
        if user_input:
            # Benutzer-Nachricht zum Chat hinzufügen
            with st.chat_message("user"):
                st.write(user_input)
            st.session_state.streamlit_messages.append(HumanMessage(content=user_input))

            # Benutzereingabe durch das StateGraph verarbeiten
            outputs =graph.invoke({
                "input": user_input,
                "slots": st.session_state.slots,
                "messages": st.session_state.messages,
                "active_order": st.session_state.active_order,
                "give_description": st.session_state.give_description,
                "pizza_id": st.session_state.pizza_id,
                "customer_address": st.session_state.customer_address,
                "order_id": st.session_state.order_id,
                "invalid": st.session_state.invalid,
                "ended": st.session_state.ended
            })

            # Antwort des Bots extrahieren und Session-State aktualisieren
            last_ai_message = next((msg for msg in reversed(outputs["messages"]) if isinstance(msg, AIMessage)), None)
                
            st.session_state.slots = outputs["slots"]
            st.session_state.messages = outputs["messages"]
            st.session_state.active_order = outputs["active_order"]
            st.session_state.pizza_id = outputs["pizza_id"]
            st.session_state.customer_address = outputs["customer_address"]
            st.session_state.order_id = outputs["order_id"]
            st.session_state.give_description = outputs["give_description"]
            st.session_state.invalid = outputs["invalid"]
            st.session_state.ended = outputs["ended"]

            with st.chat_message("assistant"):
                # Letzte Antwort des Bots anzeigen
                last_ai_message = next((msg for msg in reversed(st.session_state.messages) if isinstance(msg, AIMessage)), None)
                st.session_state.streamlit_messages.append(last_ai_message)
                if last_ai_message:
                    st.write(last_ai_message.content)
                    
if __name__ == "__main__":
    create_chat_app()
        