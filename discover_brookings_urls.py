#!/usr/bin/env python3
"""
Discover Brookings article URLs by web scraping
"""
import sys
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re

sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.models import get_session, Document, Source
from brookings_ingester.ingesters import BrookingsIngester


def discover_articles_from_page(url: str, max_articles: int = 100) -> list:
    """
    Discover article URLs from Brookings using web scraping

    Args:
        url: Starting URL (e.g., research page)
        max_articles: Maximum number of articles to discover

    Returns:
        List of article URLs
    """
    print(f"Discovering articles from: {url}")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        # Navigate to page
        page.goto(url, wait_until='networkidle', timeout=60000)
        time.sleep(3)

        # Scroll to load more content (many sites use lazy loading)
        # Increased from 10 to 30 iterations to load more content
        for i in range(30):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            # Check for "Load More" button
            try:
                load_more = page.locator('button:has-text("Load More"), a:has-text("Load More"), button:has-text("Show More")').first
                if load_more.is_visible(timeout=1000):
                    print(f"Clicking 'Load More' button (iteration {i+1})...")
                    load_more.click()
                    time.sleep(2)
            except:
                pass

        # Get HTML content
        html = page.content()
        browser.close()

    # Parse HTML to extract article URLs
    soup = BeautifulSoup(html, 'lxml')
    article_urls = set()

    # Look for article links with various patterns
    for link in soup.find_all('a', href=True):
        href = link['href']

        # Match Brookings article patterns
        if '/articles/' in href or '/research/' in href or '/essay/' in href or '/report/' in href:
            # Make absolute URL
            if href.startswith('http'):
                full_url = href
            else:
                full_url = urljoin('https://www.brookings.edu', href)

            # Filter out navigation/archive URLs
            if re.match(r'https://www\.brookings\.edu/(articles|research|essay|report|papers)/[a-z0-9-]+/?$', full_url):
                article_urls.add(full_url)

        if len(article_urls) >= max_articles:
            break

    return sorted(list(article_urls))


def get_existing_urls() -> set:
    """Get URLs of documents already in database"""
    session = get_session()
    source = session.query(Source).filter_by(source_code='BROOKINGS').first()

    if not source:
        session.close()
        return set()

    docs = session.query(Document).filter_by(source_id=source.source_id).all()
    urls = {doc.url for doc in docs}
    session.close()

    return urls


def ingest_urls(urls: list, limit: int = 100):
    """
    Ingest documents from URLs

    Args:
        urls: List of URLs to ingest
        limit: Maximum number to ingest
    """
    ingester = BrookingsIngester()

    success = 0
    failed = 0
    skipped = 0

    for i, url in enumerate(urls[:limit], 1):
        try:
            print(f"\n[{i}/{min(len(urls), limit)}] Processing: {url}")

            # Create document metadata
            doc_meta = {
                'document_identifier': ingester._extract_slug(url),
                'url': url
            }

            # Fetch content
            print("  Fetching...")
            content = ingester.fetch(doc_meta)

            if not content:
                print("  ✗ Failed to fetch")
                failed += 1
                continue

            # Parse content
            print("  Parsing...")
            parsed = ingester.parse(doc_meta, content)

            if not parsed:
                print("  ✗ Failed to parse")
                failed += 1
                continue

            # Convert publication_date string to date object if needed
            if parsed.get('publication_date') and isinstance(parsed['publication_date'], str):
                from datetime import datetime
                try:
                    parsed['publication_date'] = datetime.strptime(parsed['publication_date'], '%Y-%m-%d').date()
                except:
                    parsed['publication_date'] = None

            # Store document
            print("  Storing...")
            doc_id = ingester.store(parsed)

            if doc_id:
                word_count = parsed.get('word_count', 0)
                print(f"  ✓ Success: {parsed['title'][:60]}... ({word_count:,} words)")
                success += 1
            else:
                print(f"  ✗ Failed to store")
                failed += 1

            # Rate limiting
            time.sleep(2)

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed += 1
            continue

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  Success:  {success}")
    print(f"  Failed:   {failed}")
    print(f"  Skipped:  {skipped}")
    print(f"  Total:    {len(urls[:limit])}")
    print(f"{'='*60}")


def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description='Discover and ingest Brookings articles')
    parser.add_argument('--discover-only', action='store_true', help='Only discover URLs, do not ingest')
    parser.add_argument('--limit', type=int, default=100, help='Maximum articles to process')
    parser.add_argument('--url', default='https://www.brookings.edu/research/', help='Starting URL for discovery')
    args = parser.parse_args()

    # Discover article URLs
    print("Starting article discovery...")
    discovered_urls = discover_articles_from_page(args.url, max_articles=args.limit * 2)
    print(f"\nDiscovered {len(discovered_urls)} article URLs")

    # Filter out existing documents
    existing_urls = get_existing_urls()
    new_urls = [url for url in discovered_urls if url not in existing_urls]

    print(f"Existing documents: {len(existing_urls)}")
    print(f"New URLs to process: {len(new_urls)}")

    if args.discover_only:
        print("\nNew URLs:")
        for url in new_urls[:args.limit]:
            print(f"  {url}")
        return

    # Ingest new documents
    if new_urls:
        print(f"\nIngesting up to {args.limit} new documents...")
        ingest_urls(new_urls, limit=args.limit)
    else:
        print("\nNo new documents to ingest!")


if __name__ == '__main__':
    main()
