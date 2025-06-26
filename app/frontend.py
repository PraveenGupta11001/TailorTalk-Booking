import streamlit as st
import requests

st.title("TailorTalk Booking Agent")

if "messages" not in st.session_state:
    st.session_state.messages = []

user_input = st.text_input("Type your message:", key="user_input")

if user_input and user_input not in [msg["content"] for msg in st.session_state.messages if msg["role"] == "user"]:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post("http://localhost:8000/chat", json={"message": user_input})
        if response.status_code == 200:
            responses = response.json()["responses"]
            for resp in responses:
                st.session_state.messages.append({"role": "assistant", "content": resp})
        else:
            st.session_state.messages.append({"role": "assistant", "content": f"Error: Could not connect to the backend. Status code: {response.status_code}"})
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error: {str(e)}"})

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])