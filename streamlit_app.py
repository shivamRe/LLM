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
# CSS
# =============================================================================

st.markdown(
    """
<style>

.main{
    padding-top:1rem;
}

.stChatMessage{
    border-radius:12px;
}

.stButton>button{
    width:100%;
    border-radius:8px;
}

</style>
""",
    unsafe_allow_html=True,
)


# =============================================================================
# ENV VARIABLES
# =============================================================================

DATABRICKS_HOST = os.getenv("DATABRICKS_HOST")
DATABRICKS_TOKEN = os.getenv("DATABRICKS_TOKEN")
DATABRICKS_WAREHOUSE_ID = os.getenv("DATABRICKS_WAREHOUSE_ID")

ERROR_LOG_TABLE = "retail_demo.monitoring.error_log"
DOC_TABLE = "retail_demo.rag.documentation_source"


# =============================================================================
# SESSION STATE
# =============================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "connection_status" not in st.session_state:
    st.session_state.connection_status = "Not Tested"

if "connection_error" not in st.session_state:
    st.session_state.connection_error = None


# =============================================================================
# DATABRICKS CONNECTION
# =============================================================================

@st.cache_resource(show_spinner=False)
def get_connection():

    if not DATABRICKS_HOST:
        raise Exception("Missing DATABRICKS_HOST")

    if not DATABRICKS_TOKEN:
        raise Exception("Missing DATABRICKS_TOKEN")

    if not DATABRICKS_WAREHOUSE_ID:
        raise Exception("Missing DATABRICKS_WAREHOUSE_ID")

    return sql.connect(
        server_hostname=DATABRICKS_HOST,
        http_path=f"/sql/1.0/warehouses/{DATABRICKS_WAREHOUSE_ID}",
        access_token=DATABRICKS_TOKEN,
    )


def test_connection():

    try:

        conn = get_connection()

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
def execute_query(query):

    try:

        conn = get_connection()

        with conn.cursor() as cursor:

            cursor.execute(query)

            rows = cursor.fetchall()

            columns = [c[0] for c in cursor.description]

        return pd.DataFrame(rows, columns=columns)

    except Exception as e:

        st.error(str(e))

        return pd.DataFrame()


