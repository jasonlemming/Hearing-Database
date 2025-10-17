#!/usr/bin/env python3
"""Fix all sequences that are out of sync"""
import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

# Policy Library database
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

# Tables with auto-increment IDs
tables = [
    ('documents', 'document_id', 'documents_document_id_seq'),
    ('authors', 'author_id', 'authors_author_id_seq'),
    ('subjects', 'subject_id', 'subjects_subject_id_seq'),
    ('sources', 'source_id', 'sources_source_id_seq'),
    ('organizations', 'organization_id', 'organizations_organization_id_seq'),
    ('document_versions', 'version_id', 'document_versions_version_id_seq'),
    ('document_files', 'file_id', 'document_files_file_id_seq'),
    ('ingestion_logs', 'log_id', 'ingestion_logs_log_id_seq'),
    ('ingestion_errors', 'error_id', 'ingestion_errors_error_id_seq'),
]

print("Checking and fixing sequences...\n")

for table_name, id_column, seq_name in tables:
    # Check current max ID
    cur.execute(f"SELECT MAX({id_column}) FROM {table_name}")
    max_id = cur.fetchone()[0]

    # Check current sequence value
    cur.execute(f"SELECT last_value FROM {seq_name}")
    seq_val = cur.fetchone()[0]

    print(f"{table_name}:")
    print(f"  Max {id_column}: {max_id}")
    print(f"  Sequence value: {seq_val}")

    if max_id and seq_val <= max_id:
        # Reset sequence to max_id + 1
        new_val = max_id + 1
        cur.execute(f"SELECT setval('{seq_name}', {new_val}, false)")
        print(f"  ✓ Reset sequence to {new_val}")
    else:
        print(f"  ✓ Sequence is correct")
    print()

cur.close()
conn.close()

print("✓ All sequences checked and fixed!")
