#!/usr/bin/env python3
import psycopg2

# CRS Products Database
crs_url = "postgresql://neondb_owner:npg_DNVrM41GvKqI@ep-gentle-meadow-ad0eg6o9-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

conn = psycopg2.connect(crs_url)
cur = conn.cursor()

# Check what tables exist
cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")
print("Tables in CRS database:")
tables = []
for row in cur.fetchall():
    tables.append(row[0])
    print(f"  - {row[0]}")

# Check if products table exists
if 'products' in tables:
    cur.execute("SELECT COUNT(*) FROM products")
    count = cur.fetchone()[0]
    print(f"\nTotal products in CRS database: {count}")

    # Sample products
    cur.execute("""
        SELECT product_id, title, status, publication_date
        FROM products
        LIMIT 5
    """)
    print("\nSample products:")
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[2]} - {row[1][:60]}...")

cur.close()
conn.close()
