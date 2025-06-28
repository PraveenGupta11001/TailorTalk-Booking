import streamlit as st
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from app.agent import run_agent
import time

# Custom CSS for better chat interface
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

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant", 
        "content": "Hi there! 👋 I'm TailorTalk, your personal booking assistant. How can I help you schedule an appointment today?"
    }]

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
user_input = st.chat_input("Type your message here...")

if user_input:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message immediately
    with st.chat_message("user"):
        st.write(user_input)
    
    # Get assistant response
    with st.spinner("Thinking..."):
        responses = run_agent(user_input)
    
    # Add assistant responses to chat history
    for response in responses:
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Display assistant response
        with st.chat_message("assistant"):
            st.write(response)
        
        # Small delay between messages for natural flow
        time.sleep(0.3)