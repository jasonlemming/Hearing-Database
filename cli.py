#!/usr/bin/env python3
"""
Congressional Hearing Database - Unified CLI Tool

This unified CLI consolidates all database management scripts into a single,
organized command-line interface for easier management and reduced script proliferation.

Usage:
    python cli.py import --congress 119 --phase hearings
    python cli.py enhance --target titles --limit 100
    python cli.py update --incremental --lookback-days 7
    python cli.py database --init
    python cli.py analysis --audit

Commands:
    import      Import data from Congress.gov API
    enhance     Enhance existing data with additional details
    update      Update database with latest changes
    database    Database management operations
    analysis    Analysis and audit operations
    witness     Witness-specific operations
    web         Web application operations
"""

import sys
import os
import click
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.settings import settings
from config.logging_config import setup_logging, get_logger


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--config-check', is_flag=True, help='Check configuration and exit')
@click.pass_context
def cli(ctx, verbose, config_check):
    """Congressional Hearing Database - Unified CLI Tool"""
    setup_logging()

    # Override log level if verbose
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

    if config_check:
        check_configuration()
        sys.exit(0)


@cli.group()
def import_cmd():
    """Import data from Congress.gov API"""
    pass


@import_cmd.command()
@click.option('--congress', default=settings.target_congress, help='Congress number to import')
@click.option('--validation', is_flag=True, help='Run in validation mode (no database writes)')
@click.option('--phase', type=click.Choice(['committees', 'members', 'hearings', 'documents', 'all']),
              default='all', help='Specific phase to run')
@click.option('--resume', is_flag=True, help='Resume from last checkpoint')
@click.option('--batch-size', default=settings.batch_size, help='Batch size for processing')
def full(congress, validation, phase, resume, batch_size):
    """Run full data import (equivalent to run_import.py)"""
    logger = get_logger(__name__)

    try:
        from importers.orchestrator import ImportOrchestrator

        # Initialize components
        db_manager = DatabaseManager()
        api_client = CongressAPIClient()
        orchestrator = ImportOrchestrator(db_manager, api_client)

        logger.info(f"Starting import for Congress {congress}, phase: {phase}")
        if validation:
            logger.info("Running in VALIDATION mode - no data will be written")

        # Check if resuming
        if resume:
            logger.info("Attempting to resume from last checkpoint...")
            last_phase = orchestrator.resume_from_checkpoint()
            if last_phase:
                logger.info(f"Resuming from phase: {last_phase}")

        # Run import based on phase
        if phase == 'all':
            result = orchestrator.run_full_import(
                congress=congress,
                validation_mode=validation,
                batch_size=batch_size
            )
        else:
            result = run_specific_phase(orchestrator, phase, congress, validation, batch_size)

        # Display results
        display_import_results(result, db_manager)
        logger.info("Import completed successfully")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)


@import_cmd.command()
@click.option('--congress', default=119, help='Congress number')
@click.option('--chamber', type=click.Choice(['house', 'senate', 'both']), default='both')
@click.option('--committee', help='Specific committee system name')
def hearings(congress, chamber, committee):
    """Import hearings for specific criteria"""
    logger = get_logger(__name__)

    try:
        from fetchers.hearing_fetcher import HearingFetcher
        from parsers.hearing_parser import HearingParser

        db = DatabaseManager()
        fetcher = HearingFetcher()
        parser = HearingParser()

        chambers = ['house', 'senate'] if chamber == 'both' else [chamber]

        total_imported = 0
        for ch in chambers:
            logger.info(f"Importing {ch} hearings for Congress {congress}")

            if committee:
                hearings = fetcher.fetch_committee_hearings(congress, ch, committee)
            else:
                hearings = fetcher.fetch_hearings_by_congress(congress, ch)

            for hearing_data in hearings:
                parsed = parser.parse_hearing(hearing_data)
                if parsed:
                    db.save_hearing(parsed)
                    total_imported += 1

        logger.info(f"Imported {total_imported} hearings")

    except Exception as e:
        logger.error(f"Hearing import failed: {e}")
        sys.exit(1)


@cli.group()
def enhance():
    """Enhance existing data with additional details"""
    pass


@enhance.command()
@click.option('--target', type=click.Choice(['titles', 'dates', 'committees', 'all']),
              default='all', help='What to enhance')
