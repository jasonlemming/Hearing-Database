#!/usr/bin/env python3
"""
Simple daily update script for Congressional Hearing Database

This script can be run daily via cron to automatically update the database
with new and modified hearings from the Congress.gov API.

Usage:
    python scripts/daily_update.py [--congress 119] [--lookback-days 7]

Cron example (daily at 2 AM):
    0 2 * * * cd /path/to/project && python scripts/daily_update.py >> logs/cron.log 2>&1
"""

import sys
import os
from datetime import datetime
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from updaters.daily_updater import DailyUpdater


def setup_logging():
    """Setup logging for daily update."""
    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # Setup logging
    log_file = os.path.join(log_dir, f'daily_update_{datetime.now().strftime("%Y%m%d")}.log')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )

    return logging.getLogger(__name__)


def main():
    """Main entry point for daily update."""
    import argparse

    parser = argparse.ArgumentParser(description='Daily update for Congressional Hearing Database')
    parser.add_argument('--congress', type=int, default=119, help='Congress number to update (default: 119)')
    parser.add_argument('--lookback-days', type=int, default=7, help='Days to look back for changes (default: 7)')
    parser.add_argument('--quiet', action='store_true', help='Reduce output (for cron jobs)')

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging()

    if not args.quiet:
        logger.info(f"Starting daily update for Congress {args.congress}")
        logger.info(f"Looking back {args.lookback_days} days for changes")

    try:
        # Create and run updater
        updater = DailyUpdater(congress=args.congress, lookback_days=args.lookback_days)
        result = updater.run_daily_update()

        if result['success']:
            metrics = result['metrics']
            logger.info("Daily update completed successfully")
            logger.info(f"Processed {metrics['hearings_checked']} hearings")
            logger.info(f"Updated {metrics['hearings_updated']} existing hearings")
            logger.info(f"Added {metrics['hearings_added']} new hearings")
            logger.info(f"Updated {metrics['committees_updated']} committee associations")
            logger.info(f"Updated {metrics['witnesses_updated']} witnesses")
            logger.info(f"Made {metrics['api_requests']} API requests")

            if metrics['duration_seconds']:
                logger.info(f"Completed in {metrics['duration_seconds']:.2f} seconds")

            if metrics['error_count'] > 0:
                logger.warning(f"Encountered {metrics['error_count']} errors during update")

        else:
            logger.error(f"Daily update failed: {result['error']}")
            if result.get('metrics', {}).get('error_count', 0) > 0:
                logger.error(f"Additional errors: {result['metrics']['errors']}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error during daily update: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()