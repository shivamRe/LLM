# Databricks notebook source
# DBTITLE 1,Gold Layer - Business Metrics
import dlt
from pyspark.sql.functions import *

# Gold table - daily revenue summary
@dlt.table(
    name="gold_daily_revenue",
    comment="Daily revenue metrics for reporting"
)
def gold_daily_revenue():
    return (
        dlt.read("silver_orders")
        .groupBy("order_date")
        .agg(
            count("order_id").alias("total_orders"),
            sum("amount").alias("total_revenue"),
            avg("amount").alias("avg_order_value")
        )
    )

# COMMAND ----------

