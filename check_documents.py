#!/usr/bin/env python3
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Check what documents exist (using the view)
cur.execute("SELECT COUNT(*) FROM products")
product_count = cur.fetchone()[0]
print(f"Total products (via view): {product_count}")

# Check documents table directly
cur.execute("SELECT COUNT(*) FROM documents")
doc_count = cur.fetchone()[0]
print(f"Total documents (direct): {doc_count}")

# Check document sources
cur.execute("""
    SELECT s.source_code, s.name, COUNT(d.document_id) as doc_count
    FROM sources s
    LEFT JOIN documents d ON s.source_id = d.source_id
    GROUP BY s.source_id, s.source_code, s.name
    ORDER BY s.source_code
""")
print("\nDocuments by source:")
for row in cur.fetchall():
    print(f"  {row[0]:15} {row[1]:40} {row[2]:>5} docs")

cur.close()
conn.close()
