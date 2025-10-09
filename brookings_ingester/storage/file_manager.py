"""
File storage management utilities
"""
import hashlib
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class FileManager:
    """
    Manages file storage for documents (PDFs, HTML, text)

    File naming convention:
    - CRS: {product_id}.{ext}
    - Brookings: {slug}.{ext}
    - GAO: {product_number}.{ext}

    Directory structure:
    data/
    ├── pdfs/brookings/
    ├── text/brookings/
    └── html/brookings/
    """

    def __init__(self, base_path: Path = None):
        """
        Initialize file manager

        Args:
            base_path: Base storage path (defaults to config.STORAGE_PATH)
        """
        self.base_path = base_path or config.STORAGE_PATH
        self.pdf_dir = self.base_path / 'pdfs' / 'brookings'
        self.text_dir = self.base_path / 'text' / 'brookings'
        self.html_dir = self.base_path / 'html' / 'brookings'

        # Ensure directories exist
        self._ensure_directories()

        # Statistics
        self.stats = {
            'files_saved': 0,
            'bytes_saved': 0,
            'files_deleted': 0
        }

    def _ensure_directories(self):
        """Create storage directories if they don't exist"""
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.text_dir.mkdir(parents=True, exist_ok=True)
        self.html_dir.mkdir(parents=True, exist_ok=True)

    def save_pdf(self, document_id: str, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Save PDF file

        Args:
            document_id: Document identifier (used for filename)
            pdf_bytes: PDF file content as bytes

        Returns:
            Dictionary with:
            {
                'file_path': str,      # Relative path
                'file_size': int,      # Bytes
                'checksum': str        # SHA256
            }
        """
        filename = f"{self._sanitize_filename(document_id)}.pdf"
        file_path = self.pdf_dir / filename
        relative_path = file_path.relative_to(self.base_path.parent)

        # Calculate checksum
        checksum = hashlib.sha256(pdf_bytes).hexdigest()
        file_size = len(pdf_bytes)

        # Save file
        with open(file_path, 'wb') as f:
            f.write(pdf_bytes)

        self.stats['files_saved'] += 1
        self.stats['bytes_saved'] += file_size

        logger.info(f"✓ Saved PDF: {relative_path} ({file_size:,} bytes)")

        return {
            'file_path': str(relative_path),
            'file_size': file_size,
            'checksum': checksum
        }

    def save_text(self, document_id: str, text_content: str) -> Dict[str, Any]:
        """
        Save extracted text file

        Args:
            document_id: Document identifier
            text_content: Plain text content

        Returns:
            Same format as save_pdf()
        """
        filename = f"{self._sanitize_filename(document_id)}.txt"
        file_path = self.text_dir / filename
        relative_path = file_path.relative_to(self.base_path.parent)

        # Encode to bytes for checksum and size
        text_bytes = text_content.encode('utf-8')
        checksum = hashlib.sha256(text_bytes).hexdigest()
        file_size = len(text_bytes)

        # Save file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        self.stats['files_saved'] += 1
        self.stats['bytes_saved'] += file_size

        logger.debug(f"Saved text: {relative_path}")

        return {
            'file_path': str(relative_path),
            'file_size': file_size,
            'checksum': checksum
        }

    def save_html(self, document_id: str, html_content: str) -> Dict[str, Any]:
        """
        Save HTML content

        Args:
            document_id: Document identifier
            html_content: HTML content

        Returns:
            Same format as save_pdf()
        """
        filename = f"{self._sanitize_filename(document_id)}.html"
        file_path = self.html_dir / filename
        relative_path = file_path.relative_to(self.base_path.parent)

        html_bytes = html_content.encode('utf-8')
        checksum = hashlib.sha256(html_bytes).hexdigest()
        file_size = len(html_bytes)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.stats['files_saved'] += 1
        self.stats['bytes_saved'] += file_size

        logger.debug(f"Saved HTML: {relative_path}")

        return {
            'file_path': str(relative_path),
            'file_size': file_size,
            'checksum': checksum
        }

    def file_exists(self, file_type: str, document_id: str) -> bool:
        """
        Check if file exists

        Args:
            file_type: 'PDF', 'TEXT', or 'HTML'
            document_id: Document identifier

        Returns:
            True if file exists
        """
        directory_map = {
            'PDF': self.pdf_dir,
            'TEXT': self.text_dir,
            'HTML': self.html_dir
        }

        extension_map = {
            'PDF': '.pdf',
            'TEXT': '.txt',
            'HTML': '.html'
        }

        directory = directory_map.get(file_type.upper())
        extension = extension_map.get(file_type.upper())

        if not directory or not extension:
            return False

        filename = f"{self._sanitize_filename(document_id)}{extension}"
        file_path = directory / filename

        return file_path.exists()

    def get_file_path(self, file_type: str, document_id: str) -> Optional[Path]:
        """
        Get absolute path to file

        Args:
            file_type: 'PDF', 'TEXT', or 'HTML'
            document_id: Document identifier

        Returns:
            Path object or None if file doesn't exist
        """
        directory_map = {
            'PDF': self.pdf_dir,
            'TEXT': self.text_dir,
            'HTML': self.html_dir
        }

        extension_map = {
            'PDF': '.pdf',
            'TEXT': '.txt',
            'HTML': '.html'
        }

        directory = directory_map.get(file_type.upper())
        extension = extension_map.get(file_type.upper())

        if not directory or not extension:
            return None

        filename = f"{self._sanitize_filename(document_id)}{extension}"
        file_path = directory / filename

        return file_path if file_path.exists() else None

    def delete_file(self, file_type: str, document_id: str) -> bool:
        """
        Delete file

        Args:
            file_type: 'PDF', 'TEXT', or 'HTML'
            document_id: Document identifier

        Returns:
            True if file was deleted
        """
        file_path = self.get_file_path(file_type, document_id)

        if file_path and file_path.exists():
            file_path.unlink()
            self.stats['files_deleted'] += 1
            logger.info(f"Deleted file: {file_path}")
            return True

        return False

    def copy_file_from_url(self, source_path: str, document_id: str, file_type: str) -> Dict[str, Any]:
        """
        Copy file from local path (for testing)

        Args:
            source_path: Source file path
            document_id: Document identifier
            file_type: 'PDF', 'TEXT', or 'HTML'

        Returns:
            Same format as save_pdf()
        """
        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Read file
        with open(source, 'rb') as f:
            content_bytes = f.read()

        # Save based on file type
        if file_type.upper() == 'PDF':
            return self.save_pdf(document_id, content_bytes)
        elif file_type.upper() == 'TEXT':
            content_str = content_bytes.decode('utf-8')
            return self.save_text(document_id, content_str)
        elif file_type.upper() == 'HTML':
            content_str = content_bytes.decode('utf-8')
            return self.save_html(document_id, content_str)
        else:
            raise ValueError(f"Unknown file type: {file_type}")

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to be safe for all file systems

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Replace problematic characters with hyphens
        safe_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.')
        sanitized = ''.join(c if c in safe_chars else '-' for c in filename)

        # Remove leading/trailing hyphens and dots
        sanitized = sanitized.strip('-.')

        # Collapse multiple hyphens
        while '--' in sanitized:
            sanitized = sanitized.replace('--', '-')

        # Limit length (255 is max on most filesystems, leave room for extension)
        if len(sanitized) > 200:
            sanitized = sanitized[:200]

        return sanitized

    def get_stats(self) -> Dict[str, int]:
        """Get file management statistics"""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            'files_saved': 0,
            'bytes_saved': 0,
            'files_deleted': 0
        }
