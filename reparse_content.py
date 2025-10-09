#!/usr/bin/env python3
"""
Re-parse existing Brookings documents with improved parser
"""
import sys
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.models import get_session, Document
from brookings_ingester.ingesters.utils.html_parser import BrookingsHTMLParser

def fetch_with_browser(url: str) -> str:
    """Fetch HTML using Playwright to bypass Cloudflare"""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # Navigate and wait for content
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(3)  # Wait for dynamic content

        html_content = page.content()
        browser.close()

        return html_content

def reparse_documents(limit=None):
    """Re-fetch and re-parse document content with improved parser"""
    import re

    session = get_session()
    parser = BrookingsHTMLParser()

    # Get documents to re-parse (excluding 404s)
    query = session.query(Document).filter(
        ~Document.title.like('Page not found%')
    )

    if limit:
        query = query.limit(limit)

    documents = query.all()

    print(f"Found {len(documents)} documents to re-parse")
    if limit:
        print(f"(Limited to {limit} for testing)")
    print()

    updated = 0
    failed = 0
    total_figures = 0
    total_charts = 0
    total_tables = 0

    for i, doc in enumerate(documents, 1):
        try:
            old_word_count = doc.word_count or 0

            print(f"[{i}/{len(documents)}] {doc.title[:60]}...")
            print(f"  URL: {doc.url}")

            # Fetch HTML with Playwright
            html_content = fetch_with_browser(doc.url)

            # Parse HTML
            soup = BeautifulSoup(html_content, 'lxml')

            # Extract text with improved parser
            content_soup = parser._extract_content_area(soup)
            if content_soup:
                new_text = parser._extract_text(content_soup)
                new_word_count = len(new_text.split())

                # Count extracted elements
                figures = len(re.findall(r'\[FIGURE[^\]]*\]', new_text))
                charts = len(re.findall(r'\[Interactive chart:', new_text))
                tables = len(re.findall(r'\[TABLE\]', new_text))

                # Update database
                doc.full_text = new_text
                doc.word_count = new_word_count
                session.commit()

                # Track totals
                total_figures += figures
                total_charts += charts
                total_tables += tables

                # Show results
                word_diff = new_word_count - old_word_count
                word_change = f"+{word_diff:,}" if word_diff > 0 else f"{word_diff:,}"
                print(f"  ✓ Updated: {new_word_count:,} words (was {old_word_count:,}, {word_change})")
                if figures > 0 or charts > 0 or tables > 0:
                    print(f"    Extracted: {figures} figures, {charts} charts, {tables} tables")
                updated += 1
            else:
                print(f"  ✗ Could not extract content")
                failed += 1

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
            session.rollback()
            continue

    session.close()

    print(f"\n{'='*60}")
    print(f"Reparse Results:")
    print(f"  Updated:  {updated}")
    print(f"  Failed:   {failed}")
    print(f"  Total:    {len(documents)}")
    print(f"\nContent Extracted:")
    print(f"  Figures:  {total_figures}")
    print(f"  Charts:   {total_charts}")
    print(f"  Tables:   {total_tables}")
    print(f"{'='*60}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Re-parse Brookings documents')
    parser.add_argument('--limit', type=int, help='Limit number of documents to process (for testing)')
    args = parser.parse_args()

    reparse_documents(limit=args.limit)
