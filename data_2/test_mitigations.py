import duckdb
import pandas as pd
import numpy as np
import re
import hashlib
import time
from collections import Counter

con = duckdb.connect()
df_notices = con.execute("SELECT notice_id, portal_id, title, body, estimated_value FROM 'notices/*.csv'").df().set_index('notice_id')
df_labels = pd.read_csv('labelled_pairs.csv')

# Ground truth label pairs
same_pairs = set()
for _, r in df_labels[df_labels['label'] == 'same'].iterrows():
    pair = tuple(sorted([r['notice_id_a'], r['notice_id_b']]))
    same_pairs.add(pair)
total_same = len(same_pairs)

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

print("Preprocessing notices...")
cleaned_texts = {nid: clean_processed(row['body'], row['title']) for nid, row in df_notices.iterrows()}

# Let's test multiple mitigations:
# Baseline: Word 2-grams, no DF filtering, b=32, r=4 (unmitigated)
# Mitigation 1: Document Frequency (DF) threshold pruning (drop shingles appearing in > 10% of notices)
# Mitigation 2: Word 3-grams instead of 2-grams
# Mitigation 3: LSH Bucket Size Capping (ignore buckets with > M notices, e.g. M=50 or 100)
# Mitigation 4: Tuning b and r (e.g. b=16, r=8 or b=20, r=6)

def evaluate_retrieval(shingles_dict, K, b, r, bucket_cap=None):
    t0 = time.time()
    rng = np.random.RandomState(42)
    hash_a = rng.randint(1, 1000000000, size=K, dtype=np.uint64)
    hash_b = rng.randint(0, 1000000000, size=K, dtype=np.uint64)
    
    sigs = {}
    for nid, sh_set in shingles_dict.items():
        if len(sh_set) == 0:
            sigs[nid] = np.zeros(K, dtype=np.uint64)
            continue
        h_arr = np.array([hash_sh(s) for s in sh_set], dtype=np.uint64)
        vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
        sigs[nid] = np.min(vals, axis=0)
        
    bucket_map = {}
    for nid, sig in sigs.items():
        for band_idx in range(b):
            band_chunk = tuple(sig[band_idx*r : (band_idx+1)*r])
            key = (band_idx, band_chunk)
            if key not in bucket_map:
                bucket_map[key] = []
            bucket_map[key].append(nid)
            
    # Apply bucket cap if specified
    candidate_pairs = set()
    total_comparisons_raw = 0
    bucket_sizes = []
    
    work_per_notice = Counter()
    
    for key, nids in bucket_map.items():
        sz = len(nids)
        bucket_sizes.append(sz)
        if sz > 1:
            total_comparisons_raw += sz * (sz - 1) // 2
            if bucket_cap is not None and sz > bucket_cap:
                continue # drop mega-bucket
            for i in range(sz):
                work_per_notice[nids[i]] += (sz - 1)
                for j in range(i + 1, sz):
                    p = tuple(sorted([nids[i], nids[j]]))
                    candidate_pairs.add(p)
                    
    runtime = time.time() - t0
    
    # Recall on labelled pairs
    hits = 0
    for p in same_pairs:
        if p in candidate_pairs:
            hits += 1
    recall = hits / total_same
    
    # Work distribution per notice
    cand_counts = np.array(list(work_per_notice.values())) if len(work_per_notice) > 0 else np.array([0])
    
    return {
        'runtime': runtime,
        'recall': recall,
        'hits': hits,
        'total_same': total_same,
        'unique_candidates': len(candidate_pairs),
        'total_bucket_pairs': total_comparisons_raw,
        'max_bucket_size': max(bucket_sizes) if bucket_sizes else 0,
        'p50_work': np.percentile(cand_counts, 50),
        'p90_work': np.percentile(cand_counts, 90),
        'p99_work': np.percentile(cand_counts, 99),
        'max_work': cand_counts.max()
    }

print("1. Computing Baseline (Processed, Word 2-grams, b=32, r=4, no cap)...")
sh_2gram = {nid: get_word_ngrams(txt, 2) for nid, txt in cleaned_texts.items()}
res_base = evaluate_retrieval(sh_2gram, K=128, b=32, r=4)

print("2. Computing Mitigation: Bucket Capping at 100...")
res_cap100 = evaluate_retrieval(sh_2gram, K=128, b=32, r=4, bucket_cap=100)

print("3. Computing Mitigation: Bucket Capping at 50...")
res_cap50 = evaluate_retrieval(sh_2gram, K=128, b=32, r=4, bucket_cap=50)

print("4. Computing Mitigation: High-DF Shingle Pruning (DF > 5%)...")
df_counts = Counter()
for s_set in sh_2gram.values():
    for s in s_set:
        df_counts[s] += 1
max_df = int(0.05 * len(df_notices)) # 5% = 600 notices
sh_2gram_pruned = {nid: {s for s in s_set if df_counts[s] <= max_df} for nid, s_set in sh_2gram.items()}
res_pruned = evaluate_retrieval(sh_2gram_pruned, K=128, b=32, r=4)

print("5. Computing Mitigation: Parameter Rebalancing (b=16, r=8)...")
res_b16r8 = evaluate_retrieval(sh_2gram, K=128, b=16, r=8)

print("6. Computing Mitigation: Word 3-grams with b=32, r=4...")
sh_3gram = {nid: get_word_ngrams(txt, 3) for nid, txt in cleaned_texts.items()}
res_3gram = evaluate_retrieval(sh_3gram, K=128, b=32, r=4)

# Print Summary Table
results = [
    ("Baseline (b=32, r=4, unmitigated)", res_base),
    ("Mitigation A: Bucket Cap M=100", res_cap100),
    ("Mitigation B: Bucket Cap M=50", res_cap50),
    ("Mitigation C: Stop-Shingle Pruning (DF>5%)", res_pruned),
    ("Mitigation D: Tuning (b=16, r=8)", res_b16r8),
    ("Mitigation E: Word 3-grams (b=32, r=4)", res_3gram)
]

print("\n" + "="*85)
print(f"{'Strategy':<35} | {'Recall':<8} | {'Candidates':<12} | {'MaxBucket':<10} | {'MaxWork/N':<10} | {'Time(s)':<7}")
print("="*85)
for name, r in results:
    print(f"{name:<35} | {r['recall']*100:6.2f}% | {r['unique_candidates']:>12,d} | {r['max_bucket_size']:>10d} | {r['max_work']:>10.0f} | {r['runtime']:>6.2f}s")
print("="*85)
