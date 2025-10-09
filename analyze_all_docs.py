#!/usr/bin/env python3
"""
Analyze HTML structure of all ingested Brookings documents
"""
import sys
sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.models import get_session, Document
from playwright.sync_api import sync_playwright
import time

def analyze_document_html(url: str, doc_id: int, title: str):
    """Fetch and analyze HTML structure of a document"""
    print(f"\n{'='*80}")
    print(f"Document ID {doc_id}: {title}")
    print(f"URL: {url}")
    print(f"{'='*80}")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()

            # Navigate
            page.goto(url, wait_until='networkidle', timeout=60000)
            time.sleep(3)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)

            html = page.content()
            browser.close()

        # Analyze structure
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Check for 404/error pages
        title_tag = soup.find('title')
        h1_tags = soup.find_all('h1')

        print(f"\nTitle tag: {title_tag.text if title_tag else 'None'}")
        print(f"H1 tags: {[h1.text.strip() for h1 in h1_tags]}")

        # Check for main content selectors
        selectors_to_check = [
            'main',
            'article',
            'div.article-content',
            'div.post-body',
            'div.byo-blocks',
            '.post-content',
            '[role="main"]',
            '.entry-content',
            'div.post-full-content',
            'div.article-body',
            'div[class*="content"]',
            'section.article',
        ]

        print(f"\nContent selector analysis:")
        for selector in selectors_to_check:
            elements = soup.select(selector)
            if elements:
                for i, elem in enumerate(elements[:2]):  # Show first 2 matches
                    word_count = len(elem.get_text().split())
                    print(f"  ✓ {selector} [{i}]: {word_count} words")
                    if word_count > 50:
                        # Show first 200 chars of text
                        text_preview = elem.get_text()[:200].replace('\n', ' ').strip()
                        print(f"    Preview: {text_preview}...")
            else:
                print(f"  ✗ {selector}: Not found")

        # Check body word count
        body = soup.find('body')
        if body:
            body_words = len(body.get_text().split())
            print(f"\nTotal body word count: {body_words}")

        # Look for React components or data attributes
        print(f"\nReact/JS indicators:")
        react_root = soup.find(id='root') or soup.find(id='__next')
        if react_root:
            print(f"  Found React root: {react_root.name}#{react_root.get('id')}")

        data_attrs = soup.find_all(attrs={'data-component': True})
        if data_attrs:
            print(f"  Found {len(data_attrs)} elements with data-component")
            for elem in data_attrs[:5]:
                print(f"    - {elem.name}.{elem.get('class', [])} data-component='{elem.get('data-component')}'")

    except Exception as e:
        print(f"ERROR analyzing document: {e}")
        import traceback
        traceback.print_exc()

def main():
    session = get_session()

    # Get all documents
    documents = session.query(Document).order_by(Document.document_id).all()

    print(f"Analyzing {len(documents)} documents...")

    for doc in documents:
        analyze_document_html(doc.url, doc.document_id, doc.title)
        time.sleep(2)  # Rate limit between requests

    session.close()

if __name__ == '__main__':
    main()
