# sql-agent-pro/utils/data_profiler.py
import pandas as pd
from typing import Dict, Any, List

def profile_dataframe(df: pd.DataFrame, max_rows_sample: int = 20) -> Dict[str, Any]:
    """Profile dataframe for chart recommendations"""
    prof = {
        "columns": [], 
        "row_count": int(len(df)), 
        "head": df.head(min(max_rows_sample, len(df))).to_dict(orient="records")
    }
    
    for c in df.columns:
        prof["columns"].append({
            "name": c,
            "dtype": str(df[c].dtype),
            "nunique": int(df[c].nunique(dropna=True)),
            "is_numeric": bool(pd.api.types.is_numeric_dtype(df[c])),
            "is_datetime": bool(pd.api.types.is_datetime64_any_dtype(df[c])),
        })
    return prof

def wants_plot_from_text(q: str) -> bool:
    """Check if user wants a plot based on text analysis"""
    if not q:
        return False
    ql = q.lower()
    from config.settings import VIZ_KEYWORDS
    return any(k in ql for k in VIZ_KEYWORDS)

def data_suitable_for_plot(df: pd.DataFrame) -> bool:
    """Check if data is suitable for plotting"""
    if df is None or df.empty:
        return False
    if df.shape == (1, 1):
        return False
    if df.shape[1] == 1 and not pd.api.types.is_numeric_dtype(df.iloc[:, 0]):
        return False
    has_num = any(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns)
    has_dt  = any(pd.api.types.is_datetime64_any_dtype(df[c]) for c in df.columns)
    if not (has_num or has_dt):
        return False
    if len(df) < 3:
        return False
    return True

def should_plot(question: str, df: pd.DataFrame) -> bool:
    """Determine if we should generate a plot"""
    if wants_plot_from_text(question):
        return data_suitable_for_plot(df)
    return data_suitable_for_plot(df)
