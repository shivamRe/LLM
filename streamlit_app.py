"""
Pipeline Troubleshooting Assistant - Streamlit Chatbot
A production-ready chatbot for Databricks pipeline troubleshooting and documentation search.

Features:
- Real-time error log queries
- AI-powered responses from documentation
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
# AI IMPORTS (Optional - with safe fallback)
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from databricks.vector_search.client import VectorSearchClient
    from openai import OpenAI
    AI_ENABLED = True
except ImportError:
    AI_ENABLED = False
    # Will show warning in UI when AI features are attempted


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
# AI-POWERED SEMANTIC SEARCH & LLM RESPONSE GENERATION
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_vector_search_client():
    """Initialize Vector Search client (cached)."""
    if not AI_ENABLED:
        return None
    return VectorSearchClient(disable_notice=True)

@st.cache_resource
def get_foundation_model_client():
    """Initialize Foundation Model API client (cached)."""
    if not AI_ENABLED:
        return None
    return OpenAI(
        api_key=os.getenv('DATABRICKS_TOKEN'),
        base_url=f"https://{os.getenv('DATABRICKS_HOST')}/serving-endpoints"
    )

def semantic_search_documentation(query: str, limit: int = 5) -> pd.DataFrame:
    """
    Semantic search using Vector Search - replaces manual keyword matching!
    Falls back to empty DataFrame if AI not available.
    
    Args:
        query: User's natural language question
        limit: Number of results to return
        
    Returns:
        DataFrame with matching documents
    """
    if not AI_ENABLED:
        return pd.DataFrame()  # Fallback  to keyword search
    
    try:
        vsc = get_vector_search_client()
        if vsc is None:
            return pd.DataFrame()
        
        # Get the vector search index
        index = vsc.get_index(
            endpoint_name=os.getenv('VECTOR_SEARCH_ENDPOINT', 'pipeline_chatbot_endpoint'),
            index_name=os.getenv('VECTOR_INDEX_NAME', 'retail_demo.rag.documentation_vector_index')
        )
        
        # Perform semantic similarity search
        results = index.similarity_search(
            query_text=query,
            columns=['id', 'category', 'source_doc', 'text'],
            num_results=limit
        )
        
        # Convert to DataFrame - Vector Search returns results + similarity score
        if results and 'result' in results and 'data_array' in results['result']:
            docs = results['result']['data_array']
            
            # Vector Search returns: [id, category, source_doc, text, score]
            # Handle dynamic column count in case the API changes
            if len(docs) > 0 and len(docs[0]) == 5:
                # 5 columns: the 4 we requested + similarity score
                df = pd.DataFrame(docs, columns=['id', 'category', 'source_doc', 'text', 'score'])
                # Drop score column for consistency with rest of code
                return df[['id', 'category', 'source_doc', 'text']]
            elif len(docs) > 0 and len(docs[0]) == 4:
                # 4 columns: exactly what we requested (no score)
                return pd.DataFrame(docs, columns=['id', 'category', 'source_doc', 'text'])
            else:
                # Unexpected format - return empty
                return pd.DataFrame()
        else:
            return pd.DataFrame()
    
    except Exception as e:
        st.warning(f"⚠️ Semantic search unavailable: {str(e)}")
        return pd.DataFrame()  # Fallback to keyword search


def generate_llm_response(user_query: str, context_docs: pd.DataFrame, 
                         errors_df: Optional[pd.DataFrame] = None,
                         response_type: str = "general") -> str:
    """
    Generate AI response using Foundation Model with retrieved context.
    
    Args:
        user_query: User's question
        context_docs: Documentation retrieved from vector search
        errors_df: Optional error data to include
        response_type: Type of response (general, pipeline_overview, dlt_expectations, etc.)
        
    Returns:
        AI-generated response
    """
    if not AI_ENABLED:
        return "❌ AI features are disabled. Please install required packages: databricks-vector-search, openai"
    
    try:
        client = get_foundation_model_client()
        if client is None:
            return "❌ Failed to initialize AI model client."
        
        # Build context from documentation
        context = ""
        if context_docs is not None and not context_docs.empty:
            context += "**Relevant Documentation:**\n\n"
            for _, row in context_docs.iterrows():
                context += f"Category: {row.get('category', 'N/A')}\n"
                context += f"{row['text']}\n\n"
                context += "---\n\n"
        
        # Add error context if provided
        if errors_df is not None and not errors_df.empty:
            context += "\n**Error Data:**\n\n"
            error_records = errors_df.to_dict('records')
            for err in error_records[:5]:  # Limit to 5 errors for context
                context += f"Error ID: {err['error_id']}\n"
                context += f"Type: {err['error_type']}\n"
                context += f"Layer: {err['layer']}\n"
                context += f"Message: {err['error_message']}\n"
                context += f"Solution: {err['solution']}\n"
                context += f"Status: {err['status']}\n\n"
        
        # Build system prompt based on response type
        if response_type == "pipeline_overview":
            system_prompt = """You are a Databricks pipeline expert. Explain the pipeline architecture 
            in a clear, structured way using markdown formatting. Include:
            - Purpose and business context
            - Layer breakdown (Bronze, Silver, Gold)
            - Data flow
            - Data quality strategy
            
            Use emojis and formatting to make it engaging. Be concise but comprehensive."""
        
        elif response_type == "dlt_expectations":
            system_prompt = """You are a Delta Live Tables expert. Explain DLT expectations clearly:
            - What they are and why they matter
            - Types: expect(), expect_or_drop(), expect_or_fail()
            - When to use each type
            - Code examples
            
            Use markdown, code blocks, and emojis. Be practical and actionable."""
        
        elif response_type == "error_analysis":
            system_prompt = """You are a data pipeline troubleshooting expert. Analyze the errors provided
            and give practical, actionable advice. Format responses with:
            - Clear problem identification
            - Root cause analysis
            - Step-by-step solutions with code examples
            - Prevention tips
            
            Use markdown formatting and be concise."""
        
        else:
            system_prompt = """You are a helpful Databricks pipeline assistant. Answer questions using
            the provided documentation and error data. Be:
            - Conversational but professional
            - Concise (2-3 paragraphs max unless asked for details)
            - Practical with code examples when relevant
            - Use markdown formatting and emojis appropriately
            
            If you don't have enough context, say so and suggest what the user should look into."""
        
        # Call the LLM
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nUser Question: {user_query}"}
        ]
        
        response = client.chat.completions.create(
            model=os.getenv('LLM_MODEL_NAME', 'databricks-meta-llama-3-1-70b-instruct'),
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )
        
        return response.choices[0].message.content
    
    except Exception as e:
        return f"❌ AI response generation failed: {str(e)}\n\nPlease check your model endpoint configuration."


