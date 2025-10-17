"""
CRS Content Manager (PostgreSQL) - Database operations for CRS content versions

PostgreSQL-compatible version using Neon database.
"""
import json
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from contextlib import contextmanager
from config.logging_config import get_logger
from database.postgres_config import get_connection
import psycopg2
from psycopg2.extras import RealDictCursor

logger = get_logger(__name__)


class CRSContentManager:
    """
    Manages CRS content storage and retrieval (PostgreSQL version)

    Handles:
    - Version storage and updates
    - Full-text search index management (using ts_vector)
    - Ingestion logging
    - Content retrieval
    """

    def __init__(self):
        """Initialize CRS content manager with PostgreSQL"""
        self._init_r2_client()

    def _init_r2_client(self):
        """Initialize Cloudflare R2 client for blob storage"""
        self.r2_enabled = False
        self.s3_client = None
        self.bucket_name = None
        self.public_url = None

        try:
            access_key = os.getenv('R2_ACCESS_KEY_ID')
            secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
            account_id = os.getenv('R2_ACCOUNT_ID')
            self.bucket_name = os.getenv('R2_BUCKET_NAME')
            self.public_url = os.getenv('R2_PUBLIC_URL')

            if all([access_key, secret_key, account_id, self.bucket_name, self.public_url]):
                endpoint_url = f'https://{account_id}.r2.cloudflarestorage.com'
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=endpoint_url,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name='auto'
                )
                self.r2_enabled = True
                # Remove trailing slash from public_url
                self.public_url = self.public_url.rstrip('/')
                logger.info(f"✓ R2 storage enabled (bucket: {self.bucket_name})")
            else:
                logger.warning("R2 credentials not found - content will be stored in database")
        except Exception as e:
            logger.error(f"Failed to initialize R2 client: {e}")
            self.r2_enabled = False

    def _upload_to_r2(self, product_id: str, version_number: int, html_content: str) -> Optional[str]:
        """
        Upload HTML content to Cloudflare R2

        Args:
            product_id: CRS product ID
            version_number: Version number
            html_content: HTML content to upload

        Returns:
            Public blob URL or None if upload failed
        """
        if not self.r2_enabled:
            return None

        filename = f"crs-{product_id}-v{version_number}.html"

        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=html_content.encode('utf-8'),
                ContentType='text/html; charset=utf-8'
            )

            blob_url = f"{self.public_url}/{filename}"
            logger.debug(f"✓ Uploaded {product_id} v{version_number} to R2")
            return blob_url

        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_msg = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"R2 upload failed for {product_id}: [{error_code}] {error_msg}")
            return None
        except Exception as e:
            logger.error(f"R2 upload failed for {product_id}: {e}")
            return None

    def upsert_version(self, product_id: str, version_number: int,
                      parsed_content, html_url: str) -> bool:
        """
        Insert or update a product version

        Marks all previous versions as not current
        Uploads HTML content to R2 if enabled

        Args:
            product_id: CRS product ID
            version_number: Version number
            parsed_content: ParsedContent object from parser
            html_url: Source URL

        Returns:
            True if new version was added, False if updated
        """
        # Extract fields from ParsedContent
        html_content = parsed_content.html_content
        text_content = parsed_content.text_content
        structure_json = parsed_content.structure_json
        content_hash = parsed_content.content_hash
        word_count = parsed_content.word_count

        # Upload HTML content to R2 if enabled
        blob_url = self._upload_to_r2(product_id, version_number, html_content)
        if not blob_url:
            logger.warning(f"R2 upload failed for {product_id} v{version_number} - skipping ingestion")
            # If R2 is enabled but upload failed, don't proceed
            if self.r2_enabled:
                raise Exception(f"R2 upload failed for {product_id} v{version_number}")

        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            # Check if this version already exists
            cursor.execute("""
                SELECT version_id, content_hash
                FROM product_versions
                WHERE product_id = %s AND version_number = %s
            """, (product_id, version_number))
            existing = cursor.fetchone()

            is_new = False

            if existing:
                # Check if content has changed
                if existing['content_hash'] == content_hash:
                    logger.debug(f"Version {version_number} of {product_id} unchanged, skipping update")
                    return False

                # Content changed, update it
                cursor.execute("""
                    UPDATE product_versions
                    SET structure_json = %s,
                        content_hash = %s,
                        word_count = %s,
                        html_url = %s,
                        blob_url = %s,
                        ingested_at = NOW()
                    WHERE version_id = %s
                """, (json.dumps(structure_json), content_hash, word_count,
                     html_url, blob_url, existing['version_id']))

                version_id = existing['version_id']
                logger.info(f"✓ Updated version {version_number} of {product_id} (content changed)")

            else:
                # Insert new version
                cursor.execute("""
                    INSERT INTO product_versions
                    (product_id, version_number, structure_json,
                     content_hash, word_count, html_url, blob_url, is_current)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, false)
                    RETURNING version_id
                """, (product_id, version_number, json.dumps(structure_json),
                     content_hash, word_count, html_url, blob_url))

                version_id = cursor.fetchone()['version_id']
                is_new = True
                logger.info(f"✓ Inserted version {version_number} of {product_id}")

            # Mark this version as current, all others as not current
            cursor.execute("""
                UPDATE product_versions
                SET is_current = false
                WHERE product_id = %s AND version_id != %s
            """, (product_id, version_id))

            cursor.execute("""
                UPDATE product_versions
                SET is_current = true
                WHERE version_id = %s
            """, (version_id,))

            # Update FTS index
            self._update_fts_index(conn, version_id, product_id, structure_json, text_content)

            return is_new

    def _update_fts_index(self, conn, version_id: int,
                         product_id: str, structure_json: Dict, text_content: str):
        """
        Update full-text search index for a version (PostgreSQL ts_vector)

        Args:
            conn: Database connection
            version_id: Version ID
            product_id: Product ID
            structure_json: Document structure
            text_content: Plain text content
        """
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get product title from products table
        cursor.execute("""
            SELECT title FROM products WHERE product_id = %s
        """, (product_id,))
        product = cursor.fetchone()

        title = product['title'] if product else ''
        headings = ' '.join(structure_json.get('headings', []))

        # Delete existing FTS entry for this version
        cursor.execute("""
            DELETE FROM product_content_fts WHERE version_id = %s
        """, (version_id,))

        # Insert new FTS entry with ts_vector
        cursor.execute("""
            INSERT INTO product_content_fts (product_id, version_id, title, headings, text_content, search_vector)
            VALUES (%s, %s, %s, %s, %s,
                    setweight(to_tsvector('english', %s), 'A') ||
                    setweight(to_tsvector('english', %s), 'B') ||
                    setweight(to_tsvector('english', %s), 'C'))
        """, (product_id, version_id, title, headings, text_content, title, headings, text_content))

    def get_current_version(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current version of a product

        Args:
            product_id: Product ID

        Returns:
            Version record as dict or None
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM product_versions
                WHERE product_id = %s AND is_current = true
            """, (product_id,))

            version = cursor.fetchone()
            return dict(version) if version else None

    def get_version(self, product_id: str, version_number: int) -> Optional[Dict[str, Any]]:
        """
        Get specific version of a product

        Args:
            product_id: Product ID
            version_number: Version number

        Returns:
            Version record as dict or None
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT * FROM product_versions
                WHERE product_id = %s AND version_number = %s
            """, (product_id, version_number))

            version = cursor.fetchone()
            return dict(version) if version else None

    def get_version_history(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Get all versions of a product (metadata only, not content)

        Args:
            product_id: Product ID

        Returns:
            List of version records (without large content fields)
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT version_id, product_id, version_number, word_count,
                       content_hash, ingested_at, is_current, html_url
                FROM product_versions
                WHERE product_id = %s
                ORDER BY version_number DESC
            """, (product_id,))

            versions = cursor.fetchall()
            return [dict(v) for v in versions]

    def needs_update(self, product_id: str, version_number: int) -> bool:
        """
        Check if content needs to be fetched/updated

        Returns True if:
        - Version doesn't exist
        - Version was ingested more than 7 days ago

        Args:
            product_id: Product ID
            version_number: Version number

        Returns:
            True if content should be fetched
        """
        current = self.get_version(product_id, version_number)

        if not current:
            return True  # Version doesn't exist

        # Don't re-fetch if ingested recently (within 7 days)
        ingested_at = current.get('ingested_at')
        if ingested_at:
            try:
                # Handle both string and datetime types
                if isinstance(ingested_at, str):
                    ingested_date = datetime.fromisoformat(ingested_at)
                else:
                    ingested_date = ingested_at
                days_old = (datetime.now() - ingested_date).days
                if days_old < 7:
                    return False
            except:
                pass

        return False  # Already have this version

    def get_products_needing_content(self, since_date: Optional[datetime] = None,
                                    limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get products that need content updates

        Args:
            since_date: Only include products updated since this date
            limit: Optional limit on number of products

        Returns:
            List of product records that need content
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)

            query = """
                SELECT p.*
                FROM products p
                LEFT JOIN product_versions pv ON p.product_id = pv.product_id AND pv.is_current = true
                WHERE 1=1
            """
            params = []

            # Add date filter if provided
            if since_date:
                query += " AND p.update_date >= %s"
                params.append(since_date)

            # Prioritize products without content or with old content
            query += """
                ORDER BY
                    CASE WHEN pv.version_id IS NULL THEN 0 ELSE 1 END,
                    p.update_date DESC
            """

            if limit:
                query += f" LIMIT %s"
                params.append(limit)

            cursor.execute(query, params)
            products = cursor.fetchall()
            return [dict(p) for p in products]

    def start_ingestion_log(self, run_type: str, products_checked: int = 0) -> int:
        """
        Create new ingestion log entry

        Args:
            run_type: Type of run ('backfill', 'update', 'manual')
            products_checked: Number of products to check

        Returns:
            log_id
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                INSERT INTO content_ingestion_logs
                (run_type, started_at, status, products_checked)
                VALUES (%s, NOW(), 'running', %s)
                RETURNING log_id
            """, (run_type, products_checked))

            return cursor.fetchone()['log_id']

    def update_ingestion_log(self, log_id: int, **kwargs):
        """
        Update ingestion log with metrics

        Args:
            log_id: Log ID
            **kwargs: Fields to update (products_checked, content_fetched, etc.)
        """
        if not kwargs:
            return

        # Build SET clause from kwargs
        set_parts = []
        values = []

        for key, value in kwargs.items():
            if key == 'error_details' and isinstance(value, (list, dict)):
                set_parts.append(f"{key} = %s")
                values.append(json.dumps(value))
            else:
                set_parts.append(f"{key} = %s")
                values.append(value)

        values.append(log_id)
        query = f"""
            UPDATE content_ingestion_logs
            SET {', '.join(set_parts)}
            WHERE log_id = %s
        """

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, values)

    def complete_ingestion_log(self, log_id: int, content_fetched: int = 0,
                               content_updated: int = 0, content_skipped: int = 0,
                               errors_count: int = 0, total_size_bytes: int = 0,
                               avg_fetch_time_ms: float = 0, total_duration_seconds: float = 0):
        """
        Mark ingestion log as completed

        Args:
            log_id: Log ID
            content_fetched: Number of new versions fetched
            content_updated: Number of existing versions updated
            content_skipped: Number skipped (no change)
            errors_count: Number of errors
            total_size_bytes: Total size fetched
            avg_fetch_time_ms: Average fetch time
            total_duration_seconds: Total run duration
        """
        with get_connection() as conn:
            cursor = conn.cursor()

            # Determine final status
            if errors_count > 0 and (content_fetched + content_updated) == 0:
                status = 'failed'
            elif errors_count > 0:
                status = 'partial'
            else:
                status = 'completed'

            cursor.execute("""
                UPDATE content_ingestion_logs
                SET completed_at = NOW(),
                    status = %s,
                    content_fetched = %s,
                    content_updated = %s,
                    content_skipped = %s,
                    errors_count = %s,
                    total_size_bytes = %s,
                    avg_fetch_time_ms = %s,
                    total_duration_seconds = %s
                WHERE log_id = %s
            """, (status, content_fetched, content_updated, content_skipped,
                 errors_count, total_size_bytes, avg_fetch_time_ms,
                 total_duration_seconds, log_id))

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get overall content ingestion statistics

        Returns:
            Dictionary with stats
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            stats = {}

            # Total products
            cursor.execute("SELECT COUNT(*) as count FROM products")
            stats['total_products'] = cursor.fetchone()['count']

            # Products with content
            cursor.execute("""
                SELECT COUNT(DISTINCT product_id) as count FROM product_versions
            """)
            stats['products_with_content'] = cursor.fetchone()['count']

            # Current versions
            cursor.execute("""
                SELECT COUNT(*) as count FROM product_versions WHERE is_current = true
            """)
            stats['current_versions'] = cursor.fetchone()['count']

            # Total versions
            cursor.execute("""
                SELECT COUNT(*) as count FROM product_versions
            """)
            stats['total_versions'] = cursor.fetchone()['count']

            # Content in R2
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM product_versions
                WHERE blob_url IS NOT NULL
            """)
            stats['content_in_r2'] = cursor.fetchone()['count']

            # Average word count
            cursor.execute("""
                SELECT AVG(word_count) as avg_words
                FROM product_versions
                WHERE is_current = true
            """)
            result = cursor.fetchone()
            stats['avg_word_count'] = round(result['avg_words'] or 0, 0)

            # Last ingestion
            cursor.execute("""
                SELECT started_at, status, content_fetched
                FROM content_ingestion_logs
                ORDER BY started_at DESC
                LIMIT 1
            """)
            last_log = cursor.fetchone()

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

    def get_recent_ingestion_logs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent ingestion logs

        Args:
            limit: Number of logs to return

        Returns:
            List of ingestion log records
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT log_id, run_type, started_at, completed_at, status,
                       products_checked, content_fetched, content_updated,
                       content_skipped, errors_count, total_duration_seconds
                FROM content_ingestion_logs
                ORDER BY started_at DESC
                LIMIT %s
            """, (limit,))

            logs = cursor.fetchall()
            return [dict(log) for log in logs]

    def get_products_with_versions(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get products with their current version info

        Args:
            limit: Number of products to return
            offset: Offset for pagination

        Returns:
            List of product records with version info
        """
        with get_connection() as conn:
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT
                    p.product_id, p.title, p.product_number, p.publication_date,
                    p.update_date, p.product_type,
                    pv.version_number, pv.word_count, pv.ingested_at,
                    pv.blob_url
                FROM products p
                LEFT JOIN product_versions pv ON p.product_id = pv.product_id AND pv.is_current = true
                ORDER BY p.update_date DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))

            products = cursor.fetchall()
            return [dict(p) for p in products]
