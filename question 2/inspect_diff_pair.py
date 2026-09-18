import duckdb
import pandas as pd

con = duckdb.connect()
df_notices = con.execute("SELECT * FROM 'notices/*.csv' WHERE notice_id IN ('N007876', 'N008565')").df().set_index('notice_id')

print("--- N007876 ---")
print("Portal:", df_notices.loc['N007876', 'portal_id'])
print("Title:", df_notices.loc['N007876', 'title'])
print("Est val:", df_notices.loc['N007876', 'estimated_value'])
print("Body:\n", df_notices.loc['N007876', 'body'])

print("\n--- N008565 ---")
print("Portal:", df_notices.loc['N008565', 'portal_id'])
print("Title:", df_notices.loc['N008565', 'title'])
print("Est val:", df_notices.loc['N008565', 'estimated_value'])
print("Body:\n", df_notices.loc['N008565', 'body'])
