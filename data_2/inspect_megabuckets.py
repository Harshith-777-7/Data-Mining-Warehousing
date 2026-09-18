import duckdb
import pandas as pd
import numpy as np
import re
import hashlib
from collections import Counter

con = duckdb.connect()
df_notices = con.execute("SELECT notice_id, portal_id, title, body FROM 'notices/*.csv'").df().set_index('notice_id')

def clean_naive(body, title):
    text = (str(title) + " " + str(body)).lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

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

def get_shingles(text, n=2):
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
b = 32
r = 4
rng = np.random.RandomState(42)
hash_a = rng.randint(1, 1000000000, size=K, dtype=np.uint64)
hash_b = rng.randint(0, 1000000000, size=K, dtype=np.uint64)

def run_lsh(shingles_dict):
    sigs = {}
    for nid, sh_set in shingles_dict.items():
        if len(sh_set) == 0:
            sigs[nid] = np.zeros(K, dtype=np.uint64)
            continue
        h_arr = np.array([hash_sh(s) for s in sh_set], dtype=np.uint64)
        vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
        sigs[nid] = np.min(vals, axis=0)
        
    bucket_map = {} # (band, bucket_val) -> list of nids
    for nid, sig in sigs.items():
        for band_idx in range(b):
            band_chunk = tuple(sig[band_idx*r : (band_idx+1)*r])
            key = (band_idx, band_chunk)
            if key not in bucket_map:
                bucket_map[key] = []
            bucket_map[key].append(nid)
    return sigs, bucket_map

print("Running Naive LSH...")
naive_sh = {nid: get_shingles(clean_naive(row['body'], row['title']), 2) for nid, row in df_notices.iterrows()}
sigs_naive, buckets_naive = run_lsh(naive_sh)

# Inspect top bucket in Naive
sorted_naive = sorted(buckets_naive.items(), key=lambda x: len(x[1]), reverse=True)
top_b = sorted_naive[0]
print(f"\nTop bucket size in Naive: {len(top_b[1])} notices (Band {top_b[0][0]})")
portals_in_top = Counter(df_notices.loc[nid, 'portal_id'] for nid in top_b[1])
print("Portals in top bucket:", portals_in_top.most_common(10))

print("\nRunning Processed LSH...")
proc_sh = {nid: get_shingles(clean_processed(row['body'], row['title']), 2) for nid, row in df_notices.iterrows()}
sigs_proc, buckets_proc = run_lsh(proc_sh)

sorted_proc = sorted(buckets_proc.items(), key=lambda x: len(x[1]), reverse=True)
top_proc = sorted_proc[0]
print(f"\nTop bucket size in Processed: {len(top_proc[1])} notices (Band {top_proc[0][0]})")
portals_in_proc = Counter(df_notices.loc[nid, 'portal_id'] for nid in top_proc[1])
print("Portals in top processed bucket:", portals_in_proc.most_common(10))

# Distribution of candidate comparisons generated
def get_stats(bucket_map):
    sizes = [len(v) for v in bucket_map.values()]
    multi = [s for s in sizes if s > 1]
    pairs = sum(s * (s - 1) // 2 for s in multi)
    
    # Work per notice: count how many candidates each notice is paired with (with deduplication across bands)
    notice_candidates = Counter()
    for nids in bucket_map.values():
        if len(nids) > 1:
            for n in nids:
                notice_candidates[n] += (len(nids) - 1)
    
    cand_counts = np.array(list(notice_candidates.values()))
    p50 = np.percentile(cand_counts, 50) if len(cand_counts) > 0 else 0
    p90 = np.percentile(cand_counts, 90) if len(cand_counts) > 0 else 0
    p99 = np.percentile(cand_counts, 99) if len(cand_counts) > 0 else 0
    p999 = np.percentile(cand_counts, 99.9) if len(cand_counts) > 0 else 0
    max_c = cand_counts.max() if len(cand_counts) > 0 else 0
    
    return pairs, max(sizes), p50, p90, p99, p999, max_c

pairs_n, max_s_n, p50_n, p90_n, p99_n, p999_n, max_c_n = get_stats(buckets_naive)
print(f"\nNaive Stats:")
print(f"  Total candidate pair comparisons: {pairs_n:,}")
print(f"  Max bucket size: {max_s_n}")
print(f"  Candidate comparisons per notice: p50={p50_n:.0f}, p90={p90_n:.0f}, p99={p99_n:.0f}, p99.9={p999_n:.0f}, max={max_c_n:.0f}")

pairs_p, max_s_p, p50_p, p90_p, p99_p, p999_p, max_c_p = get_stats(buckets_proc)
print(f"\nProcessed Stats:")
print(f"  Total candidate pair comparisons: {pairs_p:,}")
print(f"  Max bucket size: {max_s_p}")
print(f"  Candidate comparisons per notice: p50={p50_p:.0f}, p90={p90_p:.0f}, p99={p99_p:.0f}, p99.9={p999_p:.0f}, max={max_c_p:.0f}")
