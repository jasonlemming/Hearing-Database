"""
Unified Database Manager - supports both SQLite and PostgreSQL

This manager auto-detects the database type from the connection string
and handles dialect differences transparently.
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, Dict, Any, List, Tuple, Union
from pathlib import Path

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class PostgresConnectionWrapper:
    """
    Wrapper for psycopg2 connections that adds execute() method for compatibility

    This allows blueprints to use conn.execute() syntax which works for both
    SQLite and Postgres without modification.
    """
    def __init__(self, conn, db_manager):
        self._conn = conn
        self._db_manager = db_manager

    def execute(self, query, params=None):
        """Execute query and return cursor (Postgres-compatible)"""
        # Convert ? to %s for Postgres
        query = query.replace('?', '%s')
        cursor = self._conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def cursor(self, cursor_factory=None):
        """Get cursor with optional factory"""
        if cursor_factory:
            return self._conn.cursor(cursor_factory=cursor_factory)
        return self._conn.cursor()

    def commit(self):
        """Commit transaction"""
        return self._conn.commit()

    def rollback(self):
        """Rollback transaction"""
        return self._conn.rollback()

    def close(self):
        """Close connection"""
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()


class UnifiedDatabaseManager:
    """
    Unified database manager supporting both SQLite and PostgreSQL

    Automatically detects database type from connection string and handles
    SQL dialect differences (? vs %s placeholders, AUTOINCREMENT vs SERIAL, etc.)
    """

    def __init__(self, db_url: Optional[str] = None, prefer_postgres: bool = True):
        """
        Initialize database manager

        Args:
            db_url: Database URL. Can be:
                   - SQLite: path like "database.db" or "sqlite:///database.db"
                   - Postgres: "postgresql://user:pass@host/db"
                   - None: Auto-detect from environment
            prefer_postgres: If True and POSTGRES_URL is set, use Postgres
        """
        # Determine database URL
        if db_url is None:
            # Auto-detect: Check for Postgres URL first if preferred
            if prefer_postgres:
                # Check both POSTGRES_URL and DATABASE_URL (common on Vercel/Neon)
                db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')
                if not db_url or not db_url.startswith('postgres'):
                    # Fall back to SQLite if no Postgres URL found
                    db_url = settings.database_path
            else:
                db_url = settings.database_path

        self.db_url = db_url
        self.db_type = self._detect_database_type(db_url)

        logger.info(f"Initialized {self.db_type.upper()} database manager: {self._safe_url()}")

        if self.db_type == 'sqlite':
            self.ensure_database_directory()
        elif self.db_type == 'postgres' and not POSTGRES_AVAILABLE:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")

    def _detect_database_type(self, url: str) -> str:
        """
        Detect database type from URL

        Args:
            url: Database URL

        Returns:
            'sqlite' or 'postgres'
        """
        if url.startswith('postgresql://') or url.startswith('postgres://'):
            return 'postgres'
        return 'sqlite'

    def _safe_url(self) -> str:
        """Return URL with password redacted for logging"""
        if self.db_type == 'postgres':
            # Redact password from postgres://user:password@host/db
            parts = self.db_url.split('@')
            if len(parts) == 2:
                prefix = parts[0].split(':')[0:2]  # Keep protocol and user
                return f"{prefix[0]}:***@{parts[1]}"
        return self.db_url

    def ensure_database_directory(self):
        """Ensure database directory exists (SQLite only)"""
        if self.db_type == 'sqlite':
            db_dir = Path(self.db_url).parent
            db_dir.mkdir(parents=True, exist_ok=True)

    def get_connection(self):
        """
        Get database connection with row factory

        Returns:
            sqlite3.Connection or PostgresConnectionWrapper
        """
        if self.db_type == 'sqlite':
            conn = sqlite3.connect(self.db_url)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        else:  # postgres
            raw_conn = psycopg2.connect(self.db_url)
            return PostgresConnectionWrapper(raw_conn, self)

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions

        Yields connection that auto-commits on success or rolls back on exception
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _convert_placeholders(self, query: str, params: Optional[Union[Tuple, List]] = None) -> Tuple[str, Optional[Union[Tuple, List]]]:
        """
        Convert query placeholders based on database type

        SQLite uses ? placeholders
        Postgres uses %s placeholders

        Args:
            query: SQL query with ? placeholders (SQLite style)
            params: Query parameters

        Returns:
            Tuple of (converted_query, params)
        """
        if self.db_type == 'postgres':
            # Replace ? with %s for Postgres
            query = query.replace('?', '%s')

        return query, params

    def execute(self, query: str, params: Optional[Union[Tuple, List]] = None):
        """
        Execute single query

        Args:
            query: SQL query (use ? placeholders, will be converted automatically)
            params: Query parameters

        Returns:
            Cursor with results
        """
        query, params = self._convert_placeholders(query, params)

        with self.transaction() as conn:
            if self.db_type == 'postgres':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            return cursor

    def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        Execute query with multiple parameter sets

        Args:
            query: SQL query
            params_list: List of parameter tuples
        """
        query, _ = self._convert_placeholders(query)

        with self.transaction() as conn:
            if self.db_type == 'postgres':
                cursor = conn.cursor()
            else:
                cursor = conn.cursor()

            cursor.executemany(query, params_list)

    def fetch_one(self, query: str, params: Optional[Tuple] = None):
        """
        Fetch single row

        Returns:
            Dict-like row object (works for both SQLite Row and Postgres RealDictCursor)
        """
        query, params = self._convert_placeholders(query, params)

        with self.transaction() as conn:
            if self.db_type == 'postgres':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            return cursor.fetchone()

    def fetch_all(self, query: str, params: Optional[Tuple] = None):
        """
        Fetch all rows

        Returns:
            List of dict-like row objects
        """
        query, params = self._convert_placeholders(query, params)

        with self.transaction() as conn:
            if self.db_type == 'postgres':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            return cursor.fetchall()

    def get_table_counts(self) -> Dict[str, int]:
        """Get record counts for all major tables"""
        tables = [
            'committees', 'members', 'hearings', 'bills', 'witnesses',
            'committee_memberships', 'hearing_committees', 'hearing_bills',
            'witness_appearances', 'products', 'documents', 'sources'
        ]

        counts = {}
        with self.transaction() as conn:
            if self.db_type == 'postgres':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    result = cursor.fetchone()
                    if self.db_type == 'postgres':
                        counts[table] = result['count']
                    else:
                        counts[table] = result[0]
                except Exception as e:
                    # Table might not exist
                    logger.debug(f"Could not count table {table}: {e}")
                    counts[table] = 0

        return counts

    def health_check(self) -> Dict[str, Any]:
        """
        Check database health and return diagnostics

        Returns:
            Dict with status, connection info, table counts, etc.
        """
        try:
            # Test connection
            with self.transaction() as conn:
                if self.db_type == 'postgres':
                    cursor = conn.cursor()
                    cursor.execute("SELECT version()")
                    version = cursor.fetchone()[0]
                else:
                    cursor = conn.cursor()
                    cursor.execute("SELECT sqlite_version()")
                    version = cursor.fetchone()[0]

            # Get table counts
            counts = self.get_table_counts()
            total_records = sum(counts.values())

            return {
                'status': 'healthy',
                'database_type': self.db_type,
                'version': version,
                'table_counts': counts,
                'total_records': total_records,
                'url': self._safe_url()
            }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'database_type': self.db_type,
                'error': str(e),
                'url': self._safe_url()
            }

    # Entity lookup methods
    def get_hearing_by_event_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        """Get hearing by event ID"""
        query = "SELECT * FROM hearings WHERE event_id = ?"
        return self.fetch_one(query, (event_id,))

    def get_committee_by_system_code(self, system_code: str) -> Optional[Dict[str, Any]]:
        """Get committee by system code"""
        query = "SELECT * FROM committees WHERE system_code = ?"
        return self.fetch_one(query, (system_code,))

    def get_member_by_bioguide_id(self, bioguide_id: str) -> Optional[Dict[str, Any]]:
        """Get member by bioguide ID"""
        query = "SELECT * FROM members WHERE bioguide_id = ?"
        return self.fetch_one(query, (bioguide_id,))

    # Relationship operations
    def link_hearing_committee(self, hearing_id: int, committee_id: int, is_primary: bool = True) -> None:
        """Link hearing to committee"""
        if self.db_type == 'postgres':
            query = """
            INSERT INTO hearing_committees (hearing_id, committee_id, is_primary)
            VALUES (%s, %s, %s)
            ON CONFLICT (hearing_id, committee_id) DO UPDATE SET is_primary = EXCLUDED.is_primary
            """
            params = (hearing_id, committee_id, is_primary)
        else:
            query = """
            INSERT OR REPLACE INTO hearing_committees (hearing_id, committee_id, is_primary)
            VALUES (?, ?, ?)
            """
            params = (hearing_id, committee_id, is_primary)

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

    def delete_hearing_committee_links(self, hearing_id: int) -> None:
        """Delete all committee links for a hearing"""
        query = "DELETE FROM hearing_committees WHERE hearing_id = ?"
        query, params = self._convert_placeholders(query, (hearing_id,))

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)

    def reset_hearing_committee_primary_flags(self, hearing_id: int) -> None:
        """Reset all is_primary flags to FALSE for a hearing to prevent duplicate primary committees"""
        if self.db_type == 'postgres':
            query = "UPDATE hearing_committees SET is_primary = FALSE WHERE hearing_id = %s"
        else:
            query = "UPDATE hearing_committees SET is_primary = 0 WHERE hearing_id = ?"

        with self.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (hearing_id,))

    def execute_insert(self, query: str, params: Optional[Union[Tuple, List]], id_column: str) -> int:
        """
        Execute INSERT and return the new row's ID.

        For SQLite: Uses cursor.lastrowid
        For PostgreSQL: Adds RETURNING clause to query

        Args:
            query: INSERT query (use ? placeholders, will be converted automatically)
            params: Query parameters
            id_column: Name of the ID column (e.g., 'witness_id', 'appearance_id')

        Returns:
            The ID of the inserted row
        """
        query, params = self._convert_placeholders(query, params)

        if self.db_type == 'postgres':
            # Add RETURNING clause for PostgreSQL
            if 'RETURNING' not in query.upper():
                query = query.rstrip().rstrip(';') + f' RETURNING {id_column}'

            with self.transaction() as conn:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(query, params)
                result = cursor.fetchone()
                return result[id_column] if result else None
        else:
            # Use lastrowid for SQLite
            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.lastrowid

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

        witness_id = self.execute_insert(insert_query, params, 'witness_id')
        logger.debug(f"Created new witness {witness_id}: '{full_name}'")
        return witness_id

    def create_witness_appearance(self, witness_id: int, hearing_id: int, appearance_data: Dict[str, Any]) -> int:
        """Create witness appearance record"""
        params = (
            witness_id,
            hearing_id,
            appearance_data.get('position'),
            appearance_data.get('witness_type'),
            appearance_data.get('appearance_order')
        )

        if self.db_type == 'postgres':
            query = """
            INSERT INTO witness_appearances
            (witness_id, hearing_id, position, witness_type, appearance_order)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (witness_id, hearing_id) DO UPDATE SET
                position = EXCLUDED.position,
                witness_type = EXCLUDED.witness_type,
                appearance_order = EXCLUDED.appearance_order
            RETURNING appearance_id
            """
        else:
            query = """
            INSERT OR REPLACE INTO witness_appearances
            (witness_id, hearing_id, position, witness_type, appearance_order)
            VALUES (?, ?, ?, ?, ?)
            """

        return self.execute_insert(query, params, 'appearance_id')

    # Hearing operations
    def upsert_hearing(self, hearing_data: Dict[str, Any]) -> int:
        """
        Insert or update hearing record using proper UPDATE to avoid foreign key violations

        Args:
            hearing_data: Hearing data dictionary

        Returns:
            Hearing ID
        """
        from datetime import datetime, date as dt_date

        event_id = hearing_data.get('event_id')

        # Parse hearing_date into separate date and time fields
        hearing_date_only = None
        hearing_time = None
        if hearing_data.get('hearing_date'):
            try:
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

            query, params = self._convert_placeholders(update_query, params)

            with self.transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)

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

            return self.execute_insert(insert_query, params, 'hearing_id')
