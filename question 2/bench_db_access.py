import sqlite3
import duckdb
import pandas as pd
import numpy as np
import re
import hashlib
import time

# Precompute signatures
con = duckdb.connect()
df_notices = con.execute("SELECT notice_id, portal_id, published_at, title, body, estimated_value, closing_date FROM 'notices/*.csv'").df()

def clean_processed(body, title):
    text = str(body)
    if "NOTICE DETAILS FOLLOW" in text:
        idx = text.find("NOTICE DETAILS FOLLOW")
        after = text[idx:]
        m = re.search(r'-{10,}\s*', after)
        text = after[m.end():] if m else after[len("NOTICE DETAILS FOLLOW"):]
    elif "===============================================================================" in text:
        idx = text.find("===============================================================================")
        text = text[idx + len("==============================================================================="):]
    
    if "-------------------------------------------------------------------------------" in text:
        text = text.split("-------------------------------------------------------------------------------")[0]
    if "[entry truncated" in text:
        text = text[:text.find("[entry truncated")]
        
    t = str(title)
    t = re.sub(r'^(nit for|e-tender\s*-?|tender notice:?|corrigendum\s*-?|\s*)+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\[[a-z0-9/_-]+\]', '', t, flags=re.IGNORECASE)
    
    full = t + " " + text
    full = re.sub(r'tender reference number:[^\n]+', '', full, flags=re.IGNORECASE)
    full = re.sub(r'\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b', '', full)
    full = re.sub(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', '', full)
    full = re.sub(r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b', '', full, flags=re.IGNORECASE)
    full = re.sub(r'[^a-z0-9\s]', ' ', full.lower())
    return re.sub(r'\s+', ' ', full).strip()

def get_word_ngrams(text, n=2):
    tokens = text.split()
    if len(tokens) < n:
        return set(tokens)
    return set(' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

shingle_cache = {}
def hash_sh(s):
    if s not in shingle_cache:
        shingle_cache[s] = int(hashlib.md5(s.encode('utf-8')).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF
    return shingle_cache[s]

K = 128
b = 16
r = 8
rng = np.random.RandomState(42)
hash_a = rng.randint(1, 1000000000, size=K, dtype=np.uint64)
hash_b = rng.randint(0, 1000000000, size=K, dtype=np.uint64)

print("Computing MinHash signatures and LSH rows...")
lsh_rows = []
for idx, row in df_notices.iterrows():
    nid = row['notice_id']
    txt = clean_processed(row['body'], row['title'])
    sh_set = get_word_ngrams(txt, 2)
    if len(sh_set) == 0:
        continue
    h_arr = np.array([hash_sh(s) for s in sh_set], dtype=np.uint64)
    vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
    sig = np.min(vals, axis=0)
    for band_idx in range(b):
        chunk = tuple(sig[band_idx*r : (band_idx+1)*r])
        bucket_id = int(hashlib.md5(str(chunk).encode()).hexdigest()[:15], 16)
        lsh_rows.append((band_idx, bucket_id, nid))

print(f"Generated {len(lsh_rows)} LSH index rows ({len(df_notices)} notices * {b} bands).")

# Insert into SQLite database
conn = sqlite3.connect("setubid_lsh.db")
cursor = conn.cursor()

cursor.execute("DELETE FROM lsh_buckets;")
cursor.executemany("INSERT INTO lsh_buckets (band_id, bucket_id, notice_id) VALUES (?, ?, ?);", lsh_rows)
conn.commit()

# Populate notices table
notice_tuples = [(r['notice_id'], r['portal_id'], str(r['published_at']), r['title'], int(r['estimated_value']) if pd.notnull(r['estimated_value']) else 0, str(r['closing_date'])) for _, r in df_notices.iterrows()]
cursor.execute("DELETE FROM notices;")
cursor.executemany("INSERT INTO notices VALUES (?, ?, ?, ?, ?, ?);", notice_tuples)
conn.commit()

# Create B-Tree Index
cursor.execute("CREATE INDEX IF NOT EXISTS idx_band_bucket ON lsh_buckets (band_id, bucket_id);")
conn.commit()

# Let's test a lookup query for a notice with 16 bands
sample_nid = "N000001"
sample_bands = [(band_idx, bucket_id) for band_idx, bucket_id, nid in lsh_rows if nid == sample_nid]

query_indexed = """
SELECT DISTINCT notice_id 
FROM lsh_buckets 
WHERE (band_id = ? AND bucket_id = ?)
"""

print("\n--- EXPLAIN QUERY PLAN (WITH B-TREE INDEX) ---")
cursor.execute("EXPLAIN QUERY PLAN " + query_indexed, sample_bands[0])
for row in cursor.fetchall():
    print(row)

# Benchmark 500 lookups with B-Tree index
t0 = time.time()
total_candidates = 0
for band_id, bucket_id in sample_bands * 30: # 480 queries
    cursor.execute(query_indexed, (band_id, bucket_id))
    rows = cursor.fetchall()
    total_candidates += len(rows)
t_indexed = time.time() - t0
print(f"Indexed Lookup: 480 band queries executed in {t_indexed*1000:.2f} ms ({t_indexed/480*1000:.3f} ms/query)")

# Now force unindexed alternative: DROP INDEX or use `NOT INDEXED`
query_unindexed = """
SELECT DISTINCT notice_id 
FROM lsh_buckets NOT INDEXED
WHERE (band_id = ? AND bucket_id = ?)
"""

print("\n--- EXPLAIN QUERY PLAN (FORCED TABLE SCAN / REJECTED ALTERNATIVE) ---")
cursor.execute("EXPLAIN QUERY PLAN " + query_unindexed, sample_bands[0])
for row in cursor.fetchall():
    print(row)

# Benchmark lookups with Table Scan
t0 = time.time()
for band_id, bucket_id in sample_bands[:10]: # only 10 queries because it's slow
    cursor.execute(query_unindexed, (band_id, bucket_id))
    rows = cursor.fetchall()
t_unindexed = time.time() - t0
print(f"Unindexed Scan: 10 queries executed in {t_unindexed*1000:.2f} ms ({t_unindexed/10*1000:.3f} ms/query)")
print(f"Slowdown factor: {(t_unindexed/10) / (t_indexed/480):.1f}x slower!")

# Total rows examined:
# With index: B-tree search examines only matching entries (log N steps + count of matches)
# Without index: examines all 192,000 rows in lsh_buckets PER QUERY!
total_rows = len(lsh_rows)
print(f"\nPhysical rows examined per query:")
print(f"  Unindexed: {total_rows:,} rows scanned per band query")
print(f"  Indexed (B-Tree): ~{np.log2(total_rows):.1f} tree levels + ~1-5 leaf rows")

conn.close()
