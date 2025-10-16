#!/usr/bin/env python3
"""
Ingest Jamie Dupree's Substack posts from the last 150 days

Usage:
    export BROOKINGS_DATABASE_URL='postgresql://...'
    python scripts/ingest_jamie_dupree_150days.py
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct imports to avoid Playwright dependency
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'brookings_ingester'))

from ingesters.substack import SubstackIngester
from models import get_session, Source, Document, Author, Subject, DocumentAuthor, DocumentSubject, IngestionLog
import config as ingester_config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_or_create_author(session, author_name: str):
    """Get or create author"""
    author = session.query(Author).filter_by(full_name=author_name).first()
    if not author:
        author = Author(
            full_name=author_name,
            first_name=author_name.split()[0] if ' ' in author_name else author_name,
            last_name=author_name.split()[-1] if ' ' in author_name else ''
        )
        session.add(author)
        session.flush()
    return author


def get_or_create_subject(session, subject_name: str):
    """Get or create subject"""
    subject = session.query(Subject).filter_by(name=subject_name).first()
    if not subject:
        subject = Subject(name=subject_name)
        session.add(subject)
        session.flush()
    return subject


def save_document(session, doc_data: dict, source_id: int):
    """Save document to database"""
    # Check if document already exists
    existing = session.query(Document).filter_by(
        source_id=source_id,
        document_identifier=doc_data['document_identifier']
    ).first()

    if existing:
        logger.info(f"  Document already exists: {doc_data['title'][:60]}...")
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
        pdf_url=doc_data.get('pdf_url'),
        page_count=doc_data.get('page_count'),
        word_count=doc_data.get('word_count'),
        metadata_json=str(doc_data.get('metadata', {}))
    )
    session.add(document)
    session.flush()

    # Add authors
    for idx, author_name in enumerate(doc_data.get('authors', [])):
        if author_name:
            author = get_or_create_author(session, author_name)
            doc_author = DocumentAuthor(
                document_id=document.document_id,
                author_id=author.author_id,
                author_order=idx + 1
            )
            session.add(doc_author)

    # Add subjects
    for subject_name in doc_data.get('subjects', []):
        if subject_name:
            subject = get_or_create_subject(session, subject_name)
            doc_subject = DocumentSubject(
                document_id=document.document_id,
                subject_id=subject.subject_id
            )
            session.add(doc_subject)

    session.flush()
    logger.info(f"  ✅ Saved: {doc_data['title'][:60]}... ({doc_data.get('word_count', 0):,} words)")
    return document, True


def main():
    """Main ingestion function"""
    logger.info("=" * 80)
    logger.info("Jamie Dupree Substack Ingestion - 150 Days Lookback")
    logger.info("=" * 80)

    # Check environment
    if not os.environ.get('BROOKINGS_DATABASE_URL'):
        logger.error("❌ BROOKINGS_DATABASE_URL environment variable not set")
        logger.info("\nUsage:")
        logger.info("  export BROOKINGS_DATABASE_URL='postgresql://...'")
        logger.info("  python scripts/ingest_jamie_dupree_150days.py")
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
        lookback_days = 150
        since_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        logger.info(f"📅 Fetching posts since: {since_date} ({lookback_days} days)")

        # Create ingestion log
        log = IngestionLog(
            source_id=source.source_id,
            run_type='manual',
            started_at=datetime.now(),
            status='running'
        )
        session.add(log)
        session.commit()

        # Initialize ingester
        logger.info("\n🔍 Discovering posts...")
        ingester = SubstackIngester(rate_limit_delay=1.0)

        # Discover posts
        publications = ['jamiedupree.substack.com']
        documents = ingester.discover(
            publications=publications,
            since_date=since_date
        )

        logger.info(f"✅ Found {len(documents)} posts from Jamie Dupree")
        log.documents_checked = len(documents)
        session.commit()

        # Fetch and save each document
        logger.info("\n📥 Fetching and saving documents...")
        saved_count = 0
        skipped_count = 0
        error_count = 0

        for idx, doc_meta in enumerate(documents, 1):
            try:
                logger.info(f"\n[{idx}/{len(documents)}] {doc_meta['title'][:60]}...")

                # Fetch HTML content
                fetched = ingester.fetch(doc_meta)
                if not fetched:
                    logger.warning("  ⚠️  Failed to fetch content")
                    error_count += 1
                    continue

                # Parse content
                parsed = ingester.parse(doc_meta, fetched)
                if not parsed:
                    logger.warning("  ⚠️  Failed to parse content")
                    error_count += 1
                    continue

                # Save to database
                doc, is_new = save_document(session, parsed, source.source_id)
                if is_new:
                    saved_count += 1
                else:
                    skipped_count += 1

                session.commit()

            except Exception as e:
                logger.error(f"  ❌ Error processing document: {e}")
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
        logger.info(f"  Posts discovered: {len(documents)}")
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
