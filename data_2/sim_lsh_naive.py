import duckdb
import pandas as pd
import numpy as np
import re
import hashlib
import time

con = duckdb.connect()
df_notices = con.execute("SELECT notice_id, portal_id, title, body, estimated_value FROM 'notices/*.csv'").df().set_index('notice_id')
print(f"Loaded {len(df_notices)} notices.")

# Let's test NAIVE / UNSTRIPPED LSH vs STRIPPED / MITIGATED LSH
# Choice: Word 2-grams or 3-grams, K = 128 (e.g., b=16, r=8 or b=32, r=4)

def clean_naive(body, title):
    # Naive: keep entire text, just lowercase
    text = (str(title) + " " + str(body)).lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def get_shingles(text, n=2):
    tokens = text.split()
    if len(tokens) < n:
        return set(tokens)
    return set(' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

# Let's test on 1,000 notices first or full 12,000
print("Testing on full corpus with naive text...")
t0 = time.time()
naive_shingles = {}
for nid, row in df_notices.iterrows():
    naive_shingles[nid] = get_shingles(clean_naive(row['body'], row['title']), 2)
print(f"Shingled 12,000 notices in {time.time()-t0:.2f}s")

# Let's compute MinHash signatures
K = 128
b = 16
r = 8
# LSH threshold = (1/16)^(1/8) = (0.0625)^0.125 = 0.707
# Or b=32, r=4 -> threshold = (1/32)^(1/4) = 0.420

rng = np.random.RandomState(42)
hash_a = rng.randint(1, 1000000000, size=K, dtype=np.uint64)
hash_b = rng.randint(0, 1000000000, size=K, dtype=np.uint64)

# Hash shingles
shingle_hash_cache = {}
def hash_sh(s):
    if s not in shingle_hash_cache:
        shingle_hash_cache[s] = int(hashlib.md5(s.encode('utf-8')).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF
    return shingle_hash_cache[s]

print("Hashing shingles and computing MinHash...")
t0 = time.time()
sigs = {}
for nid, sh_set in naive_shingles.items():
    if len(sh_set) == 0:
        sigs[nid] = np.zeros(K, dtype=np.uint64)
        continue
    h_arr = np.array([hash_sh(s) for s in sh_set], dtype=np.uint64)
    vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
    sigs[nid] = np.min(vals, axis=0)
print(f"MinHash computed in {time.time()-t0:.2f}s")

# Now let's inspect LSH bucket sizes under naive text for b=16, r=8 and b=32, r=4
for (bands, rows) in [(16, 8), (32, 4)]:
    print(f"\n--- Naive Text: b={bands}, r={rows} ---")
    bucket_counts = {}
    for nid, sig in sigs.items():
        for band_idx in range(bands):
            band_chunk = sig[band_idx*rows : (band_idx+1)*rows]
            bucket_key = (band_idx, tuple(band_chunk))
            bucket_counts[bucket_key] = bucket_counts.get(bucket_key, 0) + 1
            
    sizes = list(bucket_counts.values())
    sizes_multi = [s for s in sizes if s > 1]
    pairs_generated = sum(s * (s - 1) // 2 for s in sizes_multi)
    print(f"Total buckets: {len(sizes)}, Multi-notice buckets: {len(sizes_multi)}")
    print(f"Max bucket size: {max(sizes)}")
    print(f"Total candidate pair comparisons generated across all bands: {pairs_generated:,}")
    # Top 10 largest buckets
    sorted_buckets = sorted(bucket_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    print("Top 5 bucket sizes:", [count for _, count in sorted_buckets[:5]])
