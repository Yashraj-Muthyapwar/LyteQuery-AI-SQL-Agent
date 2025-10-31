# sql-agent-pro/utils/state_manager.py
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from langchain.chat_models import init_chat_model
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import inspect
import pandas as pd
from datetime import datetime
from typing import Dict, Any

def initialize_session_state():
    """Initialize session state variables"""
    for k, v in {
        "history": [],
        "query_log": [],
        "db_connected": False,
        "schema_cache": None,
        "query_count": 0,
        "error_count": 0,
        "explain_cache": {},
        "thread_id": "default",
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v

@st.cache_resource(show_spinner=False)
def get_engine(db_uri: str):
    """Get cached database engine"""
    return create_engine(db_uri, pool_pre_ping=True)

@st.cache_resource(show_spinner=False)
def get_llm_and_agent(provider: str, api_key: str, model_name: str, db_uri: str):
    """Get cached LLM and agent"""
    llm = init_chat_model(f"{provider}:{model_name}", api_key=api_key)
    db = SQLDatabase.from_uri(db_uri)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)

    memory = MemorySaver()
    
    agent = create_sql_agent(llm=llm, toolkit=toolkit, agent_type="tool-calling", verbose=True, checkpointer = memory)
    return llm, agent

@st.cache_data(show_spinner=False)
def cached_schema_info(db_uri: str) -> dict:
    """Get cached schema information"""
    engine = get_engine(db_uri)
    insp = inspect(engine)
    tables = insp.get_table_names()
    info = {'tables': {}, 'total_tables': len(tables)}
    for t in tables[:50]:
        cols = insp.get_columns(t)
        pk = insp.get_pk_constraint(t)
        fks = insp.get_foreign_keys(t)
        entry = {
            'columns': cols,
            'primary_key': pk.get('constrained_columns', []),
            'foreign_keys': fks,
            'column_count': len(cols)
        }
        try:
            with engine.connect() as conn:
                entry['row_count'] = conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
        except Exception:
            entry['row_count'] = 'N/A'
        info['tables'][t] = entry
    return info

def log_query(query: str, status: str, execution_time: float = 0, error: str = None):
    """Log query to session state"""
    st.session_state.query_log.append({
        'timestamp': datetime.now().isoformat(),
        'query': query,
        'status': status,
        'execution_time': execution_time,
        'error': error
    })
    if status == 'success':
        st.session_state.query_count += 1
    elif status == 'error':
        st.session_state.error_count += 1


@st.cache_data(ttl=3600, show_spinner=False)
def cached_sql_execution(db_uri: str, sql_query: str) -> pd.DataFrame:
    """Cache SQL query results for 1 hour"""
    engine = get_engine(db_uri)
    with engine.connect() as conn:
        return pd.read_sql(sql_query, conn)
