"""
CRS Content Manager - Database operations for CRS content versions
"""
import sqlite3
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from config.logging_config import get_logger

logger = get_logger(__name__)


class CRSContentManager:
    """
    Manages CRS content storage and retrieval

    Handles:
    - Version storage and updates
    - Full-text search index management
    - Ingestion logging
    - Content retrieval
    """

    def __init__(self, db_path: str = 'crs_products.db'):
        """
        Initialize CRS content manager

        Args:
            db_path: Path to CRS SQLite database
        """
        self.db_path = db_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Ensure database file exists"""
        db_file = Path(self.db_path)
        if not db_file.exists():
            logger.warning(f"Database not found: {self.db_path}")

    @contextmanager
    def get_connection(self):
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_version(self, product_id: str, version_number: int,
                      html_content: str, text_content: str, structure_json: Dict,
                      content_hash: str, word_count: int, html_url: str) -> int:
        """
        Insert or update a product version

        Marks all previous versions as not current

        Args:
            product_id: CRS product ID
            version_number: Version number
            html_content: Cleaned HTML
            text_content: Plain text
            structure_json: Document structure
            content_hash: SHA256 hash
            word_count: Word count
            html_url: Source URL

        Returns:
            version_id of inserted/updated version
        """
        with self.get_connection() as conn:
            # Check if this version already exists
            existing = conn.execute("""
                SELECT version_id, content_hash
                FROM product_versions
                WHERE product_id = ? AND version_number = ?
            """, (product_id, version_number)).fetchone()

            if existing:
                # Check if content has changed
                if existing['content_hash'] == content_hash:
                    logger.debug(f"Version {version_number} of {product_id} unchanged, skipping update")
                    return existing['version_id']

                # Content changed, update it
                conn.execute("""
                    UPDATE product_versions
                    SET html_content = ?,
                        text_content = ?,
                        structure_json = ?,
                        content_hash = ?,
                        word_count = ?,
                        html_url = ?,
                        ingested_at = CURRENT_TIMESTAMP
                    WHERE version_id = ?
                """, (html_content, text_content, json.dumps(structure_json),
                     content_hash, word_count, html_url, existing['version_id']))

                version_id = existing['version_id']
                logger.info(f"✓ Updated version {version_number} of {product_id} (content changed)")

            else:
                # Insert new version
                cursor = conn.execute("""
                    INSERT INTO product_versions
                    (product_id, version_number, html_content, text_content, structure_json,
                     content_hash, word_count, html_url, is_current)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (product_id, version_number, html_content, text_content,
                     json.dumps(structure_json), content_hash, word_count, html_url))

                version_id = cursor.lastrowid
                logger.info(f"✓ Inserted version {version_number} of {product_id}")

            # Mark this version as current, all others as not current
            conn.execute("""
                UPDATE product_versions
                SET is_current = 0
                WHERE product_id = ? AND version_id != ?
            """, (product_id, version_id))

            conn.execute("""
                UPDATE product_versions
                SET is_current = 1
                WHERE version_id = ?
            """, (version_id,))

            # Update FTS index
            self._update_fts_index(conn, version_id, product_id, structure_json, text_content)

            return version_id

    def _update_fts_index(self, conn: sqlite3.Connection, version_id: int,
                         product_id: str, structure_json: Dict, text_content: str):
        """
        Update full-text search index for a version

        Args:
            conn: Database connection
            version_id: Version ID
            product_id: Product ID
            structure_json: Document structure
            text_content: Plain text content
        """
        # Get product title from products table
        product = conn.execute("""
            SELECT title FROM products WHERE product_id = ?
        """, (product_id,)).fetchone()

        title = product['title'] if product else ''
        headings = ' '.join(structure_json.get('headings', []))

        # Delete existing FTS entry for this version
        conn.execute("""
            DELETE FROM product_content_fts WHERE version_id = ?
        """, (version_id,))

        # Insert new FTS entry
        conn.execute("""
            INSERT INTO product_content_fts (product_id, version_id, title, headings, text_content)
            VALUES (?, ?, ?, ?, ?)
        """, (product_id, version_id, title, headings, text_content))

    def get_current_version(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current version of a product

        Args:
            product_id: Product ID

        Returns:
            Version record as dict or None
        """
        with self.get_connection() as conn:
            version = conn.execute("""
                SELECT * FROM product_versions
                WHERE product_id = ? AND is_current = 1
            """, (product_id,)).fetchone()

            if version:
                return dict(version)
            return None

    def get_version(self, product_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """
        Get specific version of a product

        Args:
            product_id: Product ID
            version_number: Version number

        Returns:
            Version record as dict or None
        """
        with self.get_connection() as conn:
            version = conn.execute("""
                SELECT * FROM product_versions
                WHERE product_id = ? AND version_number = ?
            """, (product_id, version_number)).fetchone()

            if version:
                return dict(version)
            return None

    def get_version_history(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a product (metadata only, not content)

        Args:
            product_id: Product ID

        Returns:
            List of version records (without large content fields)
        """
        with self.get_connection() as conn:
            versions = conn.execute("""
                SELECT version_id, product_id, version_number, word_count,
                       content_hash, ingested_at, is_current, html_url
                FROM product_versions
                WHERE product_id = ?
                ORDER BY version_number DESC
            """, (product_id,)).fetchall()

            return [dict(v) for v in versions]

    def needs_update(self, product_id: str, version_number: int, html_url: str) -> bool:
        """
        Check if content needs to be fetched/updated

        Returns True if:
        - Version doesn't exist
        - Version exists but might have changed (different URL or old)

        Args:
            product_id: Product ID
            version_number: Version number
            html_url: HTML URL

        Returns:
            True if content should be fetched
        """
        current = self.get_version(product_id, version_number)

        if not current:
            return True  # Version doesn't exist

        # Check if URL changed (might indicate content change)
        if current.get('html_url') != html_url:
            logger.debug(f"URL changed for {product_id} v{version_number}, needs update")
            return True

        # Don't re-fetch if ingested recently (within 7 days)
        ingested_at = current.get('ingested_at')
        if ingested_at:
            try:
                ingested_date = datetime.fromisoformat(ingested_at)
                days_old = (datetime.now() - ingested_date).days
                if days_old < 7:
                    return False
            except:
                pass

        return False  # Already have this version

    def get_products_needing_content(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get products that don't have current version content

        Args:
            limit: Optional limit on number of products

        Returns:
            List of product records that need content
        """
        with self.get_connection() as conn:
            query = """
                SELECT p.*
                FROM products p
                LEFT JOIN product_versions pv ON p.product_id = pv.product_id AND pv.is_current = 1
                WHERE pv.version_id IS NULL
                ORDER BY p.publication_date DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            products = conn.execute(query).fetchall()
            return [dict(p) for p in products]

    def start_ingestion_log(self, run_type: str) -> int:
        """
        Create new ingestion log entry

        Args:
            run_type: Type of run ('backfill', 'update', 'manual')

        Returns:
            log_id
        """
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO content_ingestion_logs
                (run_type, started_at, status)
                VALUES (?, ?, 'running')
            """, (run_type, datetime.now().isoformat()))

            return cursor.lastrowid

    def update_ingestion_log(self, log_id: int, **kwargs):
        """
        Update ingestion log with metrics

        Args:
            log_id: Log ID
            **kwargs: Fields to update (products_checked, content_fetched, etc.)
        """
        # Build SET clause from kwargs
        set_parts = []
        values = []

        for key, value in kwargs.items():
            if key == 'error_details' and isinstance(value, (list, dict)):
                set_parts.append(f"{key} = ?")
                values.append(json.dumps(value))
            else:
                set_parts.append(f"{key} = ?")
                values.append(value)

        if not set_parts:
            return

        values.append(log_id)
        query = f"""
            UPDATE content_ingestion_logs
            SET {', '.join(set_parts)}
            WHERE log_id = ?
        """

        with self.get_connection() as conn:
            conn.execute(query, values)

    def complete_ingestion_log(self, log_id: int, status: str = 'completed'):
        """
        Mark ingestion log as completed

        Args:
            log_id: Log ID
            status: Final status ('completed', 'failed', 'partial')
        """
        with self.get_connection() as conn:
            # Calculate duration
            log = conn.execute("""
                SELECT started_at FROM content_ingestion_logs WHERE log_id = ?
            """, (log_id,)).fetchone()

            if log:
                started = datetime.fromisoformat(log['started_at'])
                duration = (datetime.now() - started).total_seconds()

                conn.execute("""
                    UPDATE content_ingestion_logs
                    SET completed_at = ?,
                        status = ?,
                        total_duration_seconds = ?
                    WHERE log_id = ?
                """, (datetime.now().isoformat(), status, duration, log_id))

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get overall content ingestion statistics

        Returns:
            Dictionary with stats
        """
        with self.get_connection() as conn:
            stats = {}

            # Total products
            stats['total_products'] = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

            # Products with content
            stats['products_with_content'] = conn.execute("""
                SELECT COUNT(DISTINCT product_id) FROM product_versions
            """).fetchone()[0]

            # Current versions
            stats['current_versions'] = conn.execute("""
                SELECT COUNT(*) FROM product_versions WHERE is_current = 1
            """).fetchone()[0]

            # Total versions
            stats['total_versions'] = conn.execute("""
                SELECT COUNT(*) FROM product_versions
            """).fetchone()[0]

            # Total storage
            storage = conn.execute("""
                SELECT SUM(LENGTH(html_content) + LENGTH(text_content)) as total_bytes
                FROM product_versions
            """).fetchone()
            stats['total_storage_bytes'] = storage['total_bytes'] or 0

            # Average word count
            avg_words = conn.execute("""
                SELECT AVG(word_count) as avg_words
                FROM product_versions
                WHERE is_current = 1
            """).fetchone()
            stats['avg_word_count'] = round(avg_words['avg_words'] or 0, 0)

            # Last ingestion
            last_log = conn.execute("""
                SELECT started_at, status, content_fetched
                FROM content_ingestion_logs
                ORDER BY started_at DESC
                LIMIT 1
            """).fetchone()

            if last_log:
                stats['last_ingestion'] = dict(last_log)

            # Coverage percentage
            if stats['total_products'] > 0:
                stats['coverage_percent'] = round(
                    (stats['products_with_content'] / stats['total_products']) * 100, 1
                )
            else:
                stats['coverage_percent'] = 0

            return stats
