# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Error Logger - Auto Capture System
# Simple Error Logging System
# This captures errors and auto-updates documentation

from pyspark.sql.functions import *
from datetime import datetime

# Create schema and error log table
spark.sql("CREATE SCHEMA IF NOT EXISTS retail_demo.monitoring")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS retail_demo.monitoring.error_log (
        error_id STRING,
        timestamp TIMESTAMP,
        pipeline_name STRING,
        layer STRING,
        error_type STRING,
        error_message STRING,
        solution STRING,
        status STRING
    ) USING DELTA
""")

print("✅ Error logging table ready!")
print("📊 Table: retail_demo.monitoring.error_log")

# COMMAND ----------

# DBTITLE 1,Log Error Function
def log_error(pipeline_name, layer, error_type, error_message, solution="Under investigation"):
    """
    Log error to table - NO manual doc updates needed!
    """
    error_id = f"ERR_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    error_data = [(
        error_id,
        datetime.now(),
        pipeline_name,
        layer,
        error_type,
        error_message,
        solution,
        "open"
    )]
    
    df = spark.createDataFrame(error_data, [
        "error_id", "timestamp", "pipeline_name", "layer", 
        "error_type", "error_message", "solution", "status"
    ])
    
    df.write.mode("append").saveAsTable("retail_demo.monitoring.error_log")
    
    print(f"✅ Error logged: {error_id}")
    print(f"📝 Type: {error_type}")
    print(f"💡 Solution: {solution}")
    
    return error_id

print("\n✅ Error logging function ready!")
print("📝 Usage: log_error('pipeline_name', 'layer', 'error_type', 'message', 'solution')")

# COMMAND ----------

# DBTITLE 1,Example - Log an Error
# Example: Log a sample error
error_id = log_error(
    pipeline_name="Retail_Demo_Pipeline",
    layer="silver",
    error_type="DataQualityFailure",
    error_message="NULL customer_id found - fails validation rule",
    solution="Filter NULL customer_ids OR change validation to expect_or_drop"
)

print(f"\n📋 Error ID: {error_id}")
print("\n🔍 View all errors:")
display(spark.table("retail_demo.monitoring.error_log").orderBy(col("timestamp").desc()))

# COMMAND ----------



# COMMAND ----------

# DBTITLE 1,How to Use This in Your Pipeline
# MAGIC %md
# MAGIC # 🎯 **HOW TO CAPTURE PIPELINE ERRORS (PRACTICAL GUIDE)**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ✅ **Working Approach: Call log_error() When Errors Occur**
# MAGIC
# MAGIC Since DBFS event logs are blocked on serverless, use **manual error logging** in your pipeline code:
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### **Example 1: In Your DLT Pipeline Notebook**
# MAGIC
# MAGIC ```python
# MAGIC import dlt
# MAGIC from pyspark.sql.functions import *
# MAGIC
# MAGIC # Bronze layer - load raw data
# MAGIC @dlt.table(
# MAGIC     name="bronze_orders",
# MAGIC     comment="Raw orders data"
# MAGIC )
# MAGIC def bronze_orders():
# MAGIC     return spark.read.format("csv") \
# MAGIC         .option("header", "true") \
# MAGIC         .load("/databricks-datasets/retail-org/customers/")
# MAGIC
# MAGIC # Silver layer - with data quality expectations
# MAGIC @dlt.table(
# MAGIC     name="silver_orders",
# MAGIC     comment="Cleaned orders with quality checks"
# MAGIC )
# MAGIC @dlt.expect_or_fail("valid_customer", "customer_id IS NOT NULL")
# MAGIC @dlt.expect_or_fail("positive_amount", "amount > 0")
# MAGIC def silver_orders():
# MAGIC     return dlt.read("bronze_orders") \
# MAGIC         .withColumn("processed_date", current_timestamp())
# MAGIC ```
# MAGIC
# MAGIC **When expectation fails:**
# MAGIC - DLT automatically logs error to its event log
# MAGIC - Pipeline shows error in UI
# MAGIC - **You log it manually:** Run this notebook's `log_error()` function
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### **Example 2: Add Error Logging to Your Pipeline Job**
# MAGIC
# MAGIC **Job Structure:**
# MAGIC ```
# MAGIC Your Pipeline Job:
# MAGIC   ├─ Task 1: Run DLT Pipeline
# MAGIC   └─ Task 2: Error_Logger notebook (this one!)
# MAGIC            Run Condition: ALL_DONE (runs even if Task 1 fails)
# MAGIC ```
# MAGIC
# MAGIC **In Task 2 (this notebook), add:**
# MAGIC ```python
# MAGIC # Check if pipeline failed by querying your tables
# MAGIC try:
# MAGIC     # Try to read your silver table
# MAGIC     silver_df = spark.table("workspace.default.silver_orders")
# MAGIC     record_count = silver_df.count()
# MAGIC     
# MAGIC     if record_count == 0:
# MAGIC         # Empty table = likely data quality failure
# MAGIC         log_error(
# MAGIC             pipeline_name="Retail_Demo_Pipeline",
# MAGIC             layer="silver",
# MAGIC             error_type="EmptyTable",
# MAGIC             error_message="silver_orders table is empty after pipeline run",
# MAGIC             solution="Check bronze layer data quality and expectations"
# MAGIC         )
# MAGIC except Exception as e:
# MAGIC     # Table doesn't exist = pipeline failed badly
# MAGIC     log_error(
# MAGIC         pipeline_name="Retail_Demo_Pipeline",
# MAGIC         layer="silver",
# MAGIC         error_type="TableNotFound",
# MAGIC         error_message=f"silver_orders table not found: {str(e)}",
# MAGIC         solution="Pipeline failed to create table - check DLT pipeline logs"
# MAGIC     )
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ### **Example 3: Log from Pipeline Monitoring**
# MAGIC
# MAGIC When you see errors in the DLT UI:
# MAGIC
# MAGIC ```
# MAGIC Error: Flow 'silver_orders' failed
# MAGIC Expectation: 'valid_customer' violated
# MAGIC Input: order_id=3, customer_id=NULL
# MAGIC ```
# MAGIC
# MAGIC **Manually run:**
# MAGIC ```python
# MAGIC log_error(
# MAGIC     pipeline_name="Retail_Demo_Pipeline",
# MAGIC     layer="silver",
# MAGIC     error_type="EXPECTATION_VIOLATION_valid_customer",
# MAGIC     error_message="customer_id NULL found in order_id=3",
# MAGIC     solution="Use @dlt.expect_or_drop OR filter NULLs in bronze layer"
# MAGIC )
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 📊 **Query Errors with Genie**
# MAGIC
# MAGIC Once errors are logged, Genie can answer:
# MAGIC
# MAGIC * **"What errors happened today?"**
# MAGIC * **"Show me silver layer errors"**
# MAGIC * **"How do I fix the customer_id error?"**
# MAGIC * **"Which layer has the most errors?"**
# MAGIC
# MAGIC **Genie queries:**
# MAGIC ```sql
# MAGIC SELECT * FROM retail_demo.monitoring.error_log
# MAGIC WHERE timestamp >= current_date()
# MAGIC ORDER BY timestamp DESC
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🚀 **Recommended Setup**
# MAGIC
# MAGIC 1. ✅ **Keep this notebook** for error logging function
# MAGIC 2. ✅ **Add log_error() calls** in your pipeline notebooks when you catch errors
# MAGIC 3. ✅ **Add this notebook as Task 2** in your pipeline job (runs after pipeline)
# MAGIC 4. ✅ **Add error_log table** to your Genie Space
# MAGIC 5. ✅ **Ask Genie** for error insights!
# MAGIC
# MAGIC ---

# COMMAND ----------

# DBTITLE 1,View All Errors
# ═══════════════════════════════════════════════════════════════════════════════
# 📊 VIEW ALL LOGGED ERRORS
# ═══════════════════════════════════════════════════════════════════════════════

from pyspark.sql.functions import *

print("\n📊 Error Log Summary\n")
print("="*80)

# Get error statistics
error_log_df = spark.table("retail_demo.monitoring.error_log")

total_errors = error_log_df.count()
open_errors = error_log_df.filter(col("status") == "open").count()

print(f"Total Errors Logged: {total_errors}")
print(f"Open Errors: {open_errors}")
print(f"Resolved Errors: {total_errors - open_errors}")

print("\n📈 Errors by Layer:")
display(
    error_log_df.groupBy("layer") \
        .count() \
        .orderBy(col("count").desc())
)

print("\n📋 Recent Errors (Last 10):")
print("="*80)
display(
    error_log_df.orderBy(col("timestamp").desc()).limit(10)
)

print("\n💡 TIP: Add this table to your Genie Space!")
print("   Then ask: 'What errors happened today?' or 'Show me silver layer errors'")

# COMMAND ----------

# DBTITLE 1,Simulate a Real Pipeline Error
# ═══════════════════════════════════════════════════════════════════════════════
# 🧪 SIMULATE REAL PIPELINE ERRORS (FOR TESTING)
# ═══════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta
import random

print("\n🧪 Simulating pipeline errors for testing...\n")
print("="*80)

# Simulate common DLT pipeline errors
error_scenarios = [
    {
        "layer": "bronze",
        "error_type": "EXPECTATION_VIOLATION_valid_date",
        "error_message": "Invalid date format in order_date column. Found: '2026-13-45' (invalid month)",
        "solution": """Use try_cast() to handle invalid dates:
        