@click.option('--limit', default=200, help='Maximum number of records to process')
@click.option('--chamber', type=click.Choice(['house', 'senate', 'both']), default='both')
def hearings(target, limit, chamber):
    """Enhance hearing data (equivalent to enhance_hearings.py and variants)"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager
        from api.client import CongressAPIClient

        db = DatabaseManager()
        client = CongressAPIClient()

        # Build query based on target
        where_conditions = []
        if target in ['titles', 'all']:
            where_conditions.append("(h.title IS NULL OR h.title = '')")
        if target in ['dates', 'all']:
            where_conditions.append("h.hearing_date IS NULL")
        if target in ['committees', 'all']:
            where_conditions.append("hc.hearing_id IS NULL")

        chamber_filter = ""
        if chamber != 'both':
            chamber_filter = f"AND h.chamber = '{chamber.upper()}'"

        with db.transaction() as conn:
            query = f'''
                SELECT DISTINCT h.hearing_id, h.event_id, h.congress, h.chamber
                FROM hearings h
                LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                WHERE ({' OR '.join(where_conditions)})
                AND h.event_id IS NOT NULL
                {chamber_filter}
                ORDER BY h.hearing_id
                LIMIT {limit}
            '''
            cursor = conn.execute(query)
            hearings_to_enhance = cursor.fetchall()

        logger.info(f"Found {len(hearings_to_enhance)} hearings to enhance")

        enhanced_count = 0
        errors = 0

        for hearing_id, event_id, congress, chamber in hearings_to_enhance:
            try:
                logger.info(f"Enhancing hearing {hearing_id} (event {event_id})")

                # Fetch detailed hearing data
                detailed_data = client.get_hearing_details(congress, chamber.lower(), event_id)

                if detailed_data:
                    # Parse and update hearing
                    updates = {}
                    if 'title' in detailed_data and detailed_data['title']:
                        updates['title'] = detailed_data['title']

                    if 'date' in detailed_data and detailed_data['date']:
                        updates['hearing_date'] = detailed_data['date']
                        updates['hearing_date_only'] = detailed_data['date'][:10]

                    if updates:
                        db.update_hearing(hearing_id, updates)
                        enhanced_count += 1

            except Exception as e:
                logger.error(f"Error enhancing hearing {hearing_id}: {e}")
                errors += 1

        logger.info(f"Enhanced {enhanced_count} hearings with {errors} errors")

    except Exception as e:
        logger.error(f"Enhancement failed: {e}")
        sys.exit(1)


@enhance.command()
@click.option('--limit', default=100, help='Maximum number of missing titles to fix')
def titles(limit):
    """Fix missing titles (equivalent to enhance_missing_titles.py)"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager
        from api.client import CongressAPIClient

        db = DatabaseManager()
        client = CongressAPIClient()

        # Find hearings with missing or generic titles
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT hearing_id, event_id, congress, chamber
                FROM hearings
                WHERE (title IS NULL OR title = '' OR title LIKE 'Event #%')
                AND event_id IS NOT NULL
                ORDER BY hearing_id
                LIMIT ?
            ''', (limit,))
            hearings = cursor.fetchall()

        logger.info(f"Found {len(hearings)} hearings with missing titles")

        fixed_count = 0
        for hearing_id, event_id, congress, chamber in hearings:
            try:
                detailed_data = client.get_hearing_details(congress, chamber.lower(), event_id)

                if detailed_data and detailed_data.get('title'):
                    title = detailed_data['title']
                    if title and not title.startswith('Event #'):
                        db.update_hearing(hearing_id, {'title': title})
                        logger.info(f"Fixed title for hearing {hearing_id}: {title[:60]}...")
                        fixed_count += 1

            except Exception as e:
                logger.error(f"Error fixing title for hearing {hearing_id}: {e}")

        logger.info(f"Fixed {fixed_count} hearing titles")

    except Exception as e:
        logger.error(f"Title enhancement failed: {e}")
        sys.exit(1)


@cli.group()
def update():
    """Update database with latest changes"""
    pass


@update.command()
@click.option('--congress', default=119, help='Congress number to update')
@click.option('--lookback-days', default=7, help='Days to look back for changes')
@click.option('--mode', type=click.Choice(['incremental', 'full']), default='incremental',
              help='Update mode: incremental (lookback window) or full (all hearings)')
@click.option('--components', '-c',
              multiple=True,
              type=click.Choice(['hearings', 'witnesses', 'committees'], case_sensitive=False),
              default=['hearings', 'witnesses', 'committees'],
              help='Components to update. hearings includes videos (same API response). Omit witnesses/committees for faster updates.')
@click.option('--dry-run', is_flag=True, help='Preview changes without modifying database')
@click.option('--quiet', is_flag=True, help='Reduce output for cron jobs')
@click.option('--json-progress', is_flag=True, help='Output progress as JSON for admin dashboard')
def incremental(congress, lookback_days, mode, components, dry_run, quiet, json_progress):
    """Run incremental daily update (equivalent to daily_update.py)"""
    import json
    from datetime import datetime

    logger = get_logger(__name__)

    if quiet:
        logger.setLevel('WARNING')

    # JSON progress mode: output structured progress to stdout
    if json_progress:
        print(json.dumps({
            'type': 'start',
            'timestamp': datetime.now().isoformat(),
            'congress': congress,
            'lookback_days': lookback_days,
            'mode': mode
        }), flush=True)

    try:
        from updaters.daily_updater import DailyUpdater

        # Convert components tuple to list
        components_list = list(components) if components else None

        updater = DailyUpdater(
            congress=congress,
            lookback_days=lookback_days,
            update_mode=mode,
            components=components_list
        )

        if json_progress:
            mode_desc = 'full sync of all hearings' if mode == 'full' else f'{lookback_days}-day lookback'
            dry_run_note = ' (DRY RUN - no database changes)' if dry_run else ''
            print(json.dumps({
                'type': 'log',
                'level': 'info',
                'message': f'Starting {mode} update for Congress {congress}, {mode_desc}{dry_run_note}',
                'components': components_list
            }), flush=True)

        # Create progress callback for JSON mode
        def progress_callback(data):
            if json_progress:
                print(json.dumps({
                    'type': 'progress',
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                }), flush=True)

        result = updater.run_daily_update(
            dry_run=dry_run,
            progress_callback=progress_callback if json_progress else None
        )

        if json_progress:
            # Output completion with metrics
            print(json.dumps({
                'type': 'complete',
                'success': result.get('success', False),
                'metrics': result.get('metrics', {}),
                'timestamp': datetime.now().isoformat()
            }), flush=True)
        elif not quiet:
            logger.info("Daily update completed successfully")
            logger.info(f"Results: {result}")

        # Exit code based on success
        if not result.get('success', False):
            sys.exit(1)

    except Exception as e:
        if json_progress:
            print(json.dumps({
                'type': 'error',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }), flush=True)
        else:
            logger.error(f"Daily update failed: {e}")
        sys.exit(1)


@update.command()
@click.option('--congress', default=119, help='Congress number')
@click.option('--chamber', type=click.Choice(['house', 'senate', 'joint', 'all']), default='all')
def committees(congress, chamber):
    """Refresh committee data (equivalent to refresh_committees.py)"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager
        from api.client import CongressAPIClient

        db = DatabaseManager()
        client = CongressAPIClient()

        chambers = ['house', 'senate', 'joint'] if chamber == 'all' else [chamber]

        total_updated = 0
        total_new = 0

        for ch in chambers:
            logger.info(f"Refreshing {ch} committees for Congress {congress}")

            # Fetch committees from API
            committees_data = client.get(f"committee/{congress}/{ch}", {"limit": 250})

            if 'committees' in committees_data:
                for committee_data in committees_data['committees']:
                    committee_id = committee_data.get('systemCode')
                    name = committee_data.get('name')

                    if committee_id and name:
                        # Check if exists
                        existing = db.fetch_one(
                            "SELECT committee_id FROM committees WHERE committee_id = ?",
                            (committee_id,)
                        )

                        if existing:
                            # Update existing
                            db.execute(
                                "UPDATE committees SET name = ?, congress = ?, chamber = ? WHERE committee_id = ?",
                                (name, congress, ch.upper(), committee_id)
                            )
                            total_updated += 1
                        else:
                            # Insert new
                            db.execute(
                                "INSERT INTO committees (committee_id, name, congress, chamber) VALUES (?, ?, ?, ?)",
                                (committee_id, name, congress, ch.upper())
                            )
                            total_new += 1

        logger.info(f"Committee refresh complete: {total_new} new, {total_updated} updated")

    except Exception as e:
        logger.error(f"Committee refresh failed: {e}")
        sys.exit(1)


@update.command()
@click.option('--congress', default=119, help='Congress number')
@click.option('--chamber', type=click.Choice(['house', 'senate', 'all']), default='all')
@click.option('--lookback-days', default=30, help='Days to look back for updated hearings')
@click.option('--include-videos', is_flag=True, help='Fetch and update video URLs')
def hearings(congress, chamber, lookback_days, include_videos):
    """Update hearing data including titles, dates, status, and optionally videos"""
    logger = get_logger(__name__)

    try:
        from updaters.daily_updater import DailyUpdater

        chambers = ['house', 'senate'] if chamber == 'all' else [chamber]

        logger.info(f"Updating hearings for Congress {congress}, lookback: {lookback_days} days")
        if include_videos:
            logger.info("Video URL updates enabled")

        # Use DailyUpdater for hearing updates
        updater = DailyUpdater(congress=congress, lookback_days=lookback_days)
        result = updater.run_daily_update()

        if result['success']:
            metrics = result['metrics']
            logger.info(f"Updated {metrics['hearings_updated']} hearings")
            logger.info(f"Added {metrics['hearings_added']} new hearings")
            if metrics['error_count'] > 0:
                logger.warning(f"Encountered {metrics['error_count']} errors")
        else:
            logger.error(f"Update failed: {result.get('error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Hearing update failed: {e}")
        sys.exit(1)


@update.command()
@click.option('--congress', default=119, help='Congress number')
@click.option('--limit', default=100, help='Maximum number of hearings to update')
@click.option('--force', is_flag=True, help='Update all hearings, even those with existing videos')
def videos(congress, limit, force):
    """Update video URLs and YouTube video IDs for hearings"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager
        from fetchers.hearing_fetcher import HearingFetcher
        from parsers.hearing_parser import HearingParser
        from api.client import CongressAPIClient

        db = DatabaseManager()
        api_client = CongressAPIClient()
        fetcher = HearingFetcher(api_client)
        parser = HearingParser()

        # Build query
        video_filter = "" if force else "AND (video_url IS NULL OR video_url = '')"

        with db.transaction() as conn:
            query = f"""
                SELECT event_id, congress, chamber
                FROM hearings
                WHERE event_id IS NOT NULL
                {video_filter}
                ORDER BY hearing_date DESC
                LIMIT {limit}
            """
            cursor = conn.execute(query)
            hearings_to_update = cursor.fetchall()

        logger.info(f"Found {len(hearings_to_update)} hearings to update with video data")

        updated_count = 0
        errors = 0

        for row in hearings_to_update:
            event_id = row['event_id']
            congress = row['congress']
            chamber = row['chamber']

            try:
                # Fetch detailed hearing data including video
                detailed_data = fetcher.fetch_hearing_details(congress, chamber.lower(), event_id)

                if detailed_data:
                    # Parse to extract video data
                    parsed = parser.parse(detailed_data)
                    if parsed and (parsed.video_url or parsed.youtube_video_id):
                        # Update using db.upsert_hearing to handle FK constraints properly
                        hearing_dict = parsed.dict()
                        hearing_dict['congress'] = congress
                        db.upsert_hearing(hearing_dict)
                        updated_count += 1
                        logger.info(f"Updated video for {event_id}: {parsed.video_url or 'YouTube ID: ' + str(parsed.youtube_video_id)}")

            except Exception as e:
                logger.error(f"Error updating video for {event_id}: {e}")
                errors += 1

        logger.info(f"Video update complete: {updated_count} updated, {errors} errors")

    except Exception as e:
        logger.error(f"Video update failed: {e}")
        sys.exit(1)


@update.command()
@click.option('--congress', default=119, help='Congress number')
@click.option('--lookback-days', default=30, help='Update witnesses for hearings in last N days')
def witnesses(congress, lookback_days):
    """Update witness information for recent hearings"""
    logger = get_logger(__name__)

    try:
        from updaters.daily_updater import DailyUpdater

        logger.info(f"Updating witnesses for hearings in last {lookback_days} days")

        # DailyUpdater handles witness updates as part of its process
        updater = DailyUpdater(congress=congress, lookback_days=lookback_days)
        result = updater.run_daily_update()

        if result['success']:
            metrics = result['metrics']
            logger.info(f"Updated {metrics['witnesses_updated']} witnesses")
            if metrics['error_count'] > 0:
                logger.warning(f"Encountered {metrics['error_count']} errors")
        else:
            logger.error(f"Update failed: {result.get('error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Witness update failed: {e}")
        sys.exit(1)


@cli.group()
def database():
    """Database management operations"""
    pass


@database.command()
def init():
    """Initialize database schema (equivalent to init_database.py)"""
    logger = get_logger(__name__)

    try:
        from scripts.init_database import main as init_main
        init_main()
        logger.info("Database initialization completed")

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)


@database.command()
def clean():
    """Clean obsolete committees and data (equivalent to clean_committees.py)"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager

        db = DatabaseManager()

        # Remove obsolete committees
        removed = db.execute('''
            DELETE FROM committees
            WHERE committee_id IN (
                SELECT committee_id FROM committees
                WHERE name LIKE '%Historical%'
                OR name LIKE '%Archive%'
                OR committee_id LIKE '%HIST%'
            )
        ''')

        logger.info(f"Cleaned {removed} obsolete committee records")

    except Exception as e:
        logger.error(f"Database cleanup failed: {e}")
        sys.exit(1)


@database.command()
def status():
    """Show database status and record counts"""
    logger = get_logger(__name__)

    try:
        db = DatabaseManager()
        counts = db.get_table_counts()

        click.echo("\nDatabase Status:")
        click.echo("=" * 50)
        for table, count in counts.items():
            click.echo(f"{table:20}: {count:>10,}")

    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        sys.exit(1)


@cli.group()
def witness():
    """Witness-specific operations"""
    pass


@witness.command()
@click.option('--congress', default=119, help='Congress number to import witnesses for')
@click.option('--limit', help='Maximum number of hearings to process')
@click.option('--batch-size', default=10, help='Number of hearings to process per batch')
def import_all(congress, limit, batch_size):
    """Import witnesses for all hearings (equivalent to import_witnesses.py)"""
    logger = get_logger(__name__)

    try:
        from scripts.import_witnesses import WitnessImporter

        importer = WitnessImporter()
        result = importer.import_witnesses_for_congress(
            congress=congress,
            limit=limit,
            batch_size=batch_size
        )

        logger.info("Witness import completed")
        logger.info(f"Results: {result}")

    except Exception as e:
        logger.error(f"Witness import failed: {e}")
        sys.exit(1)


@witness.command()
def test():
    """Test witness API connectivity (equivalent to test_witness_api.py)"""
    logger = get_logger(__name__)

    try:
        from scripts.test_witness_api import main as test_main
        test_main()

    except Exception as e:
        logger.error(f"Witness API test failed: {e}")
        sys.exit(1)


@cli.group()
def analysis():
    """Analysis and audit operations"""
    pass


@analysis.command()
def audit():
    """Comprehensive database audit (equivalent to comprehensive_database_audit.py)"""
    logger = get_logger(__name__)

    try:
        from scripts.comprehensive_database_audit import main as audit_main
        audit_main()

    except Exception as e:
        logger.error(f"Database audit failed: {e}")
        sys.exit(1)


@analysis.command()
@click.option('--days', default=7, help='Number of days to analyze')
def recent(days):
    """Analyze recent hearing activity"""
    logger = get_logger(__name__)

    try:
        from database.manager import DatabaseManager
        from datetime import datetime, timedelta

        db = DatabaseManager()

        cutoff_date = datetime.now() - timedelta(days=days)

        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_hearings,
                    COUNT(CASE WHEN chamber = 'HOUSE' THEN 1 END) as house_hearings,
                    COUNT(CASE WHEN chamber = 'SENATE' THEN 1 END) as senate_hearings,
                    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_titles
                FROM hearings
                WHERE hearing_date >= ?
            ''', (cutoff_date.strftime('%Y-%m-%d'),))

            results = cursor.fetchone()

        click.echo(f"\nRecent Activity ({days} days):")
        click.echo("=" * 40)
        click.echo(f"Total hearings: {results[0]}")
        click.echo(f"House hearings: {results[1]}")
        click.echo(f"Senate hearings: {results[2]}")
        click.echo(f"With titles: {results[3]}")

    except Exception as e:
        logger.error(f"Recent analysis failed: {e}")
        sys.exit(1)


