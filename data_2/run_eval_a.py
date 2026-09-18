import duckdb
import pandas as pd
import numpy as np
import re
import time

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv'").df().set_index('notice_id')
df_labels = pd.read_csv('labelled_pairs.csv')

def clean_raw(row):
    return (str(row['title']) + " " + str(row['body'])).lower()

def clean_processed(row):
    text = str(row['body'])
    # Strip Nodal Preambles
    if "NOTICE DETAILS FOLLOW" in text:
        idx = text.find("NOTICE DETAILS FOLLOW")
        after = text[idx:]
        m = re.search(r'-{10,}\s*', after)
        if m:
            text = after[m.end():]
        else:
            text = after[len("NOTICE DETAILS FOLLOW"):]
    elif "===============================================================================" in text:
        idx = text.find("===============================================================================")
        text = text[idx + len("==============================================================================="):]
    
    # Strip Footers
    if "-------------------------------------------------------------------------------" in text:
        text = text.split("-------------------------------------------------------------------------------")[0]
    if "[entry truncated" in text:
        text = text[:text.find("[entry truncated")]
        
    # Title without administrative wrappers
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

def get_char_ngrams(text, n=5):
    if len(text) < n:
        return set([text])
    return set(text[i:i+n] for i in range(len(text) - n + 1))

def get_unigrams(text):
    return set(text.split())

def jaccard(s1, s2):
    if not s1 or not s2:
        return 0.0
    u = len(s1.union(s2))
    if u == 0:
        return 0.0
    return len(s1.intersection(s2)) / u

print("Pre-cleaning notices...")
raw_texts = {nid: clean_raw(row) for nid, row in df_notices.iterrows()}
proc_texts = {nid: clean_processed(row) for nid, row in df_notices.iterrows()}

configurations = {
    "Raw + Char-5gram": lambda row: get_char_ngrams(raw_texts[row.name], 5),
    "Raw + Word-2gram": lambda row: get_word_ngrams(raw_texts[row.name], 2),
    "Processed + Char-5gram": lambda row: get_char_ngrams(proc_texts[row.name], 5),
    "Processed + Word-1gram": lambda row: get_unigrams(proc_texts[row.name]),
    "Processed + Word-2gram": lambda row: get_word_ngrams(proc_texts[row.name], 2),
    "Processed + Word-3gram": lambda row: get_word_ngrams(proc_texts[row.name], 3),
}

# Example pairs
# Pair 1: Same (N010018, N010020) - P004 (nodal) and P008 (non-nodal)
# Pair 2: Different (N007876, N008565) - P001 and P006 (both nodal aggregators)
same_pair = ('N010018', 'N010020')
diff_pair = ('N007876', 'N008565')

print("\n=== SPECIFIC PAIR COMPARISON ===")
for name, shingle_fn in configurations.items():
    s_same_a = shingle_fn(df_notices.loc[same_pair[0]])
    s_same_b = shingle_fn(df_notices.loc[same_pair[1]])
    j_same = jaccard(s_same_a, s_same_b)
    
    s_diff_a = shingle_fn(df_notices.loc[diff_pair[0]])
    s_diff_b = shingle_fn(df_notices.loc[diff_pair[1]])
    j_diff = jaccard(s_diff_a, s_diff_b)
    
    print(f"[{name}]")
    print(f"  SAME pair {same_pair}: Jaccard = {j_same:.4f}")
    print(f"  DIFF pair {diff_pair}: Jaccard = {j_diff:.4f}")
    print(f"  Separation (Same - Diff): {j_same - j_diff:.4f}")

# Now evaluate on all 900 labelled pairs
print("\n=== EVALUATION ACROSS ALL 900 LABELED PAIRS ===")
labels = df_labels['label'].values
is_same = (labels == 'same')

for name, shingle_fn in configurations.items():
    t0 = time.time()
    # Cache shingles for the notices in labelled pairs
    needed_ids = set(df_labels['notice_id_a']).union(set(df_labels['notice_id_b']))
    shingles = {nid: shingle_fn(df_notices.loc[nid]) for nid in needed_ids}
    
    scores = []
    for _, row in df_labels.iterrows():
        s_a = shingles[row['notice_id_a']]
        s_b = shingles[row['notice_id_b']]
        scores.append(jaccard(s_a, s_b))
    scores = np.array(scores)
    t_elapsed = time.time() - t0
    
    same_scores = scores[is_same]
    diff_scores = scores[~is_same]
    
    mean_shingle_size = np.mean([len(s) for s in shingles.values()])
    
    # Overlap / Separation
    # Best threshold by F1
    best_f1, best_th = 0, 0
    for th in np.linspace(0.01, 0.99, 99):
        pred_same = (scores >= th)
        tp = np.sum(pred_same & is_same)
        fp = np.sum(pred_same & ~is_same)
        fn = np.sum(~pred_same & is_same)
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        if f1 > best_f1:
            best_f1 = f1
            best_th = th
            
    print(f"\nConfiguration: {name}")
    print(f"  Avg Shingles per notice: {mean_shingle_size:.1f}")
    print(f"  Same pairs   (N={len(same_scores)}): min={same_scores.min():.3f}, mean={same_scores.mean():.3f}, max={same_scores.max():.3f}")
    print(f"  Diff pairs   (N={len(diff_scores)}): min={diff_scores.min():.3f}, mean={diff_scores.mean():.3f}, max={diff_scores.max():.3f}")
    print(f"  Max Diff vs Min Same: Max(Diff)={diff_scores.max():.3f}, Min(Same)={same_scores.min():.3f}")
    print(f"  Best F1: {best_f1:.4f} at Threshold: {best_th:.2f}")
    print(f"  Time to compute 900 pairs: {t_elapsed*1000:.1f} ms")
