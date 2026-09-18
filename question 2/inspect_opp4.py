import duckdb

con = duckdb.connect()
df = con.execute("""
    SELECT n.notice_id, n.portal_id, c.copy_index, c.is_corrigendum, c.archetype, n.title, n.estimated_value, n.closing_date, n.body
    FROM 'notices/*.csv' n
    JOIN '_truth/clusters.csv' c ON n.notice_id = c.notice_id
    WHERE c.cluster_id = 'OPP000004'
    ORDER BY c.copy_index
""").df()

for i, row in df.iterrows():
    print(f"--- Notice {row['notice_id']} (portal {row['portal_id']}, copy {row['copy_index']}, corrigendum={row['is_corrigendum']}, arch={row['archetype']}) ---")
    print("Title:", row['title'])
    print("Est Value:", row['estimated_value'])
    print("Closing Date:", row['closing_date'])
    print("Body length:", len(row['body']))
    print("Body[:400]:\n", repr(row['body'][:400]))
    print("Body[-200:]:\n", repr(row['body'][-200:]))
