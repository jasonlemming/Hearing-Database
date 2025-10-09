"""
Configuration for Brookings Ingestion System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for Brookings ingester"""

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///brookings_products.db')

    # Storage paths
    BASE_DIR = Path(__file__).parent.parent
    STORAGE_PATH = BASE_DIR / 'data'
    PDF_STORAGE = STORAGE_PATH / 'pdfs' / 'brookings'
    TEXT_STORAGE = STORAGE_PATH / 'text' / 'brookings'
    HTML_STORAGE = STORAGE_PATH / 'html' / 'brookings'

    # Brookings API & Website
    BROOKINGS_BASE_URL = 'https://www.brookings.edu'
    BROOKINGS_WP_API = 'https://www.brookings.edu/wp-json/wp/v2'
    BROOKINGS_SITEMAP = 'https://www.brookings.edu/sitemap.xml'

    # Ingestion parameters
    RATE_LIMIT_DELAY = float(os.getenv('RATE_LIMIT_DELAY', '1.5'))  # seconds
    MAX_CONCURRENT_REQUESTS = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
    START_DATE = '2025-01-01'  # Only ingest content from 2025 onward
    REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

    # User agent
    USER_AGENT = os.getenv(
        'USER_AGENT',
        'Research-Aggregator/1.0 (Educational Research; https://github.com/your-repo)'
    )

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = BASE_DIR / 'logs' / 'brookings_ingestion.log'

    # Content filters
    INCLUDE_CONTENT_TYPES = [
        'Research',
        'Report',
        'Working Paper',
        'Policy Brief',
        'Essay',
        'Paper',
        'Book Chapter'
    ]

    EXCLUDE_CONTENT_TYPES = [
        'Blog',
        'Op-Ed',
        'Podcast',
        'Video',
        'Event',
        'Testimony',
        'Commentary'
    ]

    @classmethod
    def ensure_directories(cls):
        """Ensure all storage directories exist"""
        cls.PDF_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.TEXT_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.HTML_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


config = Config()
