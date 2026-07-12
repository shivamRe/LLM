"""
Pipeline Troubleshooting Assistant - Streamlit Chatbot
A production-ready chatbot for Databricks pipeline troubleshooting and documentation search.

Features:
- Real-time error log queries
- Documentation semantic search
- Code examples with syntax highlighting
- Chat history management
"""

import streamlit as st
import pandas as pd
from databricks import sql
import os
from datetime import datetime
from typing import List, Dict, Optional
import re

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Page config
st.set_page_config(
    page_title="Pipeline Troubleshooting Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .stButton button {
        width: 100%;
        border-radius: 5px;
        margin: 2px 0;
    }
    .error-box {
        background-color: #fee;
        border-left: 4px solid #f44;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .solution-box {
        background-color: #efe;
        border-left: 4px solid #4f4;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .doc-box {
        background-color: #eef;
        border-left: 4px solid #44f;
        padding: 10px;
        margin: 10px 0;
        border-radius: 5px;
    }
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATABRICKS CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_databricks_connection():
    """
    Establish connection to Databricks SQL warehouse.
    Uses environment variables for credentials.
    
    Required Environment Variables:
    - DATABRICKS_HOST: Your workspace URL (e.g., "adb-1234567890.cloud.databricks.com")
    - DATABRICKS_TOKEN: Personal access token or OAuth token
    - DATABRICKS_WAREHOUSE_ID: SQL warehouse ID (e.g., "abc123def456")
    """
    try:
        host = os.getenv("DATABRICKS_HOST")
        token = os.getenv("DATABRICKS_TOKEN")
        warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
        
        if not all([host, token, warehouse_id]):
            st.error("⚠️ Missing Databricks credentials. Please set environment variables.")
            return None
        
        connection = sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse_id}",
            access_token=token
        )
        
        return connection
    except Exception as e:
        st.error(f"❌ Failed to connect to Databricks: {str(e)}")
        return None