def extract_corrected_keywords(semantic_results: pd.DataFrame, max_keywords: int = 5) -> str:
    """
    Extract corrected keywords from semantic search results to fix typos.
    
    This is the "typo correction layer" - it uses semantic understanding to figure out
    what the user MEANT to type, even if they misspelled it.
    
    Args:
        semantic_results: DataFrame from semantic_search_documentation
        max_keywords: Maximum number of keywords to extract
        
    Returns:
        Space-separated string of corrected keywords
        
    Example:
        User types: "failuer yesterday"
        Semantic search finds docs about "failure" and "errors"
        Returns: "failure error"
    """
    if semantic_results.empty:
        return ""
    
    # Extract keywords from categories and key phrases in text
    keywords = set()
    
    for _, row in semantic_results.iterrows():
        # Add category keywords
        category = row.get('category', '').lower()
        if category:
            # Split category by spaces and underscores
            category_words = re.findall(r'\b\w+\b', category)
            keywords.update([w for w in category_words if len(w) > 3])
        
        # Extract key terms from text (look for important nouns/concepts)
        text = row.get('text', '').lower()
        
        # Look for common error-related terms in the text
        error_terms = ['error', 'failure', 'null', 'invalid', 'missing', 'expectation', 
                       'drop', 'customer_id', 'order_id', 'validation', 'quality',
                       'bronze', 'silver', 'gold', 'pipeline', 'constraint']
        
        for term in error_terms:
            if term in text:
                keywords.add(term)
    
    # Return top keywords (sorted by length to prefer longer, more specific terms)
    keywords_list = sorted(list(keywords), key=len, reverse=True)[:max_keywords]
    return " ".join(keywords_list)


