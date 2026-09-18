import duckdb
import pandas as pd

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv'").df().set_index('notice_id')
df_clusters = pd.read_csv('_truth/clusters.csv').set_index('notice_id')
df_labels = pd.read_csv('labelled_pairs.csv')

# Check consistency between labelled_pairs and clusters.csv
mismatches = 0
for idx, row in df_labels.iterrows():
    c_a = df_clusters.loc[row['notice_id_a'], 'cluster_id']
    c_b = df_clusters.loc[row['notice_id_b'], 'cluster_id']
    true_same = (c_a == c_b)
    label_same = (row['label'] == 'same')
    if true_same != label_same:
        mismatches += 1

print(f"Total labelled pairs: {len(df_labels)}, Mismatches with clusters.csv: {mismatches}")

# Let's inspect some labelled pairs: same vs different
print("\n--- Example 'same' pair ---")
same_row = df_labels[df_labels['label'] == 'same'].iloc[0]
a_id = same_row['notice_id_a']
b_id = same_row['notice_id_b']
print(f"A ({a_id}, portal={df_notices.loc[a_id, 'portal_id']}, val={df_notices.loc[a_id, 'estimated_value']}):")
print("Title:", df_notices.loc[a_id, 'title'])
print("Body[:300]:", repr(df_notices.loc[a_id, 'body'][:300]))
print(f"\nB ({b_id}, portal={df_notices.loc[b_id, 'portal_id']}, val={df_notices.loc[b_id, 'estimated_value']}):")
print("Title:", df_notices.loc[b_id, 'title'])
print("Body[:300]:", repr(df_notices.loc[b_id, 'body'][:300]))

print("\n--- Example 'different' pair ---")
diff_row = df_labels[df_labels['label'] == 'different'].iloc[0]
a_id = diff_row['notice_id_a']
b_id = diff_row['notice_id_b']
print(f"A ({a_id}, portal={df_notices.loc[a_id, 'portal_id']}, val={df_notices.loc[a_id, 'estimated_value']}):")
print("Title:", df_notices.loc[a_id, 'title'])
print("Body[:300]:", repr(df_notices.loc[a_id, 'body'][:300]))
print(f"\nB ({b_id}, portal={df_notices.loc[b_id, 'portal_id']}, val={df_notices.loc[b_id, 'estimated_value']}):")
print("Title:", df_notices.loc[b_id, 'title'])
print("Body[:300]:", repr(df_notices.loc[b_id, 'body'][:300]))
