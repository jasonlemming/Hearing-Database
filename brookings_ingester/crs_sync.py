"""
CRS to Policy Library Sync Module

Synchronizes CRS products from CRS database to Policy Library database.
Handles one-way sync: CRS → Policy Library
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.exc import IntegrityError

from brookings_ingester.models.database import session_scope, init_database
from brookings_ingester.models.document import (
    Source, Document, DocumentVersion, Author,
    DocumentAuthor, Subject, DocumentSubject
)
from config.logging_config import get_logger

logger = get_logger(__name__)


class CRSPolicyLibrarySync:
    """
    Syncs CRS products to Policy Library database

    Features:
    - Read-only access to CRS database
    - Idempotent sync (safe to run multiple times)
    - Handles authors and subjects
    - Preserves all CRS metadata
    """

    def __init__(self, crs_db_url: str = None, policy_db_url: str = None):
        """
        Initialize CRS sync

        Args:
            crs_db_url: CRS database URL (defaults to CRS_DATABASE_URL env var)
            policy_db_url: Policy library database URL (defaults to BROOKINGS_DATABASE_URL)
        """
        self.crs_db_url = crs_db_url or os.getenv('CRS_DATABASE_URL') or os.getenv('DATABASE_URL')
        if not self.crs_db_url:
            raise ValueError("CRS database URL not configured")

        # Initialize policy library database
        policy_url = policy_db_url or os.getenv('BROOKINGS_DATABASE_URL')
        if policy_url:
            init_database(policy_url)
        else:
            init_database()  # Use default from config

        logger.info(f"CRS sync initialized (CRS DB: {self.crs_db_url[:30]}...)")

    def get_crs_connection(self):
        """Get read-only connection to CRS database"""
        return psycopg2.connect(
            self.crs_db_url,
            cursor_factory=RealDictCursor,
            options='-c default_transaction_read_only=on'  # Read-only mode
        )

    def get_or_create_crs_source(self, session) -> Source:
        """
        Get or create CRS source in policy library

        Args:
            session: SQLAlchemy session

        Returns:
            Source object
        """
        source = session.query(Source).filter_by(source_code='CRS').first()
        if not source:
            source = Source(
                source_code='CRS',
                name='Congressional Research Service',
                short_name='CRS',
                description='Public policy research for U.S. Congress',
                url='https://www.congress.gov',
                is_active=True
            )
            session.add(source)
            session.flush()
            logger.info("Created CRS source in policy library")
        return source

    def get_or_create_author(self, session, author_name: str) -> Author:
        """
        Get or create author by name

        Args:
            session: SQLAlchemy session
            author_name: Full author name

        Returns:
            Author object
        """
        # Parse first/last name (simple split on last space)
        name_parts = author_name.strip().rsplit(' ', 1)
        if len(name_parts) == 2:
            first_name, last_name = name_parts
        else:
            first_name = author_name
            last_name = ''

        # Check if author exists
        author = session.query(Author).filter_by(full_name=author_name).first()
        if not author:
            author = Author(
                full_name=author_name,
                first_name=first_name,
                last_name=last_name
            )
            session.add(author)
            session.flush()
            logger.debug(f"Created author: {author_name}")
        return author

    def get_or_create_subject(self, session, subject_name: str) -> Subject:
        """
        Get or create subject/topic

        Args:
            session: SQLAlchemy session
            subject_name: Subject name

        Returns:
            Subject object
        """
        subject = session.query(Subject).filter_by(name=subject_name).first()
        if not subject:
            subject = Subject(
                name=subject_name,
                source_vocabulary='CRS'
            )
            session.add(subject)
            session.flush()
            logger.debug(f"Created subject: {subject_name}")
        return subject

    def fetch_crs_products(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch all CRS products from CRS database

        Args:
            limit: Optional limit on number of products

        Returns:
            List of product dictionaries
        """
        with self.get_crs_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        product_id,
                        title,
                        product_type,
                        status,
                        publication_date,
                        summary,
                        authors,
                        topics,
                        url_html,
                        url_pdf,
                        raw_json
                    FROM products
                    WHERE status = 'Active'
                    ORDER BY publication_date DESC
                """
                if limit:
                    query += f" LIMIT {limit}"

                cur.execute(query)
                products = cur.fetchall()
                logger.info(f"Fetched {len(products)} CRS products from database")
                return [dict(p) for p in products]

    def sync_product_to_policy_library(
        self,
        session,
        source: Source,
        product: Dict[str, Any]
    ) -> Optional[Document]:
        """
        Sync single CRS product to policy library

        Args:
            session: SQLAlchemy session
            source: CRS Source object
            product: CRS product dictionary

        Returns:
            Document object or None if skipped
        """
        product_id = product['product_id']

        # Check if document already exists
        existing_doc = session.query(Document).filter_by(
            source_id=source.source_id,
            document_identifier=product_id
        ).first()

        # Prepare metadata JSON with CRS-specific fields
        metadata = {
            'product_type': product.get('product_type'),
            'crs_product_id': product_id,
            'crs_status': product.get('status'),
            'url_html': product.get('url_html'),
            'url_pdf': product.get('url_pdf'),
            'raw_json': product.get('raw_json')
        }

        # Create or update document
        if existing_doc:
            # Check if content has changed (compare key fields)
            changed = (
                existing_doc.title != product['title'] or
                existing_doc.summary != product.get('summary') or
                existing_doc.publication_date != product.get('publication_date')
            )

            if not changed:
                logger.debug(f"CRS product {product_id} unchanged, skipping")
                return None

            # Update existing document
            existing_doc.title = product['title']
            existing_doc.document_type = product.get('product_type', 'Report')
            existing_doc.status = 'Active' if product.get('status') == 'Active' else 'Inactive'
            existing_doc.publication_date = product.get('publication_date')
            existing_doc.summary = product.get('summary')
            existing_doc.url = product.get('url_html')
            existing_doc.pdf_url = product.get('url_pdf')
            existing_doc.metadata_json = json.dumps(metadata)
            existing_doc.updated_at = datetime.now()

            document = existing_doc
            action = "updated"
        else:
            # Create new document
            document = Document(
                source_id=source.source_id,
                document_identifier=product_id,
                title=product['title'],
                document_type=product.get('product_type', 'Report'),
                status='Active' if product.get('status') == 'Active' else 'Inactive',
                publication_date=product.get('publication_date'),
                summary=product.get('summary'),
                url=product.get('url_html'),
                pdf_url=product.get('url_pdf'),
                metadata_json=json.dumps(metadata)
            )
            session.add(document)
            session.flush()
            action = "created"

        # Handle authors
        if product.get('authors'):
            # Remove existing authors for this document
            session.query(DocumentAuthor).filter_by(
                document_id=document.document_id
            ).delete()

            # Parse authors JSONB array
            authors_data = product['authors']
            if isinstance(authors_data, str):
                authors_data = json.loads(authors_data)

            for idx, author_name in enumerate(authors_data):
                if author_name and author_name.strip():
                    author = self.get_or_create_author(session, author_name.strip())
                    doc_author = DocumentAuthor(
                        document_id=document.document_id,
                        author_id=author.author_id,
                        author_order=idx + 1
                    )
                    session.add(doc_author)

        # Handle topics/subjects
        if product.get('topics'):
            # Remove existing subjects for this document
            session.query(DocumentSubject).filter_by(
                document_id=document.document_id
            ).delete()

            # Parse topics JSONB array
            topics_data = product['topics']
            if isinstance(topics_data, str):
                topics_data = json.loads(topics_data)

            for topic_name in topics_data:
                if topic_name and topic_name.strip():
                    subject = self.get_or_create_subject(session, topic_name.strip())
                    doc_subject = DocumentSubject(
                        document_id=document.document_id,
                        subject_id=subject.subject_id
                    )
                    session.add(doc_subject)

        logger.info(f"✓ {action.capitalize()} CRS product {product_id} in policy library")
        return document

    def sync_all_products(self, limit: Optional[int] = None) -> Dict[str, int]:
        """
        Sync all CRS products to policy library

        Args:
            limit: Optional limit on number of products to sync

        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'products_checked': 0,
            'documents_created': 0,
            'documents_updated': 0,
            'documents_skipped': 0,
            'errors': 0
        }

        logger.info("Starting CRS to Policy Library sync...")

        try:
            # Fetch CRS products
            products = self.fetch_crs_products(limit=limit)
            stats['products_checked'] = len(products)

            # Sync each product
            with session_scope() as session:
                source = self.get_or_create_crs_source(session)

                for product in products:
                    try:
                        result = self.sync_product_to_policy_library(session, source, product)
                        if result:
                            # Check if it was created or updated
                            if session.is_modified(result):
                                stats['documents_updated'] += 1
                            else:
                                stats['documents_created'] += 1
                        else:
                            stats['documents_skipped'] += 1
                    except Exception as e:
                        stats['errors'] += 1
                        logger.error(f"Error syncing product {product.get('product_id')}: {e}")
                        # Continue with next product

            logger.info(f"✓ CRS sync completed: {stats['documents_created']} created, "
                       f"{stats['documents_updated']} updated, {stats['documents_skipped']} skipped")

        except Exception as e:
            logger.error(f"CRS sync failed: {e}")
            stats['errors'] += 1

        return stats

    def sync_single_product(self, product_id: str) -> bool:
        """
        Sync a single CRS product by ID

        Args:
            product_id: CRS product ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_crs_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            product_id, title, product_type, status,
                            publication_date, summary, authors, topics,
                            url_html, url_pdf, raw_json
                        FROM products
                        WHERE product_id = %s
                    """, (product_id,))

                    product = cur.fetchone()
                    if not product:
                        logger.warning(f"CRS product {product_id} not found")
                        return False

            with session_scope() as session:
                source = self.get_or_create_crs_source(session)
                self.sync_product_to_policy_library(session, source, dict(product))

            logger.info(f"✓ Synced CRS product {product_id} to policy library")
            return True

        except Exception as e:
            logger.error(f"Failed to sync CRS product {product_id}: {e}")
            return False


def sync_crs_to_policy_library(limit: Optional[int] = None) -> Dict[str, int]:
    """
    Convenience function to sync CRS products to policy library

    Args:
        limit: Optional limit on number of products

    Returns:
        Sync statistics dictionary
    """
    sync = CRSPolicyLibrarySync()
    return sync.sync_all_products(limit=limit)


if __name__ == '__main__':
    # Run sync when executed directly
    import sys

    limit = None
    if len(sys.argv) > 1:
        limit = int(sys.argv[1])

    print(f"Syncing CRS products to Policy Library{f' (limit: {limit})' if limit else ''}...")
    stats = sync_crs_to_policy_library(limit=limit)
    print(f"\nSync Results:")
    print(f"  Products checked: {stats['products_checked']}")
    print(f"  Documents created: {stats['documents_created']}")
    print(f"  Documents updated: {stats['documents_updated']}")
    print(f"  Documents skipped: {stats['documents_skipped']}")
    print(f"  Errors: {stats['errors']}")
