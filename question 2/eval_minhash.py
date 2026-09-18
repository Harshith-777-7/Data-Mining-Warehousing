import duckdb
import pandas as pd
import numpy as np
import re
import hashlib
import time

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv'").df().set_index('notice_id')
df_labels = pd.read_csv('labelled_pairs.csv')

def clean_notice(row):
    text = str(row['body'])
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
        
    title = str(row['title'])
    title = re.sub(r'^(nit for|e-tender\s*-?|tender notice:?|corrigendum\s*-?|\s*)+', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\[[a-z0-9/_-]+\]', '', title, flags=re.IGNORECASE)
    
    full = title + " " + text
    full = re.sub(r'tender reference number:[^\n]+', '', full, flags=re.IGNORECASE)
    full = re.sub(r'\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b', '', full)
    full = re.sub(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', '', full)
    full = re.sub(r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b', '', full, flags=re.IGNORECASE)
    full = re.sub(r'[^a-z0-9\s]', ' ', full.lower())
    full = re.sub(r'\s+', ' ', full).strip()
    return full

def get_word_ngrams(text, n=2):
    tokens = text.split()
    if len(tokens) < n:
        return set(tokens)
    return set(' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

def jaccard(s1, s2):
    if not s1 or not s2:
        return 0.0
    u = len(s1.union(s2))
    return len(s1.intersection(s2)) / u if u > 0 else 0.0

# Pre-compute shingles for all notices in labelled_pairs
needed_ids = set(df_labels['notice_id_a']).union(set(df_labels['notice_id_b']))
cleaned = {nid: clean_notice(df_notices.loc[nid]) for nid in needed_ids}
shingles = {nid: get_word_ngrams(cleaned[nid], 2) for nid in needed_ids}

# Compute exact Jaccard for all 900 pairs
exact_jaccards = []
for _, row in df_labels.iterrows():
    exact_jaccards.append(jaccard(shingles[row['notice_id_a']], shingles[row['notice_id_b']]))
exact_jaccards = np.array(exact_jaccards)

# MinHash implementation using 64-bit murmur-like or xxhash/hashlib
# We can generate K hash functions using linear congruential hashing: h_i(x) = (a_i * hash(x) + b_i) % p
def generate_hash_params(K, seed=42):
    rng = np.random.RandomState(seed)
    a = rng.randint(1, 1000000000, size=K, dtype=np.uint64)
    b = rng.randint(0, 1000000000, size=K, dtype=np.uint64)
    return a, b

# Hash shingles to 64-bit ints
shingle_hash_cache = {}
def hash_shingle(s):
    if s not in shingle_hash_cache:
        h = int(hashlib.md5(s.encode('utf-8')).hexdigest()[:16], 16) & 0x7FFFFFFFFFFFFFFF
        shingle_hash_cache[s] = h
    return shingle_hash_cache[s]

shingles_hashed = {nid: np.array([hash_shingle(s) for s in sh_set], dtype=np.uint64) 
                   if len(sh_set) > 0 else np.array([0], dtype=np.uint64)
                   for nid, sh_set in shingles.items()}

def compute_minhash_signatures(hashed_shingles_dict, K, a, b):
    sigs = {}
    for nid, h_arr in hashed_shingles_dict.items():
        # h_arr: (M,), a: (K,), b: (K,)
        # Use simple integer arithmetic
        # Vectorized across M and K:
        vals = (h_arr[:, None] * a[None, :] + b[None, :]) % 2147483647
        sigs[nid] = np.min(vals, axis=0)
    return sigs

print("Evaluating MinHash across multiple sizes K...")
for K in [16, 32, 64, 128, 256, 512]:
    a, b = generate_hash_params(K)
    sigs = compute_minhash_signatures(shingles_hashed, K, a, b)
    
    est_jaccards = []
    for _, row in df_labels.iterrows():
        sig_a = sigs[row['notice_id_a']]
        sig_b = sigs[row['notice_id_b']]
        est_jaccards.append(np.mean(sig_a == sig_b))
    est_jaccards = np.array(est_jaccards)
    
    errors = est_jaccards - exact_jaccards
    mae = np.mean(np.abs(errors))
    rmse = np.sqrt(np.mean(errors**2))
    max_err = np.max(np.abs(errors))
    
    # Theoretical standard error for s around 0.3 - 0.5:
    # SE = sqrt(s*(1-s)/K)
    # Average theoretical SE over the exact jaccards:
    theo_se = np.mean(np.sqrt(exact_jaccards * (1 - exact_jaccards) / K))
    
    print(f"K={K:3d} (Size: {K*4:4d} bytes): MAE={mae:.4f}, RMSE={rmse:.4f}, MaxErr={max_err:.4f}, TheoRMSE={theo_se:.4f}")
