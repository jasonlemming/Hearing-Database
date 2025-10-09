#!/usr/bin/env python3
"""
Backfill publication dates for existing Brookings documents
"""
import sys
import time
from datetime import datetime
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

def backfill_dates():
    """Fetch and update publication dates for documents without dates"""

    session = get_session()
    parser = BrookingsHTMLParser()

    # Get documents without publication dates
    documents = session.query(Document).filter(
        Document.publication_date.is_(None),
        ~Document.title.like('Page not found%')
    ).all()

    print(f"Found {len(documents)} documents without dates")

    updated = 0
    failed = 0

    for doc in documents:
        try:
            print(f"\nProcessing: {doc.title[:60]}...")
            print(f"  URL: {doc.url}")

            # Fetch HTML with Playwright
            html_content = fetch_with_browser(doc.url)

            # Parse HTML for date
            soup = BeautifulSoup(html_content, 'lxml')
            publication_date = parser._extract_date(soup)

            if publication_date:
                # Convert string to date object (YYYY-MM-DD format)
                date_obj = datetime.strptime(publication_date, '%Y-%m-%d').date()

                # Update database
                doc.publication_date = date_obj
                session.commit()
                print(f"  ✓ Updated with date: {publication_date}")
                updated += 1
            else:
                print(f"  ✗ Could not extract date")
                failed += 1

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
            continue

    session.close()

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Updated: {updated}")
    print(f"  Failed:  {failed}")
    print(f"  Total:   {len(documents)}")
    print(f"{'='*60}")

if __name__ == '__main__':
    backfill_dates()
