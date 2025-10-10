"""
Database manager for Congressional Hearing Database
"""
import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple, Union
from pathlib import Path

from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database operations with transaction support"""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path or settings.database_path
        self.ensure_database_directory()

    def ensure_database_directory(self):
        """Ensure database directory exists"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, query: str, params: Optional[Union[Tuple, List]] = None) -> sqlite3.Cursor:
        """
        Execute single query

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor with results
        """
        with self.transaction() as conn:
            if params:
                return conn.execute(query, params)
            return conn.execute(query)

    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Execute query with multiple parameter sets

        Args:
            query: SQL query
            params_list: List of parameter tuples
        """
        with self.transaction() as conn:
            conn.executemany(query, params_list)

    def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[sqlite3.Row]:
        """Fetch single row"""
        with self.transaction() as conn:
            if params:
                cursor = conn.execute(query, params)
            else:
                cursor = conn.execute(query)
            return cursor.fetchone()

    def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[sqlite3.Row]:
        """Fetch all rows"""
        with self.transaction() as conn:
            if params:
                cursor = conn.execute(query, params)
            else:
                cursor = conn.execute(query)
            return cursor.fetchall()

    def initialize_schema(self, schema_file: str = "database/schema.sql") -> None:
        """
        Initialize database with schema

        Args:
            schema_file: Path to schema SQL file
        """
        if not os.path.exists(schema_file):
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        with self.transaction() as conn:
            conn.executescript(schema_sql)

        logger.info(f"Database initialized with schema from {schema_file}")

    # Committee operations
    def upsert_committee(self, committee_data: Dict[str, Any]) -> int:
        """
        Insert or update committee record using proper UPDATE to avoid foreign key violations

        Args:
            committee_data: Committee data dictionary

        Returns:
            Committee ID
        """
        system_code = committee_data.get('system_code')

        # Check if committee exists
        existing = self.get_committee_by_system_code(system_code)

        if existing:
            # Update existing committee
            update_query = """
            UPDATE committees SET
                name = ?,
                chamber = ?,
                type = ?,
                parent_committee_id = ?,
                is_current = ?,
                url = ?,
                congress = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE system_code = ?
            """

            params = (
                committee_data.get('name'),
                committee_data.get('chamber'),
                committee_data.get('type'),
                committee_data.get('parent_committee_id'),
                committee_data.get('is_current', True),
                committee_data.get('url'),
                committee_data.get('congress'),
                system_code
            )

            self.execute(update_query, params)
            return existing['committee_id']
        else:
            # Insert new committee
            insert_query = """
            INSERT INTO committees
            (system_code, name, chamber, type, parent_committee_id, is_current, url, congress, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            params = (
                system_code,
                committee_data.get('name'),
                committee_data.get('chamber'),
                committee_data.get('type'),
                committee_data.get('parent_committee_id'),
                committee_data.get('is_current', True),
                committee_data.get('url'),
                committee_data.get('congress')
            )

            cursor = self.execute(insert_query, params)
            return cursor.lastrowid

    def get_committee_by_system_code(self, system_code: str) -> Optional[sqlite3.Row]:
        """Get committee by system code"""
        query = "SELECT * FROM committees WHERE system_code = ?"
        return self.fetch_one(query, (system_code,))

    # Member operations
    def upsert_member(self, member_data: Dict[str, Any]) -> int:
        """
        Insert or update member record using proper UPDATE to avoid foreign key violations

        Args:
            member_data: Member data dictionary

        Returns:
            Member ID
        """
        bioguide_id = member_data.get('bioguide_id')

        # Check if member exists
        existing = self.get_member_by_bioguide_id(bioguide_id)

        if existing:
            # Update existing member
            update_query = """
            UPDATE members SET
                first_name = ?,
                middle_name = ?,
                last_name = ?,
                full_name = ?,
                party = ?,
                state = ?,
                district = ?,
                birth_year = ?,
                current_member = ?,
                honorific_prefix = ?,
                official_url = ?,
                office_address = ?,
                phone = ?,
                terms_served = ?,
                congress = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE bioguide_id = ?
            """

            params = (
                member_data.get('first_name'),
                member_data.get('middle_name'),
                member_data.get('last_name'),
                member_data.get('full_name'),
                member_data.get('party'),
                member_data.get('state'),
                member_data.get('district'),
                member_data.get('birth_year'),
                member_data.get('current_member', True),
                member_data.get('honorific_prefix'),
                member_data.get('official_url'),
                member_data.get('office_address'),
                member_data.get('phone'),
                member_data.get('terms_served'),
                member_data.get('congress'),
                bioguide_id
            )

            self.execute(update_query, params)
            return existing['member_id']
        else:
            # Insert new member
            insert_query = """
            INSERT INTO members
            (bioguide_id, first_name, middle_name, last_name, full_name, party, state,
             district, birth_year, current_member, honorific_prefix, official_url,
             office_address, phone, terms_served, congress, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            params = (
                bioguide_id,
                member_data.get('first_name'),
                member_data.get('middle_name'),
                member_data.get('last_name'),
                member_data.get('full_name'),
                member_data.get('party'),
                member_data.get('state'),
                member_data.get('district'),
                member_data.get('birth_year'),
                member_data.get('current_member', True),
                member_data.get('honorific_prefix'),
                member_data.get('official_url'),
                member_data.get('office_address'),
                member_data.get('phone'),
                member_data.get('terms_served'),
                member_data.get('congress')
            )

            cursor = self.execute(insert_query, params)
            return cursor.lastrowid

    def get_member_by_bioguide_id(self, bioguide_id: str) -> Optional[sqlite3.Row]:
        """Get member by bioguide ID"""
        query = "SELECT * FROM members WHERE bioguide_id = ?"
        return self.fetch_one(query, (bioguide_id,))

    # Hearing operations
    def upsert_hearing(self, hearing_data: Dict[str, Any]) -> int:
        """
        Insert or update hearing record using proper UPDATE to avoid foreign key violations

        Args:
            hearing_data: Hearing data dictionary

        Returns:
            Hearing ID
        """
        event_id = hearing_data.get('event_id')

        # Parse hearing_date into separate date and time fields
        hearing_date_only = None
        hearing_time = None
        if hearing_data.get('hearing_date'):
            try:
                from datetime import datetime, date as dt_date, time as dt_time
                date_value = hearing_data['hearing_date']

                # Handle datetime objects (already parsed)
                if isinstance(date_value, datetime):
                    hearing_date_only = date_value.date().isoformat()
                    hearing_time = date_value.time().isoformat()
                # Handle date objects (date only, no time)
                elif isinstance(date_value, dt_date):
                    hearing_date_only = date_value.isoformat()
                    hearing_time = None  # No time component
                # Handle string formats
                elif isinstance(date_value, str):
                    if date_value.endswith('Z'):
                        dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                    elif 'T' in date_value:
                        dt = datetime.fromisoformat(date_value.split('+')[0].split('Z')[0])
                    else:
                        # Date only format
                        dt = datetime.strptime(date_value, '%Y-%m-%d')

                    hearing_date_only = dt.date().isoformat()
                    hearing_time = dt.time().isoformat()
            except Exception as e:
                logger.warning(f"Failed to parse hearing_date '{hearing_data.get('hearing_date')}': {e}")

        # Check if hearing exists
        existing = self.get_hearing_by_event_id(event_id)

        if existing:
            # Update existing hearing
            update_query = """
            UPDATE hearings SET
                congress = ?,
                chamber = ?,
                title = ?,
                hearing_type = ?,
                status = ?,
                hearing_date = ?,
                hearing_date_only = ?,
                hearing_time = ?,
                location = ?,
                jacket_number = ?,
                url = ?,
                congress_gov_url = ?,
                video_url = ?,
                youtube_video_id = ?,
                video_type = ?,
                update_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE event_id = ?
            """

            params = (
                hearing_data.get('congress'),
                hearing_data.get('chamber'),
                hearing_data.get('title'),
                hearing_data.get('hearing_type'),
                hearing_data.get('status'),
                hearing_data.get('hearing_date'),
                hearing_date_only,
                hearing_time,
                hearing_data.get('location'),
                hearing_data.get('jacket_number'),
                hearing_data.get('url'),
                hearing_data.get('congress_gov_url'),
                hearing_data.get('video_url'),
                hearing_data.get('youtube_video_id'),
                hearing_data.get('video_type'),
                hearing_data.get('update_date'),
                event_id
            )

            self.execute(update_query, params)
            return existing['hearing_id']
        else:
            # Insert new hearing
            insert_query = """
            INSERT INTO hearings
            (event_id, congress, chamber, title, hearing_type, status, hearing_date,
             hearing_date_only, hearing_time, location, jacket_number, url, congress_gov_url,
             video_url, youtube_video_id, video_type, update_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            params = (
                event_id,
                hearing_data.get('congress'),
                hearing_data.get('chamber'),
                hearing_data.get('title'),
                hearing_data.get('hearing_type'),
                hearing_data.get('status'),
                hearing_data.get('hearing_date'),
                hearing_date_only,
                hearing_time,
                hearing_data.get('location'),
                hearing_data.get('jacket_number'),
                hearing_data.get('url'),
                hearing_data.get('congress_gov_url'),
                hearing_data.get('video_url'),
                hearing_data.get('youtube_video_id'),
                hearing_data.get('video_type'),
                hearing_data.get('update_date')
            )

            cursor = self.execute(insert_query, params)
            return cursor.lastrowid

    def get_hearing_by_event_id(self, event_id: str) -> Optional[sqlite3.Row]:
        """Get hearing by event ID"""
        query = "SELECT * FROM hearings WHERE event_id = ?"
        return self.fetch_one(query, (event_id,))

    # Witness operations
    @staticmethod
    def _normalize_witness_name(full_name: str) -> str:
        """
        Normalize witness name by removing titles and honorifics.

        This ensures witnesses are deduplicated even when names have different prefixes
        (e.g., "The Honorable John Smith" == "John Smith" == "Mr. John Smith")

        Args:
            full_name: Original full name from API

        Returns:
            Normalized name without titles
        """
        if not full_name:
            return ''

        # Remove common titles and honorifics
        normalized = full_name
        titles = [
            'The Honorable ',
            'The Hon. ',
            'Honorable ',
            'Hon. ',
            'Mr. ',
            'Ms. ',
            'Mrs. ',
            'Miss ',
            'Dr. ',
            'Prof. ',
            'Professor ',
            'Sen. ',
            'Senator ',
            'Rep. ',
            'Representative ',
            'Gov. ',
            'Governor ',
            'Lt. Gov. ',
            'Lieutenant Governor ',
            'Atty. Gen. ',
            'Attorney General ',
            'Sec. ',
            'Secretary ',
            'Director ',
            'Administrator ',
            'Commissioner ',
            'Chief ',
            'Gen. ',
            'General ',
            'Admiral ',
            'Colonel ',
            'Major ',
            'Captain ',
            'Lieutenant ',
            'Sergeant '
        ]

        for title in titles:
            if normalized.startswith(title):
                normalized = normalized[len(title):]
                break  # Only remove first matching title

        return normalized.strip()

    def get_or_create_witness(self, witness_data: Dict[str, Any]) -> int:
        """
        Get existing witness or create new one, with name normalization to prevent duplicates.

        Matches witnesses by:
        1. Normalized name + organization (primary method - handles title variations)
        2. Exact last name + first name + organization (fallback)

        This prevents duplicates like:
        - "John Smith" vs "The Honorable John Smith"
        - "Jane Doe" vs "Dr. Jane Doe"

        Args:
            witness_data: Witness data dictionary

        Returns:
            Witness ID
        """
        full_name = witness_data.get('full_name', '')
        last_name = witness_data.get('last_name', '')
        first_name = witness_data.get('first_name', '')
        organization = witness_data.get('organization', '')

        # Normalize the name for matching
        normalized_name = self._normalize_witness_name(full_name)

        # Try to find existing witness by normalized name and organization
        # This query checks if any existing witness has the same normalized name
        query = """
        SELECT witness_id, full_name FROM witnesses
        WHERE COALESCE(organization, '') = COALESCE(?, '')
        """

        params = [organization]
        candidates = self.fetch_all(query, tuple(params))

        # Check each candidate for normalized name match
        for candidate in candidates:
            candidate_normalized = self._normalize_witness_name(candidate['full_name'])
            if candidate_normalized == normalized_name:
                logger.debug(f"Found existing witness {candidate['witness_id']}: '{candidate['full_name']}' matches '{full_name}'")
                return candidate['witness_id']

        # Fallback: Try matching by exact last_name + first_name + organization
        # This catches cases where the names are structured differently
        if last_name and first_name:
            fallback_query = """
            SELECT witness_id FROM witnesses
            WHERE last_name = ? AND first_name = ?
            AND COALESCE(organization, '') = COALESCE(?, '')
            """

            existing = self.fetch_one(fallback_query, (last_name, first_name, organization))
            if existing:
                logger.debug(f"Found existing witness {existing['witness_id']} by last/first name match")
                return existing['witness_id']

        # No match found - create new witness
        insert_query = """
        INSERT INTO witnesses (first_name, last_name, full_name, title, organization)
        VALUES (?, ?, ?, ?, ?)
        """

        params = (
            first_name,
            last_name,
            full_name,  # Store original full name with titles
            witness_data.get('title'),
            organization
        )

        cursor = self.execute(insert_query, params)
        logger.debug(f"Created new witness {cursor.lastrowid}: '{full_name}'")
        return cursor.lastrowid

    # Bill operations
    def upsert_bill(self, bill_data: Dict[str, Any]) -> int:
        """
        Insert or update bill record using proper UPDATE to avoid foreign key violations

        Args:
            bill_data: Bill data dictionary

        Returns:
            Bill ID
        """
        congress = bill_data.get('congress')
        bill_type = bill_data.get('bill_type')
        bill_number = bill_data.get('bill_number')

        # Check if bill exists
        existing = self.get_bill_by_congress_type_number(congress, bill_type, bill_number)

        if existing:
            # Update existing bill
            update_query = """
            UPDATE bills SET
                title = ?,
                url = ?,
                introduced_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE congress = ? AND bill_type = ? AND bill_number = ?
            """

            params = (
                bill_data.get('title'),
                bill_data.get('url'),
                bill_data.get('introduced_date'),
                congress,
                bill_type,
                bill_number
            )

            self.execute(update_query, params)
            return existing['bill_id']
        else:
            # Insert new bill
            insert_query = """
            INSERT INTO bills
            (congress, bill_type, bill_number, title, url, introduced_date, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """

            params = (
                congress,
                bill_type,
                bill_number,
                bill_data.get('title'),
                bill_data.get('url'),
                bill_data.get('introduced_date')
            )

            cursor = self.execute(insert_query, params)
            return cursor.lastrowid

    def get_bill_by_congress_type_number(self, congress: int, bill_type: str, bill_number: int) -> Optional[sqlite3.Row]:
        """Get bill by congress, type, and number"""
        query = "SELECT * FROM bills WHERE congress = ? AND bill_type = ? AND bill_number = ?"
        return self.fetch_one(query, (congress, bill_type, bill_number))

    # Relationship operations
    def reset_hearing_committee_primary_flags(self, hearing_id: int) -> None:
        """Reset all is_primary flags to 0 for a hearing to prevent duplicate primary committees"""
        query = "UPDATE hearing_committees SET is_primary = 0 WHERE hearing_id = ?"
        self.execute(query, (hearing_id,))

    def delete_hearing_committee_links(self, hearing_id: int) -> None:
        """Delete all committee links for a hearing"""
        query = "DELETE FROM hearing_committees WHERE hearing_id = ?"
        self.execute(query, (hearing_id,))

    def link_hearing_committee(self, hearing_id: int, committee_id: int, is_primary: bool = True) -> None:
        """Link hearing to committee"""
        query = """
        INSERT OR REPLACE INTO hearing_committees (hearing_id, committee_id, is_primary)
        VALUES (?, ?, ?)
        """
        self.execute(query, (hearing_id, committee_id, is_primary))

    def link_hearing_bill(self, hearing_id: int, bill_id: int, relationship_type: str = 'mentioned') -> None:
        """Link hearing to bill"""
        query = """
        INSERT OR REPLACE INTO hearing_bills (hearing_id, bill_id, relationship_type)
        VALUES (?, ?, ?)
        """
        self.execute(query, (hearing_id, bill_id, relationship_type))

    def create_committee_membership(self, member_id: int, committee_id: int, role: str, congress: int) -> None:
        """Create committee membership record"""
        query = """
        INSERT OR REPLACE INTO committee_memberships
        (committee_id, member_id, role, congress, is_active)
        VALUES (?, ?, ?, ?, 1)
        """
        self.execute(query, (committee_id, member_id, role, congress))

    def create_witness_appearance(self, witness_id: int, hearing_id: int, appearance_data: Dict[str, Any]) -> int:
        """Create witness appearance record"""
        query = """
        INSERT OR REPLACE INTO witness_appearances
        (witness_id, hearing_id, position, witness_type, appearance_order)
        VALUES (?, ?, ?, ?, ?)
        """

        params = (
            witness_id,
            hearing_id,
            appearance_data.get('position'),
            appearance_data.get('witness_type'),
            appearance_data.get('appearance_order')
        )

        cursor = self.execute(query, params)
        return cursor.lastrowid

    # Sync tracking
    def record_sync(self, entity_type: str, status: str, records_processed: int = 0, errors_count: int = 0, notes: str = None) -> None:
        """Record sync operation status"""
        query = """
        INSERT INTO sync_tracking
        (entity_type, last_sync_timestamp, records_processed, errors_count, status, notes)
        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
        """
        self.execute(query, (entity_type, records_processed, errors_count, status, notes))

    def get_last_sync(self, entity_type: str) -> Optional[sqlite3.Row]:
        """Get last successful sync for entity type"""
        query = """
        SELECT * FROM sync_tracking
        WHERE entity_type = ? AND status = 'success'
        ORDER BY last_sync_timestamp DESC
        LIMIT 1
        """
        return self.fetch_one(query, (entity_type,))

    # Error logging
    def log_import_error(self, entity_type: str, entity_identifier: str, error_type: str,
                        error_message: str, severity: str = 'warning') -> None:
        """Log import error"""
        query = """
        INSERT INTO import_errors
        (entity_type, entity_identifier, error_type, error_message, severity)
        VALUES (?, ?, ?, ?, ?)
        """
        self.execute(query, (entity_type, entity_identifier, error_type, error_message, severity))

    # Utility methods
    def vacuum(self) -> None:
        """Vacuum database to reclaim space"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")

    def analyze(self) -> None:
        """Analyze database for query optimization"""
        with self.get_connection() as conn:
            conn.execute("ANALYZE")
        logger.info("Database analyzed")

    def get_table_counts(self) -> Dict[str, int]:
        """Get record counts for all major tables"""
        tables = [
            'committees', 'members', 'hearings', 'bills', 'witnesses',
            'committee_memberships', 'hearing_committees', 'hearing_bills',
            'witness_appearances'
        ]

        counts = {}
        with self.transaction() as conn:
            for table in tables:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cursor.fetchone()[0]

        return counts