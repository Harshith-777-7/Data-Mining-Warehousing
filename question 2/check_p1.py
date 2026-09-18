import duckdb

con = duckdb.connect()
df = con.execute("SELECT notice_id, portal_id, body FROM 'notices/*.csv' WHERE portal_id IN ('P001', 'P002') LIMIT 5").df()

for i, row in df.iterrows():
    print(f"--- Notice {row['notice_id']} ({row['portal_id']}) ---")
    print(row['body'][:600])
