"""
Database Initialization Script

Creates tables and seeds initial data (sources, organizations)
"""
import sys
import logging
from pathlib import Path

from brookings_ingester.models import init_database, get_session, Source, Organization
from brookings_ingester.config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def seed_sources(session):
    """Seed sources table with CRS, Brookings, GAO, Substack, Heritage"""
    sources_data = [
        {
            'source_code': 'CRS',
            'name': 'Congressional Research Service',
            'short_name': 'CRS',
            'description': 'The Congressional Research Service (CRS) provides policy and legal analysis to committees and Members of Congress.',
            'url': 'https://www.congress.gov',
            'is_active': True
        },
        {
            'source_code': 'BROOKINGS',
            'name': 'Brookings Institution',
            'short_name': 'Brookings',
            'description': 'The Brookings Institution is a nonprofit public policy organization based in Washington, DC.',
            'url': 'https://www.brookings.edu',
            'is_active': True
        },
        {
            'source_code': 'HERITAGE',
            'name': 'Heritage Foundation',
            'short_name': 'Heritage',
            'description': 'The Heritage Foundation is a conservative research and educational institution focused on public policy.',
            'url': 'https://www.heritage.org',
            'is_active': True
        },
        {
            'source_code': 'GAO',
            'name': 'Government Accountability Office',
            'short_name': 'GAO',
            'description': 'The U.S. Government Accountability Office (GAO) is an independent, nonpartisan agency that works for Congress.',
            'url': 'https://www.gao.gov',
            'is_active': True
        },
        {
            'source_code': 'SUBSTACK',
            'name': 'Substack Newsletters',
            'short_name': 'Substack',
            'description': 'Substack is a newsletter platform for independent writers and policy analysts.',
            'url': 'https://substack.com',
            'is_active': True
        }
    ]

    for source_data in sources_data:
        # Check if source already exists
        existing = session.query(Source).filter_by(source_code=source_data['source_code']).first()

        if existing:
            logger.info(f"Source '{source_data['source_code']}' already exists, skipping")
        else:
            source = Source(**source_data)
            session.add(source)
            logger.info(f"✓ Created source: {source_data['source_code']}")

    session.commit()


def seed_organizations(session):
    """Seed organizations table"""
    organizations_data = [
        {
            'name': 'Brookings Institution',
            'short_name': 'Brookings',
            'organization_type': 'Think Tank',
            'url': 'https://www.brookings.edu'
        },
        {
            'name': 'Heritage Foundation',
            'short_name': 'Heritage',
            'organization_type': 'Think Tank',
            'url': 'https://www.heritage.org'
        },
        {
            'name': 'Congressional Research Service',
            'short_name': 'CRS',
            'organization_type': 'Government Agency',
            'url': 'https://www.congress.gov'
        },
        {
            'name': 'Government Accountability Office',
            'short_name': 'GAO',
            'organization_type': 'Government Agency',
            'url': 'https://www.gao.gov'
        }
    ]

    for org_data in organizations_data:
        # Check if organization already exists
        existing = session.query(Organization).filter_by(name=org_data['name']).first()

        if existing:
            logger.info(f"Organization '{org_data['name']}' already exists, skipping")
        else:
            org = Organization(**org_data)
            session.add(org)
            logger.info(f"✓ Created organization: {org_data['name']}")

    session.commit()


def main():
    """Initialize database and seed data"""
    try:
        logger.info("=" * 70)
        logger.info("Brookings Ingestion System - Database Initialization")
        logger.info("=" * 70)

        # Ensure storage directories exist
        logger.info("\nCreating storage directories...")
        config.ensure_directories()
        logger.info(f"✓ PDF storage: {config.PDF_STORAGE}")
        logger.info(f"✓ Text storage: {config.TEXT_STORAGE}")
        logger.info(f"✓ HTML storage: {config.HTML_STORAGE}")

        # Initialize database
        logger.info(f"\nInitializing database: {config.DATABASE_URL}")
        init_database(db_url=config.DATABASE_URL, echo=False)
        logger.info("✓ Database tables created")

        # Seed data
        session = get_session()

        logger.info("\nSeeding sources...")
        seed_sources(session)

        logger.info("\nSeeding organizations...")
        seed_organizations(session)

        session.close()

        # Display summary
        session = get_session()
        source_count = session.query(Source).count()
        org_count = session.query(Organization).count()
        session.close()

        logger.info("\n" + "=" * 70)
        logger.info("Initialization Complete!")
        logger.info(f"  Sources: {source_count}")
        logger.info(f"  Organizations: {org_count}")
        logger.info(f"  Database: {config.DATABASE_URL}")
        logger.info("=" * 70)

        logger.info("\nNext steps:")
        logger.info("  1. Run test ingestion: python -m brookings_ingester.test_ingestion --limit 5")
        logger.info("  2. Run full backfill: python cli.py brookings backfill --limit 100")

        return 0

    except Exception as e:
        logger.error(f"\n❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