@cli.group()
def web():
    """Web application operations"""
    pass


@web.command()
@click.option('--host', default='127.0.0.1', help='Host to bind to')
@click.option('--port', default=5000, help='Port to bind to')
@click.option('--debug', is_flag=True, help='Run in debug mode')
def serve(host, port, debug):
    """Start the web application"""
    logger = get_logger(__name__)

    try:
        from web.app import app
        logger.info(f"Starting web server on {host}:{port}")
        app.run(host=host, port=port, debug=debug)

    except Exception as e:
        logger.error(f"Web server failed: {e}")
        sys.exit(1)


@cli.group(name='crs-content')
def crs_content():
    """CRS content management operations (HTML text ingestion)"""
    pass


@crs_content.command()
@click.option('--limit', default=None, type=int, help='Limit number of products to backfill')
@click.option('--product-id', help='Backfill specific product only')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip products with existing content')
def backfill(limit, product_id, skip_existing):
    """
    Initial backfill of CRS HTML content for all products

    This will fetch HTML content from congress.gov using headless browser
    to bypass Cloudflare protection, parse the content, and store it in the database.
    """
    logger = get_logger(__name__)

    try:
        from fetchers.crs_content_fetcher import CRSContentFetcher
        from parsers.crs_html_parser import CRSHTMLParser
        from database.crs_content_manager import CRSContentManager
        from database.postgres_config import get_connection
        from psycopg2.extras import RealDictCursor

        logger.info("Starting CRS content backfill...")

        # Initialize components
        fetcher = CRSContentFetcher(rate_limit_delay=1.0)  # Slower for backfill
        parser = CRSHTMLParser()
        manager = CRSContentManager()

        # Start ingestion log
        log_id = manager.start_ingestion_log('backfill')

        # Get products to process
        if product_id:
            # Single product
            with get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
                    product = cur.fetchone()

            if not product:
                logger.error(f"Product {product_id} not found")
                sys.exit(1)

            products = [dict(product)]
            logger.info(f"Processing single product: {product_id}")
        else:
            # Get products needing content
            if skip_existing:
                products = manager.get_products_needing_content(limit=limit)
                logger.info(f"Found {len(products)} products without content")
            else:
                # Get all products
                with get_connection() as conn:
                    with conn.cursor(cursor_factory=RealDictCursor) as cur:
                        query = "SELECT * FROM products ORDER BY publication_date DESC"
                        if limit:
                            query += f" LIMIT {limit}"
                        cur.execute(query)
                        products = [dict(row) for row in cur.fetchall()]
                logger.info(f"Processing {len(products)} products (including existing)")

        # Process products
        total = len(products)
        success_count = 0
        error_count = 0
        skip_count = 0
        errors = []

        for i, product in enumerate(products, 1):
            product_id = product['product_id']
            version_number = product.get('version', 1)
            html_url = product.get('url_html')

            if not html_url:
                logger.warning(f"[{i}/{total}] Skipping {product_id}: No HTML URL")
                skip_count += 1
                continue

            try:
                logger.info(f"[{i}/{total}] Processing {product_id} v{version_number}...")

                # Check if needs update
                if skip_existing and not manager.needs_update(product_id, version_number, html_url):
                    logger.info(f"  Skipping {product_id}: Already have current version")
                    skip_count += 1
                    continue

                # Fetch HTML with browser
                result = fetcher.fetch_html_with_browser(html_url)
                if not result:
                    raise Exception("Failed to fetch HTML")

                html_content, metadata = result

                # Parse HTML
                parsed = parser.parse(html_content, product_id)
                if not parsed:
                    raise Exception("Failed to parse HTML")

                # Store in database
                version_id = manager.upsert_version(
                    product_id=product_id,
                    version_number=version_number,
                    html_content=parsed.html_content,
                    text_content=parsed.text_content,
                    structure_json=parsed.structure_json,
                    content_hash=parsed.content_hash,
                    word_count=parsed.word_count,
                    html_url=html_url
                )

                success_count += 1
                logger.info(f"  ✓ Success: {parsed.word_count:,} words, {len(parsed.structure_json['headings'])} headings")

            except Exception as e:
                error_count += 1
                error_msg = f"{product_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"  ✗ Error: {e}")

        # Update log
        manager.update_ingestion_log(
            log_id,
            products_checked=total,
            content_fetched=success_count,
            content_skipped=skip_count,
            errors_count=error_count,
            error_details=errors[:100]  # Limit to 100 errors
        )

        # Complete log
        status = 'completed' if error_count == 0 else ('partial' if success_count > 0 else 'failed')
        manager.complete_ingestion_log(log_id, status)

        # Show statistics
        stats = fetcher.get_stats()
        logger.info("\n" + "=" * 70)
        logger.info("Backfill Complete!")
        logger.info(f"  Processed: {total} products")
        logger.info(f"  Success: {success_count}")
        logger.info(f"  Skipped: {skip_count}")
        logger.info(f"  Errors: {error_count}")
        logger.info(f"  Avg fetch time: {stats['avg_fetch_time_ms']:.0f}ms")
        logger.info(f"  Total size: {stats['total_bytes'] / 1024 / 1024:.1f} MB")
        logger.info("=" * 70)

        # Sync CRS products to Policy Library
        if success_count > 0:
            try:
                logger.info("\nSyncing CRS products to Policy Library...")
                from brookings_ingester.crs_sync import sync_crs_to_policy_library

                sync_stats = sync_crs_to_policy_library()
                logger.info(f"✓ Policy Library sync complete: {sync_stats['documents_created']} created, "
                           f"{sync_stats['documents_updated']} updated, {sync_stats['documents_skipped']} skipped")
            except Exception as sync_error:
                logger.warning(f"Policy Library sync failed (non-fatal): {sync_error}")
                # Don't fail the entire backfill if sync fails

        if error_count > 0:
            logger.warning(f"{error_count} errors occurred during backfill")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@crs_content.command()
