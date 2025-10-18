#!/usr/bin/env python3
"""Check if document 325 has TOC in structure_json"""
import psycopg2
import json

# Use direct connection string
DATABASE_URL = 'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require'

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get document 325 version details
cur.execute('''
    SELECT d.document_id, d.document_identifier, d.title,
           dv.structure_json::text
    FROM documents d
    LEFT JOIN document_versions dv ON d.document_id = dv.document_id AND dv.is_current = TRUE
    WHERE d.document_id = 325
''')

result = cur.fetchone()
if result:
    doc_id, identifier, title, structure_json = result
    print(f'Document {doc_id}: {identifier}')
    print(f'Title: {title}\n')

    if structure_json:
        structure = json.loads(structure_json)

        print(f'Structure keys: {list(structure.keys())}')

        if 'toc' in structure:
            toc = structure['toc']
            print(f'\n✓ TOC found with {len(toc)} entries')
            print(f'TOC type: {type(toc)}')
            if toc:
                print(f'\nFirst TOC entry:')
                print(f'  {toc[0]}')
        else:
            print('\n✗ No "toc" key in structure_json')

        print(f'\nChecking template condition:')
        print(f'  has_toc = structure_obj.get("toc", [])|length > 0')
        has_toc = len(structure.get('toc', [])) > 0
        print(f'  Result: {has_toc}')

    else:
        print('No structure_json found')

cur.close()
conn.close()
