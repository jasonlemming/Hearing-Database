"""
PDF text extraction utilities
"""
import PyPDF2
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import hashlib

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    Extract text and metadata from PDF files

    Uses PyPDF2 for extraction. For scanned PDFs (images), OCR would be needed
    but is not implemented here (future enhancement with pytesseract/ocrmypdf).
    """

    def __init__(self):
        """Initialize PDF extractor"""
        self.stats = {
            'files_processed': 0,
            'total_pages': 0,
            'extraction_errors': 0
        }

    def extract_from_file(self, pdf_path: Path) -> Optional[Dict[str, Any]]:
        """
        Extract text and metadata from PDF file

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with extracted content:
            {
                'text': str,           # Extracted text
                'page_count': int,
                'word_count': int,
                'metadata': dict,      # PDF metadata (title, author, etc.)
                'checksum': str,       # SHA256 of file
                'file_size': int       # Bytes
            }
            Returns None if extraction fails
        """
        try:
            if not pdf_path.exists():
                logger.error(f"PDF file not found: {pdf_path}")
                return None

            # Calculate file checksum
            checksum = self._calculate_checksum(pdf_path)
            file_size = pdf_path.stat().st_size

            # Open PDF
            with open(pdf_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)

                # Get page count
                page_count = len(reader.pages)

                # Extract text from all pages
                text_parts = []
                for page_num in range(page_count):
                    try:
                        page = reader.pages[page_num]
                        text = page.extract_text()
                        if text:
                            text_parts.append(text)
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num + 1} from {pdf_path.name}: {e}")

                # Combine text
                full_text = '\n\n'.join(text_parts)
                word_count = len(full_text.split())

                # Extract metadata
                metadata = {}
                if reader.metadata:
                    for key, value in reader.metadata.items():
                        # Remove leading '/' from metadata keys
                        clean_key = key.lstrip('/')
                        metadata[clean_key] = str(value)

                self.stats['files_processed'] += 1
                self.stats['total_pages'] += page_count

                logger.info(f"✓ Extracted {page_count} pages, {word_count:,} words from {pdf_path.name}")

                return {
                    'text': full_text,
                    'page_count': page_count,
                    'word_count': word_count,
                    'metadata': metadata,
                    'checksum': checksum,
                    'file_size': file_size
                }

        except PyPDF2.errors.PdfReadError as e:
            logger.error(f"PDF read error for {pdf_path.name}: {e}")
            self.stats['extraction_errors'] += 1
            return None

        except Exception as e:
            logger.error(f"Unexpected error extracting PDF {pdf_path.name}: {e}")
            self.stats['extraction_errors'] += 1
            return None

    def extract_from_bytes(self, pdf_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Extract text from PDF bytes (in-memory)

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Same format as extract_from_file()
        """
        try:
            from io import BytesIO

            # Calculate checksum
            checksum = hashlib.sha256(pdf_bytes).hexdigest()
            file_size = len(pdf_bytes)

            # Open PDF from bytes
            pdf_file = BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)

            # Get page count
            page_count = len(reader.pages)

            # Extract text
            text_parts = []
            for page_num in range(page_count):
                try:
                    page = reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                except Exception as e:
                    logger.warning(f"Error extracting page {page_num + 1}: {e}")

            full_text = '\n\n'.join(text_parts)
            word_count = len(full_text.split())

            # Extract metadata
            metadata = {}
            if reader.metadata:
                for key, value in reader.metadata.items():
                    clean_key = key.lstrip('/')
                    metadata[clean_key] = str(value)

            self.stats['files_processed'] += 1
            self.stats['total_pages'] += page_count

            return {
                'text': full_text,
                'page_count': page_count,
                'word_count': word_count,
                'metadata': metadata,
                'checksum': checksum,
                'file_size': file_size
            }

        except Exception as e:
            logger.error(f"Error extracting PDF from bytes: {e}")
            self.stats['extraction_errors'] += 1
            return None

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of file

        Args:
            file_path: Path to file

        Returns:
            SHA256 hex digest
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            # Read in chunks for large files
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def is_scanned_pdf(self, pdf_path: Path, text_threshold: int = 100) -> bool:
        """
        Heuristic check if PDF is scanned (image-based)

        Args:
            pdf_path: Path to PDF
            text_threshold: Minimum characters to consider text-based

        Returns:
            True if likely scanned (needs OCR)
        """
        result = self.extract_from_file(pdf_path)
        if not result:
            return True  # Assume scanned if can't extract

        # If very little text extracted, likely scanned
        text_length = len(result['text'].strip())
        return text_length < text_threshold

    def get_stats(self) -> Dict[str, int]:
        """Get extraction statistics"""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            'files_processed': 0,
            'total_pages': 0,
            'extraction_errors': 0
        }
