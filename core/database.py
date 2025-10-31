
# sql-agent-pro/core/database.py
import streamlit as st
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langchain.chat_models import init_chat_model
from urllib.parse import quote_plus
import tempfile
import os

from utils.state_manager import get_engine, get_llm_and_agent, cached_schema_info

def setup_database_connection():
    """Setup database connection and return LLM and agent"""
    try:
        provider = st.session_state.get("provider")
        model_id = st.session_state.get("model_id")
        api_key = st.session_state.get("api_key")  # Get from session state
        if not api_key:
            st.error("❌ API key not found. Please reconnect database.")
            return None, None
        llm, agent = get_llm_and_agent(provider, api_key, model_id, st.session_state.db_uri)
        return llm, agent
    except Exception as e:
        st.error(f"❌ Agent initialization failed: {e}")
        return None, None

def test_database_connection(db_uri):
    """Test database connection"""
    try:
        engine = get_engine(db_uri)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "✅ Connected successfully!"
    except Exception as e:
        return False, f"❌ Connection failed: {e}"

def get_database_uri(db_type, **kwargs):
    """Generate database URI based on type and parameters"""
    if db_type == "SQLite":
        mode = kwargs.get('mode')
        if mode == 'Path':
            sqlite_path = kwargs.get('sqlite_path', 'sql_agent_sandbox.db')
            if sqlite_path:
                return f"sqlite:///{sqlite_path.lstrip('/')}" if os.path.isabs(sqlite_path) else f"sqlite:///{sqlite_path}"
        else:  # Upload mode
            up = kwargs.get('uploaded_file')
            if up is not None:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                tmp.write(up.read())
                tmp.flush()
                return f"sqlite:///{tmp.name}"
        return None

    elif db_type == "MySQL":
        host = kwargs.get('host', 'localhost')
        port = kwargs.get('port', '3306')
        user = kwargs.get('user', 'root')
        password = kwargs.get('password', '')
        database = kwargs.get('database', 'test')
        if all([host, port, user, database]):
            return f"mysql+pymysql://{user}:{quote_plus(password)}@{host}:{port}/{database}"
    
    else:  # PostgreSQL
        host = kwargs.get('host', 'localhost')
        port = kwargs.get('port', '5432')
        user = kwargs.get('user', 'postgres')
        password = kwargs.get('password', '')
        database = kwargs.get('database', 'postgres')
        if all([host, port, user, database]):
            return f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{database}"
    
    return None
