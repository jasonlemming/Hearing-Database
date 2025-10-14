#!/usr/bin/env python3
"""
Policy Library Daily Update System

This module provides automated daily synchronization of Jamie Dupree's Substack
posts via RSS feed, implementing the same patterns as the Congressional updater.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
import json
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bs4 import BeautifulSoup
import requests

# Import policy library models (avoid heavy dependencies like Playwright)
from brookings_ingester.models import get_session, Source, Document, Author, DocumentAuthor, IngestionLog

logger = logging.getLogger(__name__)


class UpdateMetrics:
    """Track update operation metrics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.posts_checked = 0
        self.posts_added = 0
        self.posts_skipped = 0
        self.errors = []
        self.total_posts = 0

    def duration(self) -> Optional[timedelta]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration().total_seconds() if self.duration() else None,
            'posts_checked': self.posts_checked,
            'posts_added': self.posts_added,
            'posts_skipped': self.posts_skipped,
            'total_posts': self.total_posts,
            'error_count': len(self.errors),
            'errors': self.errors
        }


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
        logger.debug(f"Fetching RSS feed: {self.rss_url}")
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
        logger.debug(f"Document already exists: {doc_data['title'][:60]}...")
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

    logger.info(f"Saved: {doc_data['title'][:60]}... ({doc_data.get('word_count', 0):,} words)")
    return document, True


class PolicyLibraryUpdater:
    """
    Automated daily update system for Policy Library (Jamie Dupree Substack)

    Implements incremental updates by:
    - Fetching RSS feed for recent posts
    - Comparing with existing database records
    - Adding only new posts
    """

    def __init__(self, lookback_days: int = 7, publication: str = 'jamiedupree.substack.com', author: str = 'Jamie Dupree'):
        self.lookback_days = lookback_days
        self.publication = publication
        self.author = author
        self.metrics = UpdateMetrics()

        logger.info(f"PolicyLibraryUpdater initialized: {lookback_days} day lookback from {publication}")

    def run_daily_update(self) -> Dict[str, Any]:
        """
        Execute the complete daily update process

        Returns:
            Dictionary containing update metrics and results
        """
        logger.info("Starting policy library daily update")

        try:
            # Check environment
            if not os.environ.get('BROOKINGS_DATABASE_URL'):
                error_msg = "BROOKINGS_DATABASE_URL environment variable not set"
                logger.error(error_msg)
                self.metrics.errors.append(error_msg)
                raise Exception(error_msg)

            # Get database session
            session = get_session()

            # Get Substack source
            source = session.query(Source).filter_by(source_code='SUBSTACK').first()
            if not source:
                error_msg = "Substack source not found in database"
                logger.error(error_msg)
                self.metrics.errors.append(error_msg)
                raise Exception(error_msg)

            logger.info(f"Source: {source.name} (ID: {source.source_id})")

            # Calculate lookback date
            since_date = datetime.now() - timedelta(days=self.lookback_days)
            logger.info(f"Fetching posts since: {since_date.strftime('%Y-%m-%d')} ({self.lookback_days} days)")

            # Create ingestion log
            log = IngestionLog(
                source_id=source.source_id,
                run_type='update',  # Valid values: 'backfill', 'update', 'manual'
                started_at=datetime.now(),
                status='running'
            )
            session.add(log)
            session.commit()

            # Initialize ingester and fetch RSS
            ingester = SubstackRSSIngester(f"https://{self.publication}")
            rss_content = ingester.fetch_rss()

            if not rss_content:
                error_msg = "Failed to fetch RSS feed"
                logger.error(error_msg)
                log.status = 'failed'
                log.completed_at = datetime.now()
                session.commit()
                self.metrics.errors.append(error_msg)
                raise Exception(error_msg)

            # Parse RSS feed
            logger.info("Parsing RSS feed...")
            posts = ingester.parse_rss(rss_content, since_date=since_date)

            logger.info(f"Found {len(posts)} posts from {self.author}")
            log.documents_checked = len(posts)
            self.metrics.posts_checked = len(posts)
            session.commit()

            # Save each document
            logger.info("Saving documents to database...")
            saved_count = 0
            skipped_count = 0
            error_count = 0

            for idx, post in enumerate(posts, 1):
                try:
                    logger.debug(f"[{idx}/{len(posts)}] {post['title'][:60]}...")

                    # Save to database
                    doc, is_new = save_document(session, post, source.source_id, self.author)
                    if is_new:
                        saved_count += 1
                    else:
                        skipped_count += 1

                    session.commit()

                except Exception as e:
                    logger.error(f"Error saving document: {e}")
                    error_count += 1
                    self.metrics.errors.append(f"Document {post.get('title', 'unknown')}: {str(e)}")
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

            # Update metrics
            self.metrics.posts_added = saved_count
            self.metrics.posts_skipped = skipped_count
            self.metrics.end_time = datetime.now()

            # Get total count
            total_substack = session.query(Document).filter_by(source_id=source.source_id).count()
            self.metrics.total_posts = total_substack

            # Calculate duration before closing session
            duration_seconds = log.total_duration_seconds if log.total_duration_seconds else 0

            session.close()

            # Log summary
            logger.info("=" * 60)
            logger.info("Policy Library Update Summary")
            logger.info("=" * 60)
            logger.info(f"  Posts discovered: {len(posts)}")
            logger.info(f"  New posts saved: {saved_count}")
            logger.info(f"  Already existed: {skipped_count}")
            logger.info(f"  Errors: {error_count}")
            logger.info(f"  Duration: {duration_seconds:.1f} seconds")
            logger.info(f"  Total Substack documents: {total_substack}")
            logger.info("=" * 60)

            if error_count == 0:
                logger.info("Policy library update completed successfully")
            else:
                logger.warning(f"Policy library update completed with {error_count} errors")

            return {
                'success': True,
                'metrics': self.metrics.to_dict()
            }

        except Exception as e:
            self.metrics.end_time = datetime.now()
            self.metrics.errors.append(str(e))
            logger.error(f"Policy library update failed: {e}", exc_info=True)

            return {
                'success': False,
                'error': str(e),
                'metrics': self.metrics.to_dict()
            }


def main():
    """Main entry point for policy library update script"""
    import argparse

    parser = argparse.ArgumentParser(description='Run daily update for Policy Library')
    parser.add_argument('--lookback-days', type=int, default=7, help='Days to look back for new posts')
    parser.add_argument('--publication', type=str, default='jamiedupree.substack.com', help='Substack publication domain')
    parser.add_argument('--author', type=str, default='Jamie Dupree', help='Author name')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    updater = PolicyLibraryUpdater(
        lookback_days=args.lookback_days,
        publication=args.publication,
        author=args.author
    )

    result = updater.run_daily_update()

    if result['success']:
        logger.info("Daily update completed successfully")
        print(json.dumps(result['metrics'], indent=2))
    else:
        logger.error(f"Daily update failed: {result['error']}")
        sys.exit(1)


if __name__ == '__main__':
    main()
