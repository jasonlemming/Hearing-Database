#!/usr/bin/env python3
"""
Ingest Jamie Dupree's Substack posts via RSS feed (lightweight, no Playwright)

Usage:
    export BROOKINGS_DATABASE_URL='postgresql://...'
    python scripts/ingest_jamie_dupree_rss.py [--days 150]
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging
import argparse
import re
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import only what we need (avoid Playwright dependencies)
from brookings_ingester.models import get_session, Source, Document, Author, DocumentAuthor, IngestionLog
from bs4 import BeautifulSoup
import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SubstackRSSIngester:
    """Lightweight RSS-based Substack ingester"""

    def __init__(self, publication_url: str, rate_limit_delay: float = 1.0):
        self.publication_url = publication_url.rstrip('/')
        self.rss_url = f"{self.publication_url}/feed"
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def fetch_rss(self):
        """Fetch RSS feed"""
        logger.info(f"📡 Fetching RSS feed: {self.rss_url}")
        try:
            response = self.session.get(self.rss_url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch RSS: {e}")
            return None

    def parse_rss(self, rss_content: str, since_date: datetime = None):
        """Parse RSS feed and extract posts"""
        soup = BeautifulSoup(rss_content, 'xml')
        items = soup.find_all('item')

        posts = []
        for item in items:
            try:
                # Extract basic metadata
                title = item.find('title').text if item.find('title') else 'Untitled'
                link = item.find('link').text if item.find('link') else ''
                pub_date_str = item.find('pubDate').text if item.find('pubDate') else ''
                description = item.find('description').text if item.find('description') else ''

                # Parse publication date
                if pub_date_str:
                    # RSS date format: "Mon, 14 Oct 2024 10:00:00 GMT"
                    pub_date = datetime.strptime(pub_date_str, '%a, %d %b %Y %H:%M:%S %Z')
                else:
                    pub_date = None

                # Filter by date if specified
                if since_date and pub_date and pub_date < since_date:
                    continue

                # Extract content (may be in content:encoded or description)
                content_tag = item.find('content:encoded') or item.find('description')
                html_content = content_tag.text if content_tag else ''

                # Parse HTML content to plain text
                if html_content:
                    content_soup = BeautifulSoup(html_content, 'html.parser')
                    # Remove script and style tags
                    for tag in content_soup(['script', 'style']):
                        tag.decompose()
                    full_text = content_soup.get_text(separator='\n', strip=True)
                else:
                    full_text = description

                # Extract document identifier from URL
                doc_id = link.split('/')[-1] if link else title.lower().replace(' ', '-')

                # Count words
                word_count = len(full_text.split()) if full_text else 0

                post = {
                    'document_identifier': doc_id,
                    'title': title,
                    'url': link,
                    'publication_date': pub_date.date() if pub_date else None,
                    'summary': description[:500] if description else '',
                    'full_text': full_text,
                    'document_type': 'Newsletter Article',
                    'word_count': word_count,
                    'metadata': {
                        'rss_pub_date': pub_date_str,
                        'source': 'rss_feed'
                    }
                }

                posts.append(post)

            except Exception as e:
                logger.warning(f"Failed to parse RSS item: {e}")
                continue

        return posts


def get_or_create_author(session, author_name: str):
    """Get or create author"""
    author = session.query(Author).filter_by(full_name=author_name).first()
    if not author:
        parts = author_name.split()
        author = Author(
            full_name=author_name,
            first_name=parts[0] if parts else author_name,
            last_name=parts[-1] if len(parts) > 1 else ''
        )
        session.add(author)
        session.flush()
    return author


def save_document(session, doc_data: dict, source_id: int, author_name: str):
    """Save document to database"""
    # Check if document already exists
    existing = session.query(Document).filter_by(
        source_id=source_id,
        document_identifier=doc_data['document_identifier']
    ).first()

    if existing:
        logger.info(f"  ⏭️  Already exists: {doc_data['title'][:60]}...")
        return existing, False

    # Create document
    document = Document(
        source_id=source_id,
        document_identifier=doc_data['document_identifier'],
        title=doc_data['title'],
        document_type=doc_data.get('document_type', 'Newsletter Article'),
        publication_date=doc_data.get('publication_date'),
        summary=doc_data.get('summary', ''),
        full_text=doc_data.get('full_text', ''),
        url=doc_data.get('url'),
        word_count=doc_data.get('word_count'),
        metadata_json=json.dumps(doc_data.get('metadata', {}))
    )
    session.add(document)
    session.flush()

    # Add author
    author = get_or_create_author(session, author_name)
    doc_author = DocumentAuthor(
        document_id=document.document_id,
        author_id=author.author_id,
        author_order=1
    )
    session.add(doc_author)
    session.flush()

    logger.info(f"  ✅ Saved: {doc_data['title'][:60]}... ({doc_data.get('word_count', 0):,} words)")
    return document, True


def main():
    """Main ingestion function"""
    parser = argparse.ArgumentParser(description='Ingest Jamie Dupree Substack via RSS')
    parser.add_argument('--days', type=int, default=150, help='Days to look back (default: 150)')
    parser.add_argument('--publication', type=str, default='jamiedupree.substack.com', help='Substack publication domain')
    parser.add_argument('--author', type=str, default='Jamie Dupree', help='Author name')
    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info(f"Jamie Dupree Substack RSS Ingestion - {args.days} Days Lookback")
    logger.info("=" * 80)

    # Check environment
    if not os.environ.get('BROOKINGS_DATABASE_URL'):
        logger.error("❌ BROOKINGS_DATABASE_URL environment variable not set")
        logger.info("\nUsage:")
        logger.info("  export BROOKINGS_DATABASE_URL='postgresql://...'")
        logger.info("  python scripts/ingest_jamie_dupree_rss.py [--days 150]")
        return 1

    try:
        # Get database session
        session = get_session()

        # Get Substack source
        source = session.query(Source).filter_by(source_code='SUBSTACK').first()
        if not source:
            logger.error("❌ Substack source not found in database")
            logger.info("Run: python brookings_ingester/init_db.py")
            return 1

        logger.info(f"\n📚 Source: {source.name} (ID: {source.source_id})")

        # Calculate lookback date
        since_date = datetime.now() - timedelta(days=args.days)
        logger.info(f"📅 Fetching posts since: {since_date.strftime('%Y-%m-%d')} ({args.days} days)")

        # Create ingestion log
        log = IngestionLog(
            source_id=source.source_id,
            run_type='manual',
            started_at=datetime.now(),
            status='running'
        )
        session.add(log)
        session.commit()

        # Initialize ingester and fetch RSS
        ingester = SubstackRSSIngester(f"https://{args.publication}")
        rss_content = ingester.fetch_rss()

        if not rss_content:
            logger.error("❌ Failed to fetch RSS feed")
            log.status = 'failed'
            log.completed_at = datetime.now()
            session.commit()
            return 1

        # Parse RSS feed
        logger.info("\n🔍 Parsing RSS feed...")
        posts = ingester.parse_rss(rss_content, since_date=since_date)

        logger.info(f"✅ Found {len(posts)} posts from {args.author}")
        log.documents_checked = len(posts)
        session.commit()

        # Save each document
        logger.info("\n💾 Saving documents to database...")
        saved_count = 0
        skipped_count = 0
        error_count = 0

        for idx, post in enumerate(posts, 1):
            try:
                logger.info(f"\n[{idx}/{len(posts)}] {post['title'][:60]}...")

                # Save to database
                doc, is_new = save_document(session, post, source.source_id, args.author)
                if is_new:
                    saved_count += 1
                else:
                    skipped_count += 1

                session.commit()

            except Exception as e:
                logger.error(f"  ❌ Error saving document: {e}")
                error_count += 1
                session.rollback()
                continue

        # Update ingestion log
        log.completed_at = datetime.now()
        log.documents_fetched = saved_count
        log.documents_skipped = skipped_count
        log.errors_count = error_count
        log.status = 'completed' if error_count == 0 else 'partial'
        log.total_duration_seconds = (log.completed_at - log.started_at).total_seconds()
        session.commit()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📊 Ingestion Summary")
        logger.info("=" * 80)
        logger.info(f"  Posts discovered: {len(posts)}")
        logger.info(f"  New posts saved: {saved_count}")
        logger.info(f"  Already existed: {skipped_count}")
        logger.info(f"  Errors: {error_count}")
        logger.info(f"  Duration: {log.total_duration_seconds:.1f} seconds")

        # Final count
        total_substack = session.query(Document).filter_by(source_id=source.source_id).count()
        logger.info(f"\n  Total Substack documents in database: {total_substack}")

        session.close()

        if error_count == 0:
            logger.info("\n✅ Ingestion completed successfully!")
            return 0
        else:
            logger.info(f"\n⚠️  Ingestion completed with {error_count} errors")
            return 0

    except Exception as e:
        logger.error(f"\n❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
