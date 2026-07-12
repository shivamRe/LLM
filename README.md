# 🤖 Pipeline Troubleshooting Assistant

A Streamlit chatbot for Databricks pipeline troubleshooting and documentation search.

## Features

- 💬 **Interactive Chat Interface** - Natural language queries
- 🔍 **Error Log Search** - Find pipeline errors with solutions
- 📚 **Documentation Search** - Semantic search through DLT docs
- 📊 **Error Statistics** - Track error trends by layer
- ⚡ **Quick Actions** - One-click access to recent errors
- 🎯 **Starter Questions** - Guided examples to get started

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Databricks Connection

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` and add your Databricks credentials:

```
DATABRICKS_HOST=your-workspace.cloud.databricks.com
DATABRICKS_TOKEN=fkfk
DATABRICKS_WAREHOUSE_ID=your-warehouse-id
```

#### Getting Your Credentials:

**DATABRICKS_HOST:**
- Your workspace URL without `https://`
- Example: `adb-1234567890.7.azuredatabricks.net`

**DATABRICKS_TOKEN:**
1. Go to User Settings → Developer → Access Tokens
2. Click "Generate New Token"
3. Copy the token (starts with `dapi`)

**DATABRICKS_WAREHOUSE_ID:**
1. Go to SQL Warehouses
2. Select your warehouse
3. Go to "Connection Details"
4. Copy the "Server hostname" warehouse ID

### 3. Run the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Data Sources

The chatbot queries these Databricks tables:

- **retail_demo.monitoring.error_log** - Pipeline errors with auto-generated solutions
- **retail_demo.rag.documentation_source** - DLT documentation and best practices
- **retail_demo.rag.documentation_index** - Vector embeddings for semantic search

## Usage Examples

### Error Queries:
- "What errors happened today?"
- "Show me silver layer errors"
- "Find errors with NULL customer_id"
- "How many errors by layer?"

### Documentation Queries:
- "How do I use expect_or_drop?"
- "What's the difference between expect_or_fail and expect_or_drop?"
- "Show me examples of data quality checks"
- "How do I handle invalid dates in DLT?"

### General Queries:
- "Show me recent errors and their solutions"
- "Find documentation about NULL handling"
- "What are best practices for data quality?"

## Architecture

```
User Input
    ↓
Intent Detection (errors/documentation/general)
    ↓
Keyword Extraction
    ↓
Query Databricks Tables
    ↓
Format Response with Code Examples
    ↓
Display in Chat UI
```

## Features Overview

### Sidebar:
- **Connection Status** - Real-time Databricks connection monitoring
- **Error Statistics** - Total, open, and errors by layer
- **Quick Actions** - Show recent errors, clear chat
- **About Section** - App information and data sources

### Chat Interface:
- **Starter Questions** - Click to try example queries
- **Message History** - Full conversation context
- **Markdown Support** - Rich formatting for code and solutions
- **Syntax Highlighting** - Code blocks with proper formatting
- **Loading States** - Visual feedback during queries

### Response Features:
- **Error Details** - Error ID, timestamp, layer, type, message
- **Solutions** - Auto-generated code examples to fix issues
- **Documentation** - Relevant docs with examples
- **Status Tracking** - Open vs resolved errors
- **Citations** - Error IDs and doc sources

## Deployment

### Local Development:
```bash
streamlit run app.py
```

### Databricks App (Recommended):
```bash
databricks apps create pipeline-chatbot
```

### Docker:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
```

## Troubleshooting

### Connection Issues:
- ✅ Verify environment variables are set correctly
- ✅ Check SQL warehouse is running (not stopped)
- ✅ Confirm token has not expired
- ✅ Ensure network access to Databricks workspace

### Query Errors:
- ✅ Verify tables exist: `retail_demo.monitoring.error_log`, `retail_demo.rag.documentation_source`
- ✅ Check table permissions (SELECT privilege)
- ✅ Confirm schema and catalog names are correct

### Performance:
- ✅ Use a larger SQL warehouse for faster queries
- ✅ Enable caching in Streamlit
- ✅ Optimize queries with proper indexes
- ✅ Limit result sets with appropriate LIMIT clauses

## Customization

### Add New Intents:
Edit `detect_intent()` function to add custom intent detection.

### Modify UI:
Edit CSS in the `st.markdown()` section at the top.

### Add Vector Search:
Replace keyword search in `search_documentation()` with Databricks Vector Search:

```python
from databricks.vector_search.client import VectorSearchClient

def vector_search_docs(query: str):
    client = VectorSearchClient()
    index = client.get_index("retail_demo.rag.documentation_index")
    results = index.similarity_search(query, columns=["content"], num_results=5)
    return results
```

## License

MIT License - Feel free to use and modify for your needs.

## Support

For issues or questions:
- Check Databricks documentation: https://docs.databricks.com
- Review error logs in the app sidebar
- Contact your Databricks administrator for permission issues
