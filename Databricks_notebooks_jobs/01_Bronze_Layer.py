# Databricks notebook source
# DBTITLE 1,Bronze Layer - Load Raw Data
import dlt
from pyspark.sql.functions import *

# Bronze table - raw orders data
@dlt.table(
    name="bronze_orders",
    comment="Raw orders data from source system"
)
def bronze_orders():
    # Simulating data load from source
    data = [
        (1, 101, "2026-07-10", 100.50, "completed"),
        (2, 102, "2026-07-10", 250.00, "pending"),
        (3, None, "2026-07-10", 75.25, "completed"),  # NULL customer_id - will cause issue!
        (4, 104, "invalid-date", 150.00, "completed"),  # Bad date - will cause issue!
        (5, 105, "2026-07-10", -50.00, "refunded")  # Negative amount - data quality issue!
    ]
    
    return spark.createDataFrame(data, ["order_id", "customer_id", "order_date", "amount", "status"])