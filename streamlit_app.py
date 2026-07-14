"""
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
# DATABRICKS CONNECTION MANAGEMENT
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
# SQL QUERY EXECUTION CORE
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
# DATA PLATFORM METADATA SCHEMA DEFINITIONS
# =============================================================================

ERROR_LOG_TABLE = "retail_demo.monitoring.error_log"
DOC_TABLE = "retail_demo.rag.documentation_source"
VECTOR_INDEX = "retail_demo.rag.documentation_index"

# =============================================================================
# OPERATIONAL METRICS & DATA RETRIEVAL FUNCTIONS
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
# REASONING MATRIX & NLP PARSING LAYER
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
# LAYOUT STRUCTURES & MARKDOWN GENERATORS
# =============================================================================

def format_errors(df):
    if df.empty:
        return "✅ No matching errors found."
    
    response = f"## Found {len(df)} matching error(s)\n\n"
    for _, row in df.iterrows():
        response += f"### 🔴 {row['error_type']}\n"
        response += f"**ID:** `{row['error_id']}`  |  **Layer:** {row['layer']}  |  **Status:** {row['status']}\n"
        response += f"**Time:** {row['timestamp']}\n\n"
        response += "**Error Message:**\n"
        response += f"```text\n{row['error_message']}\n```\n\n"
        response += "**Recommended Solution:**\n"
        response += f"```python\n{row['solution']}\n```\n"
        response += "---\n"
    return response


def format_docs(df):
    if df.empty:
        return "📚 No documentation found."
    
    answer = ""
    for _, row in df.iterrows():
        content = row["content"]
        if len(content) > 450:
            content = content[:450] + "..."
        answer += f"## 📘 {row['title']}\n**Category:** {row['category']}\n\n{content}\n\n---\n"
    return answer

# =============================================================================
# ENGAGEMENT STRATEGY FRAMEWORK (ORCHESTRATION PIPELINE)
# =============================================================================

def generate_response(user_message: str):
    intent = detect_intent(user_message)
    keyword = extract_keywords(user_message)

    if intent == "error":
        with st.spinner("Searching error logs..."):
            df = search_errors(keyword)
            if not df.empty:
                return format_errors(df)
            
            docs = search_documentation(keyword)
            if not docs.empty:
                return "No errors found.\n\n### Related Documentation\n\n" + format_docs(docs)
            return "No matching errors or documentation found."

    elif intent == "documentation":
        with st.spinner("Searching documentation..."):
            docs = search_documentation(keyword)
            if not docs.empty:
                return format_docs(docs)
            return "No documentation found."

    else:
        with st.spinner("Searching logs and documentation..."):
            errors = search_errors(keyword, limit=3)
            docs = search_documentation(keyword, limit=3)
            answer = ""
            if not errors.empty:
                answer += format_errors(errors)
            if not docs.empty:
                answer += "\n\n" + format_docs(docs)
            
            if not answer:
                answer = """I'm your Pipeline Troubleshooting Assistant.
                
Try asking things like:
* • What failed today?
* • Show bronze errors
* • How do I use expect_or_drop?
* • Explain DLT expectations
"""
            return answer

# =============================================================================
# SIDE PANEL VIEW PORT
# =============================================================================

def render_sidebar():
    with st.sidebar:
        st.title("🤖 Pipeline Assistant")
        st.caption("Enterprise GenAI Chatbot infrastructure natively tied to Unity Catalog.")
        st.divider()

        st.subheader("Connection Status")
        if st.session_state.connection_status == "Connected":
            st.success("🟢 Connected to Databricks")
        elif st.session_state.connection_status == "Disconnected":
            st.error("🔴 Disconnected")
            error = st.session_state.get("connection_error", "")
            if error:
                st.caption(f"Error details: {error}")
        else:
            st.info("⚪ Not Tested")

        if st.button("🔌 Test Databricks Connection", use_container_width=True):
            with st.spinner("Connecting..."):
                test_connection()
            st.rerun()

        st.divider()

        if st.session_state.connection_status == "Connected":
            st.subheader("Pipeline Metrics")
            try:
                stats = get_error_statistics()
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Errors", stats["total"])
                with col2:
                    st.metric("Open Issues", stats["open"])
                
                st.write("### Layer Aggregations")
                st.write(f"指标 Bronze : {stats['bronze']}")
                st.write(f"指标 Silver : {stats['silver']}")
                st.write(f"指标 Gold : {stats['gold']}")
            except Exception:
                st.warning("Unable to dynamically calculate storage diagnostics metrics.")
            st.divider()

        st.subheader("Quick Actions")
        if st.button("📋 Today's Pipeline Errors", use_container_width=True):
            df = get_today_errors()
            response = format_errors(df)
            st.session_state.messages.append({"role": "user", "content": "What errors happened today?"})
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

        if st.button("🧹 Clear Conversation Threads", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

# =============================================================================
# CORE INTERACTIVE DIALOG WINDOW UI
# =============================================================================

def render_chat_window():
    st.title("💬 Pipeline Troubleshooting Assistant")
    
    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    if not st.session_state.messages:
        st.markdown("""## 🚀 Welcome to your Pipeline Workspace Assistant
        Ask anything regarding **DLT engines**, structural schema validation assertions, or pipeline anomalies.
        """)
        
        questions = [
            "What errors happened today?", "Show bronze layer errors",
            "Explain expect_or_drop", "Show NULL customer_id issues"
        ]
        cols = st.columns(2)
        for i, q in enumerate(questions):
            with cols[i % 2]:
                if st.button(q, key=f"start_q_index_{i}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": q})
                    answer = generate_response(q)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    st.rerun()

    prompt = st.chat_input("Ask about pipeline failures, documentation or DLT...")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(prompt)

        with chat_container:
            with st.chat_message("assistant"):
                response = generate_response(prompt)
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# =============================================================================
# APPLICATION RUNTIME ENTRY POINT
# =============================================================================

def main():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "connection_status" not in st.session_state:
        st.session_state.connection_status = "Not Tested"

    if st.session_state.connection_status == "Not Tested" and DATABRICKS_HOST:
        get_connection()
    
    render_sidebar()
    render_chat_window()

if __name__ == "__main__":
    main()
