import streamlit as st
import requests
import time
import os
from dotenv import load_dotenv
load_dotenv()

# Try backend URL from env first, fallback to localhost
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def send_message(message):
    try:
        response = requests.post(
            f"{BACKEND_URL}/chat",
            json={"message": message},
            timeout=10
        )
        return response.json().get("responses", ["Something went wrong."])
    except Exception as e:
        return [f"Error: {str(e)}"]

# UI customization
st.markdown("""
<style>
    .stChatMessage {
        padding: 12px;
        border-radius: 8px;
        margin-bottom: 12px;
    }
    .assistant-message {
        background-color: #f0f2f6;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .stTextInput>div>div>input {
        border-radius: 20px !important;
        padding: 10px 15px !important;
    }
    .stButton>button {
        border-radius: 20px !important;
        padding: 10px 20px !important;
        background-color: #4CAF50 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("TailorTalk Booking Agent")
st.caption("A smart assistant to help you schedule appointments")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant", 
        "content": "Hi there! 👋 I'm TailorTalk, your booking assistant. How can I help you today?"
    }]

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Input from user
user_input = st.chat_input("Type your message...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    with st.spinner("Thinking..."):
        responses = send_message(user_input)

    for res in responses:
        st.session_state.messages.append({"role": "assistant", "content": res})
        with st.chat_message("assistant"):
            st.write(res)
        time.sleep(0.3)