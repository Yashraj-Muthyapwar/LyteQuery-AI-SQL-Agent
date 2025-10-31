# sql-agent-pro/utils/llm_helpers.py
import json
import re
import hashlib
import uuid
import pandas as pd
import streamlit as st
from typing import Optional, List, Dict, Any
import pandas as pd
from config.settings import CHART_TYPES


def llm_recommend_charts(llm, question: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Recommend charts using LLM based on question and data profile"""
    from utils.data_profiler import profile_dataframe
    
    SYSTEM = (
        "You are a senior data viz assistant. "
        "Given a user question and a dataframe schema+sample, return JSON with 'primary', 'alternates'(0-3), 'reasoning'. "
        "Allowed 'type': " + ", ".join(sorted(CHART_TYPES.keys())) + ". "
        
        "**YOUR MOST IMPORTANT RULE:** If the user's question explicitly asks for a chart type (e.g., 'pie chart', 'choropleth map', 'bar chart'), "
        "you MUST make that the 'primary' chart. Then, find the best columns in the dataframe that fit that chart's requirements. "
        "Do not default to a different chart type if the user was specific.\n"
        
        "**CRITICAL CHOROPLETH REQUIREMENTS:**\n"
        "For choropleth maps, you MUST provide ALL of these fields:\n"
        "1. 'type': 'choropleth'\n"
        "2. 'locations': column name with location codes/names\n"
        "3. 'color': column name with numeric values to visualize\n"
        "4. 'locationmode': MUST be one of:\n"
        "   - 'USA-states' for US state codes (e.g., 'CA', 'TX', 'NY')\n"
        "   - 'country names' for country names (e.g., 'United States', 'India')\n"
        "   - 'ISO-3' for 3-letter country codes (e.g., 'USA', 'IND', 'CAN')\n"
        "5. 'scope': MUST be:\n"
        "   - 'usa' if locationmode is 'USA-states'\n"
        "   - 'world' for country-level maps\n"
        "   - 'north america', 'europe', 'asia', 'africa', 'south america' for regions\n\n"
        
        "**EXAMPLE CHOROPLETH SPEC:**\n"
        "```json\n"
        "{\n"
        "  'type': 'choropleth',\n"
        "  'locations': 'STATE',\n"
        "  'color': 'total_flights',\n"
        "  'locationmode': 'USA-states',\n"
        "  'scope': 'usa'\n"
        "}\n"
        "```\n\n"
        
        "If the data contains state abbreviations (CA, TX, NY, etc.), ALWAYS use:\n"
        "- 'locationmode': 'USA-states'\n"
        "- 'scope': 'usa'\n\n"
        
        "If you cannot determine the correct locationmode, DO NOT recommend choropleth - use bar chart instead.\n"
        )
    USER = {"question": question, "dataframe_profile": profile_dataframe(df)}
    prompt = "SYSTEM:\n"+SYSTEM+"\n\nUSER:\n"+json.dumps(USER)+"\n\nASSISTANT: Return ONLY JSON."
    try:
        resp = llm.invoke(prompt)
        txt = resp.content if hasattr(resp, "content") else str(resp)
        start = txt.find("{"); end = txt.rfind("}")
        if start != -1 and end != -1 and end > start:
            txt = txt[start:end+1]
        spec = json.loads(txt)
        if not isinstance(spec, dict):
            raise ValueError("Chart spec not a JSON object")
        spec.setdefault("primary", {})
        spec.setdefault("alternates", [])
        spec.setdefault("reasoning", "")
        return spec
    except Exception:
        return {"primary": {}, "alternates": [], "reasoning": ""}

def _schema_brief(schema: dict, max_tables: int = 15, max_cols: int = 12) -> List[Dict[str, Any]]:
    """Generate brief schema information for LLM context"""
    out = []
    tables = list(schema.get("tables", {}).items())[:max_tables]
    for tname, info in tables:
        cols = info.get("columns", [])[:max_cols]
        out.append({
            "table": tname,
            "columns": [f"{c.get('name')}:{c.get('type')}" for c in cols]
        })
    return out

def get_next_queries(
    llm,
    user_question: str,
    df: Optional[pd.DataFrame],
    sql_query: Optional[str],
    schema: Optional[dict],
    n: int = 5,
) -> List[Dict[str, str]]:
    """Generate follow-up query suggestions using LLM"""
    if not user_question and not sql_query and (df is None or df.empty):
        return []
    
    # Import profile_dataframe here to avoid circular imports
    from utils.data_profiler import profile_dataframe
    
    profile = profile_dataframe(df) if (df is not None and not df.empty) else None
    schema_brief = _schema_brief(schema or {}) if schema else None

    SYSTEM = (
        "You are a data analyst assistant. Generate follow-up ANALYTICAL questions the user might ask next. "
        "Each suggestion must be concise, directly actionable on the same database, and reflect the user's intent. "
        "Vary the angles: comparisons, breakdowns, trends, anomalies, data quality checks, filters, and drill-downs. "
        "Return strictly JSON with an array 'suggestions', each having 'question' and 'why'. "
        "Avoid duplicates and vague suggestions."
    )
    USER = {
        "original_question": user_question,
        "last_sql_query": (sql_query or "")[:4000],
        "result_profile": profile,
        "schema_brief": schema_brief,
        "max_suggestions": n
    }
    prompt = (
        "SYSTEM:\n" + SYSTEM + "\n\n"
        "USER JSON:\n" + json.dumps(USER, ensure_ascii=False) + "\n\n"
        "ASSISTANT: Return ONLY JSON of the form "
        '{"suggestions":[{"question":"...","why":"..."}, ...]}'
    )
    try:
        resp = llm.invoke(prompt)
        txt = resp.content if hasattr(resp, "content") else str(resp)
        start, end = txt.find("{"), txt.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return []
        data = json.loads(txt[start:end+1])
        suggestions = data.get("suggestions", [])
        seen = set()
        cleaned = []
        for s in suggestions:
            q = (s.get("question") or "").strip()
            why = (s.get("why") or "").strip()
            if not q or q.lower() in seen:
                continue
            seen.add(q.lower())
            cleaned.append({"question": q, "why": why})
            if len(cleaned) >= n:
                break
        return cleaned
    except Exception:
        # Fallback suggestions if LLM call fails
        base = (user_question or "this metric").rstrip("?")
        fallback = [
            {"question": f"{base} by key segment (top 10)?", "why": "Identify leading contributors."},
            {"question": f"How does {base} trend over time?", "why": "Reveal temporal patterns."},
            {"question": f"Are there anomalies/outliers within {base}?", "why": "Spot data issues or spikes."},
            {"question": f"Compare {base} across regions or cohorts.", "why": "See differences between groups."},
            {"question": f"Drill down into the worst-performing items for {base}.", "why": "Target improvement areas."},
        ]
        return fallback[:n]


def _chip_key(label: str, prefix: str = "") -> str:
    """Generate stable, deterministic key per suggestion label with optional prefix"""
    # Use a combination of prefix and label to ensure uniqueness
    key_string = f"{prefix}_{label}".strip()
    h = hashlib.md5(key_string.encode("utf-8")).hexdigest()[:12]
    return f"chip_{h}"

def render_suggestions(suggestions: List[Dict[str, str]], label: str = "💡 Explore further", message_id: str = None):
    """Render follow-up suggestions as clickable chips with unique keys"""
    if not suggestions:
        return

    st.markdown(f"### {label}")
    row = st.container()
    cols = row.columns(min(4, max(1, len(suggestions))))

    # Generate a unique prefix for this set of suggestions
    if not message_id:
        message_id = str(uuid.uuid4())[:8]  # Fallback to random UUID
    
    for i, s in enumerate(suggestions):
        q = (s.get("question") or "").strip()
        why = (s.get("why") or "").strip()
        if not q:
            continue

        # Use message_id as prefix to ensure uniqueness across messages
        key = _chip_key(q, message_id)

        with cols[i % len(cols)]:
            pressed = st.button(
                q,
                key=key,
                help=(why or "Ask this follow-up"),
                use_container_width=True,
            )
            if pressed:
                st.session_state.pending_query = q
                st.rerun()



def explain_sql_keywords_fallback(sql: str) -> str:
    """Fallback SQL explanation using keyword parsing"""
    if not sql:
        return "Explanation unavailable."
    text_sql = sql
    parts = {}
    clauses = ["SELECT","FROM","JOIN","LEFT JOIN","RIGHT JOIN","INNER JOIN","OUTER JOIN",
               "WHERE","GROUP BY","HAVING","ORDER BY","LIMIT"]
    pattern = r'(' + r'|'.join([re.escape(c) for c in clauses]) + r')'
    tokens = re.split(pattern, text_sql, flags=re.IGNORECASE)
    cur = None
    for t in tokens:
        if not t.strip():
            continue
        u = t.upper()
        if u in clauses:
            cur = u
            parts.setdefault(cur, "")
        else:
            if cur:
                parts[cur] += t.strip() + " "
    bullets = []
    def val(p): 
        return parts[p].strip() if p in parts else None
    if val("SELECT"):    
        bullets.append(f"- **SELECT** — columns: `{val('SELECT')}`")
    if val("FROM"):      
        bullets.append(f"- **FROM** — tables: `{val('FROM')}`")
    for j in ["JOIN","LEFT JOIN","RIGHT JOIN","INNER JOIN","OUTER JOIN"]:
        if val(j): 
            bullets.append(f"- **{j}** — with: `{val(j)}`")
    if val("WHERE"):     
        bullets.append(f"- **WHERE** — filter: `{val('WHERE')}`")
    if val("GROUP BY"):  
        bullets.append(f"- **GROUP BY** — keys: `{val('GROUP BY')}`")
    if val("HAVING"):    
        bullets.append(f"- **HAVING** — aggregated filter: `{val('HAVING')}`")
    if val("ORDER BY"):  
        bullets.append(f"- **ORDER BY** — sort: `{val('ORDER BY')}`")
    if val("LIMIT"):     
        bullets.append(f"- **LIMIT** — top rows: `{val('LIMIT')}`")
    return "\n".join(bullets) if bullets else "Explanation unavailable."

def llm_explain_sql(llm, sql: str, user_question: str, provider: str, model_name: str) -> str:
    """Explain SQL using LLM with caching"""
    if not sql:
        return "Explanation unavailable."
    key = (provider, model_name, sql.strip(), (user_question or "").strip())
    if key in st.session_state.explain_cache:
        return st.session_state.explain_cache[key]
    
    SYSTEM = (
        "You are a precise SQL expert. Explain the given SQL query to a business stakeholder.\n"
        "• 5–8 bullets\n• Markdown bullets '- '\n• Bold actual SQL keywords (e.g., **SELECT**, **FROM**, **WHERE**, **JOIN**, **GROUP BY**, **HAVING**, **ORDER BY**, **LIMIT**)\n"
        "• Tie clauses to the user's question and columns/tables used.\n• Don't restate the whole query."
    )
    USER = {"user_question": user_question, "sql_query": sql}
    prompt = "SYSTEM:\n"+SYSTEM+"\n\nUSER JSON:\n"+json.dumps(USER)+"\n\nASSISTANT:\nReturn ONLY Markdown bullets."
    
    try:
        resp = llm.invoke(prompt)
        text = resp.content if hasattr(resp, "content") else str(resp)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not any(ln.startswith("- ") for ln in lines):
            lines = [("- " + ln) for ln in lines]
        if len(lines) > 8:
            lines = lines[:8]
        explanation_md = "\n".join(lines)
        st.session_state.explain_cache[key] = explanation_md
        return explanation_md
    except Exception:
        return explain_sql_keywords_fallback(sql)
