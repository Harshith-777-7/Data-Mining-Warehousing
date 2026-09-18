import duckdb

con = duckdb.connect()
res = con.execute("""
    SELECT estimated_value, COUNT(DISTINCT c.cluster_id) as num_clusters, COUNT(*) as num_notices
    FROM 'notices/*.csv' n
    JOIN '_truth/clusters.csv' c ON n.notice_id = c.notice_id
    GROUP BY estimated_value
    ORDER BY num_clusters DESC
    LIMIT 10
""").df()
print("Top shared estimated values across clusters:\n", res)

total_clusters = con.execute("SELECT COUNT(DISTINCT cluster_id) FROM '_truth/clusters.csv'").fetchone()[0]
unique_values = con.execute("SELECT COUNT(DISTINCT estimated_value) FROM 'notices/*.csv'").fetchone()[0]
print(f"Total clusters: {total_clusters}, Unique estimated_values: {unique_values}")
