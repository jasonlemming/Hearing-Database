#!/usr/bin/env python3
import psycopg2

crs_url = "postgresql://neondb_owner:npg_DNVrM41GvKqI@ep-gentle-meadow-ad0eg6o9-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

conn = psycopg2.connect(crs_url)
cur = conn.cursor()

# Check products table schema
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'products'
    ORDER BY ordinal_position
""")
print("CRS products table columns:")
for row in cur.fetchall():
    print(f"  {row[0]:30} {row[1]}")

# Check if it's a view or table
cur.execute("""
    SELECT table_type
    FROM information_schema.tables
    WHERE table_name = 'products'
""")
table_type = cur.fetchone()[0]
print(f"\nproducts is a: {table_type}")

cur.close()
conn.close()
