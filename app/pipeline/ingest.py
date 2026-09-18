import os
import glob
import csv
import hashlib
from datetime import datetime, date
import boto3
from botocore.client import Config
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from .config import (
    SALES_DIR, MINIO_ENDPOINT, MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY, MINIO_BUCKET, get_duckdb_connection
)

def ensure_minio_bucket():
    """Ensure the target MinIO bucket exists."""
    s3 = boto3.client(
        's3',
        endpoint_url=f"http://{MINIO_ENDPOINT}",
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    try:
        s3.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        try:
            s3.create_bucket(Bucket=MINIO_BUCKET)
            print(f"[Ingest] Created MinIO bucket '{MINIO_BUCKET}'")
        except Exception as e:
            print(f"[Ingest] Bucket check/create note: {e}")
    return s3

def parse_sales_files(sales_dir=SALES_DIR):
    """
    Parse all sales files handling the 3 vendor dialects and perform
    line-level deduplication identified by (bill_no, line_no).
    """
    files = sorted(glob.glob(os.path.join(sales_dir, 'SALES_*')))
    if not files:
        raise FileNotFoundError(f"No sales files found in {sales_dir}")
    
    total_raw_lines = 0
    lines_by_key = {}  # (bill_no, line_no) -> record
    
    for filepath in files:
        fname = os.path.basename(filepath)
        store = fname.split('_')[1]
        
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            if store in ['S06', 'S07', 'S08', 'S09']:
                # Dialect 2: semicolon delimited, dd-mm-yyyy HH:MM:SS
                reader = csv.DictReader(f, delimiter=';')
                for r in reader:
                    total_raw_lines += 1
                    bill_no = r['bill_no'].strip()
                    line_no = int(r['line_no'])
                    key = (bill_no, line_no)
                    
                    raw_ts = r['txn_time'].strip()
                    try:
                        dt = datetime.strptime(raw_ts, '%d-%m-%Y %H:%M:%S')
                        iso_ts = dt.isoformat()
                    except Exception:
                        iso_ts = raw_ts
                        
                    lines_by_key[key] = {
                        'bill_no': bill_no,
                        'line_no': line_no,
                        'product_code': r['item_code'].strip(),
                        'qty': float(r['quantity']),
                        'unit_price': float(r['rate']),
                        'line_type': r['type'].strip(),
                        'ts': iso_ts
                    }
                    
            elif store in ['S10', 'S11', 'S12']:
                # Dialect 3: UTF-8 BOM, epoch seconds, different column order
                reader = csv.DictReader(f)
                for r in reader:
                    total_raw_lines += 1
                    bill_no = r['bill_no'].strip()
                    line_no = int(r['line_no'])
                    key = (bill_no, line_no)
                    
                    try:
                        epoch = int(r['ts'])
                        iso_ts = datetime.utcfromtimestamp(epoch).isoformat()
                    except Exception:
                        iso_ts = r['ts']
                        
                    lines_by_key[key] = {
                        'bill_no': bill_no,
                        'line_no': line_no,
                        'product_code': r['product_code'].strip(),
                        'qty': float(r['qty']),
                        'unit_price': float(r['unit_price']),
                        'line_type': r['line_type'].strip(),
                        'ts': iso_ts
                    }
                    
            else:
                # Dialect 1 (S01-S05): standard CSV, ISO-8601
                reader = csv.DictReader(f)
                for r in reader:
                    total_raw_lines += 1
                    bill_no = r['bill_no'].strip()
                    line_no = int(r['line_no'])
                    key = (bill_no, line_no)
                    
                    lines_by_key[key] = {
                        'bill_no': bill_no,
                        'line_no': line_no,
                        'product_code': r['product_code'].strip(),
                        'qty': float(r['qty']),
                        'unit_price': float(r['unit_price']),
                        'line_type': r['line_type'].strip(),
                        'ts': r['ts'].strip()
                    }

    deduped_records = []
    revenue_line_types = {'SALE', 'RETURN', 'DISCOUNT', 'VOID'}
    
    h = hashlib.sha256()
    for k in sorted(lines_by_key.keys()):
        item = lines_by_key[k]
        h.update(f"{k[0]}|{k[1]}|{item['product_code']}|{item['qty']}|{item['unit_price']}|{item['line_type']}\n".encode('utf-8'))
        
        parts = item['bill_no'].split('/')
        store_id = parts[0]
        date_str = parts[1] # YYYYMMDD
        b_date = date(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]))
        year_month = f"{date_str[:4]}-{date_str[4:6]}"
        day_of_week = b_date.strftime('%A')
        
        is_rev = item['line_type'] in revenue_line_types
        line_rev = item['qty'] * item['unit_price'] if is_rev else 0.0
        
        deduped_records.append({
            'bill_no': item['bill_no'],
            'line_no': item['line_no'],
            'store_id': store_id,
            'business_date': b_date,
            'year_month': year_month,
            'day_of_week': day_of_week,
            'product_code': item['product_code'],
            'qty': item['qty'],
            'unit_price': item['unit_price'],
            'line_revenue': round(line_rev, 4),
            'line_type': item['line_type'],
            'is_revenue': is_rev,
            'ts': item['ts']
        })
        
    checksum = h.hexdigest()
    return total_raw_lines, deduped_records, checksum

def ingest_to_minio():
    """
    Ingests cleaned, deduplicated sales data into MinIO S3 in Hive-partitioned Parquet format:
    s3://annapurna-sales/store_id={store_id}/year_month={year_month}/data.parquet
    """
    ensure_minio_bucket()
    total_raw, records, checksum = parse_sales_files()
    
    con = get_duckdb_connection(attach_postgres=False)
    
    df = pa.Table.from_pylist(records)
    con.register('raw_parsed', df)
    
    print(f"[Ingest] Writing {len(records):,} records to MinIO S3 in partitioned Parquet format...")
    con.execute(f"""
        COPY (SELECT * FROM raw_parsed WHERE is_revenue = true)
        TO 's3://{MINIO_BUCKET}/fact_sales/'
        (FORMAT PARQUET, PARTITION_BY (store_id, year_month), OVERWRITE true);
    """)
    
    con.execute(f"""
        COPY raw_parsed
        TO 's3://{MINIO_BUCKET}/all_sales/'
        (FORMAT PARQUET, PARTITION_BY (store_id, year_month), OVERWRITE true);
    """)
    
    print(f"[Ingest] Ingestion complete. Raw lines: {total_raw:,}, Unique lines: {len(records):,}, Checksum: {checksum}")
    return total_raw, len(records), checksum

if __name__ == '__main__':
    ingest_to_minio()
