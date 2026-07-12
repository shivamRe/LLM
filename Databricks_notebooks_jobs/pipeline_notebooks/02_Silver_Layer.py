# Databricks notebook source
# DBTITLE 1,Silver Layer - Clean and Validate
import dlt
from pyspark.sql.functions import *

# Silver table - cleaned orders
@dlt.table(
    name="silver_orders",
    comment="Cleaned and validated orders"
)
@dlt.expect_or_fail("valid_amount", "amount > 0")  # This will FAIL for negative amounts!
@dlt.expect_or_fail("valid_customer", "customer_id IS NOT NULL")  # This will FAIL for NULL customer_id!
def silver_orders():
    return (
        dlt.read("bronze_orders")
        .filter(col("status") != "cancelled")  # Remove cancelled orders
        .withColumn("processed_date", current_timestamp())  # Add processing timestamp
    )
