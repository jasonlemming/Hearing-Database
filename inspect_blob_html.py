#!/usr/bin/env python3
"""Inspect the actual HTML from blob storage for document 307"""
import psycopg2
import json
import requests

DATABASE_URL = 'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require'

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

# Get blob URL for document 307
cur.execute('''
    SELECT dv.structure_json::text
    FROM document_versions dv
    WHERE dv.document_id = 307 AND dv.is_current = TRUE
''')

result = cur.fetchone()
if result:
    structure_json = result[0]
    structure_data = json.loads(structure_json)
    blob_url = structure_data.get('blob_url')

    if blob_url:
        print(f"Fetching from: {blob_url}\n")
        response = requests.get(blob_url, timeout=10)

        if response.status_code == 200:
            html = response.text
            print(f"HTML length: {len(html)} characters\n")

            # Search for TOC div
            import re

            # Look for class="TOC" with various quote styles
            if 'class="TOC"' in html:
                print('✓ Found: class="TOC"')
                match = re.search(r'<div class="TOC"[^>]*>(.*?)</div>', html, re.DOTALL)
                if match:
                    toc_content = match.group(1)
                    print(f'  TOC content length: {len(toc_content)} characters')
                    print(f'  First 500 chars:\n{toc_content[:500]}')
            elif "class='TOC'" in html:
                print("✓ Found: class='TOC'")
            else:
                print("✗ No class=\"TOC\" or class='TOC' found")

                # Look for other TOC indicators
                if '<div class="TOC' in html:
                    print("  But found: <div class=\"TOC (with additional classes)")
                    # Find all TOC divs
                    toc_divs = re.findall(r'<div class="TOC[^"]*"[^>]*>', html)
                    for toc_div in toc_divs[:3]:
                        print(f"    {toc_div}")

            # Also check what the template sees
            print(f"\n\nTemplate checks:")
            check1 = 'class="TOC"' in html
            check2 = "class='TOC'" in html
            print(f"  'class=\"TOC\"' in html: {check1}")
            print(f"  \"class='TOC'\" in html: {check2}")

            # Try to find the TOC section
            print(f"\n\nSearching for TOC-related content:")
            if '<h1>Contents</h1>' in html:
                print(f"  ✓ Found <h1>Contents</h1>")
            if 'Table of Contents' in html:
                print(f"  ✓ Found 'Table of Contents'")

            # Get a snippet around the first occurrence of "Contents"
            idx = html.find('<h1>Contents</h1>')
            if idx != -1:
                snippet = html[max(0, idx-200):idx+1000]
                print(f"\n\nContext around <h1>Contents</h1>:")
                print(snippet)

cur.close()
conn.close()
