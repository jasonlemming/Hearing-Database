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