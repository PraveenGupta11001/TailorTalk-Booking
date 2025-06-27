import streamlit as st
import requests

st.title("TailorTalk Booking Agent")

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! I'm here to help you book an appointment. When would you like to schedule a meeting?"}]

with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message:", key="user_input")
    submit_button = st.form_submit_button("Send")

if submit_button and user_input:
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