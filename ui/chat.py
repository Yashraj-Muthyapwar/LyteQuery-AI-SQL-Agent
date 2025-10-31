# sql-agent-pro/ui/chat.py (ENHANCED VERSION)
import streamlit as st
import pandas as pd
import time
import uuid
from datetime import datetime

from core.agent import SQLCaptureHandler, get_agent_hint
from core.sql_utils import normalize_tool_sql, prettify_sql
from utils.llm_helpers import llm_explain_sql, llm_recommend_charts, get_next_queries, render_suggestions
from utils.state_manager import log_query, get_engine, cached_sql_execution
from utils.data_profiler import should_plot
from utils.chart_generator import build_primary_and_alts, reason_for_spec

def render_chat_interface(llm, agent):
    """Render the main chat interface"""
    # Schema viewer
    if getattr(st.session_state, 'show_schema', False):
        render_schema_viewer()
    
    # Chat history
    render_chat_history()
    
    # User input
    handle_user_input(llm, agent)

def render_schema_viewer():
    """Render schema viewer expander"""
    with st.expander("📋 Database Schema", expanded=True):
        schema = st.session_state.schema_cache or {}
        st.markdown(f"**Total Tables:** {schema.get('total_tables', 0)}")
        table = st.selectbox("Select Table", options=list(schema.get('tables', {}).keys()))
        if table:
            tinfo = schema['tables'][table]
            c1, c2, c3 = st.columns(3)
            with c1: 
                st.metric("Columns", tinfo['column_count'])
            with c2: 
                st.metric("Rows", tinfo.get('row_count', 'N/A'))
            with c3: 
                st.metric("Primary Keys", len(tinfo['primary_key']))
            st.markdown("**Columns:**")
            st.dataframe(pd.DataFrame(tinfo['columns'])[['name','type']], width='stretch')
        if st.button("Close Schema View"):
            st.session_state.show_schema = False
            st.rerun()

def render_chat_history():
    """Render chat message history"""
    for idx, (role, content, metadata) in enumerate(st.session_state.history):
        with st.chat_message(role):
            st.markdown(content)
            if not metadata:
                continue
            
            # Render message metadata (SQL, data, charts, etc.)
            render_message_metadata(metadata, content, f"msg_{idx}")

def render_message_metadata(metadata, content, message_id):
    """Render metadata for a chat message (SQL, data, charts)"""
    df = metadata.get('dataframe')
    if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
        sql_tab_msg, data_tab_msg, viz_tab_msg = st.tabs(["SQL Query", "Data", "Chart"])

        with sql_tab_msg:
            render_sql_metadata(metadata)

        with data_tab_msg:
            st.dataframe(df, width='stretch')
            # Download button for data
            st.download_button(
                "📥 Download CSV",
                data=df.to_csv(index=False),
                file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"dl_msg_{uuid.uuid4()}",
                width='stretch'
            )

        with viz_tab_msg:
            render_visualization_metadata(metadata, content, df)
    else:
        st.info("No rows returned.")

    # Suggestions - pass message_id to ensure unique keys
    suggestions = metadata.get('suggestions', [])
    if suggestions:
        render_suggestions(suggestions, "🔍 Explore further", message_id)

    # Execution time
    if 'execution_time' in metadata:
        st.caption(f"⏱️ Execution time: {metadata['execution_time']:.2f}s")


def render_sql_metadata(metadata):
    """Render SQL query and explanation"""
    sql = metadata.get('sql_query')
    sql_expl = metadata.get('sql_explanation')
    if sql:
        st.code(sql, language="sql")
    else:
        st.info("No SQL generated for this message.")
    if sql_expl:
        with st.expander("Explanation"):
            st.markdown(sql_expl)


