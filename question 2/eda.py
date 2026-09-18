import duckdb
import pandas as pd
import json

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv'").df()
print("Notices shape:", df_notices.shape)
print("Columns:", df_notices.columns.tolist())
print("Notice ID count unique:", df_notices['notice_id'].nunique())

df_labels = pd.read_csv('labelled_pairs.csv')
print("\nLabels shape:", df_labels.shape)
print("Labels counts:\n", df_labels['label'].value_counts())

# Truth json
with open('_truth/truth.json') as f:
    truth = json.load(f)
print("\nTruth json:")
for k, v in truth.items():
    if k != 'cluster_size_hist':
        print(f"  {k}: {v}")

# Clusters
df_clusters = pd.read_csv('_truth/clusters.csv')
print("\nClusters shape:", df_clusters.shape)
print(df_clusters.head(5))
print("Archetype counts:\n", df_clusters['archetype'].value_counts())
