import os
import streamlit as st
from databricks import sql

st.title("Pipeline Assistant")

st.write("App Loaded ✅")

host = os.getenv("DATABRICKS_HOST")
warehouse = os.getenv("DATABRICKS_WAREHOUSE_ID")
token = os.getenv("DATABRICKS_TOKEN")

st.write("Host:", bool(host))
st.write("Warehouse:", bool(warehouse))
st.write("Token:", bool(token))

if st.button("Test Connection"):
    try:
        conn = sql.connect(
            server_hostname=host,
            http_path=f"/sql/1.0/warehouses/{warehouse}",
            access_token=token,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            st.success(cur.fetchall())

    except Exception as e:
        st.exception(e)
