"""
Brookings CLI Commands Extension

Add these commands to cli.py to integrate Brookings ingestion.

Usage:
    python cli.py brookings init
    python cli.py brookings backfill --limit 100 --skip-existing
    python cli.py brookings update --days 30
    python cli.py brookings stats
    python cli.py brookings export --format csv --output ./exports/brookings.csv
"""

# Add this import at the top of cli.py:
# from brookings_ingester.ingesters import BrookingsIngester
# from brookings_ingester.models import init_database, get_session, Document, Source, IngestionLog

# Add this command group to cli.py (around line 1076, after @cli.group(name='crs-content')):

"""
@cli.group(name='brookings')
def brookings():
    \"\"\"Brookings Institution content management operations\"\"\"
    pass


@brookings.command()
def init():
    \"\"\"Initialize Brookings database and seed sources\"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.init_db import main as init_main
        result = init_main()

        if result == 0:
            logger.info("Brookings database initialized successfully")
        else:
            logger.error("Brookings database initialization failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--limit', default=None, type=int, help='Limit number of documents to ingest')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip documents that already exist')
@click.option('--method', type=click.Choice(['api', 'sitemap', 'both']), default='api',
              help='Discovery method: api (WordPress), sitemap, or both')
@click.option('--since-date', default='2025-01-01', help='Only ingest documents published on/after this date (YYYY-MM-DD)')
def backfill(limit, skip_existing, method, since_date):
    \"\"\"
    Initial backfill of Brookings content

    Discovers and ingests Brookings research documents using WordPress API
    or sitemap. Fetches HTML and PDF content, extracts metadata and text,
    and stores in database with full-text search support.
    \"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester

        logger.info(f"Starting Brookings backfill (method={method}, since={since_date})")

        # Initialize ingester
        ingester = BrookingsIngester()

        # Run ingestion
        result = ingester.run_ingestion(
            limit=limit,
            skip_existing=skip_existing,
            run_type='backfill',
            method=method,
            since_date=since_date
        )

        if result['success']:
            logger.info("Backfill completed successfully")
            stats = result['stats']
            logger.info(f"Checked: {stats['documents_checked']}, "
                       f"Fetched: {stats['documents_fetched']}, "
                       f"Updated: {stats['documents_updated']}, "
                       f"Skipped: {stats['documents_skipped']}, "
                       f"Errors: {stats['errors_count']}")
        else:
            logger.error(f"Backfill failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@brookings.command()
@click.option('--days', default=30, help='Update documents modified in last N days')
@click.option('--method', type=click.Choice(['api', 'sitemap', 'both']), default='api',
              help='Discovery method')
def update(days, method):
    \"\"\"
    Update Brookings content for recently modified documents

    Checks for documents updated in the last N days and refreshes their content.
    \"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester
        from datetime import datetime, timedelta

        # Calculate since_date
        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        logger.info(f"Updating Brookings content modified since {since_date}")

        # Initialize ingester
        ingester = BrookingsIngester()

        # Run update
        result = ingester.run_ingestion(
            limit=None,  # No limit for updates
            skip_existing=False,  # Re-fetch existing to check for updates
            run_type='update',
            method=method,
            since_date=since_date
        )

        if result['success']:
            logger.info("Update completed successfully")
            stats = result['stats']
            logger.info(f"Checked: {stats['documents_checked']}, "
                       f"Updated: {stats['documents_updated']}, "
                       f"Errors: {stats['errors_count']}")
        else:
            logger.error(f"Update failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
def stats(detailed):
    \"\"\"Show Brookings content statistics\"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.models import get_session, Document, Source, IngestionLog
        from sqlalchemy import func

        session = get_session()

        # Get Brookings source
        brookings = session.query(Source).filter_by(source_code='BROOKINGS').first()
        if not brookings:
            logger.error("Brookings source not found. Run: python cli.py brookings init")
            sys.exit(1)

        # Total documents
        total_docs = session.query(Document).filter_by(source_id=brookings.source_id).count()

        # Documents by type
        by_type = session.query(
            Document.document_type,
            func.count(Document.document_id)
        ).filter_by(source_id=brookings.source_id).group_by(Document.document_type).all()

        # Total words
        total_words = session.query(func.sum(Document.word_count)).filter_by(
            source_id=brookings.source_id
        ).scalar() or 0

        # Documents with PDFs
        with_pdfs = session.query(Document).filter(
            Document.source_id == brookings.source_id,
            Document.pdf_url.isnot(None)
        ).count()

        # Last ingestion
        last_log = session.query(IngestionLog).filter_by(
            source_id=brookings.source_id
        ).order_by(IngestionLog.started_at.desc()).first()

        # Print statistics
        click.echo("\n" + "=" * 70)
        click.echo("Brookings Content Statistics")
        click.echo("=" * 70)
        click.echo(f"Total documents:       {total_docs:>10,}")
        click.echo(f"Total words:           {total_words:>10,}")
        click.echo(f"Avg words/doc:         {int(total_words / total_docs) if total_docs > 0 else 0:>10,}")
        click.echo(f"Documents with PDFs:   {with_pdfs:>10,}")

        if by_type:
            click.echo("\nDocuments by type:")
            for doc_type, count in sorted(by_type, key=lambda x: x[1], reverse=True):
                click.echo(f"  {doc_type or 'Unknown':20} {count:>10,}")

        if last_log:
            click.echo(f"\nLast ingestion:")
            click.echo(f"  Date:         {last_log.started_at}")
            click.echo(f"  Type:         {last_log.run_type}")
            click.echo(f"  Status:       {last_log.status}")
            click.echo(f"  Fetched:      {last_log.documents_fetched}")
            click.echo(f"  Errors:       {last_log.errors_count}")

        click.echo("=" * 70 + "\n")

        if detailed:
            # Show recent documents
            recent_docs = session.query(Document).filter_by(
                source_id=brookings.source_id
            ).order_by(Document.created_at.desc()).limit(10).all()

            if recent_docs:
                click.echo("\nRecent documents:")
                for doc in recent_docs:
                    click.echo(f"\n  {doc.title[:70]}...")
                    click.echo(f"    Type: {doc.document_type}, Words: {doc.word_count:,}")
                    click.echo(f"    Date: {doc.publication_date}, URL: {doc.url}")

        session.close()

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--format', type=click.Choice(['csv', 'json']), default='csv',
              help='Export format')
@click.option('--output', default='brookings_export.csv', help='Output file path')
@click.option('--limit', type=int, help='Limit number of documents to export')
def export(format, output, limit):
    \"\"\"Export Brookings documents to CSV or JSON\"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.models import get_session, Document, Source
        import csv
        import json

        session = get_session()

        # Get Brookings source
        brookings = session.query(Source).filter_by(source_code='BROOKINGS').first()
        if not brookings:
            logger.error("Brookings source not found")
            sys.exit(1)

        # Query documents
        query = session.query(Document).filter_by(source_id=brookings.source_id).order_by(
            Document.publication_date.desc()
        )

        if limit:
            query = query.limit(limit)

        documents = query.all()

        if format == 'csv':
            with open(output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'document_id', 'identifier', 'title', 'document_type',
                    'publication_date', 'word_count', 'url', 'pdf_url'
                ])

                for doc in documents:
                    writer.writerow([
                        doc.document_id,
                        doc.document_identifier,
                        doc.title,
                        doc.document_type,
                        doc.publication_date,
                        doc.word_count,
                        doc.url,
                        doc.pdf_url or ''
                    ])

        elif format == 'json':
            data = []
            for doc in documents:
                data.append({
                    'document_id': doc.document_id,
                    'identifier': doc.document_identifier,
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'publication_date': str(doc.publication_date) if doc.publication_date else None,
                    'summary': doc.summary,
                    'word_count': doc.word_count,
                    'url': doc.url,
                    'pdf_url': doc.pdf_url
                })

            with open(output, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)

        logger.info(f"Exported {len(documents)} documents to {output}")
        session.close()

    except Exception as e:
        logger.error(f"Export failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--url', required=True, help='Brookings document URL to ingest')
def ingest_url(url):
    \"\"\"Ingest a single Brookings document by URL\"\"\"
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester

        logger.info(f"Ingesting document: {url}")

        ingester = BrookingsIngester()

        # Create document metadata
        doc_meta = {
            'document_identifier': ingester._extract_slug(url),
            'url': url,
            'title': None
        }

        # Fetch content
        logger.info("Fetching content...")
        fetched = ingester.fetch(doc_meta)
        if not fetched:
            logger.error("Failed to fetch content")
            sys.exit(1)

        # Parse content
        logger.info("Parsing content...")
        parsed = ingester.parse(doc_meta, fetched)
        if not parsed:
            logger.error("Failed to parse content")
            sys.exit(1)

        # Store document
        logger.info("Storing document...")
        document_id = ingester.store(parsed)
        if not document_id:
            logger.error("Failed to store document")
            sys.exit(1)

        logger.info(f"✓ Successfully ingested document (ID: {document_id})")
        logger.info(f"  Title: {parsed['title']}")
        logger.info(f"  Type: {parsed['document_type']}")
        logger.info(f"  Words: {parsed['word_count']:,}")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
"""
