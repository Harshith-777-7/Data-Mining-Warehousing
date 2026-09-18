import duckdb

con = duckdb.connect()
df = con.execute("SELECT notice_id, portal_id, body FROM 'notices/*.csv' WHERE portal_id IN ('P001', 'P002', 'P005') LIMIT 3").df()

for i, row in df.iterrows():
    print(f"================ Notice {row['notice_id']} ({row['portal_id']}) Full Body ================")
    print(row['body'][:1800])
    print("... [TAIL] ...")
    print(row['body'][-500:])
