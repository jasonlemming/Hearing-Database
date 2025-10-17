#!/usr/bin/env python3
"""Fix authors sequence that's out of sync"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Policy Library database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

# Check current max author_id
cur.execute("SELECT MAX(author_id) FROM authors")
max_id = cur.fetchone()[0]
print(f"Current max author_id: {max_id}")

# Check current sequence value
cur.execute("SELECT last_value FROM authors_author_id_seq")
seq_val = cur.fetchone()[0]
print(f"Current sequence value: {seq_val}")

if max_id and seq_val <= max_id:
    # Reset sequence to max_id + 1
    new_val = max_id + 1
    cur.execute(f"SELECT setval('authors_author_id_seq', {new_val}, false)")
    print(f"✓ Reset sequence to {new_val}")
else:
    print("✓ Sequence is already correct")

cur.close()
conn.close()
