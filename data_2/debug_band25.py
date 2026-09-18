import duckdb
import pandas as pd
import numpy as np
import re
import hashlib

con = duckdb.connect()
df_notices = con.execute("SELECT notice_id, portal_id, title, body FROM 'notices/*.csv'").df().set_index('notice_id')

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

# Look at Band 25: indices 25*4 = 100, 101, 102, 103
band_indices = [100, 101, 102, 103]

# For a sample of notices that land in that top bucket in Band 25, let's find which shingles attained the min!
sample_nids = []
sigs_band25 = {}

proc_sh = {}
for nid, row in df_notices.iterrows():
    sh_set = get_shingles(clean_processed(row['body'], row['title']), 2)
    proc_sh[nid] = sh_set
    if len(sh_set) == 0:
        continue
    h_arr = np.array([hash_sh(s) for s in sh_set], dtype=np.uint64)
    vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
    sig = np.min(vals, axis=0)
    sigs_band25[nid] = tuple(sig[100:104])

# Find the most frequent bucket tuple in Band 25
counts = pd.Series(sigs_band25).value_counts()
top_tuple = counts.index[0]
print(f"Top bucket key in Band 25: {top_tuple} with {counts.iloc[0]} notices!")

# Now find which shingles produced these 4 values for notices in this bucket
notices_in_top = [nid for nid, tup in sigs_band25.items() if tup == top_tuple][:5]

for nid in notices_in_top:
    print(f"\n--- Notice {nid} ({df_notices.loc[nid, 'portal_id']}) ---")
    sh_list = list(proc_sh[nid])
    h_arr = np.array([hash_sh(s) for s in sh_list], dtype=np.uint64)
    vals = (h_arr[:, None] * hash_a[None, :] + hash_b[None, :]) % 2147483647
    min_vals = np.min(vals, axis=0)
    winning_shingles = []
    for idx_in_band, h_idx in enumerate(band_indices):
        win_idx = np.argmin(vals[:, h_idx])
        winning_shingles.append((h_idx, sh_list[win_idx], vals[win_idx, h_idx]))
    print("Winning shingles in band 25:")
    for h_idx, sh, val in winning_shingles:
        print(f"  Hash {h_idx}: {repr(sh)} (val={val})")
