===============================================================================
Pipeline Troubleshooting Assistant
Enterprise GenAI Chatbot using Streamlit + Databricks SQL
Author: Shivam
===============================================================================
"""

import os
import re
from typing import Optional

import pandas as pd
import streamlit as st
from databricks import sql

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Pipeline Troubleshooting Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown(
    """
<style>
.main{
    padding-top:1rem;
}
.stChatMessage{
    border-radius:12px;
    padding:12px;
}
.stButton>button{
    width:100%;
    border-radius:8px;
}
.metric-card{
    padding:10px;
    border-radius:10px;
    background:#F8F9FA;
}
.success-box{
    padding:12px;
    border-left:5px solid green;
    background:#F2FFF2;
    border-radius:6px;
}
.error-box{
    padding:12px;
    border-left:5px solid red;
    background:#FFF3F3;
    border-radius:6px;
}
.info-box{
    padding:12px;
    border-left:5px solid blue;
    background:#F4F8FF;
    border-radius:6px;
}
code{
    color:#FF4B4B;
}
</style>
""",
    unsafe_allow_html=True,
)

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")

# =============================================================================
# SESSION STATE INITIALIZATION
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "connection_status" not in st.session_state:
    st.session_state.connection_status = "Not Tested"

# =============================================================================
# DATABRICKS CONNECTION
# =============================================================================

@st.cache_resource(show_spinner=False)
def get_connection():
    """
    Creates a cached Databricks SQL connection using environment variables.
    """
    if not DATABRICKS_HOST or not DATABRICKS_TOKEN or not DATABRICKS_WAREHOUSE_ID:
        return None

    try:
        conn = sql.connect(
            server_hostname=DATABRICKS_HOST,
            http_path=f"/sql/1.0/warehouses/{DATABRICKS_WAREHOUSE_ID}",
            access_token=DATABRICKS_TOKEN,
        )
        return conn
    except Exception as e:
        st.session_state.connection_error = str(e)
        return None


def test_connection():
    try:
        get_connection.clear() 
        conn = get_connection()
        if conn is None:
            raise Exception("Missing or invalid environment configurations.")

        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchall()

        st.session_state.connection_status = "Connected"
        st.session_state.connection_error = None
        return True
    except Exception as e:
        st.session_state.connection_status = "Disconnected"
        st.session_state.connection_error = str(e)
        return False


# =============================================================================
# SQL EXECUTION
# =============================================================================

@st.cache_data(ttl=30, show_spinner=False)
def execute_query(query: str):
    try:
        conn = get_connection()
        if not conn:
            st.error("Database connection is not available. Please verify configurations.")
            return pd.DataFrame()

        with conn.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            columns = [c[0] for c in cursor.description]
            return pd.DataFrame(rows, columns=columns)
    except Exception as e:
        st.error(f"Query Execution Error: {e}")
        return pd.DataFrame()


def sanitize(text: str):
    if text is None:
        return ""
    return text.replace("'", "''")


# =============================================================================
# TABLE CONFIGURATIONS
# =============================================================================

ERROR_LOG_TABLE = "retail_demo.monitoring.error_log"
DOC_TABLE = "retail_demo.rag.documentation_source"
VECTOR_INDEX = "retail_demo.rag.documentation_index"


# =============================================================================
# DATA SEARCH BACKEND FUNCTIONS
# =============================================================================

@st.cache_data(ttl=30, show_spinner=False)
def search_errors(keyword: str = "", layer: Optional[str] = None, limit: int = 5):
    keyword = sanitize(keyword)
    query = f"""
    SELECT error_id, timestamp, layer, error_type, error_message, solution, status
    FROM {ERROR_LOG_TABLE}
    WHERE 1=1
    """
    if keyword:
        query += f"""
        AND (
            LOWER(error_message) LIKE LOWER('%{keyword}%')
            OR LOWER(error_type) LIKE LOWER('%{keyword}%')
        )
        """
    if layer:
        query += f" AND LOWER(layer)=LOWER('{sanitize(layer)}')"

    query += f" ORDER BY timestamp DESC LIMIT {limit}"
    return execute_query(query)


@st.cache_data(ttl=60, show_spinner=False)
def search_documentation(keyword: str, limit: int = 5):
    keyword = sanitize(keyword)
    query = f"""
    SELECT doc_id, title, content, category, tags
    FROM {DOC_TABLE}
    WHERE LOWER(title) LIKE LOWER('%{keyword}%')
        OR LOWER(content) LIKE LOWER('%{keyword}%')
        OR LOWER(tags) LIKE LOWER('%{keyword}%')
    LIMIT {limit}
    """
    return execute_query(query)


def get_today_errors():
    query = f"""
    SELECT error_id, timestamp, layer, error_type, error_message, solution, status
    FROM {ERROR_LOG_TABLE}
    WHERE DATE(timestamp)=CURRENT_DATE()
    ORDER BY timestamp DESC
    """
    return execute_query(query)


def get_error_statistics():
    query = f"""
    SELECT layer, status, COUNT(*) cnt
    FROM {ERROR_LOG_TABLE}
    GROUP BY layer, status
    """
    df = execute_query(query)
    stats = {"total": 0, "open": 0, "resolved": 0, "bronze": 0, "silver": 0, "gold": 0}
    
    if df.empty:
        return stats

    stats["total"] = int(df["cnt"].sum())
    
    if "open" in df["status"].values:
        stats["open"] = int(df[df.status == "open"]["cnt"].sum())
    if "resolved" in df["status"].values:
        stats["resolved"] = int(df[df.status == "resolved"]["cnt"].sum())

    for layer in ["bronze", "silver", "gold"]:
        if layer in df["layer"].values:
            stats[layer] = int(df[df.layer == layer]["cnt"].sum())

    return stats


# =============================================================================
# INTENT ENGINE & NLP HELPERS
# =============================================================================

def detect_intent(message: str):
    msg = message.lower()
    error_words = ["error", "failed", "failure", "issue", "problem", "pipeline", "job", "today", "exception"]
    documentation_words = ["how", "documentation", "example", "explain", "difference", "what is", "guide", "syntax", "best practice"]

    if any(word in msg for word in error_words):
        return "error"
    if any(word in msg for word in documentation_words):
        return "documentation"
    return "general"


STOPWORDS = {
    "the", "a", "an", "to", "for", "is", "are", "what", "how", "why", "show", "me",
    "my", "today", "please", "about", "of", "in", "on", "at", "with", "can", "do"
}

def extract_keywords(message: str):
    words = re.findall(r"\w+", message.lower())
    words = [w for w in words if len(w) > 2 and w not in STOPWORDS]
    return " ".join(words[:5])


# =============================================================================
# FORMATTING UTILITIES
# =============================================================================

def format_errors(df):
    if df.empty:
        return "✅ No matching errors found."
    
    response = f"## Found {len(df)} matching error(s)\n\n"
    for _, row in df.iterrows():
        response += f"""### 🔴 {row['error_type']}
**ID:** `{row['error_id']}`  |  **Layer:** {row['layer']}  |  **Status:** {row['status']}
**Time:** {row['timestamp']}

**Error Message:**
```text
{row['error_message']}