def render_visualization_metadata(metadata, content, df, message_id=""):
    """Render visualization - GUARANTEED unique keys + Updated width parameter"""
    import uuid
    
    # Ensure we always have a unique key base
    if not message_id:
        message_id = f"auto_{uuid.uuid4().hex[:8]}"
    
    try:
        if metadata.get("chart_spec") and should_plot(content, df):
            primary_fig, alts, final_spec = build_primary_and_alts(df, metadata["chart_spec"], content)
            if primary_fig:
                tab_names = ["Chart"] + [n for n, _ in alts]
                tabs = st.tabs(tab_names)
                
                with tabs[0]:
                    st.plotly_chart(
                        primary_fig, 
                        width='stretch',  
                        config={"displaylogo": False, "responsive": True},
                        key=f"chart_primary_{message_id}_{uuid.uuid4().hex[:4]}"
                    )
                
                for i, (name, alt_fig) in enumerate(alts, start=1):
                    with tabs[i]:
                        st.plotly_chart(
                            alt_fig, 
                            width='stretch',  
                            config={"displaylogo": False, "responsive": True},
                            key=f"chart_alt_{i}_{message_id}_{uuid.uuid4().hex[:4]}"
                        )
                
                st.caption(reason_for_spec(df, final_spec.get("primary", {}), content))
        else:
            st.caption("🧠 Skipped chart to save resources (no obvious visualization needed).")
    except Exception as e:
        st.error(f"Chart rendering error: {e}")


def handle_user_input(llm, agent):
    """Handle user input and process queries"""
    if hasattr(st.session_state, 'pending_query'):
        user_msg = st.session_state.pending_query
        delattr(st.session_state, 'pending_query')
    else:
        user_msg = st.chat_input("Ask anything about your data...")

    if user_msg:
        process_user_query(user_msg, llm, agent)


def build_conversation_context(max_exchanges=3):
    """Build conversation context from recent history"""
    context_parts = []
    recent_history = st.session_state.history[-(max_exchanges * 2):]  # Get last N Q&A pairs
    
    for role, content, metadata in recent_history:
        if role == "user":
            context_parts.append(f"Previous User Question: {content}")
        elif role == "assistant" and metadata:
            # Include SQL for context (truncated)
            sql = metadata.get('sql_query', '')
            if sql:
                sql_snippet = sql[:150] + "..." if len(sql) > 150 else sql
                context_parts.append(f"Previous SQL: {sql_snippet}")
    
    if context_parts:
        return "\n".join(context_parts)
    return ""


def get_error_recovery_suggestions(error_msg, user_msg):
    """Generate helpful suggestions based on error type"""
    error_lower = error_msg.lower()
    suggestions = []
    
    if "no such table" in error_lower or "table" in error_lower and "not found" in error_lower:
        suggestions = [
            {"question": "Show me all available tables", "why": "See what tables exist in the database"},
            {"question": "Describe the database schema", "why": "Understand the database structure"}
        ]
    elif "no such column" in error_lower or "column" in error_lower and "not found" in error_lower:
        # Try to extract table name from error
        suggestions = [
            {"question": "Show all columns in the tables", "why": "Check available columns"},
            {"question": "Describe the table structure", "why": "See exact column names"}
        ]
    elif "syntax error" in error_lower or "syntax" in error_lower:
        suggestions = [
            {"question": f"Explain this in simpler terms: {user_msg[:50]}...", "why": "Try rephrasing the question"},
            {"question": "Show sample data from tables", "why": "Understand data format first"}
        ]
    elif "ambiguous" in error_lower:
        suggestions = [
            {"question": f"Be more specific: {user_msg}", "why": "Clarify which table/column"},
        ]
    elif "timeout" in error_lower or "timed out" in error_lower:
        suggestions = [
            {"question": "Limit the query to top 100 rows", "why": "Reduce query complexity"},
            {"question": "Add more filters to narrow results", "why": "Make query more specific"}
        ]
    else:
        # Generic fallback suggestions
        suggestions = [
            {"question": "Show me all tables", "why": "Start with database overview"},
            {"question": "What data is available?", "why": "Explore available information"}
        ]
    
    return suggestions


