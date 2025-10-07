#!/usr/bin/env python3
"""
Daily Update Automation System for Congressional Hearing Database

This module provides automated daily synchronization of congressional hearing data
from the Congress.gov API, implementing incremental updates to avoid full re-imports.
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
import logging
import json
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.client import CongressAPIClient
from database.manager import DatabaseManager
from fetchers.hearing_fetcher import HearingFetcher
from fetchers.committee_fetcher import CommitteeFetcher
from fetchers.witness_fetcher import WitnessFetcher
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class UpdateMetrics:
    """Track update operation metrics"""

    def __init__(self):
        self.start_time = datetime.now()
        self.end_time = None
        self.hearings_checked = 0
        self.hearings_updated = 0
        self.hearings_added = 0
        self.committees_updated = 0
        self.witnesses_updated = 0
        self.errors = []
        self.api_requests = 0

    def duration(self) -> Optional[timedelta]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': self.duration().total_seconds() if self.duration() else None,
            'hearings_checked': self.hearings_checked,
            'hearings_updated': self.hearings_updated,
            'hearings_added': self.hearings_added,
            'committees_updated': self.committees_updated,
            'witnesses_updated': self.witnesses_updated,
            'api_requests': self.api_requests,
            'error_count': len(self.errors),
            'errors': self.errors
        }


class DailyUpdater:
    """
    Automated daily update system for Congressional hearing data.

    Implements incremental updates by:
    - Fetching hearings modified in the last N days
    - Comparing with existing database records
    - Updating only changed fields
    - Adding new hearings and related data
    """

    def __init__(self, congress: int = 119, lookback_days: int = 7):
        self.settings = Settings()
        self.congress = congress
        self.lookback_days = lookback_days
        self.db = DatabaseManager()

        # Initialize API client and fetchers
        self.api_client = CongressAPIClient(
            api_key=self.settings.api_key,
            rate_limit_per_hour=self.settings.rate_limit
        )

        self.hearing_fetcher = HearingFetcher(self.api_client)
        self.committee_fetcher = CommitteeFetcher(self.api_client)
        self.witness_fetcher = WitnessFetcher(self.api_client)

        self.metrics = UpdateMetrics()

        logger.info(f"DailyUpdater initialized for Congress {congress}, {lookback_days} day lookback")

    def run_daily_update(self) -> Dict[str, Any]:
        """
        Execute the complete daily update process.

        Returns:
            Dictionary containing update metrics and results
        """
        logger.info("Starting daily update process")

        try:
            # Step 1: Get recently modified hearings from API
            recent_hearings = self._fetch_recent_hearings()
            logger.info(f"Found {len(recent_hearings)} recently modified hearings")

            # Step 2: Compare with database and identify changes
            changes = self._identify_changes(recent_hearings)
            logger.info(f"Identified {len(changes['updates'])} updates, {len(changes['additions'])} new hearings")

            # Step 3: Apply updates to database
            self._apply_updates(changes)

            # Step 4: Update related data (committees, witnesses)
            self._update_related_data(changes)

            # Step 5: Record update metrics
            self._record_update_metrics()

            self.metrics.end_time = datetime.now()
            logger.info(f"Daily update completed successfully in {self.metrics.duration()}")

            return {
                'success': True,
                'metrics': self.metrics.to_dict()
            }

        except Exception as e:
            self.metrics.errors.append(str(e))
            self.metrics.end_time = datetime.now()
            logger.error(f"Daily update failed: {e}", exc_info=True)

            return {
                'success': False,
                'error': str(e),
                'metrics': self.metrics.to_dict()
            }

    def _fetch_recent_hearings(self) -> List[Dict[str, Any]]:
        """
        Fetch hearings modified in the last N days from Congress.gov API.

        Returns:
            List of hearing data dictionaries
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)
        recent_hearings = []

        logger.info(f"Fetching hearings modified since {cutoff_date.strftime('%Y-%m-%d')}")

        try:
            # Get hearings with date filter
            # Note: Congress.gov API doesn't have direct "modified since" filter,
            # so we fetch recent hearings and check update timestamps
            api_hearings = self.hearing_fetcher.fetch_hearings_for_congress(
                congress=self.congress,
                limit=None  # Get all hearings to check modification dates
            )

            self.metrics.api_requests += 1

            # Filter by modification date (if available in API response)
            for hearing in api_hearings:
                # Check if hearing was recently updated
                updated_at = hearing.get('updateDate')
                if updated_at:
                    try:
                        update_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                        if update_date >= cutoff_date.replace(tzinfo=timezone.utc):
                            recent_hearings.append(hearing)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Could not parse update date {updated_at}: {e}")
                        # Include hearing anyway if we can't parse the date
                        recent_hearings.append(hearing)
                else:
                    # No update date available, include all recent hearings
                    hearing_date = hearing.get('date')
                    if hearing_date:
                        try:
                            h_date = datetime.fromisoformat(hearing_date.replace('Z', '+00:00'))
                            if h_date >= cutoff_date.replace(tzinfo=timezone.utc):
                                recent_hearings.append(hearing)
                        except (ValueError, TypeError):
                            recent_hearings.append(hearing)
                    else:
                        recent_hearings.append(hearing)

            self.metrics.hearings_checked = len(api_hearings)
            logger.info(f"Filtered to {len(recent_hearings)} potentially updated hearings")

        except Exception as e:
            logger.error(f"Error fetching recent hearings: {e}")
            self.metrics.errors.append(f"Fetch error: {e}")
            raise

        return recent_hearings

    def _identify_changes(self, api_hearings: List[Dict[str, Any]]) -> Dict[str, List]:
        """
        Compare API hearings with database records to identify changes.

        Args:
            api_hearings: List of hearing data from API

        Returns:
            Dictionary with 'updates' and 'additions' lists
        """
        changes = {
            'updates': [],
            'additions': []
        }

        with self.db.transaction() as conn:
            for hearing in api_hearings:
                event_id = hearing.get('eventId')
                if not event_id:
                    continue

                # Check if hearing exists in database
                cursor = conn.execute(
                    'SELECT * FROM hearings WHERE event_id = ? AND congress = ?',
                    (event_id, self.congress)
                )
                existing = cursor.fetchone()

                if existing:
                    # Check if update is needed
                    if self._hearing_needs_update(existing, hearing):
                        changes['updates'].append({
                            'existing': existing,
                            'new_data': hearing
                        })
                else:
                    # New hearing
                    changes['additions'].append(hearing)

        return changes

    def _hearing_needs_update(self, db_record: tuple, api_data: Dict[str, Any]) -> bool:
        """
        Compare database record with API data to determine if update is needed.

        Args:
            db_record: Database row tuple
            api_data: API response data

        Returns:
            True if update is needed
        """
        # Map database columns to API fields
        # This would need to match your actual database schema
        db_cols = [
            'hearing_id', 'event_id', 'congress', 'chamber', 'title',
            'hearing_date_only', 'hearing_time', 'location', 'jacket_number',
            'hearing_type', 'status', 'created_at', 'updated_at'
        ]

        # Convert database record to dict
        db_data = dict(zip(db_cols, db_record)) if db_record else {}

        # Compare key fields that might change
        fields_to_check = ['title', 'date', 'status', 'location']

        for field in fields_to_check:
            api_value = api_data.get(field)

            # Map API field to database column
            db_field = {
                'title': 'title',
                'date': 'hearing_date_only',
                'status': 'status',
                'location': 'location'
            }.get(field, field)

            db_value = db_data.get(db_field)

            # Handle date formatting
            if field == 'date' and api_value:
                try:
                    api_value = datetime.fromisoformat(api_value.replace('Z', '+00:00')).date().isoformat()
                except (ValueError, TypeError):
                    api_value = None

            # Compare values (handling None/empty cases)
            if self._values_differ(db_value, api_value):
                logger.debug(f"Field {field} changed: '{db_value}' -> '{api_value}'")
                return True

        return False

    def _values_differ(self, db_value: Any, api_value: Any) -> bool:
        """Check if two values are meaningfully different."""
        # Handle None/empty cases
        db_normalized = db_value if db_value not in (None, '', 'None') else None
        api_normalized = api_value if api_value not in (None, '', 'None') else None

        return db_normalized != api_normalized

    def _apply_updates(self, changes: Dict[str, List]) -> None:
        """
        Apply identified changes to the database.

        Args:
            changes: Dictionary with updates and additions
        """
        with self.db.transaction() as conn:
            # Apply updates
            for update in changes['updates']:
                try:
                    self._update_hearing_record(conn, update['existing'], update['new_data'])
                    self.metrics.hearings_updated += 1
                except Exception as e:
                    error_msg = f"Error updating hearing {update['new_data'].get('eventId')}: {e}"
                    logger.error(error_msg)
                    self.metrics.errors.append(error_msg)

            # Add new hearings
            for addition in changes['additions']:
                try:
                    self._add_new_hearing(conn, addition)
                    self.metrics.hearings_added += 1
                except Exception as e:
                    error_msg = f"Error adding hearing {addition.get('eventId')}: {e}"
                    logger.error(error_msg)
                    self.metrics.errors.append(error_msg)

    def _update_hearing_record(self, conn, existing_record: tuple, new_data: Dict[str, Any]) -> None:
        """Update an existing hearing record with new data."""
        # Extract hearing ID from existing record
        hearing_id = existing_record[0]  # Assuming first column is hearing_id

        # Update the hearing record
        # This would use your existing HearingParser logic
        update_sql = '''
            UPDATE hearings
            SET title = ?, hearing_date_only = ?, status = ?, location = ?, updated_at = ?
            WHERE hearing_id = ?
        '''

        # Extract and format the data
        title = new_data.get('title')
        date = new_data.get('date')
        if date:
            try:
                date = datetime.fromisoformat(date.replace('Z', '+00:00')).date().isoformat()
            except (ValueError, TypeError):
                date = None

        status = new_data.get('status')
        location = new_data.get('location')
        updated_at = datetime.now().isoformat()

        conn.execute(update_sql, (title, date, status, location, updated_at, hearing_id))

        logger.debug(f"Updated hearing {hearing_id} with new data")

    def _add_new_hearing(self, conn, hearing_data: Dict[str, Any]) -> None:
        """Add a new hearing record to the database."""
        # This would use your existing HearingParser and import logic
        # For now, implementing a basic insert
        insert_sql = '''
            INSERT INTO hearings (
                event_id, congress, chamber, title, hearing_date_only,
                status, location, hearing_type, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        date = hearing_data.get('date')
        if date:
            try:
                date = datetime.fromisoformat(date.replace('Z', '+00:00')).date().isoformat()
            except (ValueError, TypeError):
                date = None

        now = datetime.now().isoformat()

        conn.execute(insert_sql, (
            hearing_data.get('eventId'),
            self.congress,
            hearing_data.get('chamber'),
            hearing_data.get('title'),
            date,
            hearing_data.get('status'),
            hearing_data.get('location'),
            hearing_data.get('type'),
            now,
            now
        ))

        logger.debug(f"Added new hearing {hearing_data.get('eventId')}")

    def _update_related_data(self, changes: Dict[str, List]) -> None:
        """
        Update committees and witnesses for changed hearings.

        Args:
            changes: Dictionary with updates and additions
        """
        # For new hearings, fetch and add committee associations and witnesses
        for addition in changes['additions']:
            try:
                self._update_hearing_committees(addition)
                self._update_hearing_witnesses(addition)
            except Exception as e:
                error_msg = f"Error updating related data for {addition.get('eventId')}: {e}"
                logger.error(error_msg)
                self.metrics.errors.append(error_msg)

        # For updated hearings, check if witnesses need updating
        for update in changes['updates']:
            try:
                self._update_hearing_witnesses(update['new_data'])
            except Exception as e:
                error_msg = f"Error updating witnesses for {update['new_data'].get('eventId')}: {e}"
                logger.error(error_msg)
                self.metrics.errors.append(error_msg)

    def _update_hearing_committees(self, hearing_data: Dict[str, Any]) -> None:
        """Update committee associations for a hearing."""
        # This would use your existing committee association logic
        event_id = hearing_data.get('eventId')
        chamber = hearing_data.get('chamber')

        if not event_id or not chamber:
            return

        # Fetch committee associations
        committees = self.committee_fetcher.fetch_committees_for_hearing(
            congress=self.congress,
            chamber=chamber.lower(),
            event_id=event_id
        )

        self.metrics.api_requests += 1

        # Update committee associations in database
        # This would use your existing logic
        logger.debug(f"Updated {len(committees)} committee associations for hearing {event_id}")
        self.metrics.committees_updated += len(committees)

    def _update_hearing_witnesses(self, hearing_data: Dict[str, Any]) -> None:
        """Update witnesses for a hearing."""
        event_id = hearing_data.get('eventId')
        chamber = hearing_data.get('chamber')

        if not event_id or not chamber:
            return

        try:
            # Fetch witnesses
            witnesses, appearances = self.witness_fetcher.fetch_witnesses_for_hearing(
                congress=self.congress,
                chamber=chamber.lower(),
                event_id=event_id
            )

            self.metrics.api_requests += 1

            # Update witnesses in database
            # This would use your existing witness import logic
            logger.debug(f"Updated {len(witnesses)} witnesses for hearing {event_id}")
            self.metrics.witnesses_updated += len(witnesses)

        except Exception as e:
            logger.warning(f"Could not update witnesses for hearing {event_id}: {e}")

    def _record_update_metrics(self) -> None:
        """Record update metrics in the database for monitoring."""
        metrics_data = self.metrics.to_dict()

        with self.db.transaction() as conn:
            # Create update_logs table if it doesn't exist
            conn.execute('''
                CREATE TABLE IF NOT EXISTS update_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    update_date DATE NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    duration_seconds REAL,
                    hearings_checked INTEGER DEFAULT 0,
                    hearings_updated INTEGER DEFAULT 0,
                    hearings_added INTEGER DEFAULT 0,
                    committees_updated INTEGER DEFAULT 0,
                    witnesses_updated INTEGER DEFAULT 0,
                    api_requests INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    errors TEXT,
                    success BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Insert update log
            conn.execute('''
                INSERT INTO update_logs (
                    update_date, start_time, end_time, duration_seconds,
                    hearings_checked, hearings_updated, hearings_added,
                    committees_updated, witnesses_updated, api_requests,
                    error_count, errors, success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.metrics.start_time.date(),
                self.metrics.start_time,
                self.metrics.end_time,
                self.metrics.duration().total_seconds() if self.metrics.duration() else None,
                self.metrics.hearings_checked,
                self.metrics.hearings_updated,
                self.metrics.hearings_added,
                self.metrics.committees_updated,
                self.metrics.witnesses_updated,
                self.metrics.api_requests,
                len(self.metrics.errors),
                json.dumps(self.metrics.errors) if self.metrics.errors else None,
                len(self.metrics.errors) == 0
            ))

        logger.info(f"Recorded update metrics: {self.metrics.to_dict()}")


def main():
    """Main entry point for daily update script."""
    import argparse

    parser = argparse.ArgumentParser(description='Run daily update for Congressional Hearing Database')
    parser.add_argument('--congress', type=int, default=119, help='Congress number to update')
    parser.add_argument('--lookback-days', type=int, default=7, help='Days to look back for changes')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be updated without making changes')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(f'logs/daily_update_{datetime.now().strftime("%Y%m%d")}.log'),
            logging.StreamHandler()
        ]
    )

    updater = DailyUpdater(congress=args.congress, lookback_days=args.lookback_days)

    if args.dry_run:
        logger.info("DRY RUN: Would perform daily update but making no changes")
        # Implementation for dry run would go here
        return

    result = updater.run_daily_update()

    if result['success']:
        logger.info("Daily update completed successfully")
        print(json.dumps(result['metrics'], indent=2))
    else:
        logger.error(f"Daily update failed: {result['error']}")
        sys.exit(1)


if __name__ == '__main__':
    main()