def execute_query(query: str) -> Optional[pd.DataFrame]:
    """
    Execute SQL query and return results as DataFrame.
    
    Args:
        query: SQL query string
        
    Returns:
        DataFrame with query results or None if error
    """
    try:
        conn = get_databricks_connection()
        if conn is None:
            return None
        
        cursor = conn.cursor()
        cursor.execute(query)
        
        # Fetch results
        columns = [desc[0] for desc in cursor.description]
        data = cursor.fetchall()
        
        cursor.close()
        
        return pd.DataFrame(data, columns=columns)
    
    except Exception as e:
        st.error(f"❌ Query failed: {str(e)}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# CORE CHATBOT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def search_errors(keywords: str, layer: Optional[str] = None, limit: int = 10) -> pd.DataFrame:
    """
    Search error_log table for matching errors.
    
    Args:
        keywords: Search terms for error messages
        layer: Filter by layer (bronze/silver/gold) or None for all
        limit: Max number of results
        
    Returns:
        DataFrame with matching errors
    """
    query = f"""
    SELECT 
        error_id,
        timestamp,
        layer,
        error_type,
        error_message,
        solution,
        status
    FROM retail_demo.monitoring.error_log
    WHERE 1=1
    """
    
    # Add keyword filter
    if keywords:
        query += f" AND (error_message LIKE '%{keywords}%' OR error_type LIKE '%{keywords}%')"
    
    # Add layer filter
    if layer:
        query += f" AND layer = '{layer}'"
    
    query += f"""
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    
    return execute_query(query)


def search_documentation(keywords: str, limit: int = 5) -> pd.DataFrame:
    """
    Search documentation_source table for relevant docs.
    
    Args:
        keywords: Search terms
        limit: Max number of results
        
    Returns:
        DataFrame with matching documentation
    """
    # For basic keyword search (replace with vector search for production)
    query = f"""
    SELECT 
        doc_id,
        title,
        content,
        category,
        tags
    FROM retail_demo.rag.documentation_source
    WHERE content LIKE '%{keywords}%' 
       OR title LIKE '%{keywords}%'
       OR tags LIKE '%{keywords}%'
    LIMIT {limit}
    """
    
    return execute_query(query)


def get_today_errors() -> pd.DataFrame:
    """
    Get all errors from today.
    
    Returns:
        DataFrame with today's errors
    """
    query = """
    SELECT 
        error_id,
        timestamp,
        layer,
        error_type,
        error_message,
        solution,
        status
    FROM retail_demo.monitoring.error_log
    WHERE DATE(timestamp) = CURRENT_DATE()
    ORDER BY timestamp DESC
    """
    
    return execute_query(query)


def get_error_stats() -> Dict:
    """
    Get error statistics summary.
    
    Returns:
        Dictionary with error counts by status and layer
    """
    query = """
    SELECT 
        status,
        layer,
        COUNT(*) as count
    FROM retail_demo.monitoring.error_log
    GROUP BY status, layer
    """
    
    df = execute_query(query)
    
    if df is None or df.empty:
        return {"total": 0, "open": 0, "by_layer": {}}
    
    total = df['count'].sum()
    open_count = df[df['status'] == 'open']['count'].sum()
    
    by_layer = {}
    for layer in ['bronze', 'silver', 'gold']:
        layer_count = df[df['layer'] == layer]['count'].sum()
        if layer_count > 0:
            by_layer[layer] = int(layer_count)
    
    return {
        "total": int(total),
        "open": int(open_count),
        "by_layer": by_layer
    }


def detect_intent(message: str) -> str:
    """
    Detect user intent from message.
    
    Args:
        message: User message
        
    Returns:
        Intent type: 'errors', 'documentation', 'general'
    """
    message_lower = message.lower()
    
    # Error-related keywords
    error_keywords = ['error', 'fail', 'issue', 'problem', 'bug', 'broken', 'wrong', 'today', 'happened']
    if any(keyword in message_lower for keyword in error_keywords):
        return 'errors'
    
    # Documentation keywords
    doc_keywords = ['how', 'what', 'explain', 'documentation', 'example', 'show me', 'difference', 'best practice']
    if any(keyword in message_lower for keyword in doc_keywords):
        return 'documentation'
    
    return 'general'


def extract_keywords(message: str) -> List[str]:
    """
    Extract important keywords from message.
    
    Args:
        message: User message
        
    Returns:
        List of keywords
    """
    # Remove common stop words
    stop_words = ['the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 
                  'my', 'me', 'i', 'can', 'do', 'does', 'in', 'on', 'at', 'to', 'for']
    
    # Extract words
    words = re.findall(r'\b\w+\b', message.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    return keywords[:5]  # Return top 5 keywords


def format_error_response(errors_df: pd.DataFrame) -> str:
    """
    Format error DataFrame into readable response.
    
    Args:
        errors_df: DataFrame with error data
        
    Returns:
        Formatted markdown string
    """
    if errors_df is None or errors_df.empty:
        return "✅ No errors found matching your criteria."
    
    response = f"📊 **Found {len(errors_df)} error(s):**\n\n"
    
    for idx, row in errors_df.iterrows():
        response += f"### 🔴 Error {idx + 1}: `{row['error_id']}`\n\n"
        response += f"**⏰ Time:** {row['timestamp']}\n\n"
        response += f"**📍 Layer:** {row['layer']}\n\n"
        response += f"**🏷️ Type:** `{row['error_type']}`\n\n"
        
        response += f"**❌ Problem:**\n```\n{row['error_message']}\n```\n\n"
        
        response += f"**✅ Solution:**\n```python\n{row['solution']}\n```\n\n"
        
        response += f"**Status:** {'🟢 Resolved' if row['status'] == 'resolved' else '🔴 Open'}\n\n"
        response += "---\n\n"
    
    return response


def format_doc_response(docs_df: pd.DataFrame) -> str:
    """
    Format documentation DataFrame into readable response.
    
    Args:
        docs_df: DataFrame with documentation data
        
    Returns:
        Formatted markdown string
    """
    if docs_df is None or docs_df.empty:
        return "📚 No documentation found matching your query."
    
    response = f"📚 **Found {len(docs_df)} documentation entry(ies):**\n\n"
    
    for idx, row in docs_df.iterrows():
        response += f"### 📄 {row['title']}\n\n"
        response += f"**Category:** {row.get('category', 'General')}\n\n"
        
        # Truncate long content
        content = row['content']
        if len(content) > 500:
            content = content[:500] + "..."
        
        response += f"{content}\n\n"
        
        if 'tags' in row and row['tags']:
            response += f"**Tags:** {row['tags']}\n\n"
        
        response += "---\n\n"
    
    return response


def generate_response(user_message: str) -> str:
    """
    Main chatbot logic - analyzes user message and generates response.
    
    Args:
        user_message: User's input message
        
    Returns:
        Bot's response string
    """
    # Detect intent
    intent = detect_intent(user_message)
    keywords = extract_keywords(user_message)
    keywords_str = " ".join(keywords)
    
    response = ""
    
    # Handle based on intent
    if intent == 'errors':
        # Search for errors
        with st.spinner("🔍 Searching error logs..."):
            errors_df = search_errors(keywords_str, limit=5)
            response = format_error_response(errors_df)
            
            # Add documentation if no errors found
            if errors_df is None or errors_df.empty:
                docs_df = search_documentation(keywords_str, limit=3)
                response += "\n\n💡 **Related Documentation:**\n\n"
                response += format_doc_response(docs_df)
    
    elif intent == 'documentation':
        # Search documentation
        with st.spinner("📚 Searching documentation..."):
            docs_df = search_documentation(keywords_str, limit=5)
            response = format_doc_response(docs_df)
            
            # Check if there are related errors with solutions
            errors_df = search_errors(keywords_str, limit=2)
            if errors_df is not None and not errors_df.empty:
                response += "\n\n🔍 **Related Errors & Solutions:**\n\n"
                response += format_error_response(errors_df)
    
    else:
        # General query - search both
        with st.spinner("🤔 Thinking..."):
            errors_df = search_errors(keywords_str, limit=3)
            docs_df = search_documentation(keywords_str, limit=3)
            
            if (errors_df is not None and not errors_df.empty) or (docs_df is not None and not docs_df.empty):
                response = "🔍 **Here's what I found:**\n\n"
                
                if errors_df is not None and not errors_df.empty:
                    response += "**Recent Errors:**\n\n"
                    response += format_error_response(errors_df)
                
                if docs_df is not None and not docs_df.empty:
                    response += "**Documentation:**\n\n"
                    response += format_doc_response(docs_df)
            else:
                response = """
I'm here to help with pipeline troubleshooting! You can ask me:

**Error Queries:**
- "What errors happened today?"
- "Show me silver layer errors"
- "Find errors with NULL customer_id"

**Documentation Queries:**
- "How do I use expect_or_drop?"
- "What's the difference between expect_or_fail and expect_or_drop?"
- "Show me examples of data quality checks"

Try clicking one of the starter questions below! 👇
"""
    
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# STREAMLIT UI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Main application function."""
    
    # Initialize session state for chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "connection_status" not in st.session_state:
        conn = get_databricks_connection()
        st.session_state.connection_status = "connected" if conn else "disconnected"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SIDEBAR
    # ═══════════════════════════════════════════════════════════════════════════
    
    with st.sidebar:
        st.title("🤖 Pipeline Troubleshooting Assistant")
        
        # Connection status
        if st.session_state.connection_status == "connected":
            st.success("✅ Connected to Databricks")
        else:
            st.error("❌ Not connected to Databricks")
            st.info("Set environment variables: DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID")
        
        st.divider()
        
        # Error statistics
        if st.session_state.connection_status == "connected":
            st.subheader("📊 Error Statistics")
            
            try:
                stats = get_error_stats()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total Errors", stats['total'])
                
                with col2:
                    st.metric("Open Errors", stats['open'])
                
                if stats['by_layer']:
                    st.write("**By Layer:**")
                    for layer, count in stats['by_layer'].items():
                        st.write(f"- {layer.title()}: {count}")
            
            except Exception as e:
                st.warning("Could not load statistics")
        
        st.divider()
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        
        if st.button("📋 Show Recent Errors"):
            errors_df = get_today_errors()
            response = format_error_response(errors_df)
            st.session_state.messages.append({"role": "user", "content": "Show me today's errors"})
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()
        
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        
        st.divider()
        
        # About
        with st.expander("ℹ️ About"):
            st.markdown("""
            **Pipeline Troubleshooting Assistant**
            
            This chatbot helps you:
            - 🔍 Search pipeline error logs
            - 📚 Find relevant documentation
            - 💡 Get solutions for common issues
            - 📊 Track error trends
            
            **Data Sources:**
            - `retail_demo.monitoring.error_log`
            - `retail_demo.rag.documentation_source`
            - `retail_demo.rag.documentation_index`
            """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN CHAT AREA
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.title("💬 Pipeline Troubleshooting Chat")
    
    # Show starter questions if no messages
    if len(st.session_state.messages) == 0:
        st.markdown("### 👋 Welcome! Try these questions:")
        
        starter_questions = [
            "What errors happened in the pipeline today?",
            "How do I fix NULL customer_id errors?",
            "Show me all documentation about expect_or_drop",
            "What's the difference between expect_or_fail and expect_or_drop?",
            "Show me common data quality issues",
            "How do I handle invalid date formats in DLT?"
        ]
        
        cols = st.columns(2)
        for idx, question in enumerate(starter_questions):
            with cols[idx % 2]:
                if st.button(question, key=f"starter_{idx}"):
                    # Add user message
                    st.session_state.messages.append({"role": "user", "content": question})
                    
                    # Generate response
                    response = generate_response(question)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    st.rerun()
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask me about pipeline errors or documentation..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = generate_response(prompt)
                st.markdown(response)
        
        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})


# ═══════════════════════════════════════════════════════════════════════════════
# RUN APP
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    main()
