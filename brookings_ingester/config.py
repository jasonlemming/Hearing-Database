"""
Configuration for Brookings Ingestion System
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for Brookings ingester"""

    # Database - Policy Library (Neon Postgres)
    # Use BROOKINGS_DATABASE_URL to override, otherwise use DATABASE_URL from env, or default to Policy Library
    DATABASE_URL = os.getenv(
        'BROOKINGS_DATABASE_URL',
        os.getenv('DATABASE_URL', 'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require')
    )

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

    # Substack settings
    SUBSTACK_PUBLICATIONS = os.getenv('SUBSTACK_PUBLICATIONS', '').split(',') if os.getenv('SUBSTACK_PUBLICATIONS') else [
        'jamiedupree.substack.com'  # Default example publication
    ]

    @classmethod
    def ensure_directories(cls):
        """Ensure all storage directories exist"""
        cls.PDF_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.TEXT_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.HTML_STORAGE.mkdir(parents=True, exist_ok=True)
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Substack directories
        substack_pdf = cls.STORAGE_PATH / 'pdfs' / 'substack'
        substack_text = cls.STORAGE_PATH / 'text' / 'substack'
        substack_html = cls.STORAGE_PATH / 'html' / 'substack'
        substack_pdf.mkdir(parents=True, exist_ok=True)
        substack_text.mkdir(parents=True, exist_ok=True)
        substack_html.mkdir(parents=True, exist_ok=True)


config = Config()
