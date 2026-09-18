import sqlite3
import pandas as pd
import numpy as np
import time
import os

# Connect to SQLite file (disk-backed relational storage)
db_file = "setubid_lsh.db"
if os.path.exists(db_file):
    os.remove(db_file)

conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Enable WAL mode for high performance
cursor.execute("PRAGMA journal_mode = WAL;")
cursor.execute("PRAGMA synchronous = NORMAL;")

# Create Relational Schema
cursor.execute("""
CREATE TABLE IF NOT EXISTS notices (
    notice_id TEXT PRIMARY KEY,
    portal_id TEXT NOT NULL,
    published_at TEXT,
    title TEXT NOT NULL,
    estimated_value INTEGER,
    closing_date TEXT
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS lsh_buckets (
    band_id INTEGER NOT NULL,
    bucket_id INTEGER NOT NULL,
    notice_id TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS canonical_cards (
    card_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    representative_notice_id TEXT NOT NULL,
    estimated_value INTEGER,
    title TEXT NOT NULL
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS card_notices (
    card_id TEXT NOT NULL,
    notice_id TEXT NOT NULL,
    associated_at TEXT NOT NULL,
    confidence_score REAL NOT NULL,
    PRIMARY KEY (card_id, notice_id),
    FOREIGN KEY (card_id) REFERENCES canonical_cards(card_id),
    FOREIGN KEY (notice_id) REFERENCES notices(notice_id)
);
""")

print("Schema created successfully in setubid_lsh.db")
conn.commit()
conn.close()
