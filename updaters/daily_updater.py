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
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.client import CongressAPIClient
from database.manager import DatabaseManager
from fetchers.hearing_fetcher import HearingFetcher
from fetchers.committee_fetcher import CommitteeFetcher
from fetchers.witness_fetcher import WitnessFetcher
from parsers.hearing_parser import HearingParser
from parsers.witness_parser import WitnessParser
from config.settings import Settings
from config.logging_config import get_logger
from notifications import get_notifier
from utils.circuit_breaker import CircuitBreakerError

logger = get_logger(__name__)

# Import validation module
try:
    from scripts.verify_updates import UpdateValidator
except ImportError:
    logger.warning("UpdateValidator not available - post-update validation disabled")
    UpdateValidator = None


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
        self.validation_passed = None
        self.validation_warnings = []
        self.validation_issues = []

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
            'errors': self.errors,
            'validation_passed': self.validation_passed,
            'validation_warnings': self.validation_warnings,
            'validation_issues': self.validation_issues
        }


class Checkpoint:
    """
    Tracks database changes for potential rollback.

    Used in batch processing to track what each batch modifies,
    enabling independent rollback without affecting other batches.
    """

    def __init__(self, batch_number: int):
        self.batch_number = batch_number
        self.timestamp = datetime.now()

        # Track IDs of records to be modified
        self.hearings_to_update = []
        self.hearings_to_add = []
        self.witnesses_to_add = []
        self.documents_to_add = []

        # Track pre-modification state for updates
        self.original_hearing_data = {}

    def track_update(self, hearing_id: str, original_data: dict):
        """
        Track a hearing that will be updated.

        Args:
            hearing_id: ID of hearing being updated
            original_data: Original hearing data for rollback
        """
        self.hearings_to_update.append(hearing_id)
        self.original_hearing_data[hearing_id] = original_data

    def track_addition(self, hearing_id: str):
        """
        Track a hearing that will be added.

        Args:
            hearing_id: ID of new hearing
        """
        self.hearings_to_add.append(hearing_id)

    def track_witness_addition(self, witness_id: str):
        """
        Track a witness that will be added.

        Args:
            witness_id: ID of new witness
        """
        self.witnesses_to_add.append(witness_id)

    def track_document_addition(self, document_id: str):
        """
        Track a document that will be added.

        Args:
            document_id: ID of new document
        """
        self.documents_to_add.append(document_id)