# CORE CHATBOT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def search_errors(keywords: str, layer: Optional[str] = None, limit: int = 10) -> pd.DataFrame:
    """
    Search error_log table for matching errors (simple keyword search).
    
    Args:
        keywords: Search terms for error messages
        layer: Filter by layer (bronze/silver/gold) or None for all
        limit: Max number of results
        
    Returns:
        DataFrame with matching errors
    """
    # Simple keyword split (no synonyms needed)
    keyword_list = keywords.split()
    
    # Build query with keywords
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
    
    # Add keyword filter - search for each keyword
    if keyword_list:
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
    Search documentation using semantic vector search when available,
    falls back to keyword search if not.
    
    Args:
        keywords: Search terms
        limit: Max number of results
        
    Returns:
        DataFrame with matching documentation
    """
    # Try semantic search first (if AI enabled)
    if AI_ENABLED:
        semantic_results = semantic_search_documentation(keywords, limit=limit)
        if not semantic_results.empty:
            return semantic_results
    
    # Fallback: Simple keyword search (original Phase 1 logic)
    keyword_list = keywords.split()
    
    query = f"""
    SELECT 
        id,
        category,
        text,
        source_doc
    FROM retail_demo.rag.documentation_source
    WHERE 1=1
    """
    
    if keyword_list:
        keyword_conditions = []
        for kw in keyword_list:
            keyword_conditions.append(f"(text LIKE '%{kw}%' OR category LIKE '%{kw}%')")
        if keyword_conditions:
            query += " AND (" + " OR ".join(keyword_conditions) + ")"
    else:
        query += " AND 1=1"
    
    query += f" LIMIT {limit}"
    
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


def generate_response(user_message: str) -> str:
    """
    Main chatbot logic - AI-powered with dynamic responses from LLM.
    NO HARDCODED RESPONSES - everything generated by AI from documentation context.
    
    Args:
        user_message: User's input message
        
    Returns:
        AI-generated response string
    """
    intent = detect_intent(user_message)
    keywords = extract_keywords(user_message)
    keywords_str = " ".join(keywords)
    
    message_lower = user_message.lower()
    
    # Handle based on intent
    if intent == 'pipeline_overview':
        # Search for pipeline documentation
        with st.spinner("🔍 Searching pipeline documentation..."):
            docs_df = search_documentation("pipeline architecture medallion bronze silver gold", limit=5)
            
        with st.spinner("🤖 Generating response from AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                response_type="pipeline_overview"
            )
    
    elif intent == 'dlt_expectations':
        # Search for DLT/expectations documentation
        with st.spinner("🔍 Searching DLT documentation..."):
            docs_df = search_documentation("expectation expect_or_drop expect_or_fail quality", limit=5)
            
        with st.spinner("🤖 Generating response from AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                response_type="dlt_expectations"
            )
    
    elif intent == 'common_errors':
        # Get common error patterns
        with st.spinner("📊 Analyzing error patterns..."):
            common_df = get_common_errors(limit=5)
            
            if common_df is None or common_df.empty:
                return "No error patterns found in the logs."
            
            # Use LLM to analyze and explain patterns
            docs_df = search_documentation("troubleshooting error common", limit=3)
            
        with st.spinner("🤖 Analyzing with AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                errors_df=common_df,
                response_type="error_analysis"
            )
    
    elif intent == 'specific_error':
        # Search for specific errors with typo correction
        with st.spinner("🔍 Searching error logs..."):
            errors_df = search_errors(keywords_str, limit=5)
            
            # If no results, try AI-powered typo correction
            if (errors_df is None or errors_df.empty) and AI_ENABLED and keywords_str:
                with st.spinner("🤖 Using AI to understand your query..."):
                    semantic_docs = semantic_search_documentation(user_message, limit=3)
                    
                    if not semantic_docs.empty:
                        corrected_keywords = extract_corrected_keywords(semantic_docs)
                        
                        if corrected_keywords and corrected_keywords != keywords_str:
                            errors_df = search_errors(corrected_keywords, limit=5)
                            
                            if errors_df is not None and not errors_df.empty:
                                st.info(f"💡 _Interpreted your query as: **{corrected_keywords}**_")
            
            # No errors found?
            if errors_df is None or errors_df.empty:
                if "today" in message_lower:
                    return "✅ **Great news!** No errors were logged today. Your pipeline is running smoothly! 🎉"
                elif keywords_str:
                    return f"✅ No errors found matching '**{keywords_str}**'. Your pipeline appears to be healthy for this query."
                else:
                    return "✅ No recent errors found. Everything looks good!"
            
            # Found errors - use LLM to analyze and provide insights
            docs_df = search_documentation(f"troubleshooting {keywords_str}", limit=3)
            
        with st.spinner("🤖 Analyzing errors with AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                errors_df=errors_df,
                response_type="error_analysis"
            )
    
    elif intent == 'documentation':
        # General documentation query
        with st.spinner("📚 Searching documentation..."):
            docs_df = search_documentation(keywords_str, limit=5)
            
            if docs_df is None or docs_df.empty:
                return f"I couldn't find documentation about '**{keywords_str}**'.\n\nTry asking about:\n- Pipeline architecture\n- Data quality checks\n- Common troubleshooting scenarios"
            
        with st.spinner("🤖 Generating response from AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                response_type="general"
            )
    
    else:
        # General query - search both errors and docs
        with st.spinner("🤔 Thinking..."):
            errors_df = search_errors(keywords_str, limit=3)
            docs_df = search_documentation(keywords_str, limit=3)
            
            has_errors = errors_df is not None and not errors_df.empty
            has_docs = docs_df is not None and not docs_df.empty
            
            if not has_errors and not has_docs:
                # No context found - use LLM to provide helpful guidance
                docs_df = search_documentation("pipeline architecture troubleshooting", limit=3)
                
        with st.spinner("🤖 Generating response from AI..."):
            return generate_llm_response(
                user_query=user_message,
                context_docs=docs_df,
                errors_df=errors_df if has_errors else None,
                response_type="general"
            )


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
            
            stats = get_error_stats()
            
            col1, col2 = st.columns(2)
            col1.metric("Total Errors", stats['total'])
            col2.metric("Open", stats['open'])
            
            if stats['by_layer']:
                st.write("**By Layer:**")
                for layer, count in stats['by_layer'].items():
                    st.write(f"- {layer.capitalize()}: {count}")
        
        st.divider()
        
        # AI Status indicator
        if AI_ENABLED:
            st.success("🤖 AI Powered: **Active**")
            st.caption("✨ Semantic search + LLM responses")
        else:
            st.warning("🤖 AI Powered: **Disabled**")
            st.caption("Install: databricks-vector-search, openai")
        
        st.divider()
        
        # Chat controls
        if st.button("🗑️ Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
        
        # Info section
        with st.expander("ℹ️ About"):
            st.write("""
            **AI-Powered Pipeline Assistant**
            
            This chatbot uses:
            - 🔍 Vector Search for semantic understanding
            - 🤖 Foundation Models for intelligent responses
            - 📊 Real-time error log analysis
            - 📚 RAG (Retrieval-Augmented Generation)
            
            **Data Sources:**
            - Error logs: `retail_demo.monitoring.error_log`
            - Documentation: `retail_demo.rag.documentation_source`
            
            **Environment Variables Required:**
            - `DATABRICKS_HOST`
            - `DATABRICKS_TOKEN`
            - `DATABRICKS_WAREHOUSE_ID`
            - `VECTOR_SEARCH_ENDPOINT`
            - `VECTOR_INDEX_NAME`
            - `LLM_MODEL_NAME`
            """)
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MAIN CHAT INTERFACE
    # ═══════════════════════════════════════════════════════════════════════════
    
    st.title("🤖 AI Pipeline Assistant")
    
    # Display starter questions if no chat history
    if not st.session_state.messages:
        st.write("### 👋 Welcome! Ask me anything about your pipeline")
        st.write("**Quick Start Questions:**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🏗️ Explain the pipeline"):
                st.session_state.messages.append({"role": "user", "content": "Explain the pipeline architecture"})
                st.rerun()
        
        with col2:
            if st.button("🔴 Show common errors"):
                st.session_state.messages.append({"role": "user", "content": "What are the most common errors?"})
                st.rerun()
        
        with col3:
            if st.button("📚 DLT expectations"):
                st.session_state.messages.append({"role": "user", "content": "How do DLT expectations work?"})
                st.rerun()
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about errors, documentation, or pipeline architecture..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate and display assistant response
        with st.chat_message("assistant"):
            response = generate_response(prompt)
            st.markdown(response)
        
        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()
