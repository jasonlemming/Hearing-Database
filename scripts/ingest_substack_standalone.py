#!/usr/bin/env python3
"""
Standalone Substack ingester - fetches Jamie Dupree posts from last 150 days
No Playwright dependency required
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import time
import feedparser
import requests
from bs4 import BeautifulSoup

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import only what we need from models (not ingesters which has Playwright dep)
from brookings_ingester.models.database import get_session, init_database
from brookings_ingester.models.document import (
    Source, Document, Author, Subject, Organization,
    DocumentAuthor, DocumentSubject, IngestionLog
)
import brookings_ingester.config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_rss_feed(publication_url):
    """Fetch RSS feed from Substack"""
    feed_url = f"https://{publication_url}/feed"
    logger.info(f"Fetching RSS feed: {feed_url}")
    feed = feedparser.parse(feed_url)
    return feed


def parse_rss_entry(entry):
    """Parse RSS feed entry"""
    try:
        url = entry.get('link', '')
        title = entry.get('title', 'Untitled')

        # Parse date
        pub_date = None
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub_date = datetime(*entry.published_parsed[:6])

        # Extract slug from URL
        slug = url.split('/p/')[-1] if '/p/' in url else url.split('/')[-1]

        # Summary
        summary = ''
        if hasattr(entry, 'summary'):
            soup = BeautifulSoup(entry.summary, 'lxml')
            summary = soup.get_text(strip=True)[:500]

        # Author
        author = entry.get('author', '')

        return {
            'url': url,
            'title': title,
            'publication_date': pub_date.strftime('%Y-%m-%d') if pub_date else None,
            'summary': summary,
            'author': author,
            'slug': slug
        }
    except Exception as e:
        logger.error(f"Error parsing entry: {e}")
        return None


def fetch_html_content(url):
    """Fetch HTML content from URL"""
    try:
        time.sleep(1.0)  # Rate limiting
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return None


def parse_html_content(html, url):
    """Parse HTML content"""
    try:
        soup = BeautifulSoup(html, 'lxml')

        # Find main content
        content = soup.select_one('div.post-content') or soup.select_one('div.body') or soup.find('body')

        if not content:
            logger.warning(f"Could not find content in {url}")
            return None

        # Remove unwanted elements
        for tag in content.select('script, style, nav, header, footer'):
            tag.decompose()

        # Extract text
        text = content.get_text('\n', strip=True)
        word_count = len(text.split())

        return {
            'full_text': text,
            'word_count': word_count
        }
    except Exception as e:
        logger.error(f"Error parsing HTML: {e}")
        return None


def get_or_create_author(session, name):
    """Get or create author"""
    author = session.query(Author).filter_by(full_name=name).first()
    if not author:
        author = Author(
            full_name=name,
            first_name=name.split()[0] if ' ' in name else name,
            last_name=name.split()[-1] if ' ' in name else ''
        )
        session.add(author)
        session.flush()
    return author


def main():
    logger.info("=" * 80)
    logger.info("Jamie Dupree Substack Ingestion - 150 Days")
    logger.info("=" * 80)

    if not os.environ.get('BROOKINGS_DATABASE_URL'):
        logger.error("❌ BROOKINGS_DATABASE_URL not set")
        return 1

    try:
        # Initialize database
        init_database()
        session = get_session()

        # Get source
        source = session.query(Source).filter_by(source_code='SUBSTACK').first()
        if not source:
            logger.error("❌ Substack source not found")
            return 1

        logger.info(f"📚 Source: {source.name}")

        # Calculate lookback
        since_date = datetime.now() - timedelta(days=150)
        logger.info(f"📅 Fetching since: {since_date.strftime('%Y-%m-%d')}")

        # Create log
        log = IngestionLog(
            source_id=source.source_id,
            run_type='manual',
            started_at=datetime.now(),
            status='running'
        )
        session.add(log)
        session.commit()

        # Fetch RSS
        feed = fetch_rss_feed('jamiedupree.substack.com')
        logger.info(f"✅ Found {len(feed.entries)} posts in RSS")

        # Filter by date and process
        saved = 0
        skipped = 0
        errors = 0

        for idx, entry in enumerate(feed.entries, 1):
            try:
                # Parse entry
                meta = parse_rss_entry(entry)
                if not meta:
                    continue

                # Check date
                if meta['publication_date']:
                    post_date = datetime.strptime(meta['publication_date'], '%Y-%m-%d')
                    if post_date < since_date:
                        logger.debug(f"Skipping old post: {meta['title'][:50]}")
                        continue

                logger.info(f"\n[{idx}] {meta['title'][:60]}...")

                # Check if exists
                existing = session.query(Document).filter_by(
                    source_id=source.source_id,
                    document_identifier=meta['slug']
                ).first()

                if existing:
                    logger.info("  Already exists, skipping")
                    skipped += 1
                    continue

                # Fetch content
                html = fetch_html_content(meta['url'])
                if not html:
                    errors += 1
                    continue

                # Parse content
                parsed = parse_html_content(html, meta['url'])
                if not parsed:
                    errors += 1
                    continue

                # Create document
                doc = Document(
                    source_id=source.source_id,
                    document_identifier=meta['slug'],
                    title=meta['title'],
                    document_type='Newsletter Article',
                    publication_date=meta['publication_date'],
                    summary=meta['summary'],
                    full_text=parsed['full_text'],
                    url=meta['url'],
                    word_count=parsed['word_count']
                )
                session.add(doc)
                session.flush()

                # Add author
                if meta['author']:
                    author = get_or_create_author(session, meta['author'])
                    doc_author = DocumentAuthor(
                        document_id=doc.document_id,
                        author_id=author.author_id,
                        author_order=1
                    )
                    session.add(doc_author)

                session.commit()
                saved += 1
                logger.info(f"  ✅ Saved ({parsed['word_count']:,} words)")

            except Exception as e:
                logger.error(f"  ❌ Error: {e}")
                session.rollback()
                errors += 1
                continue

        # Update log
        log.completed_at = datetime.now()
        log.documents_checked = len(feed.entries)
        log.documents_fetched = saved
        log.documents_skipped = skipped
        log.errors_count = errors
        log.status = 'completed' if errors == 0 else 'partial'
        log.total_duration_seconds = (log.completed_at - log.started_at).total_seconds()
        session.commit()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 Summary")
        logger.info("=" * 80)
        logger.info(f"  Posts checked: {len(feed.entries)}")
        logger.info(f"  New posts saved: {saved}")
        logger.info(f"  Already existed: {skipped}")
        logger.info(f"  Errors: {errors}")
        logger.info(f"  Duration: {log.total_duration_seconds:.1f}s")

        total = session.query(Document).filter_by(source_id=source.source_id).count()
        logger.info(f"\n  Total Substack docs: {total}")

        session.close()
        logger.info("\n✅ Complete!")
        return 0

    except Exception as e:
        logger.error(f"\n❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