class BatchResult:
    """
    Result of processing a single batch.

    Tracks success/failure and provides details for logging and metrics.
    """

    def __init__(self, success: bool, records: int = 0, error: str = None, issues: List[str] = None):
        self.success = success
        self.records = records  # Number of records processed
        self.error = error  # Error message if failed
        self.issues = issues or []  # Validation issues if any

    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'records': self.records,
            'error': self.error,
            'issues': self.issues
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

    def __init__(self, congress: int = 119, lookback_days: int = 7, update_mode: str = 'incremental', components: Optional[List[str]] = None):
        self.settings = Settings()
        self.congress = congress
        self.lookback_days = lookback_days
        self.update_mode = update_mode  # 'incremental' or 'full'
        self.db = DatabaseManager()

        # Component selection (default: all hearing-related components)
        # Note: 'hearings' always includes videos (same API response)
        # Members are updated separately via weekly schedule
        self.enabled_components = components if components else ['hearings', 'witnesses', 'committees']

        # Ensure hearings is always included (required)
        if 'hearings' not in self.enabled_components:
            self.enabled_components.insert(0, 'hearings')

        # Initialize API client and fetchers
        self.api_client = CongressAPIClient(
            api_key=self.settings.api_key,
            rate_limit=self.settings.rate_limit
        )

        self.hearing_fetcher = HearingFetcher(self.api_client)
        self.committee_fetcher = CommitteeFetcher(self.api_client)
        self.witness_fetcher = WitnessFetcher(self.api_client)
        self.hearing_parser = HearingParser()
        self.witness_parser = WitnessParser()

        self.metrics = UpdateMetrics()

        # Initialize notification manager
        self.notifier = get_notifier()

        # Track backup path for rollback capability
        self.backup_path = None

        logger.info(f"DailyUpdater initialized for Congress {congress}, {lookback_days} day lookback, mode={update_mode}")
        logger.info(f"Enabled components: {', '.join(self.enabled_components)}")

    def run_daily_update(self, dry_run: bool = False, progress_callback=None) -> Dict[str, Any]:
        """
        Execute the complete daily update process.

        Args:
            dry_run: If True, preview changes without modifying database
            progress_callback: Optional callback function to report progress.
                             Called with dict containing progress data.

        Returns:
            Dictionary containing update metrics and results
        """
        if dry_run:
            logger.info("Starting daily update process (DRY RUN - no database changes will be made)")
        else:
            logger.info("Starting daily update process")

        try:
            # Step 0: Pre-update sanity checks
            if not dry_run:
                sanity_check_passed = self._run_pre_update_sanity_checks()
                if not sanity_check_passed:
                    error_msg = "Pre-update sanity checks failed - aborting update"
                    logger.error(error_msg)
                    self.metrics.errors.append(error_msg)
                    raise Exception(error_msg)

            # Step 1: Get recently modified hearings from API
            recent_hearings = self._fetch_recent_hearings(progress_callback=progress_callback)
            logger.info(f"Found {len(recent_hearings)} recently modified hearings")

            # Step 2: Compare with database and identify changes
            changes = self._identify_changes(recent_hearings)
            logger.info(f"Identified {len(changes['updates'])} updates, {len(changes['additions'])} new hearings")

            if dry_run:
                # In dry run mode, skip database modifications
                logger.info("DRY RUN: Skipping database updates")
                logger.info(f"Would update {len(changes['updates'])} hearings")
                logger.info(f"Would add {len(changes['additions'])} new hearings")

                # Set metrics as if we did the updates
                self.metrics.hearings_updated = len(changes['updates'])
                self.metrics.hearings_added = len(changes['additions'])
            else:
                # Step 2.5: Create database backup before modifications
                self.backup_path = self._create_database_backup()
                if not self.backup_path:
                    logger.warning("Failed to create database backup - proceeding without backup")

                try:
                    # Step 3: Apply updates to database
                    self._apply_updates(changes)

                    # Step 4: Update related data (committees, witnesses)
                    self._update_related_data(changes)

                    # Step 5: Run post-update validation
                    if not dry_run:
                        self._run_post_update_validation()

                        # If validation failed with critical issues, trigger rollback
                        if self.metrics.validation_passed == False and len(self.metrics.validation_issues) > 0:
                            logger.error("Post-update validation failed with critical issues - initiating rollback")
                            self._rollback_database()
                            raise Exception(f"Update rolled back due to validation failures: {', '.join(self.metrics.validation_issues[:3])}")

                    # Step 6: Record update metrics
                    self._record_update_metrics()

                    # Step 7: Cleanup old backups (keep last 7 days)
                    self._cleanup_old_backups(days=7)

                except Exception as e:
                    # On any error during update, attempt rollback if backup exists
                    if self.backup_path:
                        logger.error(f"Update failed, attempting rollback: {e}")
                        self._rollback_database()
                    raise

            self.metrics.end_time = datetime.now()
            logger.info(f"Daily update completed successfully in {self.metrics.duration()}")

            # Check for high error rate and notify
            if not dry_run and len(self.metrics.errors) > 10:
                self.notifier.notify_high_error_rate(
                    error_count=len(self.metrics.errors),
                    total_count=self.metrics.hearings_checked
                )

            # Check circuit breaker status and notify if open
            if self.api_client.circuit_breaker:
                cb_stats = self.api_client.get_circuit_breaker_stats()
                if cb_stats and cb_stats['state'] == 'open':
                    self.notifier.notify_circuit_breaker_open(
                        circuit_name=cb_stats['name'],
                        stats=cb_stats
                    )

            return {
                'success': True,
                'dry_run': dry_run,
                'metrics': self.metrics.to_dict()
            }

        except CircuitBreakerError as e:
            # Circuit breaker is open - notify and fail gracefully
            self.metrics.errors.append(str(e))
            self.metrics.end_time = datetime.now()
            logger.error(f"Daily update blocked by circuit breaker: {e}")

            # Send notification
            if self.api_client.circuit_breaker:
                cb_stats = self.api_client.get_circuit_breaker_stats()
                self.notifier.notify_circuit_breaker_open(
                    circuit_name=cb_stats['name'] if cb_stats else 'congress_api',
                    stats=cb_stats or {}
                )

            return {
                'success': False,
                'error': str(e),
                'circuit_breaker_open': True,
                'metrics': self.metrics.to_dict()
            }

        except Exception as e:
            self.metrics.errors.append(str(e))
            self.metrics.end_time = datetime.now()
            logger.error(f"Daily update failed: {e}", exc_info=True)

            # Send failure notification
            self.notifier.notify_update_failure(
                error=str(e),
                metrics=self.metrics.to_dict()
            )

            return {
                'success': False,
                'error': str(e),
                'metrics': self.metrics.to_dict()
            }

    def _fetch_recent_hearings(self, progress_callback=None) -> List[Dict[str, Any]]:
        """
        Fetch hearings based on update mode.

        - 'full' mode: Fetches ALL hearings with complete details (slow, comprehensive)
        - 'incremental' mode: Fetches only recent hearings within lookback window (fast)

        Args:
            progress_callback: Optional callback to report progress during fetching

        Returns:
            List of hearing data dictionaries with complete details including videos
        """
        cutoff_date = datetime.now() - timedelta(days=self.lookback_days)

        try:
            if self.update_mode == 'full':
                # Full sync mode - fetch all hearings with details
                logger.info(f"Running FULL sync - fetching all hearings for Congress {self.congress}")
                logger.info("This will take 20-30 minutes. Use 'incremental' mode for faster updates.")

                api_hearings = self.hearing_fetcher.fetch_all_with_details(
                    congress=self.congress
                )

                self.metrics.api_requests += 1
                self.metrics.hearings_checked = len(api_hearings)

                logger.info(f"Fetched {len(api_hearings)} total hearings with details")
                return api_hearings

            else:
                # Incremental mode - fetch wider window, then filter by update date
                # This catches hearings that were recently MODIFIED but scheduled far in future
                logger.info(f"Running INCREMENTAL sync - {self.lookback_days} day lookback from {cutoff_date.strftime('%Y-%m-%d')}")

                # Step 1: Fetch a wider window of hearings (90 days covers most recent activity)
                # We need to fetch more than the lookback window because hearings scheduled
                # months in advance can be updated today
                fetch_window = max(90, self.lookback_days * 3)  # At least 90 days or 3x lookback
                logger.info(f"Fetching {fetch_window}-day window to check for updates")

                all_recent = self.hearing_fetcher.fetch_recent_hearings(
                    congress=self.congress,
                    days_back=fetch_window
                )

                self.metrics.api_requests += 1
                logger.info(f"Retrieved {len(all_recent)} hearings from {fetch_window}-day window")

                # Step 2: Fetch details and filter by updateDate
                recent_hearings = []
                for i, hearing in enumerate(all_recent):
                    event_id = hearing.get('eventId')
                    chamber = hearing.get('chamber', '').lower()

                    if event_id and chamber:
                        try:
                            detailed = self.hearing_fetcher.fetch_hearing_details(
                                congress=self.congress,
                                chamber=chamber,
                                event_id=event_id
                            )

                            if detailed and 'committeeMeeting' in detailed:
                                detailed_hearing = detailed['committeeMeeting']
                                detailed_hearing['chamber'] = chamber.title()

                                # Filter by updateDate (when hearing was last modified)
                                updated_at = detailed_hearing.get('updateDate')
                                if updated_at:
                                    try:
                                        update_date = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                                        if update_date >= cutoff_date.replace(tzinfo=timezone.utc):
                                            recent_hearings.append(detailed_hearing)
                                    except (ValueError, TypeError):
                                        # Can't parse date, include it to be safe
                                        recent_hearings.append(detailed_hearing)
                                else:
                                    # No updateDate, check hearing date as fallback
                                    hearing_date = detailed_hearing.get('date')
                                    if hearing_date:
                                        try:
                                            h_date = datetime.fromisoformat(hearing_date.replace('Z', '+00:00'))
                                            if h_date >= cutoff_date.replace(tzinfo=timezone.utc):
                                                recent_hearings.append(detailed_hearing)
                                        except (ValueError, TypeError):
                                            recent_hearings.append(detailed_hearing)
                            else:
                                # Fall back to basic info
                                recent_hearings.append(hearing)

                            self.metrics.api_requests += 1

                            # Progress reporting every 50 hearings
                            if (i + 1) % 50 == 0:
                                logger.info(f"Checked {i + 1}/{len(all_recent)} hearings, found {len(recent_hearings)} updates")

                                # Call progress callback if provided
                                if progress_callback:
                                    progress_callback({
                                        'hearings_checked': i + 1,
                                        'total_hearings': len(all_recent),
                                        'hearings_found': len(recent_hearings),
                                        'percent': int((i + 1) / len(all_recent) * 100)
                                    })

                        except Exception as e:
                            logger.warning(f"Could not fetch details for {event_id}: {e}")

                self.metrics.hearings_checked = len(all_recent)
                logger.info(f"Found {len(recent_hearings)} hearings updated in last {self.lookback_days} days")
                return recent_hearings

        except Exception as e:
            logger.error(f"Error fetching hearings: {e}")
            self.metrics.errors.append(f"Fetch error: {e}")
            raise

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
        """Update an existing hearing record with new data using parser pipeline."""
        # Parse the new data using HearingParser
        hearing = self.hearing_parser.parse(new_data)

        if not hearing:
            logger.warning(f"Failed to parse hearing data for {new_data.get('eventId')}")
            return

        # Convert to dict and add congress
        hearing_dict = hearing.dict()
        hearing_dict['congress'] = self.congress

        # Use DatabaseManager's upsert_hearing which handles all fields including video
        self.db.upsert_hearing(hearing_dict)

        logger.debug(f"Updated hearing {new_data.get('eventId')} with new data")

    def _add_new_hearing(self, conn, hearing_data: Dict[str, Any]) -> None:
        """Add a new hearing record to the database using parser pipeline."""
        # Parse the new data using HearingParser
        hearing = self.hearing_parser.parse(hearing_data)

        if not hearing:
            logger.warning(f"Failed to parse hearing data for {hearing_data.get('eventId')}")
            return

        # Convert to dict and add congress
        hearing_dict = hearing.dict()
        hearing_dict['congress'] = self.congress

        # Use DatabaseManager's upsert_hearing which handles all fields including video
        self.db.upsert_hearing(hearing_dict)

        logger.debug(f"Added new hearing {hearing_data.get('eventId')}")

    def _update_related_data(self, changes: Dict[str, List]) -> None:
        """
        Update committees and witnesses from embedded hearing details.
        No additional API calls needed - data already fetched in _fetch_recent_hearings().

        Args:
            changes: Dictionary with updates and additions
        """
        # For new hearings, process committee associations and witnesses from embedded data
        for addition in changes['additions']:
            try:
                # Only process committees if enabled
                if 'committees' in self.enabled_components:
                    self._update_hearing_committees_from_details(addition)

                # Only process witnesses if enabled
                if 'witnesses' in self.enabled_components:
                    self._update_hearing_witnesses_from_details(addition)
            except Exception as e:
                error_msg = f"Error updating related data for {addition.get('eventId')}: {e}"
                logger.error(error_msg)
                self.metrics.errors.append(error_msg)

        # For updated hearings, check if committees and witnesses need updating
        for update in changes['updates']:
            try:
                # Only process committees if enabled
                if 'committees' in self.enabled_components:
                    self._update_hearing_committees_from_details(update['new_data'])

                # Only process witnesses if enabled
                if 'witnesses' in self.enabled_components:
                    self._update_hearing_witnesses_from_details(update['new_data'])
            except Exception as e:
                error_msg = f"Error updating related data for {update['new_data'].get('eventId')}: {e}"
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

    def _update_hearing_committees_from_details(self, hearing_data: Dict[str, Any]) -> None:
        """
        Extract and update committee associations from embedded hearing details.
        No additional API calls needed - data already fetched.

        Args:
            hearing_data: Full hearing data with embedded committees
        """
        event_id = hearing_data.get('eventId')
        committees = hearing_data.get('committees', [])

        if not event_id or not committees:
            logger.debug(f"No committees found in embedded data for hearing {event_id}")
            return

        # Get hearing_id from database
        hearing_record = self.db.get_hearing_by_event_id(event_id)
        if not hearing_record:
            logger.warning(f"Hearing {event_id} not found in database")
            return

        hearing_id = hearing_record['hearing_id']

        try:
            # Extract committees using parser (no API call - uses embedded data)
            committee_refs = self.hearing_parser.extract_committee_references(hearing_data)

            if not committee_refs:
                logger.debug(f"No committees extracted for hearing {event_id}")
                return

            # Delete all existing committee links to prevent duplicates
            # This is safer than resetting is_primary flags, as it handles committee ID changes
            self.db.delete_hearing_committee_links(hearing_id)

            # Link each committee to hearing
            for committee_ref in committee_refs:
                system_code = committee_ref.get('system_code')
                if not system_code:
                    continue

                # Get committee from database
                committee = self.db.get_committee_by_system_code(system_code)
                if committee:
                    # Create hearing-committee link
                    self.db.link_hearing_committee(
                        hearing_id,
                        committee['committee_id'],
                        committee_ref.get('is_primary', False)
                    )
                    self.metrics.committees_updated += 1
                    logger.debug(f"Linked committee {system_code} to hearing {event_id}")
                else:
                    logger.warning(f"Committee {system_code} not found in database for hearing {event_id}")

        except Exception as e:
            logger.warning(f"Could not process committees from embedded data for hearing {event_id}: {e}")

    def _map_witness_document_type(self, api_doc_type: str) -> str:
        """
        Map Congress.gov API document types to database enum values.

        Database allows: 'Statement', 'Biography', 'Truth Statement', 'Questions for Record', 'Supplemental'
        """
        type_mapping = {
            'Witness Biography': 'Biography',
            'Biography': 'Biography',
            'Witness Statement': 'Statement',
            'Statement': 'Statement',
            'Witness Truth in Testimony': 'Truth Statement',
            'Truth in Testimony': 'Truth Statement',
            'Questions for the Record': 'Questions for Record',
            'Supplemental Material': 'Supplemental',
            'Supplemental': 'Supplemental'
        }
        return type_mapping.get(api_doc_type, 'Statement')  # Default to Statement

    def _extract_last_name(self, full_name: str) -> str:
        """Extract last name from a witness's full name, removing titles."""
        if not full_name:
            return ''

        # Remove common titles
        cleaned = full_name
        for title in ['Mr. ', 'Ms. ', 'Mrs. ', 'Dr. ', 'Hon. ', 'The Honorable ', 'Prof. ']:
            cleaned = cleaned.replace(title, '')

        # Get last word (typically the last name)
        parts = cleaned.split()
        return parts[-1] if parts else ''

    def _update_hearing_witnesses_from_details(self, hearing_data: Dict[str, Any]) -> None:
        """
        Extract and update witness information from embedded hearing details.
        No additional API calls needed - data already fetched.

        Args:
            hearing_data: Full hearing data with embedded witnesses and witness documents
        """
        event_id = hearing_data.get('eventId')
        witnesses = hearing_data.get('witnesses', [])
        witness_documents = hearing_data.get('witnessDocuments', [])

        if not event_id:
            return

        if not witnesses and not witness_documents:
            logger.debug(f"No witnesses found in embedded data for hearing {event_id}")
            return

        # Get hearing_id from database
        hearing_record = self.db.get_hearing_by_event_id(event_id)
        if not hearing_record:
            logger.warning(f"Hearing {event_id} not found in database")
            return

        hearing_id = hearing_record['hearing_id']

        try:
            # Process each witness from embedded data
            witness_name_to_data = {}  # Map witness names to appearance IDs and last names

            for i, witness_raw in enumerate(witnesses, 1):
                try:
                    # Normalize data structure for parser
                    witness_data = {
                        'name': witness_raw.get('name'),
                        'firstName': witness_raw.get('firstName'),
                        'lastName': witness_raw.get('lastName'),
                        'position': witness_raw.get('position'),
                        'organization': witness_raw.get('organization')
                    }

                    # Parse witness data
                    parsed = self.witness_parser.parse(witness_data)
                    if not parsed:
                        logger.debug(f"Failed to parse witness for hearing {event_id}")
                        continue

                    # Get or create witness (handles deduplication internally via database manager)
                    witness_dict = parsed.dict()
                    witness_id = self.db.get_or_create_witness(witness_dict)

                    # Create witness appearance link
                    appearance_data = {
                        'position': parsed.title,
                        'witness_type': None,  # Could be inferred if needed
                        'appearance_order': i
                    }
                    appearance_id = self.db.create_witness_appearance(witness_id, hearing_id, appearance_data)

                    # Store mapping for document linking
                    witness_name = witness_raw.get('name', '')
                    if witness_name and appearance_id:
                        last_name = self._extract_last_name(witness_name)
                        witness_name_to_data[witness_name] = {
                            'appearance_id': appearance_id,
                            'last_name': last_name
                        }

                    self.metrics.witnesses_updated += 1
                    logger.debug(f"Saved witness {parsed.full_name} for hearing {event_id}")

                except Exception as e:
                    logger.warning(f"Failed to process witness for hearing {event_id}: {e}")
                    continue

            # Process witness documents if available
            if witness_documents and witness_name_to_data:
                logger.debug(f"Processing {len(witness_documents)} witness documents for hearing {event_id}")

                docs_saved = 0
                for doc in witness_documents:
                    try:
                        api_doc_type = doc.get('documentType', 'Statement')
                        doc_format = doc.get('format', 'PDF')
                        doc_url = doc.get('url', '')

                        if not doc_url:
                            continue

                        # Map API document type to database enum
                        db_doc_type = self._map_witness_document_type(api_doc_type)

                        # Match document to witness by checking last name in URL
                        matched_appearance_id = None
                        matched_witness = None

                        for witness_name, witness_info in witness_name_to_data.items():
                            last_name = witness_info['last_name']
                            # Check if last name appears in the URL filename
                            if last_name and last_name in doc_url:
                                matched_appearance_id = witness_info['appearance_id']
                                matched_witness = witness_name
                                break

                        # If no match found, log warning but don't fail
                        if not matched_appearance_id:
                            logger.debug(f"Could not match document {api_doc_type} to witness (URL: ...{doc_url[-50:]})")
                            continue

                        # Save witness document using database manager's execute method
                        query = '''
                            INSERT INTO witness_documents (appearance_id, title, document_url, format_type, document_type)
                            VALUES (?, ?, ?, ?, ?)
                        '''
                        self.db.execute(query, (matched_appearance_id, api_doc_type, doc_url, doc_format, db_doc_type))
                        docs_saved += 1
                        logger.debug(f"Saved {api_doc_type} for {matched_witness}")

                    except Exception as e:
                        logger.warning(f"Failed to save witness document for hearing {event_id}: {e}")
                        continue

                if docs_saved > 0:
                    logger.info(f"Saved {docs_saved} witness documents for hearing {event_id}")

        except Exception as e:
            logger.warning(f"Could not process witnesses from embedded data for hearing {event_id}: {e}")

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
                    trigger_source TEXT DEFAULT 'manual',
                    schedule_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (schedule_id) REFERENCES scheduled_tasks(task_id)
                )
            ''')

            # Get trigger source and schedule ID (injected by cron-update.py)
            trigger_source = getattr(self, 'trigger_source', 'manual')
            schedule_id = getattr(self, 'schedule_id', None)

            # Insert update log
            conn.execute('''
                INSERT INTO update_logs (
                    update_date, start_time, end_time, duration_seconds,
                    hearings_checked, hearings_updated, hearings_added,
                    committees_updated, witnesses_updated, api_requests,
                    error_count, errors, success, trigger_source, schedule_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                len(self.metrics.errors) == 0,
                trigger_source,
                schedule_id
            ))

        logger.info(f"Recorded update metrics: {self.metrics.to_dict()}")

    def _run_pre_update_sanity_checks(self) -> bool:
        """
        Run pre-update sanity checks to ensure database is in good state.

        Checks for:
        - Database file exists and is accessible
        - Database is not corrupted
        - Critical tables exist
        - Minimum record counts are met
        - No foreign key violations exist

        Returns:
            True if all checks pass, False otherwise
        """
        logger.info("Running pre-update sanity checks...")

        try:
            with self.db.transaction() as conn:
                # Check 1: Verify critical tables exist
                cursor = conn.execute('''
                    SELECT name FROM sqlite_master
                    WHERE type='table' AND name IN ('hearings', 'committees', 'witnesses', 'update_logs')
                    ORDER BY name
                ''')
                tables = [row[0] for row in cursor.fetchall()]
                required_tables = ['committees', 'hearings', 'witnesses']

                for required in required_tables:
                    if required not in tables:
                        logger.error(f"Critical table '{required}' missing from database")
                        return False

                logger.info(f"✓ All critical tables present: {', '.join(tables)}")

                # Check 2: Verify minimum record counts (prevent operating on empty/broken database)
                cursor = conn.execute('SELECT COUNT(*) FROM hearings')
                hearing_count = cursor.fetchone()[0]

                if hearing_count < 100:
                    logger.error(f"Database has only {hearing_count} hearings (minimum 100 required)")
                    return False

                logger.info(f"✓ Database has {hearing_count} hearings")

                # Check 3: Check for foreign key violations
                conn.execute('PRAGMA foreign_keys = ON')
                cursor = conn.execute('PRAGMA foreign_key_check')
                violations = cursor.fetchall()

                if violations:
                    logger.error(f"Found {len(violations)} foreign key violations")
                    for violation in violations[:5]:  # Show first 5
                        logger.error(f"  - {violation}")
                    return False

                logger.info("✓ No foreign key violations")

                # Check 4: Verify database integrity
                cursor = conn.execute('PRAGMA integrity_check')
                integrity = cursor.fetchone()[0]

                if integrity != 'ok':
                    logger.error(f"Database integrity check failed: {integrity}")
                    return False

                logger.info("✓ Database integrity check passed")

                # Check 5: Verify last update wasn't too recent (prevent duplicate runs)
                cursor = conn.execute('''
                    SELECT start_time FROM update_logs
                    ORDER BY start_time DESC LIMIT 1
                ''')
                last_update_row = cursor.fetchone()

                if last_update_row:
                    last_update = datetime.fromisoformat(last_update_row[0])
                    hours_since_update = (datetime.now() - last_update).total_seconds() / 3600

                    if hours_since_update < 1:
                        logger.warning(f"Last update was only {hours_since_update:.1f} hours ago - potential duplicate run")
                        # Don't fail, just warn
                    else:
                        logger.info(f"✓ Last update was {hours_since_update:.1f} hours ago")

                logger.info("All pre-update sanity checks passed ✓")
                return True

        except Exception as e:
            logger.error(f"Pre-update sanity checks failed with exception: {e}")
            return False

    def _run_post_update_validation(self) -> None:
        """
        Run post-update validation checks using UpdateValidator.
        Stores validation results in metrics for tracking and alerting.
        """
        if not UpdateValidator:
            logger.warning("UpdateValidator not available - skipping validation")
            self.metrics.validation_passed = None
            return

        logger.info("Running post-update validation...")

        try:
            validator = UpdateValidator(db_path=self.settings.database_path)
            results = validator.run_all_checks(fix_issues=False)

            # Store validation results in metrics
            self.metrics.validation_passed = results.get('passed', False)
            self.metrics.validation_warnings = results.get('warnings', [])
            self.metrics.validation_issues = results.get('issues', [])

            # Log validation outcome
            if self.metrics.validation_passed:
                logger.info(f"✓ Validation passed with {len(self.metrics.validation_warnings)} warnings")
            else:
                logger.error(f"✗ Validation failed with {len(self.metrics.validation_issues)} issues")

                # Notify on critical validation failures
                if len(self.metrics.validation_issues) > 0:
                    self.notifier.send(
                        title="Post-Update Validation Failed",
                        message=f"Data validation found {len(self.metrics.validation_issues)} critical issues after update",
                        severity="error",
                        metadata={
                            'issues': self.metrics.validation_issues[:5],  # First 5 issues
                            'warning_count': len(self.metrics.validation_warnings)
                        }
                    )

        except Exception as e:
            logger.error(f"Validation check failed with exception: {e}")
            self.metrics.validation_passed = False
            self.metrics.validation_issues.append(f"Validation error: {str(e)}")

    def _create_database_backup(self) -> Optional[str]:
        """
        Create a backup of the database before modifications.

        Returns:
            Path to backup file, or None if backup failed
        """
        try:
            # Create backups directory if it doesn't exist
            backups_dir = Path(self.settings.database_path).parent / 'backups'
            backups_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"database_backup_{timestamp}.db"
            backup_path = backups_dir / backup_filename

            # Copy database file
            logger.info(f"Creating database backup at {backup_path}")
            shutil.copy2(self.settings.database_path, backup_path)

            # Verify backup was created and has reasonable size
            if backup_path.exists():
                backup_size = backup_path.stat().st_size
                original_size = Path(self.settings.database_path).stat().st_size

                if backup_size == original_size:
                    logger.info(f"✓ Database backup created successfully ({backup_size / 1024 / 1024:.2f} MB)")
                    return str(backup_path)
                else:
                    logger.error(f"Backup size mismatch: original={original_size}, backup={backup_size}")
                    return None
            else:
                logger.error("Backup file not found after copy")
                return None

        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            return None

    def _rollback_database(self) -> bool:
        """
        Restore database from backup.

        Returns:
            True if rollback successful, False otherwise
        """
        if not self.backup_path or not Path(self.backup_path).exists():
            logger.error("Cannot rollback: backup file not found")
            return False

        try:
            logger.warning(f"Rolling back database from backup: {self.backup_path}")

            # Close any open database connections
            self.db.close()

            # Restore backup
            shutil.copy2(self.backup_path, self.settings.database_path)

            # Verify restore
            restored_size = Path(self.settings.database_path).stat().st_size
            backup_size = Path(self.backup_path).stat().st_size

            if restored_size == backup_size:
                logger.info(f"✓ Database rolled back successfully")

                # Reinitialize database connection
                self.db = DatabaseManager()

                # Send notification about rollback
                self.notifier.send(
                    title="Database Rollback Performed",
                    message=f"Database was rolled back due to update validation failures",
                    severity="warning",
                    metadata={
                        'backup_path': self.backup_path,
                        'validation_issues': self.metrics.validation_issues[:3]
                    }
                )

                return True
            else:
                logger.error(f"Rollback verification failed: sizes don't match")
                return False

        except Exception as e:
            logger.error(f"Failed to rollback database: {e}")
            return False

    def _cleanup_old_backups(self, days: int = 7) -> None:
        """
        Remove database backups older than specified days.

        Args:
            days: Number of days to keep backups (default: 7)
        """
        try:
            backups_dir = Path(self.settings.database_path).parent / 'backups'

            if not backups_dir.exists():
                return

            cutoff_time = datetime.now() - timedelta(days=days)
            removed_count = 0

            for backup_file in backups_dir.glob('database_backup_*.db'):
                # Check file modification time
                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                if file_mtime < cutoff_time:
                    logger.debug(f"Removing old backup: {backup_file.name}")
                    backup_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old backup(s) older than {days} days")

        except Exception as e:
            logger.warning(f"Failed to cleanup old backups: {e}")

    # =========================================================================
    # Batch Processing Methods (Phase 2.3.1)
    # =========================================================================

    def _divide_into_batches(self, hearings: List, batch_size: int = None) -> List[List]:
        """
        Divide hearings into batches for processing.

        Used in batch processing to split a large list of hearings into
        manageable chunks that can be validated and committed independently.

        Args:
            hearings: List of hearing data
            batch_size: Size of each batch (default: from settings or 50)

        Returns:
            List of batches, each containing up to batch_size hearings
        """
        if batch_size is None:
            batch_size = getattr(self.settings, 'batch_size', 50)

        batches = []
        for i in range(0, len(hearings), batch_size):
            batch = hearings[i:i + batch_size]
            batches.append(batch)

        return batches

    def _process_batch(self, batch: List[Dict[str, Any]], batch_number: int, checkpoint: Checkpoint) -> BatchResult:
        """
        Process a single batch of hearings.

        This is the core batch processing method that applies updates for a batch
        while tracking changes in the checkpoint for potential rollback.

        Args:
            batch: List of hearing changes to process
            batch_number: Batch number (for logging)
            checkpoint: Checkpoint to track changes

        Returns:
            BatchResult indicating success or failure
        """
        # TODO: Implement batch processing logic (Day 3-4)
        # For now, return a success result
        logger.info(f"Processing batch {batch_number} with {len(batch)} hearings")
        return BatchResult(success=True, records=len(batch))

    def _validate_batch(self, batch: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
        """
        Validate a batch of hearings before processing.

        Fast validation checks:
        - Foreign key references are valid
        - No duplicate hearing IDs within batch
        - Data format is correct

        Args:
            batch: List of hearing changes to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        # TODO: Implement batch validation logic (Day 4)
        # For now, return success
        return (True, [])

    def _rollback_checkpoint(self, checkpoint: Checkpoint) -> bool:
        """
        Rollback changes tracked in a checkpoint.

        This allows independent batch rollback without affecting other batches:
        - DELETE hearings that were added
        - RESTORE hearings that were updated (using original data)
        - DELETE witnesses that were added
        - DELETE documents that were added

        Args:
            checkpoint: Checkpoint containing changes to rollback

        Returns:
            True if rollback successful, False otherwise
        """
        # TODO: Implement rollback logic (Day 5)
        # For now, log and return success
        logger.info(f"Rolling back checkpoint for batch {checkpoint.batch_number}")
        return True


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