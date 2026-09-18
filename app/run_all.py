#!/usr/bin/env python3
"""
Annapurna Stores Analytics Platform - Master Execution & Verification Suite
Executes Tasks A through F sequentially with full empirical outputs and proofs.
"""
import sys
import time
import socket
import psycopg2
from pipeline.config import (
    MINIO_ENDPOINT, PG_HOST, PG_PORT, PG_DB, PG_USER, PG_PASSWORD
)
from pipeline.ingest import ingest_to_minio
from pipeline.task_a_metrics import run_task_a
from pipeline.task_b_idempotence import run_task_b
from pipeline.task_c_tables import run_task_c
from pipeline.task_d_prices import run_task_d
from pipeline.task_e_federated import run_task_e
from pipeline.task_f_reconcile import run_task_f

def wait_for_services(max_retries=30, delay=2):
    """Wait until MinIO and PostgreSQL are reachable and ready."""
    print("[Wait] Checking connectivity to MinIO and PostgreSQL...")
    minio_host, minio_port = MINIO_ENDPOINT.split(':')
    minio_port = int(minio_port)
    
    # Wait for MinIO TCP
    for attempt in range(1, max_retries + 1):
        try:
            with socket.create_connection((minio_host, minio_port), timeout=2):
                print(f"[Wait] MinIO is reachable at {MINIO_ENDPOINT}")
                break
        except Exception:
            if attempt == max_retries:
                raise TimeoutError(f"Cannot connect to MinIO at {MINIO_ENDPOINT}")
            time.sleep(delay)
            
    # Wait for PostgreSQL ready
    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                user=PG_USER, password=PG_PASSWORD, connect_timeout=3
            )
            # Verify masters table exists
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM stores;")
            stores_count = cur.fetchone()[0]
            cur.close()
            conn.close()
            print(f"[Wait] PostgreSQL is reachable. 'stores' table contains {stores_count} records.")
            break
        except Exception as e:
            if attempt == max_retries:
                raise TimeoutError(f"Cannot connect to PostgreSQL at {PG_HOST}:{PG_PORT}: {e}")
            time.sleep(delay)

def main():
    start_time = time.time()
    print("\n" + "#" * 80)
    print("#  ANNAPURNA STORES DATA PLATFORM - AUTOMATED EVALUATION SUITE")
    print("#  Question 1: Three Answers to One Question (Tasks A through F)")
    print("#" * 80 + "\n")
    
    # 1. Wait for underlying infrastructure
    wait_for_services()
    
    # 2. Initial Ingestion
    print("\n[Step 1/7] Ingesting Sales Data into MinIO S3...")
    ingest_to_minio()
    
    # 3. Task A
    print("\n[Step 2/7] Running Task A: Storage Layout & Pruning Metrics...")
    metrics_a = run_task_a()
    
    # 4. Task B
    print("\n[Step 3/7] Running Task B: Idempotent Ingestion & Checksum Verification...")
    metrics_b = run_task_b()
    
    # 5. Task C
    print("\n[Step 4/7] Running Task C: Dimensional Tables & Fast Slicing...")
    metrics_c = run_task_c()
    
    # 6. Task D
    print("\n[Step 5/7] Running Task D: Historical Price Lookup (March vs December)...")
    metrics_d = run_task_d()
    
    # 7. Task E
    print("\n[Step 6/7] Running Task E: Cross-System Zero-Copy Query & Engine Evidence...")
    metrics_e = run_task_e()
    
    # 8. Task F
    print("\n[Step 7/7] Running Task F: 12-Month Financial Reconciliation...")
    metrics_f = run_task_f()
    
    total_elapsed = time.time() - start_time
    print("\n" + "#" * 80)
    print(f"#  ALL TASKS A THROUGH F EXECUTED AND VERIFIED SUCCESSFULLY IN {total_elapsed:.2f}s!")
    print("#" * 80 + "\n")

if __name__ == '__main__':
    main()
