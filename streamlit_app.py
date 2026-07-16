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
# SYNONYM MAPPING - CENTRALIZED
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_vector_search_client():
    return VectorSearchClient(disable_notice=True)

@st.cache_resource
def get_foundation_model_client():
    return OpenAI(
        api_key=os.getenv("DATABRICKS_TOKEN"),
        base_url=f"https://{os.getenv(\'DATABRICKS_HOST\')}/serving-endpoints"
    )

def semantic_search_documentation(query: str, limit: int = 5) -> pd.DataFrame:
    """
    Semantic search using Vector Search - replaces manual synonym mapping!
    """
    try:
        vsc = get_vector_search_client()
        
        index = vsc.get_index(
            endpoint_name=os.getenv("VECTOR_SEARCH_ENDPOINT", "pipeline_chatbot_endpoint"),
            index_name=os.getenv("VECTOR_INDEX_NAME", "retail_demo.rag.documentation_vector_index")
        )
        
        results = index.similarity_search(
            query_text=query,
            columns=["id", "category", "source_doc", "text"],
            num_results=limit
        )
        
        # Convert to DataFrame
        if results and \'result\' in results and \'data_array\' in results[\'result\']:
            docs = results[\'result\'][\'data_array\']
            return pd.DataFrame(docs, columns=[\'id\', \'category\', \'source_doc\', \'text\'])
        else:
            return pd.DataFrame()
    
    except Exception as e:
        st.error(f"⚠️ Semantic search failed: {str(e)}")
        return pd.DataFrame()

def generate_intelligent_response(user_query: str, context: str) -> str:
    """
    Generate AI-powered response using Foundation Model.
    """
    try:
        client = get_foundation_model_client()
        
        system_prompt = """You are a data pipeline troubleshooting expert.
Provide actionable solutions with code examples. Be concise but thorough."""
        
        user_prompt = f"""Question: {user_query}\n\nContext:\n{context}\n\nProvide a helpful response."""
        
        response = client.chat.completions.create(
            model="databricks-dbrx-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=500,
            temperature=0.1
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"Error: {str(e)}"


# ═══════════════════════════════════════════════════════════════════════════════
# CORE CHATBOT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def search_errors(keywords: str, layer: Optional[str] = None, limit: int = 10) -> pd.DataFrame:
    """
    Search error_log table for matching errors with smart synonym expansion.
    
    Args:
        keywords: Search terms for error messages
        layer: Filter by layer (bronze/silver/gold) or None for all
        limit: Max number of results
        
    Returns:
        DataFrame with matching errors
    """
    # Expand keywords using error synonyms
    expanded_keywords = expand_keywords_with_synonyms(keywords, get_error_synonyms())
    
    # Build query with expanded keywords
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
    
    # Add keyword filter - search for each expanded keyword
    if expanded_keywords:
        keyword_conditions = []
        for kw in expanded_keywords:
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


def get_common_errors(limit: int = 10) -> pd.DataFrame:
    """
    Get most common errors by grouping similar error types.
    
    Args:
        limit: Max number of error types to return
        
    Returns:
        DataFrame with common errors and their counts
    """
    query = f"""
    SELECT 
        error_type,
        COUNT(*) as occurrence_count,
        MAX(timestamp) as last_occurred,
        MAX(error_message) as example_message,
        MAX(solution) as solution,
        layer
    FROM retail_demo.monitoring.error_log
    GROUP BY error_type, layer
    ORDER BY occurrence_count DESC
    LIMIT {limit}
    """
    
    return execute_query(query)


def search_documentation(keywords: str, limit: int = 5) -> pd.DataFrame:
    """
    Search documentation_source table for relevant docs with smart synonym expansion.
    
    Args:
        keywords: Search terms
        limit: Max number of results
        
    Returns:
        DataFrame with matching documentation
    """
    # Expand keywords using documentation synonyms
    expanded_keywords = expand_keywords_with_synonyms(keywords, get_documentation_synonyms())
    
    # Build query with expanded keywords
    query = f"""
    SELECT 
        id,
        category,
        text,
        source_doc
    FROM retail_demo.rag.documentation_source
    WHERE 1=1
    """
    
    # Add keyword filter
    if expanded_keywords:
        keyword_conditions = []
        for kw in expanded_keywords:
            keyword_conditions.append(f"(text LIKE '%{kw}%' OR category LIKE '%{kw}%')")
        if keyword_conditions:
            query += " AND (" + " OR ".join(keyword_conditions) + ")"
    else:
        # Fallback: no filter
        query += " AND 1=1"
    
    query += f"""
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
        Intent type: 'pipeline_overview', 'dlt_expectations', 'common_errors', 'specific_error', 'documentation', 'general'
    """
    message_lower = message.lower()
    
    # Pipeline overview questions
    pipeline_keywords = ['explain pipeline', 'what is this pipeline', 'what is the pipeline', 
                        'pipeline overview', 'pipeline architecture', 'pipeline structure',
                        'pipeline flow', 'how does pipeline work', 'pipeline layers']
    if any(keyword in message_lower for keyword in pipeline_keywords):
        return 'pipeline_overview'
    
    # DLT/Expectations questions
    dlt_keywords = ['dlt', 'expectation', 'expect_or_drop', 'expect_or_fail', 
                    'data quality', 'quality check', 'validation']
    if any(keyword in message_lower for keyword in dlt_keywords):
        return 'dlt_expectations'
    
    # Common errors questions
    common_error_keywords = ['common error', 'common issue', 'common problem', 
                            'frequent error', 'most common', 'typical error']
    if any(keyword in message_lower for keyword in common_error_keywords):
        return 'common_errors'
    
    # Specific error search
    error_keywords = ['error', 'fail', 'issue', 'problem', 'bug', 'broken', 'wrong']
    if any(keyword in message_lower for keyword in error_keywords):
        return 'specific_error'
    
    # If asking "what happened" or "what...today" - it's about errors
    if 'happened' in message_lower or ('today' in message_lower and 'what' in message_lower):
        return 'specific_error'
    
    # Documentation/how-to questions
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
                  'today', 'happened', 'show', 'tell', 'this', 'that', 'these', 'those']
    
    # Extract words
    words = re.findall(r'\b\w+\b', message.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    return keywords[:5]  # Return top 5 keywords


def extract_summary_from_doc(text: str, max_length: int = 300) -> str:
    """
    Extract a clean summary from documentation text.
    Looks for the "Purpose" section or first few sentences.
    
    Args:
        text: Full documentation text
        max_length: Maximum characters to return
        
    Returns:
        Clean summary text
    """
    # Try to find the Purpose section
    if 'Purpose' in text or 'purpose' in text:
        # Extract text after "Purpose" keyword
        purpose_match = re.search(r'[Pp]urpose[:\s]+(.*?)(?:\n\n|Business|Domain|\n[A-Z])', text, re.DOTALL)
        if purpose_match:
            summary = purpose_match.group(1).strip()
            # Clean up formatting
            summary = re.sub(r'\s+', ' ', summary)
            if len(summary) <= max_length:
                return summary
            # Truncate at sentence boundary
            truncate_at = summary[:max_length].rfind('.')
            if truncate_at > 100:
                return summary[:truncate_at + 1]
    
    # Fallback: Extract first paragraph or sentences
    # Split by double newlines to get first paragraph
    paragraphs = text.split('\n\n')
    for para in paragraphs[:3]:  # Check first 3 paragraphs
        para = para.strip()
        # Skip headers and very short paragraphs
        if len(para) > 50 and not para.isupper():
            # Clean up
            para = re.sub(r'\s+', ' ', para)
            if len(para) <= max_length:
                return para
            # Truncate at sentence boundary
            truncate_at = para[:max_length].rfind('.')
            if truncate_at > 100:
                return para[:truncate_at + 1]
            return para[:max_length] + "..."
    
    # Last resort: just truncate intelligently
    clean_text = re.sub(r'\s+', ' ', text.strip())
    if len(clean_text) <= max_length:
        return clean_text
    truncate_at = clean_text[:max_length].rfind('.')
    if truncate_at > 100:
        return clean_text[:truncate_at + 1]
    return clean_text[:max_length] + "..."


def format_error_response(errors_df: pd.DataFrame) -> str:
    """
    Format error DataFrame into readable response.
    Fix: Convert to list of dicts first to avoid Spark Connect issues.
    
    Args:
        errors_df: DataFrame with error data
        
    Returns:
        Formatted markdown string
    """
    if errors_df is None or errors_df.empty:
        return "✅ No errors found matching your criteria."
    
    response = f"📊 **Found {len(errors_df)} error(s):**\n\n"
    
    # Convert to list of dicts to avoid Spark Connect issues with .iterrows()
    error_records = errors_df.to_dict('records')
    
    for idx, row in enumerate(error_records):
        response += f"### 🔴 Error {idx + 1}: `{row['error_id']}`\n\n"
        response += f"**⏰ Time:** {row['timestamp']}\n\n"
        response += f"**📍 Layer:** {row['layer']}\n\n"
        response += f"**🏷️ Type:** `{row['error_type']}`\n\n"
        
        response += f"**❌ Problem:**\n```\n{row['error_message']}\n```\n\n"
        
        response += f"**✅ Solution:**\n```python\n{row['solution']}\n```\n\n"
        response += f"**Status:** {'🟢 Resolved' if row['status'] == 'resolved' else '🔴 Open'}\n\n"
        response += "---\n\n"
    
    return response


def format_common_errors_response(errors_df: pd.DataFrame) -> str:
    """
    Format common errors DataFrame into readable response.
    
    Args:
        errors_df: DataFrame with common error data
        
    Returns:
        Formatted markdown string
    """
    if errors_df is None or errors_df.empty:
        return "No common error patterns found."
    
    response = f"📊 **Top {len(errors_df)} Most Common Errors:**\n\n"
    
    # Convert to list of dicts to avoid Spark Connect issues
    error_records = errors_df.to_dict('records')
    
    for idx, row in enumerate(error_records, 1):
        response += f"### 🔴 #{idx}: {row['error_type']}\n\n"
        response += f"**📈 Occurrences:** {row['occurrence_count']} times\n\n"
        response += f"**📍 Layer:** {row['layer']}\n\n"
        response += f"**⏰ Last Occurred:** {row['last_occurred']}\n\n"
        
        response += f"**Example:**\n```\n{row['example_message']}\n```\n\n"
        
        response += f"**✅ Solution:**\n```python\n{row['solution']}\n```\n\n"
        response += "---\n\n"
    
    return response


def format_doc_response(docs_df: pd.DataFrame, conversational: bool = True, summary_only: bool = False) -> str:
    """
    Format documentation DataFrame into readable response.
    Fix: Convert to list of dicts first to avoid Spark Connect issues.
    
    Args:
        docs_df: DataFrame with documentation data
        conversational: If True, natural format. If False, structured format.
        summary_only: If True, extract only summaries (for "what is" questions)
        
    Returns:
        Formatted markdown string
    """
    if docs_df is None or docs_df.empty:
        return "I couldn't find documentation about that topic."
    
    # Convert to list of dicts to avoid Spark Connect issues
    doc_records = docs_df.to_dict('records')
    
    if conversational:
        # Natural conversational format
        response = ""
        
        for row in doc_records:
            content = row['text']
            
            if summary_only:
                # For "what is" questions, extract just the summary
                content = extract_summary_from_doc(content, max_length=300)
            else:
                # For other questions, show more detail but still truncate
                if len(content) > 600:
                    # Find a good breaking point
                    truncate_at = content[:600].rfind('.')
                    if truncate_at > 300:
                        content = content[:truncate_at + 1]
                    else:
                        content = content[:600] + "..."
            
            response += f"{content}\n\n"
        
        return response.strip()
    else:
        # Structured format (only used for detailed documentation queries)
        response = f"📚 **Found {len(doc_records)} documentation entry(ies):**\n\n"
        
        for idx, row in enumerate(doc_records, 1):
            response += f"### 📄 Doc {idx}\n\n"
            response += f"**Category:** {row.get('category', 'General')}\n\n"
            
            content = row['text']
            if len(content) > 500:
                content = content[:500] + "..."
            
            response += f"{content}\n\n"
            
            if 'source_doc' in row and row['source_doc']:
                response += f"**Source:** {row['source_doc']}\n\n"
            
            response += "---\n\n"
        
        return response


def format_pipeline_overview() -> str:
    """
    Generate a comprehensive pipeline overview response.
    
    Returns:
        Formatted markdown string with pipeline overview
    """
    return """
## 🏗️ Retail Demo Pipeline Overview

**Purpose:**
This is a **Medallion Architecture** pipeline demonstrating retail data processing with intentional errors for troubleshooting training.

### 📊 Architecture Layers

**1. 🥉 Bronze Layer** (Raw Data Ingestion)
- **Table:** `bronze_orders`
- **Purpose:** Store raw order data as received from source systems
- **Schema:** order_id, customer_id, order_date, amount, status
- **Data Quality:** Contains intentional data issues (NULL values, invalid dates, negative amounts)

**2. 🥈 Silver Layer** (Cleaned & Validated)
- **Table:** `silver_orders_clean`
- **Purpose:** Validated data with quality checks applied
- **Transformations:**
  - Remove NULL customer_ids
  - Parse and validate dates
  - Filter out invalid amounts
- **Expectations:** Data quality rules enforced (expect_or_drop)

**3. 🥇 Gold Layer** (Business Aggregates)
- **Table:** `gold_revenue_summary`
- **Purpose:** Business-ready aggregated metrics
- **Aggregations:** Daily revenue by customer, order counts, average amounts

### 🔄 Data Flow

```
Source System → Bronze (Raw) → Silver (Clean) → Gold (Aggregated) → Analytics/BI
```

### 🎯 Business Use Cases
- Daily Revenue Reporting
- Data Quality Monitoring
- Error Pattern Analysis
- Pipeline Troubleshooting Training

### 📈 Data Quality Strategy
- **Bronze:** Accept all data (no rejection)
- **Silver:** Enforce quality rules with expectations
- **Gold:** Business-validated aggregates

Need more details about a specific layer or concept? Just ask!
"""


def generate_response(user_message: str) -> str:
    """
    Main chatbot logic - smarter and more conversational with better intent handling.
    
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
    if intent == 'pipeline_overview':
        # User wants pipeline architecture/overview
        response = format_pipeline_overview()
    
    elif intent == 'dlt_expectations':
        # User wants DLT/expectations documentation
        with st.spinner("📚 Searching DLT documentation..."):
            docs_df = search_documentation("expectation expect_or_drop expect_or_fail quality", limit=5)
            
            if docs_df is None or docs_df.empty:
                response = """
## 📚 DLT Expectations (Data Quality Checks)

**Delta Live Tables Expectations** are data quality constraints that validate your data as it flows through the pipeline.

### Types of Expectations:

**1. `expect_or_drop()`**
- **Behavior:** Drops rows that fail the constraint
- **Use Case:** Remove bad data automatically
- **Example:**
```python
@dlt.expect_or_drop("valid_customer_id", "customer_id IS NOT NULL")
```

**2. `expect_or_fail()`**
- **Behavior:** Stops the pipeline if ANY row fails
- **Use Case:** Critical validations that must pass
- **Example:**
```python
@dlt.expect_or_fail("valid_order_id", "order_id IS NOT NULL")
```

**3. `expect()`**
- **Behavior:** Records violations but keeps data
- **Use Case:** Monitor data quality without blocking
- **Example:**
```python
@dlt.expect("valid_amount", "amount > 0")
```

### Best Practices:
- Use `expect_or_fail()` for critical business keys
- Use `expect_or_drop()` for optional fields with bad data
- Use `expect()` for monitoring and alerting

Need specific examples from your pipeline? Just ask!
"""
            else:
                response = "## 📚 DLT Expectations Documentation\n\n"
                response += format_doc_response(docs_df, conversational=True, summary_only=False)
    
    elif intent == 'common_errors':
        # User wants to see common error patterns
        with st.spinner("📊 Analyzing common error patterns..."):
            common_df = get_common_errors(limit=5)
            
            if common_df is None or common_df.empty:
                response = "No error patterns found in the logs."
            else:
                response = format_common_errors_response(common_df)
    
    elif intent == 'specific_error':
        # User is searching for specific errors
        with st.spinner("🔍 Searching error logs..."):
            errors_df = search_errors(keywords_str, limit=5)
            
            if errors_df is None or errors_df.empty:
                if "today" in message_lower:
                    response = "✅ **Great news!** No errors were logged today. Your pipeline is running smoothly! 🎉"
                elif keywords_str:
                    response = f"✅ No errors found matching '**{keywords_str}**'. Your pipeline appears to be healthy for this query."
                else:
                    response = "✅ No recent errors found. Everything looks good!"
            else:
                response = format_error_response(errors_df)
    
    elif intent == 'documentation':
        # User wants general documentation/how-to
        wants_summary = any(phrase in message_lower for phrase in ['what is', 'what\'s', 'tell me about', 'describe'])
        
        with st.spinner("📚 Searching documentation..."):
            docs_df = search_documentation(keywords_str, limit=3)
            
            if docs_df is None or docs_df.empty:
                response = f"I couldn't find documentation about '**{keywords_str}**'.\n\nTry asking about:\n- Pipeline architecture (bronze, silver, gold layers)\n- Data quality checks (expect_or_drop, expect_or_fail)\n- Common troubleshooting scenarios"
            else:
                response = format_doc_response(docs_df, conversational=True, summary_only=wants_summary)
    
    else:
        # General query - be smart about it
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
                    response += format_doc_response(docs_df, conversational=True, summary_only=True)
            else:
                response = """
👋 I'm here to help with pipeline troubleshooting! 

**I can help you with:**
- 🏗️ Pipeline architecture & flow
- 📊 Common errors & solutions
- 📚 DLT expectations & data quality
- 🔍 Specific error searches
- 💡 Best practices & examples

**Try asking:**
- "Explain the pipeline architecture"
- "What are common errors?"
- "How do DLT expectations work?"
- "Show me NULL customer_id errors"

What would you like to know?
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
                # Rename variable to avoid false positive lint warning
                metric_cols = st.columns(2)
                
                with metric_cols[0]:
                    st.metric("Total Errors", stats['total'])
                
                with metric_cols[1]:
                    st.metric("Open Errors", stats['open'])
                
                if stats['by_layer']:
                    st.write("**By Layer:**")
                    for layer, count in stats['by_layer'].items():
                        st.write(f"🔹 {layer.title()}: {count}")
            
            except Exception:
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
            "Explain the pipeline architecture",
            "What are common errors?",
            "How do DLT expectations work?",
            "Show me NULL customer_id errors",
            "What errors happened today?",
            "Explain expect_or_drop"
        ]
        
        # Rename variable to avoid false positive lint warning
        question_cols = st.columns(2)
        for idx, question in enumerate(starter_questions):
            with question_cols[idx % 2]:
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
