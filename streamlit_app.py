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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

# Minimal, clean CSS - NO white boxes
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Sidebar dark theme */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e1e2e 0%, #2d2d44 100%);
    }
    
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #fff !important;
    }
    
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div {
        color: #b0b0b0 !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stMetricValue"] {
        color: #fff !important;
        font-size: 1.8rem !important;
    }
    
    /* Chat messages styling */
    [data-testid="stChatMessage"] {
        border-radius: 12px;
        padding: 12px 16px;
        margin: 8px 0;
    }
    
    /* User messages - purple gradient */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    }
    
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) p,
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) div {
        color: white !important;
    }
    
    /* Assistant messages - light background */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: #f8f9fa !important;
    }
    
    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
        width: 100%;
    }
    
    .stButton button:hover {
        opacity: 0.9;
    }
    
    /* Starter question buttons */
    div[data-testid="column"] .stButton button {
        background: white;
        color: #667eea;
        border: 2px solid #667eea;
    }
    
    div[data-testid="column"] .stButton button:hover {
        background: #667eea;
        color: white;
    }
    
    /* Code blocks */
    pre {
        background: #1e1e2e !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    
    pre code {
        color: #a6e3a1 !important;
    }
    
    code {
        background: #f3f4f6 !important;
        color: #667eea !important;
        padding: 2px 6px;
        border-radius: 4px;
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
    
    # Add keyword filter - search for each keyword separately
    if keywords:
        keyword_list = keywords.split()
        keyword_conditions = []
        for kw in keyword_list:
            keyword_conditions.append(f"(error_message LIKE '%{kw}%' OR error_type LIKE '%{kw}%')")
        if keyword_conditions:
            query += " AND (" + " OR ".join(keyword_conditions) + ")"
    
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
    # For basic keyword search - search for each keyword separately
    keyword_list = keywords.split()
    keyword_conditions = []
    for kw in keyword_list:
        keyword_conditions.append(f"(text LIKE '%{kw}%' OR category LIKE '%{kw}%')")
    
    where_clause = " OR ".join(keyword_conditions) if keyword_conditions else "1=1"
    
    query = f"""
    SELECT 
        id,
        category,
        text,
        source_doc
    FROM retail_demo.rag.documentation_source
    WHERE {where_clause}
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
    Detect user intent from message with better accuracy.
    
    Args:
        message: User message
        
    Returns:
        Intent type: 'errors', 'documentation', 'general'
    """
    message_lower = message.lower()
    
    # Strong error indicators - these always mean error intent
    strong_error_keywords = ['error', 'fail', 'issue', 'problem', 'bug', 'broken', 'wrong']
    if any(keyword in message_lower for keyword in strong_error_keywords):
        return 'errors'
    
    # If asking "what happened" or "what...today" - it's about errors
    if 'happened' in message_lower or ('today' in message_lower and 'what' in message_lower):
        return 'errors'
    
    # Strong documentation indicators - asking HOW to do something
    doc_patterns = ['how to', 'how do', 'how can', 'explain ', 'what is ', 'what does', 
                    'difference between', 'best practice', 'show me example']
    if any(pattern in message_lower for pattern in doc_patterns):
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
                  'my', 'me', 'i', 'can', 'do', 'does', 'in', 'on', 'at', 'to', 'for',
                  'today', 'happened', 'show', 'tell']
    
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
        response += f"### 🔴 Error: `{row['error_id']}`\n\n"
        response += f"**⏰ Time:** {row['timestamp']}\n\n"
        response += f"**📍 Layer:** {row['layer']}\n\n"
        response += f"**🏷️ Type:** `{row['error_type']}`\n\n"
        
        response += f"**❌ Problem:**\n```\n{row['error_message']}\n```\n\n"
        
        response += f"**✅ Solution:**\n```python\n{row['solution']}\n```\n\n"
        response += f"**Status:** {'🟢 Resolved' if row['status'] == 'resolved' else '🔴 Open'}\n\n"
        response += "---\n\n"
    
    return response


def format_doc_response(docs_df: pd.DataFrame, conversational: bool = True) -> str:
    """
    Format documentation DataFrame into readable response.
    
    Args:
        docs_df: DataFrame with documentation data
        conversational: If True, natural format. If False, structured format.
        
    Returns:
        Formatted markdown string
    """
    if docs_df is None or docs_df.empty:
        return "I couldn't find documentation about that topic."
    
    if conversational:
        # Natural conversational format - NO "Doc 1", "Doc 2", "Category:" labels
        response = ""
        
        for idx, row in docs_df.iterrows():
            content = row['text']
            # Truncate very long content intelligently - DON'T show incomplete sentences
            if len(content) > 400:
                # Find a good breaking point (end of sentence)
                truncate_at = content[:400].rfind('.')
                if truncate_at > 200:
                    content = content[:truncate_at + 1]
                else:
                    # If no sentence end found, just cut at 400 and add ellipsis
                    content = content[:400] + "..."
            
            response += f"{content}\n\n"
        
        return response.strip()
    else:
        # Structured format (only used for detailed documentation queries)
        response = f"📚 **Found {len(docs_df)} documentation entry(ies):**\n\n"
        
        for idx, row in docs_df.iterrows():
            response += f"### 📄 Doc {idx + 1}\n\n"
            response += f"**Category:** {row.get('category', 'General')}\n\n"
            
            content = row['text']
            if len(content) > 500:
                content = content[:500] + "..."
            
            response += f"{content}\n\n"
            
            if 'source_doc' in row and row['source_doc']:
                response += f"**Source:** {row['source_doc']}\n\n"
            
            response += "---\n\n"
        
        return response


def generate_response(user_message: str) -> str:
    """
    Main chatbot logic - smarter and more conversational.
    
    Args:
        user_message: User's input message
        
    Returns:
        Bot's response string
    """
    intent = detect_intent(user_message)
    keywords = extract_keywords(user_message)
    keywords_str = " ".join(keywords)
    
    response = ""
    message_lower = user_message.lower()
    
    # Handle based on intent
    if intent == 'errors':
        # User is asking about errors - DON'T show documentation unless explicitly requested
        with st.spinner("🔍 Searching error logs..."):
            errors_df = search_errors(keywords_str, limit=5)
            
            if errors_df is None or errors_df.empty:
                # No errors found - give helpful, contextual response WITHOUT documentation
                if "today" in message_lower:
                    response = "✅ **Great news!** No errors were logged today. Your pipeline is running smoothly! 🎉"
                elif keywords_str:
                    response = f"✅ No errors found matching '**{keywords_str}**'. Your pipeline appears to be healthy for this query."
                else:
                    response = "✅ No recent errors found. Everything looks good!"
            else:
                # Found errors - show them
                response = format_error_response(errors_df)
    
    elif intent == 'documentation':
        # User explicitly wants documentation/how-to
        with st.spinner("📚 Searching documentation..."):
            docs_df = search_documentation(keywords_str, limit=3)
            
            if docs_df is None or docs_df.empty:
                response = f"I couldn't find documentation about '**{keywords_str}**'. \n\nTry asking about:\n- Data quality checks (expect_or_drop, expect_or_fail)\n- Pipeline architecture (bronze, silver, gold layers)\n- Common troubleshooting scenarios"
            else:
                # Show documentation in natural conversational format
                response = format_doc_response(docs_df, conversational=True)
            
            # Only show errors if user mentioned problems
            if any(word in message_lower for word in ['error', 'issue', 'problem', 'fail']):
                errors_df = search_errors(keywords_str, limit=2)
                if errors_df is not None and not errors_df.empty:
                    response += "\n\n**💡 Related Errors & Solutions:**\n\n"
                    response += format_error_response(errors_df)
    
    else:
        # General query - search both but be smart about it
        with st.spinner("🤔 Thinking..."):
            errors_df = search_errors(keywords_str, limit=3)
            docs_df = search_documentation(keywords_str, limit=3)
            
            has_errors = errors_df is not None and not errors_df.empty
            has_docs = docs_df is not None and not docs_df.empty
            
            if has_errors or has_docs:
                response = ""
                
                if has_errors:
                    response += format_error_response(errors_df)
                
                if has_docs:
                    if has_errors:
                        response += "\n\n**📚 Related Documentation:**\n\n"
                    response += format_doc_response(docs_df, conversational=True)
            else:
                response = """
👋 I'm here to help with pipeline troubleshooting! 

**I can help you:**
- 🔍 Find and diagnose pipeline errors
- 📚 Explain data quality concepts
- 💡 Provide solutions for common issues
- 📊 Show error trends and statistics

**Try asking:**
- "What errors happened today?"
- "Show me NULL customer_id issues"
- "How do I handle invalid dates?"
- "Explain expect_or_drop"

Feel free to ask any question about your pipeline!
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
        st.title("🤖 Pipeline Assistant")
        
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
                        st.write(f"🔹 {layer.title()}: {count}")
            
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
            """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN CHAT AREA
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.title("💬 Pipeline Troubleshooting Chat")
    
    # Show starter questions if no messages
    if len(st.session_state.messages) == 0:
        st.info("👋 Welcome! Click any question below to get started:")
        
        starter_questions = [
            "What errors happened today?",
            "Show NULL customer_id issues",
            "Explain expect_or_drop",
            "Show me bronze layer errors",
            "Common data quality issues",
            "How to handle invalid dates?"
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
