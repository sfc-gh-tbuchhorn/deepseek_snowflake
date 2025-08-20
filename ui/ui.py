from openai import OpenAI
import streamlit as st
import os

# Page Configuration
st.set_page_config(page_title="Snowswift AI Chat Hub", page_icon="🚘", layout="wide", initial_sidebar_state="expanded")

# Custom CSS
st.markdown("""
    <style>
    .main {background: linear-gradient(135deg, #1e3c72, #2a5298); color: #fff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
    .stTextInput>div>div>input {background-color: #1e293b; color: #fff; border-radius: 12px; padding: 12px; border: none;}
    .stButton>button {background-color: #2563eb; color: white; border-radius: 12px; padding: 12px 24px; border: none; font-weight: bold; transition: 0.3s; box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);}
    .stButton>button:hover {background-color: #1d4ed8; transform: translateY(-2px);}
    .stChatMessage {background-color: rgba(255, 255, 255, 0.15); border-radius: 15px; padding: 15px; margin-bottom: 12px; box-shadow: 0px 4px 10px rgba(0, 0, 0, 0.2);}
    .stChatMessage.user {background-color: rgba(37, 99, 235, 0.3); text-align: right;}
    .stChatMessage.assistant {background-color: rgba(14, 165, 233, 0.3); text-align: left;}
    </style>
""", unsafe_allow_html=True)

# Banner Image
st.image("https://source.unsplash.com/1600x400/?technology,ai", caption="Welcome to Snowswift AI Chat Hub", use_container_width=True)

# Title and Subtitle
st.title("🚘 Deepseek AI Chat Hub")
st.subheader(":snowflake: Powered by Snowpark Container Services")

# OpenAI Client Initialization
client = OpenAI(base_url="http://deepseek:8000/v1", api_key="dummy")

# Session State Initialization
st.session_state.setdefault("openai_model", os.getenv("MODEL"))
st.session_state.setdefault("messages", [])

# Display Previous Messages
for msg in st.session_state.messages:
    role_class = "user" if msg["role"] == "user" else "assistant"
    st.markdown(f'<div class="stChatMessage {role_class}">{msg["content"]}</div>', unsafe_allow_html=True)

# Chat Input Handling
if prompt := st.chat_input("📢 Share your thoughts..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(f'<div class="stChatMessage user">{prompt}</div>', unsafe_allow_html=True)

    # Assistant Response
    stream = client.chat.completions.create(
        model=st.session_state["openai_model"],
        messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
        stream=True,
    )
    response = st.write_stream(stream)
    st.markdown(f'<div class="stChatMessage assistant">{response}</div>', unsafe_allow_html=True)
    st.session_state.messages.append({"role": "assistant", "content": response})