def process_user_query(user_msg, llm, agent):
    """Process user query with LangGraph memory and spinner feedback"""
    # STEP 0: Check if this is a visualization request for previous data
    if is_chart_request_for_previous_data(user_msg):
        handle_chart_from_previous_data(user_msg, llm)
        return  # Exit early, don't call agent
    
    st.session_state.history.append(("user", user_msg, None))
    
    with st.chat_message("user"):
        st.markdown(user_msg)

    with st.chat_message("assistant"):
        start = time.time()
        handler = SQLCaptureHandler()
        
        try:
            # Combined spinner for all operations
            with st.spinner("🔍 Analyzing your question..."):
                time.sleep(0.3)
            
            with st.spinner("🛠️ Generating SQL query..."):
                full_input = get_agent_hint() + "\n\n**CURRENT QUESTION:** " + user_msg
                
                # LangGraph memory magic happens here!
                config = {
                    "callbacks": [handler],
                    "configurable": {
                        "thread_id": st.session_state.thread_id  # Conversation memory
                    }
                }
                
                result = agent.invoke({"input": full_input}, config=config)
                
                elapsed_generation = time.time() - start
                answer = result.get("output", str(result))
                
                # Process SQL
                raw_payload = handler.sql_calls[-1] if handler.sql_calls else None
                sql_query = normalize_tool_sql(raw_payload)
                pretty_sql = prettify_sql(sql_query) if sql_query else None
            
            # STEP 3: Execute
            df = None
            if pretty_sql:
                with st.spinner("⚡ Executing query..."):
                    try:
                        df = cached_sql_execution(st.session_state.db_uri, pretty_sql)
                        if df is not None and not df.empty:
                            st.success(f"✅ Retrieved {len(df):,} rows × {len(df.columns)} columns")
                            time.sleep(0.5)
                    except Exception as e:
                        st.warning(f"⚠️ Query issue: {str(e)[:100]}")
                        df = None
            
            # STEP 4: Explain
            with st.spinner("📝 Generating SQL explanation..."):
                sql_expl = None
                if pretty_sql:
                    sql_expl = llm_explain_sql(
                        llm, pretty_sql, user_msg,
                        st.session_state.provider, st.session_state.model_id
                    )
            
            # STEP 5: Visualize
            chart_spec = {}
            if df is not None and not df.empty and should_plot(user_msg, df):
                with st.spinner("📊 Preparing visualization..."):
                    try:
                        raw_spec = llm_recommend_charts(llm, user_msg, df)
                        chart_spec = raw_spec
                    except Exception:
                        pass
            
            # STEP 6: Suggestions
            with st.spinner("💡 Generating suggestions..."):
                suggestions = []
                try:
                    suggestions = get_next_queries(
                        llm=llm, user_question=user_msg, df=df,
                        sql_query=pretty_sql, schema=st.session_state.schema_cache, n=3
                    )
                except Exception:
                    pass
            
            # Display results
            elapsed = time.time() - start
            
            st.markdown(answer)
            st.caption(f"⏱️ Total: {elapsed:.2f}s (SQL gen: {elapsed_generation:.2f}s)")
            
            metadata = {
                "sql_query": pretty_sql,
                "sql_explanation": sql_expl,
                "dataframe": df,
                "execution_time": elapsed,
                "auto_viz": True,
                "chart_spec": chart_spec,
                "suggestions": suggestions
            }
            
            log_query(user_msg, "success", elapsed)
            st.session_state.history.append(("assistant", answer, metadata))
            
        except Exception as e:
            elapsed = time.time() - start
            error_msg = str(e)
            
            st.error(f"❌ Error: {error_msg}")
            
            suggestions = get_error_recovery_suggestions(error_msg, user_msg)
            
            if "no such table" in error_msg.lower():
                st.info("💡 **Tip:** Table doesn't exist. Try viewing all available tables first.")
            elif "no such column" in error_msg.lower():
                st.info("💡 **Tip:** Column name might be misspelled. Check the table structure.")
            elif "syntax error" in error_msg.lower():
                st.info("💡 **Tip:** Try rephrasing your question in simpler terms.")
            
            st.caption(f"⏱️ Failed after: {elapsed:.2f}s")
            
            log_query(user_msg, "error", elapsed, error_msg)
            
            error_metadata = {"error": error_msg, "suggestions": suggestions}
            st.session_state.history.append(("assistant", f"⚠️ {error_msg}", error_metadata))
    
    st.rerun()

