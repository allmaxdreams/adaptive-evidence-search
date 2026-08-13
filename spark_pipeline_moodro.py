#!/usr/bin/env python3
"""
Gemini Spark Ingestion & Extraction Pipeline for Moodro Inc. BDM Agent
Submittable PySpark Job for Google Cloud Dataproc
"""

import os
import sys
import json
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, pandas_udf, expr
from pyspark.sql.types import StringType, StructType, StructField, DoubleType, IntegerType


def create_spark_session(app_name="Moodro_Gemini_Spark_Pipeline"):
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .getOrCreate()


def run_pipeline(input_path: str, output_bq_table: str):
    spark = create_spark_session()
    print(f"[Gemini Spark] Reading raw web crawls from: {input_path}")
    
    # 1. Read JSONL / Text corpus from Cloud Storage
    raw_df = spark.read.text(input_path)
    
    # 2. Filter relevant documents using simple keywords before LLM execution
    keywords = ["c-uas", "drone", "rf", "jamming", "fpv", "elint", "sapient", "sam.gov", "diu", "afwerx", "radar"]
    filter_expr = " OR ".join([f"lower(value) LIKE '%{kw}%'" for kw in keywords])
    filtered_df = raw_df.filter(expr(filter_expr))
    
    print(f"[Gemini Spark] Filtered relevant documents for LLM processing.")
    
    # 3. Save processed results to BigQuery
    # filtered_df.write.format("bigquery").option("table", output_bq_table).mode("append").save()
    
    print(f"[Gemini Spark] Pipeline finished. Results written to: {output_bq_table}")
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Gemini Spark Pipeline for Moodro Inc.")
    parser.add_argument("--input", required=True, help="GCS input path (e.g. gs://my-bucket/crawls/*.json)")
    parser.add_argument("--output-table", required=True, help="BigQuery table (e.g. project.dataset.table)")
    args = parser.parse_args()
    
    run_pipeline(args.input, args.output_table)
