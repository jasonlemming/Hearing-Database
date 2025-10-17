#!/usr/bin/env python3
"""
CRS Library Daily Update System

This module provides automated daily synchronization of CRS (Congressional Research Service)
reports from congress.gov, implementing the same patterns as the Congressional updater.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fetchers.crs_content_fetcher import CRSContentFetcher
from parsers.crs_html_parser import CRSHTMLParser
from database.crs_content_manager_postgres import CRSContentManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class UpdateMetrics:
    """Track update operation metrics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.products_checked = 0
        self.products_updated = 0
        self.products_added = 0
        self.products_skipped = 0
        self.errors = []
        self.total_size_bytes = 0
        self.avg_fetch_time_ms = 0

    def duration(self) -> Optional[timedelta]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration().total_seconds() if self.duration() else None,
            'products_checked': self.products_checked,
            'products_updated': self.products_updated,
            'products_added': self.products_added,
            'products_skipped': self.products_skipped,
            'total_size_bytes': self.total_size_bytes,
            'avg_fetch_time_ms': self.avg_fetch_time_ms,
            'error_count': len(self.errors),
            'errors': self.errors
        }


class CRSUpdater:
    """
    Automated daily update system for CRS Library

    Implements incremental updates by:
    - Fetching recently updated CRS products from database
    - Checking which need content updates
    - Fetching HTML content from congress.gov
    - Parsing and storing content with version tracking
    """

    def __init__(self, lookback_days: int = 30, max_products: int = 100):
        """
        Initialize CRS updater

        Args:
            lookback_days: How many days back to check for updates (default: 30)
            max_products: Maximum number of products to update per run (default: 100)
        """
        self.lookback_days = lookback_days
        self.max_products = max_products
        self.metrics = UpdateMetrics()

        # Initialize components
        self.content_manager = CRSContentManager()
        self.fetcher = CRSContentFetcher(rate_limit_delay=0.5)
        self.parser = CRSHTMLParser()

        logger.info(f"CRSUpdater initialized: {lookback_days} day lookback, max {max_products} products")

    def run_daily_update(self) -> Dict[str, Any]:
        """
        Execute the complete daily update process

        Returns:
            Dictionary containing update metrics and results
        """
        logger.info("Starting CRS library daily update")

        try:
            # Step 1: Find products that need content updates
            logger.info(f"Finding products updated in last {self.lookback_days} days...")
            products_to_update = self._get_products_needing_update()

            if not products_to_update:
                logger.info("No products need updating")
                self.metrics.end_time = datetime.now()
                return {
                    'success': True,
                    'metrics': self.metrics.to_dict()
                }

            # Limit to max_products
            if len(products_to_update) > self.max_products:
                logger.info(f"Limiting update to {self.max_products} of {len(products_to_update)} products")
                products_to_update = products_to_update[:self.max_products]

            self.metrics.products_checked = len(products_to_update)
            logger.info(f"Found {len(products_to_update)} products to update")

            # Step 2: Start ingestion log
            log_id = self.content_manager.start_ingestion_log(
                run_type='update',
                products_checked=len(products_to_update)
            )

            # Step 3: Process each product
            logger.info("Fetching and processing product content...")
            for idx, product in enumerate(products_to_update, 1):
                try:
                    self._process_product(product, idx, len(products_to_update))
                except Exception as e:
                    error_msg = f"Error processing product {product['product_id']}: {e}"
                    logger.error(error_msg)
                    self.metrics.errors.append(error_msg)
                    continue

            # Step 4: Get fetcher stats
            fetcher_stats = self.fetcher.get_stats()
            self.metrics.total_size_bytes = fetcher_stats.get('total_bytes', 0)
            self.metrics.avg_fetch_time_ms = fetcher_stats.get('avg_fetch_time_ms', 0)

            # Step 5: Complete ingestion log
            self.metrics.end_time = datetime.now()
            duration_seconds = self.metrics.duration().total_seconds() if self.metrics.duration() else 0

            self.content_manager.complete_ingestion_log(
                log_id=log_id,
                content_fetched=self.metrics.products_updated + self.metrics.products_added,
                content_updated=self.metrics.products_updated,
                content_skipped=self.metrics.products_skipped,
                errors_count=len(self.metrics.errors),
                total_size_bytes=self.metrics.total_size_bytes,
                avg_fetch_time_ms=self.metrics.avg_fetch_time_ms,
                total_duration_seconds=duration_seconds
            )

            # Log summary
            logger.info("=" * 60)
            logger.info("CRS Library Update Summary")
            logger.info("=" * 60)
            logger.info(f"  Products checked: {self.metrics.products_checked}")
            logger.info(f"  New versions added: {self.metrics.products_added}")
            logger.info(f"  Existing versions updated: {self.metrics.products_updated}")
            logger.info(f"  Skipped (no change): {self.metrics.products_skipped}")
            logger.info(f"  Errors: {len(self.metrics.errors)}")
            logger.info(f"  Total size: {self.metrics.total_size_bytes / 1024 / 1024:.2f} MB")
            logger.info(f"  Duration: {duration_seconds:.1f} seconds")
            logger.info("=" * 60)

            if len(self.metrics.errors) == 0:
                logger.info("CRS library update completed successfully")
            else:
                logger.warning(f"CRS library update completed with {len(self.metrics.errors)} errors")

            return {
                'success': True,
                'metrics': self.metrics.to_dict()
            }

        except Exception as e:
            self.metrics.end_time = datetime.now()
            self.metrics.errors.append(str(e))
            logger.error(f"CRS library update failed: {e}", exc_info=True)

            return {
                'success': False,
                'error': str(e),
                'metrics': self.metrics.to_dict()
            }
        finally:
            # Cleanup
            self.fetcher.close()

    def _get_products_needing_update(self) -> List[Dict[str, Any]]:
        """
        Get list of products that need content updates

        Returns:
            List of product dictionaries with product_id, html_url, version, etc.
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)

        # Get products from database that were updated recently
        products = self.content_manager.get_products_needing_content(
            since_date=cutoff_date,
            limit=self.max_products * 2  # Get more than needed to prioritize
        )

        logger.info(f"Found {len(products)} products updated since {cutoff_date.strftime('%Y-%m-%d')}")

        return products

    def _process_product(self, product: Dict[str, Any], current: int, total: int):
        """
        Process a single CRS product: fetch, parse, and store

        Args:
            product: Product dictionary with product_id, html_url, version, etc.
            current: Current product number (for logging)
            total: Total products to process (for logging)
        """
        product_id = product['product_id']
        html_url = product['html_url']
        version_number = product.get('version', 1)

        logger.info(f"[{current}/{total}] Processing {product_id} v{version_number}")

        # Check if we need to update this version
        if not self.content_manager.needs_update(product_id, version_number):
            logger.info(f"  Skipping {product_id} v{version_number} (already have current version)")
            self.metrics.products_skipped += 1
            return

        # Fetch HTML content
        logger.debug(f"  Fetching content from {html_url}")
        result = self.fetcher.fetch_html(html_url)

        if not result:
            # Try with browser if HTTP fetch failed
            logger.warning(f"  HTTP fetch failed for {product_id}, trying browser...")
            result = self.fetcher.fetch_html_with_browser(html_url)

        if not result:
            error_msg = f"Failed to fetch content for {product_id}"
            logger.error(f"  {error_msg}")
            self.metrics.errors.append(error_msg)
            return

        html_content, fetch_metadata = result

        # Parse HTML content
        logger.debug(f"  Parsing HTML content...")
        try:
            parsed_content = self.parser.parse(html_content, html_url)

            if not parsed_content:
                error_msg = f"Failed to parse content for {product_id}"
                logger.error(f"  {error_msg}")
                self.metrics.errors.append(error_msg)
                return

        except Exception as e:
            error_msg = f"Parse error for {product_id}: {e}"
            logger.error(f"  {error_msg}")
            self.metrics.errors.append(error_msg)
            return

        # Store content in database
        logger.debug(f"  Storing content in database...")
        try:
            is_new = self.content_manager.upsert_version(
                product_id=product_id,
                version_number=version_number,
                parsed_content=parsed_content,
                html_url=html_url
            )

            if is_new:
                self.metrics.products_added += 1
                logger.info(f"  ✓ Added new version: {product_id} v{version_number} ({parsed_content.word_count:,} words)")
            else:
                # Count as updated even if content was the same (skipped internally)
                if parsed_content:
                    self.metrics.products_updated += 1
                    logger.info(f"  ✓ Updated version: {product_id} v{version_number} ({parsed_content.word_count:,} words)")
                else:
                    self.metrics.products_skipped += 1

        except Exception as e:
            error_msg = f"Database error for {product_id}: {e}"
            logger.error(f"  {error_msg}")
            self.metrics.errors.append(error_msg)
            return


def main():
    """Main entry point for CRS update script"""
    import argparse

    parser = argparse.ArgumentParser(description='Run daily update for CRS Library')
    parser.add_argument('--lookback-days', type=int, default=30, help='Days to look back for updates')
    parser.add_argument('--max-products', type=int, default=100, help='Maximum products to update per run')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    updater = CRSUpdater(
        lookback_days=args.lookback_days,
        max_products=args.max_products
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
