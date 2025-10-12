"""
Base Ingester - Abstract class for document ingestion

Defines the common pattern for all ingesters (CRS, Brookings, GAO, etc.)
"""
from abc import ABC, abstractmethod
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests
from tqdm import tqdm

from brookings_ingester.config import config
from brookings_ingester.models import get_session, Source, Document, IngestionLog, IngestionError
from brookings_ingester.storage import FileManager, PDFExtractor

logger = logging.getLogger(__name__)


class BaseIngester(ABC):
    """
    Abstract base class for document ingesters

    Defines the ingestion pipeline:
    1. discover() - Find documents to ingest
    2. fetch() - Download content (HTML, PDF)
    3. parse() - Extract metadata and text
    4. store() - Save to database and files
    """

    def __init__(self, source_code: str, rate_limit_delay: float = None):
        """
        Initialize ingester

        Args:
            source_code: Source identifier ('CRS', 'BROOKINGS', 'GAO')
            rate_limit_delay: Delay between requests in seconds
        """
        self.source_code = source_code
        self.rate_limit_delay = rate_limit_delay or config.RATE_LIMIT_DELAY
        self.last_request_time = 0

        # Initialize components
        self.file_manager = FileManager()
        self.pdf_extractor = PDFExtractor()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': config.USER_AGENT
        })

        # Get source from database
        db_session = get_session()
        self.source = db_session.query(Source).filter_by(source_code=source_code).first()
        if not self.source:
            raise ValueError(f"Source '{source_code}' not found in database. Please seed sources table.")
        db_session.close()

        # Statistics
        self.stats = {
            'documents_checked': 0,
            'documents_fetched': 0,
            'documents_updated': 0,
            'documents_skipped': 0,
            'errors_count': 0,
            'total_size_bytes': 0,
            'total_time_ms': 0,
            'errors': []
        }

    @abstractmethod
    def discover(self, limit: int = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Discover documents to ingest

        Args:
            limit: Maximum number of documents to discover
            **kwargs: Source-specific parameters

        Returns:
            List of document metadata dictionaries with at least:
            {
                'document_identifier': str,
                'url': str,
                'title': str (optional),
                'publication_date': str (optional)
            }
        """
        pass

    @abstractmethod
    def fetch(self, document_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch document content (HTML, PDF, etc.)

        Args:
            document_meta: Document metadata from discover()

        Returns:
            Dictionary with fetched content:
            {
                'html_content': str,
                'pdf_bytes': bytes (optional),
                'pdf_url': str (optional)
            }
            Returns None if fetch fails
        """
        pass

    @abstractmethod
    def parse(self, document_meta: Dict[str, Any], fetched_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse document content and extract metadata

        Args:
            document_meta: Metadata from discover()
            fetched_content: Content from fetch()

        Returns:
            Complete document data:
            {
                'document_identifier': str,
                'title': str,
                'document_type': str,
                'publication_date': str,
                'summary': str,
                'full_text': str,
                'url': str,
                'pdf_url': str,
                'authors': List[str],
                'subjects': List[str],
                'metadata': Dict (source-specific),
                'html_content': str,
                'text_content': str,
                'structure': Dict,
                'page_count': int,
                'word_count': int
            }
            Returns None if parsing fails
        """
        pass

    def _parse_date_string(self, date_str: Optional[str]):
        """Convert date string (YYYY-MM-DD) to Python date object"""
        if not date_str:
            return None
        try:
            from datetime import date as date_type
            if isinstance(date_str, date_type):
                return date_str
            # Parse YYYY-MM-DD format
            parts = date_str.split('-')
            if len(parts) == 3:
                return date_type(int(parts[0]), int(parts[1]), int(parts[2]))
        except:
            return None
        return None

    def store(self, parsed_data: Dict[str, Any]) -> Optional[int]:
        """
        Store document in database and save files

        Args:
            parsed_data: Parsed document data

        Returns:
            document_id if successful, None otherwise
        """
        try:
            db_session = get_session()

            # Check if document already exists
            existing_doc = db_session.query(Document).filter_by(
                source_id=self.source.source_id,
                document_identifier=parsed_data['document_identifier']
            ).first()

            # Calculate checksum for deduplication
            checksum = self._calculate_checksum(parsed_data.get('full_text', ''))

            # Convert publication date string to date object
            pub_date = self._parse_date_string(parsed_data.get('publication_date'))

            if existing_doc:
                # Check if content has changed
                if existing_doc.checksum == checksum:
                    logger.debug(f"Document {parsed_data['document_identifier']} unchanged, skipping")
                    db_session.close()
                    self.stats['documents_skipped'] += 1
                    return existing_doc.document_id

                # Update existing document
                existing_doc.title = parsed_data.get('title')
                existing_doc.document_type = parsed_data.get('document_type')
                existing_doc.publication_date = pub_date
                existing_doc.summary = parsed_data.get('summary')
                existing_doc.full_text = parsed_data.get('full_text')
                existing_doc.url = parsed_data.get('url')
                existing_doc.pdf_url = parsed_data.get('pdf_url')
                existing_doc.page_count = parsed_data.get('page_count')
                existing_doc.word_count = parsed_data.get('word_count')
                existing_doc.checksum = checksum
                existing_doc.metadata = str(parsed_data.get('metadata', {}))
                existing_doc.updated_at = datetime.utcnow()

                document = existing_doc
                self.stats['documents_updated'] += 1
                logger.info(f"✓ Updated document: {parsed_data['document_identifier']}")

            else:
                # Create new document
                from brookings_ingester.models.document import Document as DocumentModel
                document = DocumentModel(
                    source_id=self.source.source_id,
                    document_identifier=parsed_data['document_identifier'],
                    title=parsed_data.get('title'),
                    document_type=parsed_data.get('document_type'),
                    publication_date=pub_date,
                    summary=parsed_data.get('summary'),
                    full_text=parsed_data.get('full_text'),
                    url=parsed_data.get('url'),
                    pdf_url=parsed_data.get('pdf_url'),
                    page_count=parsed_data.get('page_count'),
                    word_count=parsed_data.get('word_count'),
                    checksum=checksum,
                    metadata=str(parsed_data.get('metadata', {}))
                )
                db_session.add(document)
                db_session.flush()  # Get document_id

                self.stats['documents_fetched'] += 1
                logger.info(f"✓ Created document: {parsed_data['document_identifier']}")

            # Save authors and subjects
            from brookings_ingester.models.document import Author, DocumentAuthor, Subject, DocumentSubject

            # Clear existing associations if updating
            if existing_doc:
                db_session.query(DocumentAuthor).filter_by(document_id=document.document_id).delete()
                db_session.query(DocumentSubject).filter_by(document_id=document.document_id).delete()

            # Add authors
            for author_name in parsed_data.get('authors', []):
                if not author_name or not author_name.strip():
                    continue

                # Find or create author
                author = db_session.query(Author).filter_by(full_name=author_name.strip()).first()
                if not author:
                    author = Author(full_name=author_name.strip())
                    db_session.add(author)
                    db_session.flush()  # Get author_id

                # Create association
                doc_author = DocumentAuthor(
                    document_id=document.document_id,
                    author_id=author.author_id
                )
                db_session.add(doc_author)

            # Add subjects
            for subject_name in parsed_data.get('subjects', []):
                if not subject_name or not subject_name.strip():
                    continue

                # Find or create subject
                subject = db_session.query(Subject).filter_by(name=subject_name.strip()).first()
                if not subject:
                    subject = Subject(name=subject_name.strip())
                    db_session.add(subject)
                    db_session.flush()  # Get subject_id

                # Create association
                doc_subject = DocumentSubject(
                    document_id=document.document_id,
                    subject_id=subject.subject_id
                )
                db_session.add(doc_subject)

            # Save files if available
            if parsed_data.get('pdf_bytes'):
                pdf_info = self.file_manager.save_pdf(
                    parsed_data['document_identifier'],
                    parsed_data['pdf_bytes']
                )
                self.stats['total_size_bytes'] += pdf_info['file_size']

            if parsed_data.get('text_content'):
                self.file_manager.save_text(
                    parsed_data['document_identifier'],
                    parsed_data['text_content']
                )

            if parsed_data.get('html_content'):
                self.file_manager.save_html(
                    parsed_data['document_identifier'],
                    parsed_data['html_content']
                )

            db_session.commit()
            document_id = document.document_id
            db_session.close()

            return document_id

        except Exception as e:
            logger.error(f"Error storing document {parsed_data.get('document_identifier')}: {e}")
            if db_session:
                db_session.rollback()
                db_session.close()
            self.stats['errors_count'] += 1
            return None

    def run_ingestion(self, limit: int = None, skip_existing: bool = True,
                     run_type: str = 'manual', **kwargs) -> Dict[str, Any]:
        """
        Run full ingestion pipeline

        Args:
            limit: Maximum number of documents to process
            skip_existing: Skip documents that already exist
            run_type: 'backfill', 'update', or 'manual'
            **kwargs: Source-specific parameters

        Returns:
            Dictionary with ingestion results
        """
        # Create ingestion log
        db_session = get_session()
        log = IngestionLog(
            source_id=self.source.source_id,
            run_type=run_type,
            started_at=datetime.utcnow(),
            status='running'
        )
        db_session.add(log)
        db_session.commit()
        log_id = log.log_id
        db_session.close()

        start_time = time.time()

        try:
            # Step 1: Discover documents
            logger.info(f"Discovering {self.source_code} documents...")
            documents = self.discover(limit=limit, **kwargs)
            logger.info(f"Found {len(documents)} documents")

            self.stats['documents_checked'] = len(documents)

            # Step 2: Process each document
            with tqdm(total=len(documents), desc=f"Ingesting {self.source_code}") as pbar:
                for doc_meta in documents:
                    try:
                        # Check if document exists and should skip
                        if skip_existing and self.document_exists(doc_meta['document_identifier']):
                            logger.debug(f"Skipping existing: {doc_meta['document_identifier']}")
                            self.stats['documents_skipped'] += 1
                            pbar.update(1)
                            continue

                        # Fetch content
                        fetched = self.fetch(doc_meta)
                        if not fetched:
                            self._log_error(log_id, doc_meta, 'fetch_error', 'Failed to fetch content')
                            pbar.update(1)
                            continue

                        # Parse content
                        parsed = self.parse(doc_meta, fetched)
                        if not parsed:
                            self._log_error(log_id, doc_meta, 'parse_error', 'Failed to parse content')
                            pbar.update(1)
                            continue

                        # Store document
                        document_id = self.store(parsed)
                        if not document_id:
                            self._log_error(log_id, doc_meta, 'storage_error', 'Failed to store document')

                        pbar.update(1)

                    except Exception as e:
                        logger.error(f"Error processing {doc_meta.get('document_identifier')}: {e}")
                        self._log_error(log_id, doc_meta, 'unexpected_error', str(e))
                        pbar.update(1)

            # Calculate metrics
            duration = time.time() - start_time
            self.stats['total_time_ms'] = duration * 1000

            # Update ingestion log
            db_session = get_session()
            log = db_session.query(IngestionLog).get(log_id)
            log.completed_at = datetime.utcnow()
            log.documents_checked = self.stats['documents_checked']
            log.documents_fetched = self.stats['documents_fetched']
            log.documents_updated = self.stats['documents_updated']
            log.documents_skipped = self.stats['documents_skipped']
            log.errors_count = self.stats['errors_count']
            log.total_size_bytes = self.stats['total_size_bytes']
            log.total_duration_seconds = duration

            # Determine final status
            if self.stats['errors_count'] == 0:
                log.status = 'completed'
            elif self.stats['documents_fetched'] > 0 or self.stats['documents_updated'] > 0:
                log.status = 'partial'
            else:
                log.status = 'failed'

            db_session.commit()
            db_session.close()

            # Print summary
            self._print_summary(duration)

            return {
                'success': log.status in ['completed', 'partial'],
                'log_id': log_id,
                'stats': self.stats.copy()
            }

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")

            # Mark log as failed
            db_session = get_session()
            log = db_session.query(IngestionLog).get(log_id)
            log.completed_at = datetime.utcnow()
            log.status = 'failed'
            log.total_duration_seconds = time.time() - start_time
            db_session.commit()
            db_session.close()

            return {
                'success': False,
                'log_id': log_id,
                'error': str(e),
                'stats': self.stats.copy()
            }

    def document_exists(self, document_identifier: str) -> bool:
        """Check if document already exists in database"""
        db_session = get_session()
        exists = db_session.query(Document).filter_by(
            source_id=self.source.source_id,
            document_identifier=document_identifier
        ).first() is not None
        db_session.close()
        return exists

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def _calculate_checksum(self, text: str) -> str:
        """Calculate SHA256 checksum of text"""
        import hashlib
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def _log_error(self, log_id: int, doc_meta: Dict, error_type: str, error_message: str):
        """Log error to database"""
        try:
            db_session = get_session()
            error = IngestionError(
                log_id=log_id,
                document_identifier=doc_meta.get('document_identifier'),
                url=doc_meta.get('url'),
                error_type=error_type,
                error_message=error_message
            )
            db_session.add(error)
            db_session.commit()
            db_session.close()

            self.stats['errors_count'] += 1
            self.stats['errors'].append({
                'document': doc_meta.get('document_identifier'),
                'type': error_type,
                'message': error_message
            })

        except Exception as e:
            logger.error(f"Failed to log error: {e}")

    def _print_summary(self, duration: float):
        """Print ingestion summary"""
        logger.info("\n" + "=" * 70)
        logger.info(f"{self.source_code} Ingestion Complete!")
        logger.info(f"  Checked: {self.stats['documents_checked']}")
        logger.info(f"  Fetched: {self.stats['documents_fetched']}")
        logger.info(f"  Updated: {self.stats['documents_updated']}")
        logger.info(f"  Skipped: {self.stats['documents_skipped']}")
        logger.info(f"  Errors: {self.stats['errors_count']}")
        logger.info(f"  Duration: {duration:.1f}s")
        if self.stats['total_size_bytes'] > 0:
            logger.info(f"  Total size: {self.stats['total_size_bytes'] / 1024 / 1024:.1f} MB")
        logger.info("=" * 70)

    def get_stats(self) -> Dict[str, Any]:
        """Get ingestion statistics"""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics"""
        self.stats = {
            'documents_checked': 0,
            'documents_fetched': 0,
            'documents_updated': 0,
            'documents_skipped': 0,
            'errors_count': 0,
            'total_size_bytes': 0,
            'total_time_ms': 0,
            'errors': []
        }