@click.option('--days', default=30, help='Update products modified in last N days')
def update(days):
    """
    Update CRS content for recently modified products

    Checks for products updated in the last N days and fetches their latest content.
    """
    logger = get_logger(__name__)

    try:
        from fetchers.crs_content_fetcher import CRSContentFetcher
        from parsers.crs_html_parser import CRSHTMLParser
        from database.crs_content_manager import CRSContentManager
        from database.postgres_config import get_connection
        from psycopg2.extras import RealDictCursor
        from datetime import datetime, timedelta

        logger.info(f"Updating CRS content for products modified in last {days} days...")

        # Initialize components
        fetcher = CRSContentFetcher()
        parser = CRSHTMLParser()
        manager = CRSContentManager()

        # Get recently updated products
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        with get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM products
                    WHERE updated_at >= %s
                    OR publication_date >= %s
                    ORDER BY updated_at DESC
                """, (cutoff, cutoff))
                products = [dict(p) for p in cur.fetchall()]
        logger.info(f"Found {len(products)} recently updated products")

        if not products:
            logger.info("No products to update")
            return

        # Start ingestion log
        log_id = manager.start_ingestion_log('update')

        # Process products
        success_count = 0
        error_count = 0

        for i, product in enumerate(products, 1):
            product_id = product['product_id']
            version_number = product.get('version', 1)
            html_url = product.get('url_html')

            if not html_url:
                continue

            try:
                if not manager.needs_update(product_id, version_number, html_url):
                    continue

                logger.info(f"[{i}/{len(products)}] Updating {product_id}...")

                result = fetcher.fetch_html_with_browser(html_url)
                if result:
                    html_content, _ = result
                    parsed = parser.parse(html_content, product_id)
                    if parsed:
                        manager.upsert_version(
                            product_id=product_id,
                            version_number=version_number,
                            html_content=parsed.html_content,
                            text_content=parsed.text_content,
                            structure_json=parsed.structure_json,
                            content_hash=parsed.content_hash,
                            word_count=parsed.word_count,
                            html_url=html_url
                        )
                        success_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"Error updating {product_id}: {e}")

        # Complete log
        manager.update_ingestion_log(log_id, content_fetched=success_count, errors_count=error_count)
        manager.complete_ingestion_log(log_id)

        logger.info(f"Update complete: {success_count} updated, {error_count} errors")

        # Sync CRS products to Policy Library
        if success_count > 0:
            try:
                logger.info("Syncing CRS products to Policy Library...")
                from brookings_ingester.crs_sync import sync_crs_to_policy_library

                sync_stats = sync_crs_to_policy_library()
                logger.info(f"✓ Policy Library sync complete: {sync_stats['documents_created']} created, "
                           f"{sync_stats['documents_updated']} updated, {sync_stats['documents_skipped']} skipped")
            except Exception as sync_error:
                logger.warning(f"Policy Library sync failed (non-fatal): {sync_error}")
                # Don't fail the entire ingestion if sync fails

    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)


@crs_content.command()
def stats():
    """Show CRS content ingestion statistics"""
    logger = get_logger(__name__)

    try:
        from database.crs_content_manager import CRSContentManager

        manager = CRSContentManager()
        stats = manager.get_ingestion_stats()

        click.echo("\n" + "=" * 70)
        click.echo("CRS Content Statistics")
        click.echo("=" * 70)
        click.echo(f"Total products:        {stats['total_products']:>10,}")
        click.echo(f"With content:          {stats['products_with_content']:>10,} ({stats['coverage_percent']}%)")
        click.echo(f"Current versions:      {stats['current_versions']:>10,}")
        click.echo(f"Total versions:        {stats['total_versions']:>10,}")
        click.echo(f"Storage used:          {stats['total_storage_bytes'] / 1024 / 1024:>10.1f} MB")
        click.echo(f"Avg word count:        {stats['avg_word_count']:>10,.0f}")

        if stats.get('last_ingestion'):
            last = stats['last_ingestion']
            click.echo(f"\nLast ingestion:        {last['started_at']}")
            click.echo(f"  Status:              {last['status']}")
            click.echo(f"  Items fetched:       {last['content_fetched']}")

        click.echo("=" * 70 + "\n")

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        sys.exit(1)


@cli.group(name='brookings')
def brookings():
    """Brookings Institution content management operations"""
    pass


@brookings.command()
def init():
    """Initialize Brookings database and seed sources"""
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
@click.option('--since-date', default='2024-01-01', help='Only ingest documents published on/after this date (YYYY-MM-DD)')
def backfill(limit, skip_existing, method, since_date):
    """Initial backfill of Brookings content"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester

        logger.info(f"Starting Brookings backfill (method={method}, since={since_date})")
        ingester = BrookingsIngester()

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
@click.option('--method', type=click.Choice(['api', 'sitemap', 'both']), default='api')
def update(days, method):
    """Update Brookings content for recently modified documents"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester
        from datetime import datetime, timedelta

        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"Updating Brookings content modified since {since_date}")

        ingester = BrookingsIngester()
        result = ingester.run_ingestion(
            limit=None,
            skip_existing=False,
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
            logger.error(f"Update failed: {result.get('error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
def stats(detailed):
    """Show Brookings content statistics"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.models import get_session, Document, Source, IngestionLog
        from sqlalchemy import func

        session = get_session()
        brookings = session.query(Source).filter_by(source_code='BROOKINGS').first()

        if not brookings:
            logger.error("Brookings source not found. Run: python cli.py brookings init")
            sys.exit(1)

        total_docs = session.query(Document).filter_by(source_id=brookings.source_id).count()
        total_words = session.query(func.sum(Document.word_count)).filter_by(source_id=brookings.source_id).scalar() or 0
        with_pdfs = session.query(Document).filter(
            Document.source_id == brookings.source_id,
            Document.pdf_url.isnot(None)
        ).count()

        click.echo("\n" + "=" * 70)
        click.echo("Brookings Content Statistics")
        click.echo("=" * 70)
        click.echo(f"Total documents:       {total_docs:>10,}")
        click.echo(f"Total words:           {total_words:>10,}")
        click.echo(f"Documents with PDFs:   {with_pdfs:>10,}")
        click.echo("=" * 70 + "\n")

        session.close()

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        sys.exit(1)


