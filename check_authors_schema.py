#!/usr/bin/env python3
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'authors' ORDER BY ordinal_position
""")
print("authors table columns:")
for row in cur.fetchall():
    print(f"  - {row[0]}")
cur.close()
conn.close()
