#!/usr/bin/env python3
"""
Ingest Heritage Foundation research articles using sitemap discovery

This ingests commentary, reports, and other research content from Heritage Foundation.
"""
import sys
import logging
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

# Activate venv if available
venv_path = Path(__file__).parent / '.venv' / 'bin' / 'activate_this.py'
if venv_path.exists():
    exec(open(venv_path).read(), {'__file__': str(venv_path)})

from brookings_ingester.ingesters.heritage import HeritageIngester
from brookings_ingester.models.database import init_database

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Ingest Heritage Foundation research articles using sitemap"""

    # Initialize database
    logger.info("Initializing database...")
    init_database()

    # Create ingester
    logger.info("Creating Heritage Foundation ingester...")
    ingester = HeritageIngester()

    # Configuration
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    since_date = sys.argv[2] if len(sys.argv) > 2 else '2024-01-01'

    logger.info(f"Ingesting up to {limit} articles since {since_date}")
    logger.info("Using SITEMAP discovery method")
    logger.info("Enhanced author extraction: name, title, profile URLs")

    # Run ingestion using sitemap method
    result = ingester.run_ingestion(
        limit=limit,
        skip_existing=False,  # Re-process to add author metadata
        run_type='manual',
        since_date=since_date
    )

    if result['success']:
        logger.info("✅ Ingestion completed successfully!")
        logger.info(f"Stats: {result['stats']}")
    else:
        logger.error("❌ Ingestion failed")
        logger.error(f"Error: {result.get('error')}")
        sys.exit(1)


if __name__ == '__main__':
    main()