@brookings.command()
@click.option('--url', required=True, help='Brookings document URL to ingest')
def ingest_url(url):
    """Ingest a single Brookings document by URL"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import BrookingsIngester

        ingester = BrookingsIngester()
        doc_meta = {'document_identifier': ingester._extract_slug(url), 'url': url}

        fetched = ingester.fetch(doc_meta)
        if not fetched:
            logger.error("Failed to fetch content")
            sys.exit(1)

        parsed = ingester.parse(doc_meta, fetched)
        if not parsed:
            logger.error("Failed to parse content")
            sys.exit(1)

        document_id = ingester.store(parsed)
        if not document_id:
            logger.error("Failed to store document")
            sys.exit(1)

        logger.info(f"✓ Successfully ingested document (ID: {document_id})")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


@cli.group(name='substack')
def substack():
    """Substack newsletter content management operations"""
    pass


@substack.command()
@click.option('--limit', default=None, type=int, help='Limit number of posts to ingest')
@click.option('--skip-existing', is_flag=True, default=True, help='Skip posts that already exist')
@click.option('--publications', '-p', multiple=True, help='Substack publications to ingest (e.g., author.substack.com)')
@click.option('--since-date', default='2025-01-01', help='Only ingest posts published on/after this date (YYYY-MM-DD)')
def backfill(limit, skip_existing, publications, since_date):
    """Initial backfill of Substack newsletter content"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import SubstackIngester

        # Convert publications tuple to list
        pubs_list = list(publications) if publications else None

        logger.info(f"Starting Substack backfill (since={since_date})")
        if pubs_list:
            logger.info(f"Publications: {', '.join(pubs_list)}")

        ingester = SubstackIngester()

        result = ingester.run_ingestion(
            limit=limit,
            skip_existing=skip_existing,
            run_type='backfill',
            publications=pubs_list,
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


@substack.command()
@click.option('--days', default=30, help='Update posts published in last N days')
@click.option('--publications', '-p', multiple=True, help='Substack publications to update')
def update(days, publications):
    """Update Substack content for recently published posts"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import SubstackIngester
        from datetime import datetime, timedelta

        # Convert publications tuple to list
        pubs_list = list(publications) if publications else None

        since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        logger.info(f"Updating Substack content published since {since_date}")

        ingester = SubstackIngester()
        result = ingester.run_ingestion(
            limit=None,
            skip_existing=False,
            run_type='update',
            publications=pubs_list,
            since_date=since_date
        )

        if result['success']:
            logger.info("Update completed successfully")
            stats = result['stats']
            logger.info(f"Checked: {stats['documents_checked']}, "
                       f"Updated: {stats['documents_updated']}, "
                       f"Errors: {stats['errors_count']}")
        else:
            logger.error(f"Update failed: {result.get('error')}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Update failed: {e}")
        sys.exit(1)


@substack.command()
@click.option('--detailed', is_flag=True, help='Show detailed statistics')
def stats(detailed):
    """Show Substack content statistics"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.models import get_session, Document, Source, IngestionLog
        from sqlalchemy import func

        session = get_session()
        substack = session.query(Source).filter_by(source_code='SUBSTACK').first()

        if not substack:
            logger.error("Substack source not found. Run: python cli.py substack backfill")
            sys.exit(1)

        total_docs = session.query(Document).filter_by(source_id=substack.source_id).count()
        total_words = session.query(func.sum(Document.word_count)).filter_by(source_id=substack.source_id).scalar() or 0

        click.echo("\n" + "=" * 70)
        click.echo("Substack Content Statistics")
        click.echo("=" * 70)
        click.echo(f"Total posts:           {total_docs:>10,}")
        click.echo(f"Total words:           {total_words:>10,}")
        click.echo("=" * 70 + "\n")

        session.close()

    except Exception as e:
        logger.error(f"Stats failed: {e}")
        sys.exit(1)


@substack.command()
@click.option('--url', required=True, help='Substack post URL to ingest')
def ingest_url(url):
    """Ingest a single Substack post by URL"""
    logger = get_logger(__name__)

    try:
        from brookings_ingester.ingesters import SubstackIngester

        ingester = SubstackIngester()
        doc_meta = {'document_identifier': ingester._extract_slug(url), 'url': url}

        fetched = ingester.fetch(doc_meta)
        if not fetched:
            logger.error("Failed to fetch content")
            sys.exit(1)

        parsed = ingester.parse(doc_meta, fetched)
        if not parsed:
            logger.error("Failed to parse content")
            sys.exit(1)

        document_id = ingester.store(parsed)
        if not document_id:
            logger.error("Failed to store document")
            sys.exit(1)

        logger.info(f"✓ Successfully ingested post (ID: {document_id})")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


# Helper functions
def check_configuration():
    """Check configuration and API connectivity"""
    logger = get_logger(__name__)

    logger.info("Checking configuration...")

    # Check API key
    if not settings.api_key:
        logger.error("API key not configured")
        return False

    # Test API connectivity
    try:
        api_client = CongressAPIClient()
        response = api_client.get("committee/119/house", {"limit": 1})
        logger.info("API connectivity: OK")
    except Exception as e:
        logger.error(f"API connectivity failed: {e}")
        return False

    # Check database path
    try:
        db_manager = DatabaseManager()
        db_manager.ensure_database_directory()
        logger.info(f"Database path: {settings.database_path}")
    except Exception as e:
        logger.error(f"Database path issue: {e}")
        return False

    logger.info("Configuration check passed")
    return True


def run_specific_phase(orchestrator, phase, congress, validation, batch_size):
    """Run specific import phase"""
    phase_methods = {
        'committees': orchestrator.import_committees,
        'members': orchestrator.import_members,
        'hearings': orchestrator.import_hearings,
        'documents': orchestrator.import_documents
    }

    if phase not in phase_methods:
        raise ValueError(f"Unknown phase: {phase}. Valid phases: {list(phase_methods.keys())}")

    method = phase_methods[phase]

    if phase in ['committees', 'members']:
        return method(congress, validation_mode=validation)
    elif phase == 'hearings':
        return method(congress, validation_mode=validation, batch_size=batch_size)
    else:  # documents
        # For documents, we need hearing IDs
        db_manager = orchestrator.db_manager
        hearings = db_manager.fetch_all("SELECT hearing_id FROM hearings LIMIT 100")
        hearing_ids = [h['hearing_id'] for h in hearings]
        return method(hearing_ids, validation_mode=validation)


def display_import_results(result, db_manager):
    """Display import results"""
    logger = get_logger(__name__)

    logger.info("Import Results:")
    for entity_type, stats in result.items():
        logger.info(f"  {entity_type}: {stats}")

    # Display table counts
    counts = db_manager.get_table_counts()
    logger.info("Database Record Counts:")
    for table, count in counts.items():
        logger.info(f"  {table}: {count}")


if __name__ == "__main__":
    # Handle the import command group name conflict with Python's import keyword
    cli.add_command(import_cmd, name='import')
    cli()