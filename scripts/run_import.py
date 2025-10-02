#!/usr/bin/env python3
"""
Run Congressional hearing data import
"""
import sys
import os
import click
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from importers.orchestrator import ImportOrchestrator
from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.settings import settings
from config.logging_config import setup_logging, get_logger

@click.command()
@click.option('--congress', default=settings.target_congress, help='Congress number to import')
@click.option('--validation', is_flag=True, help='Run in validation mode (no database writes)')
@click.option('--phase', help='Specific phase to run (committees, members, hearings, documents)')
@click.option('--resume', is_flag=True, help='Resume from last checkpoint')
@click.option('--check-config', is_flag=True, help='Check configuration and exit')
@click.option('--batch-size', default=settings.batch_size, help='Batch size for processing')
def main(congress, validation, phase, resume, check_config, batch_size):
    """Run Congressional hearing data import"""
    setup_logging()
    logger = get_logger(__name__)

    if check_config:
        check_configuration()
        return

    try:
        logger.info(f"Starting import for Congress {congress}")
        if validation:
            logger.info("Running in VALIDATION mode - no data will be written")

        # Initialize components
        db_manager = DatabaseManager()
        api_client = CongressAPIClient()
        orchestrator = ImportOrchestrator(db_manager, api_client)

        # Check if resuming
        if resume:
            logger.info("Attempting to resume from last checkpoint...")
            last_phase = orchestrator.resume_from_checkpoint()
            if last_phase:
                logger.info(f"Resuming from phase: {last_phase}")
            else:
                logger.info("No checkpoint found, starting fresh import")

        # Run import
        if phase:
            # Run specific phase
            result = run_phase(orchestrator, phase, congress, validation, batch_size)
        else:
            # Run full import
            result = orchestrator.run_full_import(
                congress=congress,
                validation_mode=validation,
                batch_size=batch_size
            )

        # Display results
        display_results(result, db_manager)

        logger.info("Import completed successfully")

    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)

def check_configuration():
    """Check configuration and API connectivity"""
    logger = get_logger(__name__)

    logger.info("Checking configuration...")

    # Check API key
    if not settings.api_key:
        logger.error("API key not configured")
        return

    # Test API connectivity
    try:
        api_client = CongressAPIClient()
        response = api_client.get("committee/119/house", {"limit": 1})
        logger.info("API connectivity: OK")
    except Exception as e:
        logger.error(f"API connectivity failed: {e}")
        return

    # Check database path
    db_manager = DatabaseManager()
    try:
        db_manager.ensure_database_directory()
        logger.info(f"Database path: {settings.database_path}")
    except Exception as e:
        logger.error(f"Database path issue: {e}")
        return

    logger.info("Configuration check passed")

def run_phase(orchestrator, phase, congress, validation, batch_size):
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

def display_results(result, db_manager):
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
    main()