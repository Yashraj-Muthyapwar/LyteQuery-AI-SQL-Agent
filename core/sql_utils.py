# sql-agent-pro/core/sql_utils.py
import re
import ast
import json
from typing import Optional

try:
    import sqlparse
except Exception:
    sqlparse = None

from config.settings import SQL_CLAUSE_REGEX

def _unescape_sql_string(s: str) -> str:
    """Unescape SQL string containing escape sequences"""
    try:
        if "\\n" in s or "\\t" in s:
            return s.encode("utf-8").decode("unicode_escape")
    except Exception:
        pass
    return s

def normalize_tool_sql(payload) -> Optional[str]:
    """Normalize SQL payload from various formats to a clean SQL string"""
    if payload is None:
        return None
    if isinstance(payload, str):
        s = payload.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                obj = ast.literal_eval(s)
                return normalize_tool_sql(obj)
            except Exception:
                pass
            try:
                obj = json.loads(s)
                return normalize_tool_sql(obj)
            except Exception:
                return _unescape_sql_string(s)
        return _unescape_sql_string(s)
    if isinstance(payload, dict):
        for k in ("query", "sql", "statement"):
            v = payload.get(k)
            if isinstance(v, str) and v.strip():
                return _unescape_sql_string(v.strip())
        if isinstance(payload.get("queries"), (list, tuple)) and payload["queries"]:
            return _unescape_sql_string(str(payload["queries"][0]).strip())
        for v in payload.values():
            s = normalize_tool_sql(v)
            if s:
                return s
        return None
    if isinstance(payload, (list, tuple)) and payload:
        return normalize_tool_sql(payload[0])
    return None

def prettify_sql(sql: str) -> str:
    """Prettify SQL query with proper formatting"""
    if not sql:
        return ""
    s = sql.strip()
    if not s.endswith(";"):
        s += ";"
    if sqlparse:
        try:
            return sqlparse.format(s, keyword_case="upper", reindent=True, strip_comments=False)
        except Exception:
            pass
    def up(m): 
        return m.group(0).upper()
    s = re.compile(SQL_CLAUSE_REGEX, re.IGNORECASE).sub(up, s)
    s = re.sub(r'\s+(FROM|WHERE|GROUP BY|HAVING|ORDER BY|LIMIT|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN)\b',
               r'\n\1', s)
    s = re.sub(r'[ \t]+', ' ', s).strip()
    return s
