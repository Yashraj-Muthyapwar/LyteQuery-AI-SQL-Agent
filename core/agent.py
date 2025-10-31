# sql-agent-pro/core/agent.py
from langchain_core.callbacks.base import BaseCallbackHandler

class SQLCaptureHandler(BaseCallbackHandler):
    """Callback handler to capture SQL queries from the agent"""
    def __init__(self):
        self.sql_calls = []
        
    def on_tool_start(self, serialized, input_str, **kwargs):
        name = (serialized or {}).get("name", "")
        if name in {"sql_db_query", "sql_db_query_checker"}:
            self.sql_calls.append(input_str)


def get_agent_hint():
    """Get the agent hint for better SQL generation and context awareness"""
    return (
        "**RULE 1: ALWAYS INFER JOINS**\n"
        "When a user's query requires information from multiple tables, you MUST perform the necessary JOINs based on the database schema. "
        "Queries asking for analysis 'by' a text category (like 'by state', 'by city', 'by department name', or 'by category') "
        "almost always require joining an ID-based table (like 'flights', 'transactions') with a descriptive table (like 'airports', 'stores', 'departments').\n\n"
        
        "**RULE 2: ALWAYS ALIAS AGGREGATES**\n"
        "You MUST alias aggregated columns (like COUNT, SUM, AVG) with descriptive, snake_case names "
        "(e.g., 'total_flights', 'avg_delay', 'total_sales'). Do not use 'COUNT(*)' as a column name. "
        "This is critical for the downstream visualization engine.\n\n"
        
        "**RULE 3: CONTEXT AWARENESS**\n"
        "You have conversation memory. When the user says:\n"
        "- 'Show that as a pie chart' → They mean the data from their PREVIOUS query. DO NOT generate new SQL.\n"
        "- 'What about California?' → Filter or refine the PREVIOUS results.\n"
        "- 'Show me the top 5' → Modify the PREVIOUS query with LIMIT.\n"
        "- 'Previous result' or 'that data' → Reference the last query's data.\n"
        "Only generate NEW SQL when the user asks a completely different question about different data.\n\n"
        
        "**RULE 4: VISUALIZATION REQUESTS**\n"
        "When user requests a chart type (pie chart, bar chart, line graph) for 'previous results' or 'that data':\n"
        "- Acknowledge you'll create the visualization\n"
        "- DO NOT query the database again\n"
        "- Say something like: 'I'll create a [chart type] from the airport distribution data'\n"
        "- The visualization engine will handle creating the chart from existing data"
    )