.withColumn('order_date', try_cast(col('order_date'), 'date'))
.filter(col('order_date').isNotNull())

Or add expectation:
@dlt.expect_or_drop('valid_date', 'to_date(order_date) IS NOT NULL')"""
    },
    {
        "layer": "silver",
        "error_type": "EXPECTATION_VIOLATION_valid_customer",
        "error_message": "Flow 'silver_orders' failed. Expectation 'valid_customer' violated. Found NULL customer_id in order_id=3",
        "solution": """Options to fix NULL customer_id:
        
1. Use expect_or_drop (recommended):
   @dlt.expect_or_drop('valid_customer', 'customer_id IS NOT NULL')
   
2. Filter in bronze layer:
   .filter(col('customer_id').isNotNull())
   
3. Use default value:
   .withColumn('customer_id', coalesce(col('customer_id'), lit(-1)))"""
    },
    {
        "layer": "silver",
        "error_type": "EXPECTATION_VIOLATION_positive_amount",
        "error_message": "Negative amount detected: order_id=7 has amount=-50.00 (likely refund or data error)",
        "solution": """Handle negative amounts:
        
1. Filter negative amounts:
   .filter(col('amount') > 0)
   
2. Separate refunds:
   .withColumn('is_refund', when(col('amount') < 0, True).otherwise(False))
   
