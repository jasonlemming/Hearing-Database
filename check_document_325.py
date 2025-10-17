#!/usr/bin/env python3
"""Check document 325 structure and HTML content"""
import psycopg2
import os
import json
import requests

# Use direct connection string
DATABASE_URL = 'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require'

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get document 325 details
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
    print(f'Title: {title}')

    if structure_json:
        structure = json.loads(structure_json)
        blob_url = structure.get('blob_url')

        if blob_url:
            print(f'\nFetching HTML from: {blob_url[:60]}...')

            # Fetch the HTML content
            response = requests.get(blob_url, timeout=10)
            if response.status_code == 200:
                html = response.text
                print(f'\nHTML length: {len(html)} characters')

                # Look for image references
                if 'image' in html.lower():
                    print('\nImage references found:')
                    lines_with_images = [line.strip() for line in html.split('\n') if 'image' in line.lower()]
                    for i, line in enumerate(lines_with_images[:5]):
                        print(f'  {i+1}. {line[:120]}...' if len(line) > 120 else f'  {i+1}. {line}')

                # Look for img tags
                if '<img' in html:
                    print('\n<img> tags found')
                    import re
                    img_tags = re.findall(r'<img[^>]+>', html)
                    for i, tag in enumerate(img_tags[:3]):
                        print(f'  {i+1}. {tag}')
                else:
                    print('\nNo <img> tags found in HTML')

                # Check for markdown image syntax
                if '![' in html:
                    print('\nMarkdown image syntax found: ![...](...)')

        else:
            print('\nNo blob_url in structure_json')

cur.close()
conn.close()
