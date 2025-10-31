# sql-agent-pro/config/settings.py
import os
from typing import Dict, Any

# Default models for each provider
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-latest", 
    "google_genai": "gemini-2.5-flash",
    "groq": "llama-3.3-70b-versatile",
}

# Chart types and their requirements
CHART_TYPES = {
    "line": {"required": ["x","y"]},
    "area": {"required": ["x","y"]},
    "bar": {"required": ["x","y"]},
    "stacked_bar": {"required": ["x","y","color"]},
    "histogram": {"required": ["x"]},
    "box": {"required": ["x","y"]},
    "violin": {"required": ["x","y"]},
    "scatter": {"required": ["x","y"]},
    "scatter_trend": {"required": ["x","y"]},
    "pie": {"required": ["names","values"]},
    "donut": {"required": ["names","values"]},
    "corr_heatmap": {"required": []},
    "treemap": {"required": ["path","values"]},
    "pareto": {"required": ["x","y"]},
    "map_geo": {"required": ["lat","lon"]},
    "choropleth": {"required": ["locations","color","locationmode"]},
}

# Visualization keywords
VIZ_KEYWORDS = (
    "chart", "plot", "visual", "visualise", "visualize", "graph", "trend",
    "over time", "time series", "timeseries", "distribution", "histogram", 
    "scatter", "correlation", "heatmap", "compare", "breakdown", "by ",
    "top ", "vs ", "across", "line chart", "bar chart", "pie chart", "box plot", "violin"
)

# SQL clause regex
SQL_CLAUSE_REGEX = r'\b(SELECT|FROM|WHERE|GROUP BY|HAVING|ORDER BY|LIMIT|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|OUTER JOIN)\b'

# Feature flags
RENDER_WORKSPACE_SUMMARY = False