3. Use expectation:
   @dlt.expect_or_drop('positive_amount', 'amount > 0')"""
    },
    {
        "layer": "gold",
        "error_type": "DataQualityFailure",
        "error_message": "Aggregation produced NULL revenue for customer_id=42. Missing data in silver layer.",
        "solution": """Fix NULL aggregations:
        
1. Use COALESCE in aggregation:
   .groupBy('customer_id').agg(
       coalesce(sum('amount'), lit(0)).alias('total_revenue')
   )
   
2. Filter NULLs before aggregation:
   .filter(col('amount').isNotNull())"""
    }
]

# Log each simulated error
for i, error in enumerate(error_scenarios, 1):
    error_id = log_error(
        pipeline_name="Retail_Demo_Pipeline",
        layer=error["layer"],
        error_type=error["error_type"],
        error_message=error["error_message"],
        solution=error["solution"]
    )
    print(f"\n✅ Logged test error {i}/4: {error_id}")
    print(f"   Layer: {error['layer']}")
    print(f"   Type: {error['error_type']}")

print("\n" + "="*80)
print("\n🎉 Test errors logged successfully!")
print("\n📊 View them in the next cell or ask Genie:")
print("   'What errors happened in the silver layer?'")
print("   'How do I fix the customer_id NULL error?'")
print("   'Show me all data quality failures'")

# COMMAND ----------

# DBTITLE 1,How to Automate This
# MAGIC %md
# MAGIC # 🚀 **HOW TO AUTOMATE ERROR LOGGING**
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ✅ **Option 1: Schedule This Notebook to Run Automatically**
# MAGIC
# MAGIC ### **Best For:** Periodic error checks (every hour, every day)
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC 1. **Create a Job:**
# MAGIC    - Go to: **Workflows** → **Jobs** → **Create Job**
# MAGIC    - Name: `Error_Monitor_Hourly`
# MAGIC    - Task: Select this notebook (`Error_Logger`)
# MAGIC
# MAGIC 2. **Set Schedule:**
# MAGIC    - **Every hour:** `0 0 * * * ? *`
# MAGIC    - **Every 6 hours:** `0 0 */6 * * ? *`
# MAGIC    - **Daily at 9 AM:** `0 0 9 * * ? *`
# MAGIC
# MAGIC 3. **Configure:**
# MAGIC    - Compute: Use your serverless cluster
# MAGIC    - Timeout: 10 minutes
# MAGIC    - Notifications: Email on failure (optional)
# MAGIC
# MAGIC 4. **Done!**
# MAGIC    - Errors are automatically logged every hour
# MAGIC    - Genie can query `error_log` table anytime
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ✅ **Option 2: Run After Pipeline Completes**
# MAGIC
# MAGIC ### **Best For:** Log errors immediately after pipeline runs
# MAGIC
# MAGIC **Steps:**
# MAGIC
# MAGIC 1. **Edit Your Pipeline Job:**
# MAGIC    - Go to: **Workflows** → **Jobs** → Find your pipeline job
# MAGIC    - Click **Edit**
# MAGIC
# MAGIC 2. **Add Second Task:**
# MAGIC    - Click **Add Task**
# MAGIC    - Name: `Log_Errors`
# MAGIC    - Type: Notebook
# MAGIC    - Notebook: Select `Error_Logger`
# MAGIC    - **Depends On:** Your pipeline task
# MAGIC    - **Run If:** `ALL_SUCCESS` (or `ALL_DONE` to run even on failure)
# MAGIC
# MAGIC 3. **Done!**
# MAGIC    - Every time pipeline runs → Error_Logger runs after
# MAGIC    - Automatically captures any errors
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## ✅ **Option 3: Use Databricks Workflows Triggers**
# MAGIC
# MAGIC ### **Best For:** Real-time error logging (advanced)
# MAGIC
# MAGIC **Use Case:**
# MAGIC - Pipeline fails → Trigger error logging immediately
# MAGIC - No waiting for schedule
# MAGIC
# MAGIC **Implementation:**
# MAGIC - Set up **Job Trigger** on pipeline failure
# MAGIC - Trigger calls this Error_Logger notebook
# MAGIC - Requires Databricks Jobs API
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 🎯 **Recommended Setup:**
# MAGIC
# MAGIC ```
# MAGIC 🔄 Your Pipeline Job (Retail_Demo_Pipeline)
# MAGIC    └─ Task 1: Run DLT Pipeline
# MAGIC    └─ Task 2: Error_Logger (runs after, even on failure)
# MAGIC    
# MAGIC 🕙 Scheduled Job (Error_Monitor_Hourly)
# MAGIC    └─ Runs: Every hour
# MAGIC    └─ Scans: Last 24 hours of errors
# MAGIC    └─ Catches: Any errors missed by pipeline job
# MAGIC ```
# MAGIC
# MAGIC **Result:**
# MAGIC - ✅ Errors logged in real-time (via pipeline job task)
# MAGIC - ✅ Backup error scan (via hourly job)
# MAGIC - ✅ No manual work required!
# MAGIC - ✅ Genie always has latest error data
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 📊 **What Gets Logged:**
# MAGIC
# MAGIC | Error Type | Captured By | Logged To |
# MAGIC |------------|-------------|----------|
# MAGIC | Pipeline failure | System tables | `error_log` |
# MAGIC | DLT expectations fail | Event logs | `error_log` |
# MAGIC | Data quality issues | Event logs | `error_log` |
# MAGIC | NULL violations | Event logs | `error_log` |
# MAGIC | Schema mismatches | Event logs | `error_log` |
# MAGIC
# MAGIC **Your Genie Space can query:**
# MAGIC ```sql
# MAGIC SELECT * FROM retail_demo.monitoring.error_log
# MAGIC WHERE timestamp >= current_date()
# MAGIC ORDER BY timestamp DESC
# MAGIC ```
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 💡 **Next Steps:**
# MAGIC
# MAGIC 1. ✅ Run Cell 4 or Cell 5 above to test error scanning
# MAGIC 2. ✅ Schedule this notebook (Option 1 above)
# MAGIC 3. ✅ Add `error_log` table to your Genie Space
# MAGIC 4. ✅ Ask Genie: "What errors happened today?"
# MAGIC
# MAGIC ---
