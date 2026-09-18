import duckdb

con = duckdb.connect()
res = con.execute("""
    SELECT 
        c.cluster_id,
        COUNT(*) as cluster_size,
        COUNT(DISTINCT n.estimated_value) as distinct_values
    FROM 'notices/*.csv' n
    JOIN '_truth/clusters.csv' c ON n.notice_id = c.notice_id
    GROUP BY c.cluster_id
    HAVING COUNT(*) > 1
""").df()

print("Clusters with size > 1:", len(res))
print("Clusters where distinct estimated_value == 1:", (res['distinct_values'] == 1).sum())
print("Clusters where distinct estimated_value > 1:", (res['distinct_values'] > 1).sum())
