import duckdb
import pandas as pd
import re
from collections import Counter

con = duckdb.connect()
df = con.execute("SELECT notice_id, portal_id, title, body, estimated_value, closing_date FROM 'notices/*.csv'").df()

print("Total notices:", len(df))
print("Portals count:", df['portal_id'].nunique())

# Check nodal notices
nodal_portals = ['P001', 'P002', 'P003', 'P004', 'P005', 'P006']
df_nodal = df[df['portal_id'].isin(nodal_portals)]
print(f"Nodal notices ({nodal_portals}):", len(df_nodal))

# Check the preambles mentioned in portal_profiles.md:
# P001, P002, P005: "NATIONAL PROCUREMENT AGGREGATION SERVICE"
# P003, P004, P006: "STATE PROCUREMENT CELL"
for p in ['P001', 'P002', 'P003', 'P004', 'P005', 'P006']:
    sample = df[df['portal_id'] == p]['body'].iloc[0]
    first_line = sample.split('\n')[0]
    print(f"Portal {p} sample first line: {repr(first_line)}")

# Let's inspect the boilerplate text lengths and exact common prefixes/substrings
p1_bodies = df[df['portal_id'] == 'P001']['body'].tolist()
p3_bodies = df[df['portal_id'] == 'P003']['body'].tolist()

# Find common prefix length
def common_prefix(s1, s2):
    i = 0
    while i < min(len(s1), len(s2)) and s1[i] == s2[i]:
        i += 1
    return s1[:i]

p1_common = p1_bodies[0]
for b in p1_bodies[1:20]:
    p1_common = common_prefix(p1_common, b)
print(f"\nP001 common prefix length: {len(p1_common)}")
print(f"P001 common prefix preview:\n{p1_common[:300]}...\n{p1_common[-200:]}")

p3_common = p3_bodies[0]
for b in p3_bodies[1:20]:
    p3_common = common_prefix(p3_common, b)
print(f"\nP003 common prefix length: {len(p3_common)}")
print(f"P003 common prefix preview:\n{p3_common[:300]}...\n{p3_common[-200:]}")
