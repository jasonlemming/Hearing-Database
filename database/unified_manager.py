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
            if prefer_postgres and os.environ.get('POSTGRES_URL'):
                db_url = os.environ.get('POSTGRES_URL')
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
