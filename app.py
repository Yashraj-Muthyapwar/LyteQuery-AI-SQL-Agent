# sql-agent-pro/app.py
import streamlit as st
from ui.sidebar import render_sidebar
from ui.chat import render_chat_interface
from ui.styles import load_css
from utils.state_manager import initialize_session_state
from core.database import setup_database_connection

def main():

    # Page config
    st.set_page_config(
        page_title="LyteQuery AI SQL Agent",
        page_icon="🗄️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Load CSS
    load_css()
    
    # Initialize session state
    initialize_session_state()
    
    
    
    # Header
    c1, c2 = st.columns([5, 1])
    with c1:
        st.title("⛁ LyteQuery AI SQL Agent")
        st.markdown("Ask questions in plain English, get instant insights from your data.")
    with c2:
        if st.session_state.db_connected:
            st.markdown('<div class="success-badge">✓ Connected</div>', unsafe_allow_html=True)

    # Call to action
    st.markdown("👈 **Configure your connection in the sidebar to get started**")

    # Sidebar
    render_sidebar()
    
    # Main content area
    if not st.session_state.get("db_connected"):
        render_professional_homepage()
        return
    
    # Setup database connection
    llm, agent = setup_database_connection()
    if llm is None or agent is None:
        return
    
    # Chat interface
    render_chat_interface(llm, agent)


def render_professional_homepage():
    """Render a clean, professional homepage for Streamlit"""    
    # Core features
    # Core features - More conversational
    # Core features - Using tabs
    st.markdown("### ✨ What You Can Do")

    tab1, tab2, tab3 = st.tabs(["💬 Natural Language", "📊 Auto Visualizations", "🔄 Smart Context"])

    with tab1:
        st.markdown("""
        **Ask questions like you're talking to a colleague.**
        
        **No SQL knowledge needed** we translate your words into database queries. Just type naturally:
        - "Show me sales by region"
        - "Which customers bought most last month?"
        - "Compare Q3 to Q4"
        """)

    with tab2:
        st.markdown("""
        **See your data come to life automatically.**
        
        Charts and graphs appear when they help tell the story. Get instant visualizations:
        - Bar charts for comparisons
        - Line graphs for trends
        - Pie charts for distributions
        """)

    with tab3:
        st.markdown("""
        **The conversation remembers everything.**
        
        Follow-ups feel natural just say **"what about California?"** and it knows what you mean:
        - Build on previous queries
        - Refine results naturally
        - Explore deeper without repeating context
        """)

    # Supported databases - Compact list
    st.markdown("### 🗄️ Connect to Your Database")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("#### 📦 SQLite")
        st.markdown("Perfect for local development and demos. Upload your `.db` file and start querying in seconds.")
        st.markdown("")
        
    with col2:
        st.markdown("#### 🏢 MySQL")
        st.markdown("Connect securely to production databases. Built for enterprise scale and high-performance workloads.")
        st.markdown("")

    with col3:
        st.markdown("#### 🐘 PostgreSQL")
        st.markdown("Need advanced features? PostgreSQL support handles complex queries and sophisticated analysis.")

    # How it works - More engaging
    with st.expander("📖 How It Works", expanded=False):
        st.markdown("### From Question to Answer in Seconds")
        
        st.markdown("""
        Here's what happens when you ask a question:
        """)
        
        st.markdown("""
            1️⃣ **You ask naturally** — "What were my top products last month?"  
            
            2️⃣ **AI understands context** — Examines your schema, understands relationships, generates perfect SQL  
            
            3️⃣ **You get results** — Data appears with charts when they help visualize patterns  
            
            4️⃣ **Keep exploring** — Ask follow-ups that build on previous answers
            """)
        
       
    # Pro Tips - More actionable
    with st.expander("💡 Pro Tips for Best Results", expanded=False):
        st.markdown("### Master These Patterns for Better Answers")
        
        tip_col1, tip_col2 = st.columns(2)
        
        with tip_col1:
            st.markdown("#### ✅ Be Specific")
            st.markdown("""
            The more details you give, the better:
            
            - Include **quantities**: "top 10" or "all"
            - Specify **time periods**: "last month", "Q3 2024"
            - Want everything? Add: **"don't limit"** or **"show all"**
            
            *Example: "Sales by state, don't limit to 10"*
            """)
            
            st.markdown("#### 🔄 Smart Follow-ups")
            st.markdown("""
            Build on previous answers naturally:
            
            - **"What about California?"** → instantly filters
            - **"Show me more details"** → expands data
            - **"How does that compare to last year?"** → adds context
            
            *The AI remembers what you're analyzing!*
            """)
        
        with tip_col2:
            st.markdown("#### 📊 Control Your Visualizations")
            st.markdown("""
            Want a specific chart type? Just ask:
            
            - "Show as a bar chart" → specific chart type
            - "Plot over time" → time series view
            - Charts auto-generated when appropriate

            """)
            
            st.markdown("#### ⚡ Performance")
            st.markdown("""
            Built for performance:

            - **Repeated queries** = instant results (cached!)
            - **Export anywhere** = Export to CSV for further analysis
            - **Learn as you go** = View SQL Code & Explanation to understand the logic
            """)
        
if __name__ == "__main__":
    main()
