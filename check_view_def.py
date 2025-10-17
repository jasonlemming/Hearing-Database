#!/usr/bin/env python3
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Get full view definition for product_versions
cur.execute("""
    SELECT view_definition
    FROM information_schema.views
    WHERE table_schema = 'public'
    AND table_name = 'product_versions'
""")

view_def = cur.fetchone()[0]
print("product_versions view definition:")
print(view_def)

cur.close()
conn.close()
