# sql-agent-pro/ui/workspace.py
import streamlit as st
import pandas as pd
from datetime import datetime

from utils.chart_generator import build_primary_and_alts, reason_for_spec
from utils.data_profiler import should_plot
from utils.llm_helpers import llm_recommend_charts

def render_workspace_tabs():
    """Render unified workspace tabs for latest results"""
    st.markdown("---")
    st.markdown("### Workspace")
    st.caption("Latest run, organized into tabs: SQL Query, Visualization, and Data Results.")
    
    role, content, metadata = _find_latest_result(st.session_state.history)
    if not metadata:
        st.info("No results yet. Ask a question above to generate SQL and results.")
        return

    df = metadata.get('dataframe')
    sql = metadata.get('sql_query')
    sql_expl = metadata.get('sql_explanation')

    sql_tab, viz_tab, data_tab = st.tabs(["SQL Query", "Visualization", "Data Results"])

    # SQL Tab
    with sql_tab:
        render_sql_tab(sql, sql_expl)

    # Visualization Tab  
    with viz_tab:
        render_visualization_tab(df, metadata, content)

    # Data Results Tab
    with data_tab:
        render_data_tab(df)


def _find_latest_result(history):
    """Find the latest result in chat history"""
    for role, content, metadata in reversed(history):
        if isinstance(metadata, dict) and (metadata.get('dataframe') is not None or metadata.get('sql_query')):
            return role, content, metadata
    return None, None, None

def render_sql_tab(sql, sql_expl):
    """Render SQL query tab"""
    st.subheader("Generated SQL")
    if sql:
        st.code(sql, language="sql")
    else:
        st.info("No SQL generated for the latest message.")
    if sql_expl:
        with st.expander("Explanation"):
            st.markdown(sql_expl)

def render_visualization_tab(df, metadata, content):
    """Render visualization tab"""
    st.subheader("Visualization")
    if isinstance(df, pd.DataFrame) and not df.empty:
        chart_rendered = False

        # Try to render from chart_spec
        try:
            if metadata.get("chart_spec") and 'build_primary_and_alts' in globals():
                raw_spec = metadata.get("chart_spec")
                primary_fig, alts, final_spec = build_primary_and_alts(df, raw_spec, content)
                if primary_fig:
                    tab_names = ["Chart"] + [n for n,_ in alts]
                    tabs = st.tabs(tab_names)
                    with tabs[0]:
                        st.plotly_chart(primary_fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
                    for i,(name, alt_fig) in enumerate(alts, start=1):
                        with tabs[i]:
                            st.plotly_chart(alt_fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
                    if 'reason_for_spec' in globals():
                        st.caption(reason_for_spec(df, final_spec.get("primary", {}), content))
                    chart_rendered = True
        except Exception:
            pass

        # Fallback to auto-recommendation
        if not chart_rendered:
            try:
                if 'should_plot' in globals() and should_plot(content, df):
                    raw_spec = metadata.get("chart_spec")
                    if raw_spec is None and 'llm_recommend_charts' in globals():
                        llm = st.session_state.get('llm', None)
                        if llm:
                            from utils.llm_helpers import llm_recommend_charts
                            raw_spec = llm_recommend_charts(llm, content, df)
                    if 'build_primary_and_alts' in globals() and raw_spec:
                        primary_fig, alts, final_spec = build_primary_and_alts(df, raw_spec, content)
                        if primary_fig:
                            tab_names = ["Chart"] + [n for n,_ in alts]
                            tabs = st.tabs(tab_names)
                            with tabs[0]:
                                st.plotly_chart(primary_fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
                            for i,(name, alt_fig) in enumerate(alts, start=1):
                                with tabs[i]:
                                    st.plotly_chart(alt_fig, use_container_width=True, config={"displaylogo": False, "responsive": True})
                            if 'reason_for_spec' in globals():
                                st.caption(reason_for_spec(df, final_spec.get("primary", {}), content))
                            chart_rendered = True
            except Exception:
                pass

        if not chart_rendered:
            st.info("No chart to show yet for this result. Run a query that returns a table and I'll visualize it here.")
    else:
        st.info("No data to visualize yet.")

def render_data_tab(df):
    """Render data results tab"""
    st.subheader("Data Results")
    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df, use_container_width=True)
        try:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "📥 Download CSV", 
                csv, 
                file_name=f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                mime="text/csv"
            )
        except Exception:
            pass
    else:
        st.info("No rows returned.")
