"""
CRS Content Manager - Database operations for CRS content versions
"""
import json
import os
import boto3
from botocore.exceptions import ClientError
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from config.logging_config import get_logger
from database.postgres_config import get_connection
from psycopg2.extras import RealDictCursor

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

    def __init__(self):
        """
        Initialize CRS content manager

        Uses PostgreSQL connection from DATABASE_URL or CRS_DATABASE_URL environment variable
        """
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

    @contextmanager
    def get_db_connection(self):
        """Get PostgreSQL database connection"""
        with get_connection() as conn:
            yield conn

    def upsert_version(self, product_id: str, version_number: int,
                      html_content: str, text_content: str, structure_json: Dict,
                      content_hash: str, word_count: int, html_url: str) -> int:
        """
        Insert or update a product version

        Marks all previous versions as not current
        Uploads HTML content to R2 if enabled

        Args:
            product_id: CRS product ID
            version_number: Version number
            html_content: Cleaned HTML (uploaded to R2, not stored in DB)
            text_content: Plain text (used for FTS, not stored in DB)
            structure_json: Document structure
            content_hash: SHA256 hash
            word_count: Word count
            html_url: Source URL

        Returns:
            version_id of inserted/updated version
        """
        # Upload HTML content to R2 if enabled
        blob_url = self._upload_to_r2(product_id, version_number, html_content)
        if not blob_url:
            logger.warning(f"R2 upload failed for {product_id} v{version_number} - skipping ingestion")
            # If R2 is enabled but upload failed, don't proceed
            if self.r2_enabled:
                raise Exception(f"R2 upload failed for {product_id} v{version_number}")

        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if this version already exists
                cur.execute("""
                    SELECT version_id, content_hash
                    FROM product_versions
                    WHERE product_id = %s AND version_number = %s
                """, (product_id, version_number))
                existing = cur.fetchone()

                if existing:
                    # Check if content has changed
                    if existing['content_hash'] == content_hash:
                        logger.debug(f"Version {version_number} of {product_id} unchanged, skipping update")
                        return existing['version_id']

                    # Content changed, update it
                    cur.execute("""
                        UPDATE product_versions
                        SET structure_json = %s,
                            content_hash = %s,
                            word_count = %s,
                            html_url = %s,
                            blob_url = %s,
                            ingested_at = CURRENT_TIMESTAMP
                        WHERE version_id = %s
                    """, (json.dumps(structure_json), content_hash, word_count,
                         html_url, blob_url, existing['version_id']))

                    version_id = existing['version_id']
                    logger.info(f"✓ Updated version {version_number} of {product_id} (content changed)")

                else:
                    # Insert new version using RETURNING clause
                    cur.execute("""
                        INSERT INTO product_versions
                        (product_id, version_number, structure_json,
                         content_hash, word_count, html_url, blob_url, is_current)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE)
                        RETURNING version_id
                    """, (product_id, version_number, json.dumps(structure_json),
                         content_hash, word_count, html_url, blob_url))

                    version_id = cur.fetchone()['version_id']
                    logger.info(f"✓ Inserted version {version_number} of {product_id}")

                # Mark this version as current, all others as not current
                cur.execute("""
                    UPDATE product_versions
                    SET is_current = FALSE
                    WHERE product_id = %s AND version_id != %s
                """, (product_id, version_id))

                cur.execute("""
                    UPDATE product_versions
                    SET is_current = TRUE
                    WHERE version_id = %s
                """, (version_id,))

                # Update FTS index
                self._update_fts_index(cur, version_id, product_id, structure_json, text_content)

                return version_id

    def _update_fts_index(self, cur, version_id: int,
                         product_id: str, structure_json: Dict, text_content: str):
        """
        Update full-text search index for a version

        Args:
            cur: Database cursor
            version_id: Version ID
            product_id: Product ID
            structure_json: Document structure
            text_content: Plain text content
        """
        # Get product title from products table
        cur.execute("""
            SELECT title FROM products WHERE product_id = %s
        """, (product_id,))
        product = cur.fetchone()

        title = product['title'] if product else ''
        headings = ' '.join(structure_json.get('headings', []))

        # Delete existing FTS entry for this version
        cur.execute("""
            DELETE FROM product_content_fts WHERE version_id = %s
        """, (version_id,))

        # Insert new FTS entry
        cur.execute("""
            INSERT INTO product_content_fts (product_id, version_id, title, headings, text_content)
            VALUES (%s, %s, %s, %s, %s)
        """, (product_id, version_id, title, headings, text_content))

    def get_current_version(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current version of a product

        Args:
            product_id: Product ID

        Returns:
            Version record as dict or None
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM product_versions
                    WHERE product_id = %s AND is_current = TRUE
                """, (product_id,))
                version = cur.fetchone()

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
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM product_versions
                    WHERE product_id = %s AND version_number = %s
                """, (product_id, version_number))
                version = cur.fetchone()

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
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT version_id, product_id, version_number, word_count,
                           content_hash, ingested_at, is_current, html_url
                    FROM product_versions
                    WHERE product_id = %s
                    ORDER BY version_number DESC
                """, (product_id,))
                versions = cur.fetchall()

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
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = """
                    SELECT p.*
                    FROM products p
                    LEFT JOIN product_versions pv ON p.product_id = pv.product_id AND pv.is_current = TRUE
                    WHERE pv.version_id IS NULL
                    ORDER BY p.publication_date DESC
                """

                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query)
                products = cur.fetchall()
                return [dict(p) for p in products]

    def start_ingestion_log(self, run_type: str) -> int:
        """
        Create new ingestion log entry

        Args:
            run_type: Type of run ('backfill', 'update', 'manual')

        Returns:
            log_id
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO content_ingestion_logs
                    (run_type, started_at, status)
                    VALUES (%s, %s, 'running')
                    RETURNING log_id
                """, (run_type, datetime.now().isoformat()))

                return cur.fetchone()['log_id']

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
                set_parts.append(f"{key} = %s")
                values.append(json.dumps(value))
            else:
                set_parts.append(f"{key} = %s")
                values.append(value)

        if not set_parts:
            return

        values.append(log_id)
        query = f"""
            UPDATE content_ingestion_logs
            SET {', '.join(set_parts)}
            WHERE log_id = %s
        """

        with self.get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, values)

    def complete_ingestion_log(self, log_id: int, status: str = 'completed'):
        """
        Mark ingestion log as completed

        Args:
            log_id: Log ID
            status: Final status ('completed', 'failed', 'partial')
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Calculate duration
                cur.execute("""
                    SELECT started_at FROM content_ingestion_logs WHERE log_id = %s
                """, (log_id,))
                log = cur.fetchone()

                if log:
                    started = datetime.fromisoformat(log['started_at'])
                    duration = (datetime.now() - started).total_seconds()

                    cur.execute("""
                        UPDATE content_ingestion_logs
                        SET completed_at = %s,
                            status = %s,
                            total_duration_seconds = %s
                        WHERE log_id = %s
                    """, (datetime.now().isoformat(), status, duration, log_id))

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """
        Get overall content ingestion statistics

        Returns:
            Dictionary with stats
        """
        with self.get_db_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                stats = {}

                # Total products
                cur.execute("SELECT COUNT(*) as count FROM products")
                stats['total_products'] = cur.fetchone()['count']

                # Products with content
                cur.execute("""
                    SELECT COUNT(DISTINCT product_id) as count FROM product_versions
                """)
                stats['products_with_content'] = cur.fetchone()['count']

                # Current versions
                cur.execute("""
                    SELECT COUNT(*) as count FROM product_versions WHERE is_current = TRUE
                """)
                stats['current_versions'] = cur.fetchone()['count']

                # Total versions
                cur.execute("""
                    SELECT COUNT(*) as count FROM product_versions
                """)
                stats['total_versions'] = cur.fetchone()['count']

                # Total storage (now in R2, show count of blob URLs instead)
                cur.execute("""
                    SELECT COUNT(*) as blob_count
                    FROM product_versions
                    WHERE blob_url IS NOT NULL
                """)
                blob_count = cur.fetchone()
                stats['content_in_r2'] = blob_count['blob_count'] or 0

                # Average word count
                cur.execute("""
                    SELECT AVG(word_count) as avg_words
                    FROM product_versions
                    WHERE is_current = TRUE
                """)
                avg_words = cur.fetchone()
                stats['avg_word_count'] = round(avg_words['avg_words'] or 0, 0)

                # Last ingestion
                cur.execute("""
                    SELECT started_at, status, content_fetched
                    FROM content_ingestion_logs
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
                last_log = cur.fetchone()

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
