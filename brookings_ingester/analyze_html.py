"""Analyze Brookings HTML structure in detail"""
import sys
sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.ingesters import BrookingsIngester
from bs4 import BeautifulSoup

# Fetch a document
ingester = BrookingsIngester()
url = "https://www.brookings.edu/articles/how-to-improve-the-nations-health-care-system/"

doc_meta = {'document_identifier': 'test', 'url': url}
result = ingester.fetch(doc_meta)

if result:
    soup = BeautifulSoup(result['html_content'], 'lxml')

    print("=== Full Structure Analysis ===\n")

    # Find main tag
    main = soup.find('main')
    if main:
        print(f"Main tag found")

        # Count all byo-block divs
        byo_blocks = main.find_all('div', class_='byo-block')
        print(f"Number of byo-block divs: {len(byo_blocks)}")

        total_words = 0
        for i, block in enumerate(byo_blocks):
            words = len(block.get_text().split())
            total_words += words
            print(f"  Block {i+1}: {words} words")
            if i < 3:  # Show first 3 blocks content preview
                text = block.get_text(strip=True)[:150]
                print(f"    Preview: {text}...")

        print(f"\nTotal words in all byo-blocks: {total_words}")

        # Look for article tag within main
        article = main.find('article')
        if article:
            print(f"\nArticle tag found within main")
            article_words = len(article.get_text().split())
            print(f"Article total words: {article_words}")

        # Look for specific content containers
        print("\n=== Checking specific selectors ===")
        for selector in ['div.post-body', 'div.post-body__content', 'div.article-body',
                        'div.entry-content', 'section.article-content', 'main > div']:
            elem = main.select_one(selector) if main else soup.select_one(selector)
            if elem:
                words = len(elem.get_text().split())
                print(f"{selector}: {words} words")

        # Check for paragraphs in main
        paragraphs = main.find_all('p') if main else soup.find_all('p')
        total_p_words = sum(len(p.get_text().split()) for p in paragraphs)
        print(f"\n{len(paragraphs)} paragraphs found, {total_p_words} total words")
