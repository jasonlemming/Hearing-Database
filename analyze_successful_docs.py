#!/usr/bin/env python3
"""
Deep analysis of successfully parsed Brookings documents to identify structural patterns
"""
import sys
sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.models import get_session, Document
from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup

def deep_analyze_document(url: str, doc_id: int, title: str, word_count: int):
    """Deep structural analysis of a successfully parsed document"""
    print(f"\n{'='*100}")
    print(f"Doc ID {doc_id}: {title[:80]}")
    print(f"URL: {url}")
    print(f"Stored Word Count: {word_count}")
    print(f"{'='*100}")

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.goto(url, wait_until='networkidle', timeout=60000)
            time.sleep(3)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, 'lxml')

        # Check main content structure
        main = soup.select_one('main')
        if main:
            print(f"\n<main> tag found:")
            print(f"  - Word count: {len(main.get_text().split())}")
            print(f"  - Classes: {main.get('class', [])}")

            # Check children of main
            direct_children = [child for child in main.children if child.name]
            print(f"  - Direct children ({len(direct_children)}):")
            for i, child in enumerate(direct_children[:10]):
                child_classes = child.get('class', [])
                child_words = len(child.get_text().split())
                print(f"    [{i}] <{child.name}> class={child_classes} ({child_words} words)")

        # Check for article-content
        article_content = soup.select_one('div.article-content')
        if article_content:
            print(f"\n<div class='article-content'> found:")
            print(f"  - Word count: {len(article_content.get_text().split())}")
            print(f"  - Classes: {article_content.get('class', [])}")

            # Check children
            direct_children = [child for child in article_content.children if child.name]
            print(f"  - Direct children ({len(direct_children)}):")
            for i, child in enumerate(direct_children[:10]):
                child_classes = child.get('class', [])
                child_words = len(child.get_text().split())
                print(f"    [{i}] <{child.name}> class={child_classes} ({child_words} words)")

        # Check for byo-blocks (React component wrapper)
        byo_blocks = soup.select_one('div.byo-blocks')
        if byo_blocks:
            print(f"\n<div class='byo-blocks'> found:")
            print(f"  - Word count: {len(byo_blocks.get_text().split())}")

            # Check children - these might be the actual content blocks
            direct_children = [child for child in byo_blocks.children if child.name]
            print(f"  - Direct children ({len(direct_children)}):")
            for i, child in enumerate(direct_children[:15]):
                child_classes = child.get('class', [])
                child_words = len(child.get_text().split())
                child_data_component = child.get('data-component', '')
                print(f"    [{i}] <{child.name}> class={child_classes} data-component='{child_data_component}' ({child_words} words)")

        # Look for common content patterns
        print(f"\nContent block patterns:")

        # Paragraphs within article-content or byo-blocks
        content_areas = soup.select('div.article-content, div.byo-blocks')
        if content_areas:
            for area in content_areas[:1]:  # Just first one
                paragraphs = area.find_all('p', recursive=True)
                print(f"  - Found {len(paragraphs)} <p> tags in content area")
                if paragraphs:
                    total_p_words = sum(len(p.get_text().split()) for p in paragraphs)
                    print(f"  - Total words in <p> tags: {total_p_words}")

                # Look for divs with specific classes
                for class_pattern in ['block', 'content', 'text', 'body', 'paragraph']:
                    divs = area.find_all('div', class_=lambda c: c and class_pattern in ' '.join(c).lower())
                    if divs:
                        print(f"  - Found {len(divs)} divs with '{class_pattern}' in class")

        # Check for author metadata
        print(f"\nAuthor/metadata patterns:")
        author_patterns = [
            'div.author',
            'div.byline',
            'span.author',
            '[data-component*="author" i]',
            'div[class*="author" i]',
        ]
        for pattern in author_patterns:
            authors = soup.select(pattern)
            if authors:
                print(f"  - {pattern}: Found {len(authors)} elements")
                for auth in authors[:2]:
                    print(f"    Text: {auth.get_text().strip()[:100]}")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

def main():
    session = get_session()

    # Get only successfully parsed documents (word_count > 400)
    documents = session.query(Document).filter(Document.word_count > 400).order_by(Document.document_id).all()

    print(f"Analyzing {len(documents)} successfully parsed documents...")
    print(f"(Filtered for word_count > 400 to exclude 404 pages)")

    for doc in documents:
        deep_analyze_document(doc.url, doc.document_id, doc.title, doc.word_count)
        time.sleep(2)

    session.close()

if __name__ == '__main__':
    main()
