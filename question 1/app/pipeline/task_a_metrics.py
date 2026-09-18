import os
import glob
import json
import boto3
from botocore.client import Config
from tabulate import tabulate
from .config import (
    SALES_DIR, MINIO_ENDPOINT, MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY, MINIO_BUCKET, get_duckdb_connection
)

def run_task_a():
    """
    Task A: Stand the platform up and land the data.
    Measures file and byte counts for a query about Store S01 in October 2024
    under the partitioned object store layout vs putting everything in one folder.
    """
    print("\n" + "=" * 80)
    print("TASK A: PLATFORM STANDUP & S3 PARTITIONED LAYOUT METRICS")
    print("=" * 80)
    
    # 1. Measure raw flat folder metrics
    raw_files = glob.glob(os.path.join(SALES_DIR, 'SALES_*'))
    total_raw_files = len(raw_files)
    total_raw_bytes = sum(os.path.getsize(f) for f in raw_files)
    
    s01_oct_raw_files = [f for f in raw_files if 'SALES_S01_202410' in os.path.basename(f)]
    s01_oct_raw_count = len(s01_oct_raw_files)
    s01_oct_raw_bytes = sum(os.path.getsize(f) for f in s01_oct_raw_files)
    
    # 2. Query engine execution on partitioned layout in S3
    con = get_duckdb_connection(attach_postgres=False)
    
    # Measure execution on partitioned S3 path
    query = f"""
        SELECT COUNT(*) AS row_count, ROUND(SUM(line_revenue), 2) AS oct_revenue
        FROM read_parquet('s3://{MINIO_BUCKET}/fact_sales/*/*/*.parquet', hive_partitioning=true)
        WHERE store_id = 'S01' AND year_month = '2024-10'
    """
    res = con.execute(query).fetchall()
    row_count, oct_rev = res[0]
    
    # 3. Get accurate Parquet file metrics from MinIO via S3 API
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    prefix_s01_oct = 'fact_sales/store_id=S01/year_month=2024-10/'
    resp = s3.list_objects_v2(Bucket=MINIO_BUCKET, Prefix=prefix_s01_oct)
    s01_oct_objects = resp.get('Contents', [])
    partitioned_files_count = len(s01_oct_objects)
    partitioned_bytes = sum(obj['Size'] for obj in s01_oct_objects)
    
    # Get total S3 fact_sales objects
    paginator = s3.get_paginator('list_objects_v2')
    total_s3_files = 0
    total_s3_bytes = 0
    for page in paginator.paginate(Bucket=MINIO_BUCKET, Prefix='fact_sales/'):
        for obj in page.get('Contents', []):
            total_s3_files += 1
            total_s3_bytes += obj['Size']
            
    # Prepare comparison table
    table_data = [
        [
            "Layout / Organization",
            "Target Scope",
            "Files Opened / Scanned",
            "Bytes Opened / Scanned",
            "Query Result (Oct S01 Revenue)"
        ],
        [
            "Flat Unpartitioned Folder",
            "All stores & months (must scan all)",
            f"{total_raw_files:,} files",
            f"{total_raw_bytes:,} bytes ({total_raw_bytes/(1024*1024):.2f} MB)",
            f"₹{oct_rev:,.2f}"
        ],
        [
            "Flat Unpartitioned (Target scope)",
            "Store S01, October 2024 (unpartitioned)",
            f"{s01_oct_raw_count:,} files",
            f"{s01_oct_raw_bytes:,} bytes ({s01_oct_raw_bytes/(1024*1024):.2f} MB)",
            f"₹{oct_rev:,.2f}"
        ],
        [
            "Hive Partitioned S3 Parquet (Our Layout)",
            "store_id=S01/year_month=2024-10/",
            f"{partitioned_files_count:,} file(s)",
            f"{partitioned_bytes:,} bytes ({partitioned_bytes/1024:.2f} KB)",
            f"₹{oct_rev:,.2f}"
        ]
    ]
    
    file_reduction_flat = total_raw_files / max(partitioned_files_count, 1)
    byte_reduction_flat = total_raw_bytes / max(partitioned_bytes, 1)
    
    print("\nORGANIZATION CHOSEN:")
    print("  Structure: Hive-style two-level partition hierarchy in S3:")
    print(f"             s3://{MINIO_BUCKET}/fact_sales/store_id=<store_id>/year_month=<YYYY-MM>/data.parquet")
    print("  Rationale: Allows partition pruning on both dimensions (store and time). A query for")
    print("             store S01 in 2024-10 only scans the target partition prefix, completely skipping")
    print("             the other 11 stores and the other 11 months.\n")
    
    print(tabulate(table_data, headers="firstrow", tablefmt="grid"))
    
    print(f"\nEMPIRICAL MEASUREMENTS & GAINS:")
    print(f"  * Total files in flat folder:               {total_raw_files:,}")
    print(f"  * Total bytes in flat folder:               {total_raw_bytes:,} bytes ({total_raw_bytes/(1024*1024):.2f} MB)")
    print(f"  * Total files in S3 (all partitions):       {total_s3_files:,} Parquet file(s)")
    print(f"  * Total bytes in S3 (all partitions):       {total_s3_bytes:,} bytes ({total_s3_bytes/(1024*1024):.2f} MB)")
    print(f"  * Files engine opens under our layout:      {partitioned_files_count} file(s)")
    print(f"  * Bytes engine opens under our layout:      {partitioned_bytes:,} bytes ({partitioned_bytes/1024:.2f} KB)")
    print(f"  * File Pruning Improvement:                 {file_reduction_flat:,.1f}x reduction")
    print(f"  * I/O Byte Scan Improvement:                {byte_reduction_flat:,.1f}x reduction")
    print(f"  * Oct 2024 Revenue for S01:                 ₹{oct_rev:,.2f} ({row_count:,} revenue lines)")
    print("=" * 80 + "\n")
    
    return {
        "total_raw_files": total_raw_files,
        "total_raw_bytes": total_raw_bytes,
        "partitioned_files_count": partitioned_files_count,
        "partitioned_bytes": partitioned_bytes,
        "file_reduction": file_reduction_flat,
        "byte_reduction": byte_reduction_flat,
        "s01_oct_revenue": oct_rev
    }

if __name__ == '__main__':
    run_task_a()