def get_error_recovery_suggestions(error_msg, user_msg):
    """Generate helpful suggestions based on error type"""
    error_lower = error_msg.lower()
    suggestions = []
    
    if "no such table" in error_lower or "table" in error_lower and "not found" in error_lower:
        suggestions = [
            {"question": "Show me all available tables", "why": "See what tables exist"},
            {"question": "Describe the database schema", "why": "Understand structure"}
        ]
    elif "no such column" in error_lower:
        suggestions = [
            {"question": "Show all columns in the tables", "why": "Check columns"},
        ]
    elif "syntax error" in error_lower:
        suggestions = [
            {"question": f"Explain this simpler: {user_msg[:50]}...", "why": "Rephrase"},
        ]
    else:
        suggestions = [
            {"question": "Show me all tables", "why": "Start with overview"},
        ]
    
    return suggestions

def is_chart_request_for_previous_data(user_msg):
    """
    Detect if user is requesting a chart/visualization of previous data
    """
    user_lower = user_msg.lower().strip()
    
    # Chart type keywords
    chart_keywords = [
        'pie chart', 'bar chart', 'line chart', 'line graph', 
        'bar graph', 'scatter plot', 'histogram', 'chart',
        'graph', 'plot', 'visualize', 'visualization'
    ]
    
    # Reference to previous data
    reference_keywords = [
        'previous', 'that', 'those', 'it', 'them',
        'the data', 'the result', 'above', 'same data'
    ]
    
    # Check if message contains both chart request and reference
    has_chart_keyword = any(keyword in user_lower for keyword in chart_keywords)
    has_reference = any(keyword in user_lower for keyword in reference_keywords)
    
    # Also check for patterns like "show as X" or "display as X"
    show_as_pattern = ('show' in user_lower or 'display' in user_lower) and 'as' in user_lower
    
    return has_chart_keyword and (has_reference or show_as_pattern)




