# sql-agent-pro/ui/sidebar.py
import streamlit as st
from core.database import test_database_connection, get_database_uri
from utils.state_manager import cached_schema_info
from config.settings import DEFAULT_MODELS

def render_sidebar():
    """Render the sidebar with configuration options"""
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # AI Provider section
        with st.expander("🤖 AI Provider", expanded=not st.session_state.db_connected):
            provider = st.selectbox("Provider", ["openai", "anthropic", "google_genai", "groq"])
            api_key = st.text_input("API Key", type="password")
            model_id = DEFAULT_MODELS[provider]
            
            if not api_key:
                st.warning("⚠️ API key required")
        
        st.divider()
        
        # Database Connection section
        with st.expander("🗄️ Database Connection", expanded=not st.session_state.db_connected):
            db_config = render_database_config()
        
        # Connection button
        if st.button("🔗 Connect Database", width='stretch', type="primary"):
            handle_database_connection(db_config, provider, model_id, api_key)
        
        # Disconnect button
        if st.session_state.db_connected:
            if st.button("🔌 Disconnect", width='stretch'):
                st.session_state.db_connected = False
                st.session_state.history = []
                st.rerun()
        
        st.divider()
        
        # Session analytics and quick actions
        render_sidebar_actions()

def render_database_config():
    """Render database configuration based on selected type"""
    db_type = st.selectbox("Database Type", ["SQLite", "MySQL", "PostgreSQL"], index=0)
    config = {'type': db_type}
    
    if db_type == "SQLite":
        st.caption("📁 Use a file path or upload a .db file")
        mode = st.radio("Source", ["Path", "Upload"], horizontal=True)
        config['mode'] = mode
        if mode == "Path":
            config['sqlite_path'] = st.text_input("SQLite file path", value="sql_agent_sandbox.db")
        else:
            config['uploaded_file'] = st.file_uploader("Upload SQLite .db", type=["db", "sqlite", "sqlite3"])
    
    elif db_type == "MySQL":
        st.caption("📦 Requires: `pip install pymysql`")
        config['host'] = st.text_input("Host", value="localhost")
        config['port'] = st.text_input("Port", value="3306")
        config['user'] = st.text_input("User", value="root")
        config['password'] = st.text_input("Password", type="password")
        config['database'] = st.text_input("Database", value="test")
    
    else:  # PostgreSQL
        st.caption("📦 Requires: `pip install psycopg2-binary`")
        config['host'] = st.text_input("Host", value="localhost")
        config['port'] = st.text_input("Port", value="5432")
        config['user'] = st.text_input("User", value="postgres")
        config['password'] = st.text_input("Password", type="password")
        config['database'] = st.text_input("Database", value="postgres")
    
    return config

def handle_database_connection(db_config, provider, model_id, api_key):
    """Handle database connection logic"""
    if not api_key:
        st.error("❌ Please provide API key first")
        return

    st.session_state.api_key = api_key
    
    db_type = db_config.get('type')
    db_uri = get_database_uri(db_type, **db_config)
    if not db_uri:
        st.error("❌ Please configure database connection")
        return
    
    success, message = test_database_connection(db_uri)
    if success:
        st.session_state.db_connected = True
        st.session_state.db_uri = db_uri
        st.session_state.provider = provider
        st.session_state.model_id = model_id
        st.session_state.schema_cache = cached_schema_info(db_uri)
        st.success(message)
        st.rerun()
    else:
        st.error(message)

def render_sidebar_actions():
    """Render sidebar actions and analytics"""
    if st.session_state.db_connected and st.session_state.query_count > 0:
        st.subheader("📊 Session Analytics")
        c1, c2 = st.columns(2)
        with c1: 
            st.metric("Queries", st.session_state.query_count)
        with c2:
            denom = (st.session_state.query_count + st.session_state.error_count) or 1
            st.metric("Success Rate", f"{st.session_state.query_count / denom * 100:.0f}%")
        
        if st.button("📥 Export Query Log", width='stretch'):
            import json
            from datetime import datetime
            st.download_button(
                "Download JSON",
                data=json.dumps(st.session_state.query_log, indent=2),
                file_name=f"query_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"dl_export_{st.session_state.query_count}",
                width='stretch'
            )
    
    st.divider()
    
    if st.session_state.db_connected:
        st.subheader("⚡ Quick Actions")
        if st.button("🔍 View Schema", width='stretch'):
            st.session_state.show_schema = True
        
        if st.button("🗑️ Clear Chat", width='stretch'):
            st.session_state.history = []
            st.rerun()
        
        st.caption("💡 Sample Queries")
        sample_queries = [
            "Show me all tables", 
            "Describe the schema", 
            "Count rows in each table", 
            "Show sample data"
        ]
        
        for q in sample_queries:
            if st.button(q, width='stretch', key=f"sample_{q}"):
                st.session_state.pending_query = q
                st.rerun()
