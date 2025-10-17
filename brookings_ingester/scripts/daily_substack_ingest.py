#!/usr/bin/env python3
"""
Daily Substack Ingestion Script

Runs daily to pull the latest articles from the Substack RSS feed
and store them in the database.

Usage:
    python brookings_ingester/scripts/daily_substack_ingest.py
"""
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from brookings_ingester.ingesters.substack import SubstackIngester

# Configure logging
log_dir = project_root / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'substack_daily.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """Run daily Substack ingestion"""
    logger.info('='*60)
    logger.info(f'Starting daily Substack ingestion at {datetime.now()}')
    logger.info('='*60)

    try:
        ingester = SubstackIngester()

        # Discover articles (RSS feed typically has 20 most recent)
        logger.info('Discovering articles from Substack RSS feed...')
        docs = ingester.discover()
        logger.info(f'Discovered {len(docs)} articles')

        if not docs:
            logger.warning('No articles found in RSS feed')
            return

        # Process each article
        success = 0
        failed = 0
        skipped = 0

        for i, doc in enumerate(docs, 1):
            title = doc.get('title', doc.get('url', 'Unknown'))[:60]
            logger.info(f'[{i}/{len(docs)}] Processing: {title}...')

            try:
                # Fetch
                fetched = ingester.fetch(doc)
                if not fetched:
                    logger.warning(f'  Failed to fetch')
                    failed += 1
                    continue

                # Parse
                parsed = ingester.parse(doc, fetched)
                if not parsed:
                    logger.warning(f'  Failed to parse')
                    failed += 1
                    continue

                # Store (will skip if already exists based on URL)
                try:
                    ingester.store(parsed)
                    success += 1
                    logger.info(f'  ✓ Stored successfully')
                except Exception as store_error:
                    # Check if it's a duplicate
                    if 'duplicate' in str(store_error).lower() or 'unique constraint' in str(store_error).lower():
                        skipped += 1
                        logger.info(f'  - Already exists, skipped')
                    else:
                        raise

            except Exception as e:
                logger.error(f'  Error: {str(e)[:200]}')
                failed += 1

        # Summary
        logger.info('='*60)
        logger.info(f'Ingestion complete at {datetime.now()}')
        logger.info(f'Total articles: {len(docs)}')
        logger.info(f'Success (new): {success}')
        logger.info(f'Skipped (duplicates): {skipped}')
        logger.info(f'Failed: {failed}')
        logger.info('='*60)

        # Exit code based on results
        if failed == len(docs):
            sys.exit(1)  # All failed
        elif failed > 0:
            sys.exit(2)  # Partial failure
        else:
            sys.exit(0)  # Success

    except Exception as e:
        logger.error(f'Fatal error during ingestion: {e}')
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
