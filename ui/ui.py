from openai import OpenAI
import streamlit as st
import os
import snowflake.connector
from snowflake.snowpark import Session
from snowflake.ml.registry import Registry
from snowflake.snowpark import Row
from snowflake.snowpark.functions import col
from snowflake.snowpark.types import StructType, StructField, StringType
from snowflake.snowpark import functions as F
from snowflake.snowpark import types as T


# Page Configuration
st.set_page_config(page_title="Snowswift AI Chat Hub", page_icon="🚘", layout="wide", initial_sidebar_state="expanded")

def connection() -> snowflake.connector.SnowflakeConnection:
    if os.path.isfile("/snowflake/session/token"):
        creds = {
            'host': os.getenv('SNOWFLAKE_HOST'),
            'port': os.getenv('SNOWFLAKE_PORT'),
            'protocol': "https",
            'account': os.getenv('SNOWFLAKE_ACCOUNT'),
            'authenticator': "oauth",
            'token': open('/snowflake/session/token', 'r').read(),
            'warehouse': "INSURANCEWAREHOUSE",
            'database': os.getenv('SNOWFLAKE_DATABASE'),
            'schema': os.getenv('SNOWFLAKE_SCHEMA'),
            'client_session_keep_alive': True
        }
    else:
        creds = {
            'account': os.getenv('SNOWFLAKE_ACCOUNT'),
            'user': os.getenv('SNOWFLAKE_USER'),
            'password': os.getenv('SNOWFLAKE_PASSWORD'),
            'warehouse': os.getenv('SNOWFLAKE_WAREHOUSE'),
            'database': os.getenv('SNOWFLAKE_DATABASE'),
            'schema': os.getenv('SNOWFLAKE_SCHEMA'),
            'client_session_keep_alive': True
        }

    connection = snowflake.connector.connect(**creds)
    return connection

def session() -> Session:
    return Session.builder.configs({"connection": connection()}).create()

# Make connection to Snowflake and cache it
@st.cache_resource
def connect_to_snowflake():
    return session()

session = connect_to_snowflake()
session.sql("USE WAREHOUSE DEEPSEEK_WH").collect()

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

# Title and Subtitle
st.title("🚘 Deepseek AI Chat Hub")
st.subheader(":snowflake: Powered by Snowpark Container Services")

# Sidebar Navigation
mode = st.sidebar.radio("Choose a mode", ["Chat", "RAG"])
debug_mode = st.sidebar.checkbox("🔧 Debug mode", value=False)

if debug_mode:
    # Debug: Print Snowflake session context
    try:
        ctx_info = session.sql('''
            SELECT 
                CURRENT_ACCOUNT() AS account,
                CURRENT_USER() AS user,
                CURRENT_ROLE() AS role,
                CURRENT_DATABASE() AS database,
                CURRENT_SCHEMA() AS schema,
                CURRENT_WAREHOUSE() AS warehouse
        ''').to_pandas()
        st.write(ctx_info)
    except Exception as e:
        st.write(f"❌ Could not fetch session context: {e}")

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
    
    if mode == "RAG":
        try:
            with st.status("Fetching information from documents…", expanded=True) as status:
                # Embed query
                status.write("🔎 Embedding your query…")

                input_df = session.create_dataframe(
                [Row(CONTEXT=prompt)],
                schema=StructType([StructField("CONTEXT", StringType())])
                )

                # Create Model Registry
                reg = Registry(
                    session=session, 
                    database_name="DEEPSEEK_DB", 
                    schema_name="EMBEDDING_MODEL_HOL_SCHEMA"
                    )
                
                mv = reg.get_model('sentence_transformer_minilm').version('V1')

                prompt_embedded_chunk_df = mv.run(
                input_df,
                function_name="encode",
                service_name="minilm_gpu_service"
                )

                prompt_embedded_chunk_df = prompt_embedded_chunk_df.with_column('"output_feature_0"', F.col('"output_feature_0"').cast(T.VectorType(float, 384)))
                prompt_embedded_chunk_df = prompt_embedded_chunk_df.rename(F.col('"output_feature_0"'), "CHUNK_VEC")
                
                status.write("💾 Staging query vector…")
                prompt_embedded_chunk_df.write.mode('overwrite').save_as_table("DEEPSEEK_DB.RAGTOAI.QUERY_TABLE")

                status.update(label="📚 Searching for relevant chunks…", state="running")

                closest_vector_q = "SELECT r.chunk, VECTOR_COSINE_SIMILARITY(r.chunk_vec, q.chunk_vec) AS similarity FROM DEEPSEEK_DB.RAGTOAI.RAG_CHUNKED_EMBEDDED_TABLE r, DEEPSEEK_DB.RAGTOAI.QUERY_TABLE q ORDER BY similarity DESC LIMIT 1"

                closest_vector = session.sql(closest_vector_q).to_pandas()

                if closest_vector.empty:
                    context = ""
                    status.write("⚠️ No relevant chunk found; proceeding without extra context.")
                else:
                    context = closest_vector['CHUNK'].iloc[0]
                    status.write("✅ Found relevant context.")

                prompt_with_context = f"Use the following context to answer the question:\n\nContext:\n{context}\n\nQuestion:\n{prompt}"

                status.update(label="Done fetching context ✅", state="complete")

        except Exception as e:
            st.error(f"❌ Failed to retrieve context: {e}")
            prompt_with_context = prompt
    else:
        prompt_with_context = prompt
    # Assistant Response
    stream = client.chat.completions.create(
        model=st.session_state["openai_model"],
        messages=[
            *[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]],
            {"role": "user", "content": prompt_with_context}
        ],
        stream=True,
    )
    # Capture tokens incrementally
    full_response = ""
    with st.container():
        assistant_placeholder = st.empty()
        for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            full_response += token
            assistant_placeholder.markdown(
                f'<div class="stChatMessage assistant">{full_response}</div>',
                unsafe_allow_html=True,
            )

    st.session_state.messages.append({"role": "assistant", "content": full_response})