def extract_chart_type(user_msg):
    """
    Extract the requested chart type from user message
    Returns SPECIFIC chart type (not generic Vega mark)
    """
    user_lower = user_msg.lower().strip()
    
    # Map keywords to SPECIFIC chart types (not generic marks)
    chart_patterns = {
        # Pie variations - DIFFERENT TYPES
        'pie': 'pie',           # Solid pie
        'donut': 'donut',       # Pie with hole
        'doughnut': 'donut',    # Pie with hole
        
        # Bar variations - DIFFERENT TYPES
        'bar': 'bar',                      # Vertical bar
        'bars': 'bar',                     # Vertical bar
        'column': 'bar',                   # Vertical bar
        'horizontal bar': 'bar_horizontal', # Horizontal bar
        
        # Line variations
        'line': 'line',
        'lines': 'line',
        'trend': 'line',
        'time series': 'line',
        'timeseries': 'line',
        
        # Area variations - DIFFERENT TYPES
        'area': 'area',                    # Simple area
        'stacked area': 'stacked_area',    # Stacked area
        
        # Scatter variations - DIFFERENT TYPES
        'scatter': 'scatter',              # Points only
        'scatterplot': 'scatter',          # Points only
        'scatter plot': 'scatter',         # Points only
        'point': 'scatter',                # Points only
        'bubble': 'bubble',                # Points with size
        
        # Statistical charts - DIFFERENT TYPES
        'histogram': 'histogram',          # Distribution bars
        'distribution': 'histogram',       # Distribution bars
        'frequency': 'histogram',          # Distribution bars
        'box': 'box',                      # Box and whisker
        'boxplot': 'box',                  # Box and whisker
        'box plot': 'box',                 # Box and whisker
        'violin': 'violin',                # Violin shape
        
        # Heat and tree maps - DIFFERENT TYPES
        'heatmap': 'heatmap',              # Color intensity grid
        'heat map': 'heatmap',             # Color intensity grid
        'treemap': 'treemap',              # Nested rectangles
        'tree map': 'treemap',             # Nested rectangles
        
        # Other specialized - ALL DIFFERENT
        'funnel': 'funnel',
        'waterfall': 'waterfall',
        'gauge': 'gauge',
        'sunburst': 'sunburst',
        'radar': 'radar',
        'spider': 'radar',
        'sankey': 'sankey',
    }
    
    # Check for "keyword chart/graph/plot"
    for keyword, chart_type in chart_patterns.items():
        if (f'{keyword} chart' in user_lower or 
            f'{keyword} graph' in user_lower or 
            f'{keyword} plot' in user_lower):
            return chart_type
    
    # Check for "show as/display as/visualize as keyword"
    action_phrases = ['show as', 'display as', 'visualize as', 'plot as', 
                     'make a', 'create a', 'draw a', 'render as']
    for phrase in action_phrases:
        if phrase in user_lower:
            parts = user_lower.split(phrase)
            if len(parts) > 1:
                after_phrase = parts[1].strip().split()[0] if parts[1].strip() else ''
                if after_phrase in chart_patterns:
                    return chart_patterns[after_phrase]
    
    # Check for standalone keywords when context suggests visualization
    if any(word in user_lower for word in ['chart', 'graph', 'plot', 'visualize', 'show']):
        for keyword, chart_type in chart_patterns.items():
            if f' {keyword} ' in f' {user_lower} ' or \
               user_lower.startswith(keyword + ' ') or \
               user_lower.endswith(' ' + keyword):
                return chart_type
    
    return None



# FIXED: handle_chart_from_previous_data
# This version properly creates charts that will be displayed (not skipped)

