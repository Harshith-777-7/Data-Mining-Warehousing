import duckdb
import pandas as pd
import numpy as np
import re

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv'").df().set_index('notice_id')
df_labels = pd.read_csv('labelled_pairs.csv')

# Let's inspect the boilerplate patterns across all portals
# Nodal preambles:
# P001, P002, P005: "GOVERNMENT OF INDIA -- NATIONAL PROCUREMENT AGGREGATION SERVICE ... NOTICE DETAILS FOLLOW\n---..."
# P003, P004, P006: "STATE PROCUREMENT CELL -- CONSOLIDATED TENDER BULLETIN ... ===============================================================================\n\nName of work:"

def clean_notice_raw(row):
    # Competing Choice A: Naive / Raw text
    return (str(row['title']) + " " + str(row['body'])).lower()

def clean_notice_processed(row):
    # Competing Choice B: Normalized, stripped signal text
    text = str(row['body'])
    
    # 1. Strip Nodal Preambles
    if "NOTICE DETAILS FOLLOW" in text:
        idx = text.find("NOTICE DETAILS FOLLOW")
        # jump past the dashes
        after = text[idx:]
        m = re.search(r'-{10,}\s*', after)
        if m:
            text = after[m.end():]
        else:
            text = after[len("NOTICE DETAILS FOLLOW"):]
    elif "===============================================================================" in text:
        idx = text.find("===============================================================================")
        text = text[idx + len("==============================================================================="):]
    
    # 2. Strip Footers
    # Disclaimer footer or truncation footer
    if "-------------------------------------------------------------------------------" in text:
        # Check for disclaimer
        parts = text.split("-------------------------------------------------------------------------------")
        # Usually last part is disclaimer
        text = parts[0]
    if "[entry truncated" in text:
        idx = text.find("[entry truncated")
        text = text[:idx]
    
    # 3. Add title (without generic prefixes like NIT for, e-Tender, Tender Notice, Corrigendum)
    title = str(row['title'])
    title = re.sub(r'^(nit for|e-tender\s*-?|tender notice:?|corrigendum\s*-?|\s*)+', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\[[a-z0-9/_-]+\]', '', title, flags=re.IGNORECASE) # strip ref code in brackets e.g. [MUNI/2025/98454]
    
    # Combine title + body
    full = title + " " + text
    
    # 4. Remove reference numbers pattern: "Tender reference number: ...\n"
    full = re.sub(r'tender reference number:[^\n]+', '', full, flags=re.IGNORECASE)
    # Remove dates inside text: e.g. dd-mm-yyyy, yyyy-mm-dd, 12 Mar 2024 etc.
    full = re.sub(r'\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b', '', full)
    full = re.sub(r'\b\d{4}[-/.]\d{1,2}[-/.]\d{1,2}\b', '', full)
    full = re.sub(r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4}\b', '', full, flags=re.IGNORECASE)
    
    # Lowercase and clean non-alphanumeric (keep spaces)
    full = re.sub(r'[^a-z0-9\s]', ' ', full.lower())
    full = re.sub(r'\s+', ' ', full).strip()
    return full

# Shingling methods:
# 1. Word n-grams
def get_word_ngrams(text, n=2):
    tokens = text.split()
    if len(tokens) < n:
        return set(tokens)
    return set(' '.join(tokens[i:i+n]) for i in range(len(tokens) - n + 1))

# 2. Character n-grams
def get_char_ngrams(text, n=5):
    if len(text) < n:
        return set([text])
    return set(text[i:i+n] for i in range(len(text) - n + 1))

# Jaccard similarity
def jaccard(s1, s2):
    if not s1 or not s2:
        return 0.0
    u = len(s1.union(s2))
    if u == 0:
        return 0.0
    return len(s1.intersection(s2)) / u

print("Testing pre-processing and shingling on sample pairs...")
