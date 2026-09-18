import os
import duckdb

# Environment detection (inside Docker container vs local host)
IN_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('IN_DOCKER', 'false').lower() == 'true'

# Paths
DATA_DIR = os.environ.get('DATA_DIR', '/exam/data' if os.path.exists('/exam/data') else os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data')))
SALES_DIR = os.path.join(DATA_DIR, 'sales')
MASTERS_SQL = os.path.join(DATA_DIR, 'masters.sql')
FINANCE_CSV = os.path.join(DATA_DIR, 'finance_monthly.csv')
TRUTH_JSON = os.path.join(DATA_DIR, '_truth', 'truth.json')

# MinIO / S3 Configuration
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', 'minio:9000' if IN_DOCKER else 'localhost:9000')
MINIO_ACCESS_KEY = os.environ.get('MINIO_ROOT_USER', 'minioadmin')
MINIO_SECRET_KEY = os.environ.get('MINIO_ROOT_PASSWORD', 'minioadmin')
MINIO_BUCKET = os.environ.get('MINIO_BUCKET', 'annapurna-sales')
S3_BASE_URL = f"s3://{MINIO_BUCKET}"

# PostgreSQL Configuration
PG_HOST = os.environ.get('POSTGRES_HOST', 'postgres' if IN_DOCKER else 'localhost')
PG_PORT = int(os.environ.get('POSTGRES_PORT', '5432'))
PG_DB = os.environ.get('POSTGRES_DB', 'annapurna')
PG_USER = os.environ.get('POSTGRES_USER', 'annapurna')
PG_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'annapurna')

def get_duckdb_connection(attach_postgres=True):
    """
    Returns a configured DuckDB connection with S3 (httpfs) and PostgreSQL attached.
    """
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_endpoint='{MINIO_ENDPOINT}';")
    con.execute("SET s3_use_ssl=false;")
    con.execute("SET s3_url_style='path';")
    con.execute(f"SET s3_access_key_id='{MINIO_ACCESS_KEY}';")
    con.execute(f"SET s3_secret_access_key='{MINIO_SECRET_KEY}';")
    
    if attach_postgres:
        con.execute("INSTALL postgres; LOAD postgres;")
        pg_conn_str = f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASSWORD}"
        con.execute(f"ATTACH '{pg_conn_str}' AS pg (TYPE POSTGRES, READ_ONLY);")
        
    return con
