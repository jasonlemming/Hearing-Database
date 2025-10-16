#!/usr/bin/env python3
"""
Migrate Policy Library data from SQLite to PostgreSQL (production database)

Usage:
    python migrate_policy_library.py            # Migrate all data
    python migrate_policy_library.py --limit 5  # Test with first 5 documents
"""
import sqlite3
import os
import sys
import argparse
from database.postgres_config import get_direct_connection

def truncate_field(value, max_length):
    """Truncate a field to max_length, adding ... if truncated"""
    if value is None:
        return None
    if len(value) <= max_length:
        return value
    return value[:max_length-3] + '...'

def migrate(limit=None):
    # Connect to SQLite
    print("Connecting to SQLite database...")
    sqlite_conn = sqlite3.connect('/tmp/brookings_products.db')
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    # Connect to PostgreSQL
    print("Connecting to PostgreSQL database...")
    pg_conn = get_direct_connection()
    pg_cur = pg_conn.cursor()

    limit_msg = f" (LIMIT {limit} documents)" if limit else " (ALL documents)"
    print(f"Starting migration{limit_msg}...")

    try:
        # 1. Migrate organizations
        print('\n[1/6] Migrating organizations...')
        sqlite_cur.execute('SELECT * FROM organizations')
        orgs = sqlite_cur.fetchall()
        for row in orgs:
            values = list(row)
            # Truncate fields
            values[1] = truncate_field(values[1], 200)  # name
            values[2] = truncate_field(values[2], 100)  # short_name
            values[3] = truncate_field(values[3], 50)   # organization_type
            values[4] = truncate_field(values[4], 500)  # url

            pg_cur.execute('''
                INSERT INTO organizations (organization_id, name, short_name, organization_type, url, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    short_name = EXCLUDED.short_name,
                    organization_type = EXCLUDED.organization_type,
                    url = EXCLUDED.url
            ''', values)
        print(f'  ✓ Migrated {len(orgs)} organizations')

        # 2. Migrate subjects
        print('\n[2/6] Migrating subjects...')
        sqlite_cur.execute('SELECT * FROM subjects ORDER BY subject_id')
        subjects = sqlite_cur.fetchall()
        for row in subjects:
            values = list(row)
            values[1] = truncate_field(values[1], 200)  # name
            values[4] = truncate_field(values[4], 50)   # source_vocabulary

            pg_cur.execute('''
                INSERT INTO subjects (subject_id, name, parent_subject_id, description, source_vocabulary, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET
                    parent_subject_id = EXCLUDED.parent_subject_id,
                    description = EXCLUDED.description,
                    source_vocabulary = EXCLUDED.source_vocabulary
            ''', values)
        print(f'  ✓ Migrated {len(subjects)} subjects')

        # 3. Migrate authors
        print('\n[3/6] Migrating authors...')
        sqlite_cur.execute('SELECT * FROM authors')
        authors = sqlite_cur.fetchall()
        for row in authors:
            values = list(row)
            # Truncate fields that might be too long
            values[1] = truncate_field(values[1], 200)  # full_name
            values[2] = truncate_field(values[2], 100)  # first_name
            values[3] = truncate_field(values[3], 100)  # last_name
            values[5] = truncate_field(values[5], 200)  # email
            values[6] = truncate_field(values[6], 50)   # orcid

            pg_cur.execute('''
                INSERT INTO authors (author_id, full_name, first_name, last_name, organization_id, email, orcid, bio, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (author_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    organization_id = EXCLUDED.organization_id,
                    email = EXCLUDED.email,
                    orcid = EXCLUDED.orcid,
                    bio = EXCLUDED.bio
            ''', values)
        print(f'  ✓ Migrated {len(authors)} authors')

        # 4. Migrate documents (with optional limit)
        print(f'\n[4/6] Migrating documents{limit_msg}...')
        if limit:
            sqlite_cur.execute('SELECT * FROM documents LIMIT ?', (limit,))
        else:
            sqlite_cur.execute('SELECT * FROM documents')
        documents = sqlite_cur.fetchall()

        document_ids = []  # Track migrated document IDs for junction tables
        for row in documents:
            document_ids.append(row[0])  # document_id is first column
            values = list(row)
            # Truncate fields that might be too long for PostgreSQL schema
            # document_id, source_id, document_identifier, title, document_type, status,
            # publication_date, summary, full_text, url, pdf_url, page_count, word_count,
            # checksum, metadata_json, created_at, updated_at
            values[2] = truncate_field(values[2], 100)  # document_identifier
            values[4] = truncate_field(values[4], 50)   # document_type
            values[5] = truncate_field(values[5], 20)   # status
            values[9] = truncate_field(values[9], 500)  # url
            values[10] = truncate_field(values[10], 500)  # pdf_url
            values[13] = truncate_field(values[13], 64)  # checksum

            pg_cur.execute('''
                INSERT INTO documents (document_id, source_id, document_identifier, title, document_type, status,
                                       publication_date, summary, full_text, url, pdf_url, page_count, word_count,
                                       checksum, metadata_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_id, document_identifier) DO UPDATE SET
                    title = EXCLUDED.title,
                    document_type = EXCLUDED.document_type,
                    status = EXCLUDED.status,
                    publication_date = EXCLUDED.publication_date,
                    summary = EXCLUDED.summary,
                    full_text = EXCLUDED.full_text,
                    url = EXCLUDED.url,
                    pdf_url = EXCLUDED.pdf_url,
                    page_count = EXCLUDED.page_count,
                    word_count = EXCLUDED.word_count,
                    checksum = EXCLUDED.checksum,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = EXCLUDED.updated_at
            ''', values)
        print(f'  ✓ Migrated {len(documents)} documents')

        # 5. Migrate document_authors (only for migrated documents)
        print(f'\n[5/6] Migrating document_authors...')
        if document_ids:
            placeholders = ','.join('?' * len(document_ids))
            sqlite_cur.execute(f'SELECT * FROM document_authors WHERE document_id IN ({placeholders})', document_ids)
        else:
            sqlite_cur.execute('SELECT * FROM document_authors')
        doc_authors = sqlite_cur.fetchall()
        for row in doc_authors:
            pg_cur.execute('''
                INSERT INTO document_authors (document_id, author_id, author_order, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', tuple(row))
        print(f'  ✓ Migrated {len(doc_authors)} document_authors')

        # 6. Migrate document_subjects (only for migrated documents)
        print(f'\n[6/6] Migrating document_subjects...')
        if document_ids:
            placeholders = ','.join('?' * len(document_ids))
            sqlite_cur.execute(f'SELECT * FROM document_subjects WHERE document_id IN ({placeholders})', document_ids)
        else:
            sqlite_cur.execute('SELECT * FROM document_subjects')
        doc_subjects = sqlite_cur.fetchall()
        for row in doc_subjects:
            pg_cur.execute('''
                INSERT INTO document_subjects (document_id, subject_id, relevance_score)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
            ''', tuple(row))
        print(f'  ✓ Migrated {len(doc_subjects)} document_subjects')

        pg_conn.commit()
        print('\n✅ Policy Library data migration to PRODUCTION database complete!')
        print(f'\nMigrated:')
        print(f'  • {len(orgs)} organizations')
        print(f'  • {len(subjects)} subjects')
        print(f'  • {len(authors)} authors')
        print(f'  • {len(documents)} documents')
        print(f'  • {len(doc_authors)} document-author relationships')
        print(f'  • {len(doc_subjects)} document-subject relationships')

    except Exception as e:
        print(f'\n✗ Migration failed: {e}')
        print(f'   Rolling back all changes...')
        pg_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate Policy Library data from SQLite to PostgreSQL')
    parser.add_argument('--limit', type=int, help='Limit number of documents to migrate (for testing)')
    args = parser.parse_args()

    migrate(limit=args.limit)
