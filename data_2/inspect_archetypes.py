import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT c.archetype, n.notice_id, n.portal_id, n.title, n.body 
    FROM 'notices/*.csv' n
    JOIN '_truth/clusters.csv' c ON n.notice_id = c.notice_id
    QUALIFY ROW_NUMBER() OVER (PARTITION BY c.archetype ORDER BY n.notice_id) = 1
""").df()

for i, row in df.iterrows():
    print(f"================ Archetype: {row['archetype']} ({row['notice_id']}, {row['portal_id']}) ================")
    print("Title:", row['title'])
    print("Body[:500]:\n", row['body'][:500])