def handle_chart_from_previous_data(user_msg, llm):
    """
    Create chart from previous query results
    Works with existing chart infrastructure to avoid "skipped chart" issue
    """
    import streamlit as st
    import uuid
    from utils.llm_helpers import llm_recommend_charts
    from utils.chart_generator import build_primary_and_alts
    
    st.session_state.history.append(("user", user_msg, None))
    
    with st.chat_message("user"):
        st.markdown(user_msg)
    
    with st.chat_message("assistant"):
        # Find previous data
        previous_data = None
        previous_sql = None
        for role, content, metadata in reversed(st.session_state.history[:-1]):
            if role == "assistant" and metadata:
                df = metadata.get('dataframe')
                if df is not None and not df.empty:
                    previous_data = df
                    previous_sql = metadata.get('sql_query')
                    break
        
        if previous_data is None:
            st.error("❌ No previous data to visualize")
            st.info("💡 **Tip:** First run a query to get data, then ask for a visualization.")
            st.rerun()
            return
        
        # Extract requested chart type
        chart_type = extract_chart_type(user_msg)
        
        # Chart display names
        chart_names = {
            'pie': 'Pie Chart',
            'donut': 'Donut Chart',
            'bar': 'Bar Chart',
            'bar_horizontal': 'Horizontal Bar Chart',
            'line': 'Line Chart',
            'area': 'Area Chart',
            'stacked_area': 'Stacked Area Chart',
            'scatter': 'Scatter Plot',
            'bubble': 'Bubble Chart',
            'histogram': 'Histogram',
            'box': 'Box Plot',
            'violin': 'Violin Plot',
            'heatmap': 'Heatmap',
            'treemap': 'Treemap',
            'funnel': 'Funnel Chart',
            'waterfall': 'Waterfall Chart',
            'gauge': 'Gauge Chart',
            'sunburst': 'Sunburst Chart',
            'radar': 'Radar Chart',
            'sankey': 'Sankey Diagram',
        }
        
        # Map chart type to Vega-Lite mark
        chart_type_to_mark = {
            'pie': 'arc',
            'donut': 'arc',
            'bar': 'bar',
            'bar_horizontal': 'bar',
            'line': 'line',
            'area': 'area',
            'stacked_area': 'area',
            'scatter': 'point',
            'bubble': 'point',
            'histogram': 'bar',
            'box': 'boxplot',
            'violin': 'area',
            'heatmap': 'rect',
            'treemap': 'rect',
            'funnel': 'bar',
            'waterfall': 'bar',
            'gauge': 'arc',
            'sunburst': 'arc',
            'radar': 'line',
            'sankey': 'line',
        }
        
        chart_name = chart_names.get(chart_type, 'Chart')
        
        if chart_type:
            st.success(f"✅ Creating **{chart_name}** from previous query ({len(previous_data)} rows)")
        else:
            st.success(f"✅ Creating chart from previous query ({len(previous_data)} rows)")
        
        try:
            with st.spinner(f"📊 Generating {chart_name.lower()}..."):
                # Get base chart recommendation from LLM
                chart_spec = llm_recommend_charts(llm, user_msg, previous_data)
                
                # Override with user's specific chart type request
                if chart_type and 'primary' in chart_spec:
                    # Get original encodings
                    original_x = chart_spec['primary'].get('x')
                    original_y = chart_spec['primary'].get('y')
                    
                    # Get column info
                    cols = previous_data.columns.tolist()
                    cat_cols = [col for col in cols if previous_data[col].dtype == 'object']
                    num_cols = [col for col in cols if previous_data[col].dtype in ['int64', 'float64']]
                    
                    cat_col = cat_cols[0] if cat_cols else cols[0]
                    num_col = num_cols[0] if num_cols else (cols[1] if len(cols) > 1 else cols[0])
                    
                    # Determine which is categorical and which is numeric
                    if original_x and original_y:
                        if previous_data[original_x].dtype == 'object':
                            cat_col = original_x
                            num_col = original_y
                        else:
                            cat_col = original_y
                            num_col = original_x
                    
                    # Set the Vega mark type
                    vega_mark = chart_type_to_mark.get(chart_type, 'bar')
                    chart_spec['primary']['mark'] = vega_mark
                    
                    # Apply chart-specific transformations
                    if chart_type in ['pie', 'donut']:
                        # PIE/DONUT CHARTS - need theta and color
                        chart_spec['primary']['theta'] = num_col
                        chart_spec['primary']['color'] = cat_col
                        chart_spec['primary'].pop('x', None)
                        chart_spec['primary'].pop('y', None)
                        
                        # Add donut-specific property
                        if chart_type == 'donut':
                            chart_spec['primary']['innerRadius'] = 80  # Creates hole
                    
                    elif chart_type == 'bar':
                        # VERTICAL BAR CHART
                        chart_spec['primary']['x'] = cat_col
                        chart_spec['primary']['y'] = num_col
                    
                    elif chart_type == 'bar_horizontal':
                        # HORIZONTAL BAR CHART
                        chart_spec['primary']['x'] = num_col
                        chart_spec['primary']['y'] = cat_col
                    
                    elif chart_type in ['line', 'area']:
                        # LINE/AREA CHARTS
                        chart_spec['primary']['x'] = cols[0]
                        chart_spec['primary']['y'] = num_col
                    
                    elif chart_type == 'stacked_area':
                        # STACKED AREA
                        chart_spec['primary']['x'] = cols[0]
                        chart_spec['primary']['y'] = num_col
                        if len(cat_cols) > 1:
                            chart_spec['primary']['color'] = cat_cols[1]
                    
                    elif chart_type in ['scatter', 'bubble']:
                        # SCATTER/BUBBLE PLOTS
                        x_col = num_cols[0] if len(num_cols) > 0 else cols[0]
                        y_col = num_cols[1] if len(num_cols) > 1 else num_col
                        chart_spec['primary']['x'] = x_col
                        chart_spec['primary']['y'] = y_col
                        
                        if chart_type == 'bubble' and len(num_cols) >= 3:
                            chart_spec['primary']['size'] = num_cols[2]
                    
                    elif chart_type == 'histogram':
                        # HISTOGRAM
                        chart_spec['primary']['x'] = num_col
                        chart_spec['primary'].pop('y', None)
                    
                    elif chart_type in ['box', 'violin']:
                        # BOX/VIOLIN PLOTS
                        chart_spec['primary']['x'] = cat_col
                        chart_spec['primary']['y'] = num_col
                    
                    elif chart_type in ['heatmap', 'treemap']:
                        # HEATMAP/TREEMAP
                        if len(cols) >= 3:
                            chart_spec['primary']['x'] = cols[0]
                            chart_spec['primary']['y'] = cols[1]
                            chart_spec['primary']['color'] = num_col
                        else:
                            chart_spec['primary']['x'] = cat_col
                            chart_spec['primary']['y'] = num_col
                            chart_spec['primary']['color'] = num_col
                
                # Build the chart using existing infrastructure
                primary_fig, alts, final_spec = build_primary_and_alts(
                    previous_data, 
                    chart_spec, 
                    user_msg
                )
                
                # Display the chart
                if primary_fig:
                    message_id = f"prev_chart_{uuid.uuid4().hex[:8]}"
                    
                    # Display with tabs if alternates exist
                    if alts:
                        tab_names = [chart_name] + [name for name, _ in alts]
                        tabs = st.tabs(tab_names)
                        
                        with tabs[0]:
                            st.plotly_chart(
                                primary_fig, 
                                width='stretch',
                                key=f"chart_primary_{message_id}"
                            )
                        
                        for i, (name, alt_fig) in enumerate(alts, start=1):
                            with tabs[i]:
                                st.plotly_chart(
                                    alt_fig, 
                                    width='stretch',
                                    key=f"chart_alt_{i}_{message_id}"
                                )
                    else:
                        st.plotly_chart(
                            primary_fig, 
                            width='stretch',
                            key=f"chart_{message_id}"
                        )
                    
                    # Show data source
                    with st.expander("📊 Data Source & Details"):
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.caption("**Original SQL Query:**")
                            if previous_sql:
                                st.code(previous_sql, language='sql')
                        
                        with col2:
                            st.caption("**Chart Info:**")
                            st.write(f"**Type:** {chart_name}")
                            st.write(f"**Rows:** {len(previous_data)}")
                            st.write(f"**Columns:** {len(cols)}")
                        
                        st.caption("**Data Preview:**")
                        st.dataframe(previous_data.head(10), width='stretch')
                        if len(previous_data) > 10:
                            st.caption(f"Showing first 10 of {len(previous_data)} rows")
                    
                    # Save to history
                    answer = f"Created {chart_name} from previous query results."
                    metadata = {
                        'dataframe': previous_data,
                        'sql_query': previous_sql,
                        'chart_spec': chart_spec,
                        'chart_type': chart_type,
                        'from_previous': True
                    }
                    st.session_state.history.append(("assistant", answer, metadata))
                    
                else:
                    st.warning("⚠️ Could not generate chart from the data.")
                    st.info("💡 Try a different chart type or check your data structure.")
                    
        except Exception as e:
            st.error(f"❌ Error creating {chart_name.lower()}: {str(e)}")
            import traceback
            with st.expander("🔍 Error Details"):
                st.code(traceback.format_exc())
    
    st.rerun()
