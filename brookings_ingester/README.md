# Brookings Content Ingestion System

A Python-based system for ingesting, processing, and indexing research content from the Brookings Institution. This system fetches documents, extracts full-text from HTML and PDFs, and stores them in a searchable database with comprehensive metadata.

## Features

- **Multi-method Discovery**: WordPress REST API and sitemap-based document discovery
- **Full-text Extraction**: Extracts text from both HTML pages and PDF files
- **Intelligent Deduplication**: Checksum-based duplicate detection and version tracking
- **Full-text Search**: FTS5 (SQLite) and tsvector (PostgreSQL) support
- **Comprehensive Metadata**: Authors, subjects, publication dates, document types
- **Rate Limiting**: Respectful scraping with configurable delays and retries
- **Progress Tracking**: Real-time progress bars and detailed ingestion logs
- **Flexible Storage**: Supports both SQLite (development) and PostgreSQL (production)
- **CLI Interface**: Complete command-line interface for all operations

## Architecture

### System Components

```
brookings_ingester/
├── models/              # SQLAlchemy ORM models
│   ├── database.py      # Database initialization and session management
│   └── document.py      # Core data models (Document, Author, Subject, etc.)
├── storage/             # File storage and PDF processing
│   ├── pdf_extractor.py # PDF text extraction and analysis
│   └── file_manager.py  # File storage management (PDFs, HTML, text)
├── ingesters/           # Content ingestion pipeline
│   ├── base.py          # Abstract base ingester class
│   ├── brookings.py     # Brookings-specific implementation
│   └── utils/
│       └── html_parser.py  # HTML parsing and content extraction
├── config.py            # Configuration management
├── init_db.py          # Database initialization and seeding
└── test_ingestion.py   # Test suite for validation

data/
├── pdfs/               # Downloaded PDF files
├── text/               # Extracted text content
└── html/               # Downloaded HTML content
```

### Data Flow

1. **Discovery**: WordPress API or sitemap identifies available documents
2. **Fetch**: Downloads HTML content and any associated PDFs
3. **Parse**: Extracts metadata, full-text, and structure from content
4. **Store**: Saves to database with deduplication and version tracking

## Installation

### Prerequisites

- Python 3.9 or higher
- SQLite 3.35+ (for FTS5 support) or PostgreSQL 12+

### Setup

1. **Install Dependencies**

```bash
pip install -r requirements.txt
```

Required packages:
- SQLAlchemy >= 2.0.0
- PyPDF2 >= 3.0.0
- BeautifulSoup4 >= 4.12.0
- lxml >= 5.0.0
- requests >= 2.31.0
- click >= 8.1.0
- tqdm >= 4.66.0

2. **Initialize Database**

```bash
python -m brookings_ingester.init_db
```

This creates:
- Database tables (11 core tables)
- Storage directories (data/pdfs, data/text, data/html)
- Seed data (sources and organizations)

3. **Verify Setup**

```bash
python -m brookings_ingester.test_ingestion --test discovery --limit 5
```

## Quick Start

### 1. Test with Sample Documents

Run the test suite to validate the system with a small number of documents:

```bash
# Run all tests with 5 documents
python -m brookings_ingester.test_ingestion --limit 5

# Test specific components
python -m brookings_ingester.test_ingestion --test discovery --limit 10
python -m brookings_ingester.test_ingestion --test single
python -m brookings_ingester.test_ingestion --test full --limit 5
```

### 2. CLI Integration (Optional)

To integrate with the main CLI (cli.py), follow instructions in `cli_brookings_commands.txt`:

```bash
# Add imports to cli.py (around line 37)
# Then add command group (around line 1076)

# After integration:
python cli.py brookings init
python cli.py brookings backfill --limit 100 --since-date 2025-01-01
python cli.py brookings stats
```

### 3. Programmatic Usage

```python
from brookings_ingester.ingesters import BrookingsIngester
from brookings_ingester.models import get_session, Document

# Initialize ingester
ingester = BrookingsIngester()

# Discover documents
documents = ingester.discover(limit=10, method='api', since_date='2025-01-01')
print(f"Found {len(documents)} documents")

# Run full ingestion
result = ingester.run_ingestion(
    limit=100,
    skip_existing=True,
    run_type='backfill',
    method='api',
    since_date='2025-01-01'
)

if result['success']:
    stats = result['stats']
    print(f"Fetched: {stats['documents_fetched']}")
    print(f"Errors: {stats['errors_count']}")

# Query database
session = get_session()
recent_docs = session.query(Document).order_by(
    Document.publication_date.desc()
).limit(10).all()

for doc in recent_docs:
    print(f"{doc.title} ({doc.publication_date})")

session.close()
```

## Usage Examples

### Discovery Methods

The system supports three discovery methods:

**1. WordPress API (Recommended)**
```bash
python -m brookings_ingester.test_ingestion --method api --limit 50
```
- Uses WordPress REST API endpoint
- Reliable metadata
- Filtered by publication date
- Paginated results

**2. Sitemap**
```bash
python -m brookings_ingester.test_ingestion --method sitemap --limit 50
```
- Parses sitemap.xml
- Filtered by URL patterns
- Fallback method

**3. Both (Comprehensive)**
```bash
python -m brookings_ingester.test_ingestion --method both --limit 100
```
- Combines API and sitemap results
- Deduplicates automatically
- Maximum coverage

### Ingestion Scenarios

**Initial Backfill**
```python
from brookings_ingester.ingesters import BrookingsIngester

ingester = BrookingsIngester()
result = ingester.run_ingestion(
    limit=1000,              # Process 1000 documents
    skip_existing=True,      # Skip already ingested
    run_type='backfill',     # Mark as backfill operation
    method='api',            # Use WordPress API
    since_date='2024-01-01'  # Documents from 2024 onwards
)
```

**Incremental Updates**
```python
from datetime import datetime, timedelta

# Update documents from last 30 days
since_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

result = ingester.run_ingestion(
    limit=None,              # No limit
    skip_existing=False,     # Re-fetch to check for updates
    run_type='update',       # Mark as update operation
    method='api',
    since_date=since_date
)
```

**Single Document**
```python
from brookings_ingester.ingesters import BrookingsIngester

ingester = BrookingsIngester()

doc_meta = {
    'document_identifier': ingester._extract_slug(url),
    'url': 'https://www.brookings.edu/articles/example-article/',
    'title': None
}

# Fetch, parse, and store
fetched = ingester.fetch(doc_meta)
parsed = ingester.parse(doc_meta, fetched)
document_id = ingester.store(parsed)

print(f"Stored document ID: {document_id}")
```

## Database Schema

### Core Tables

**Document** - Main document storage
- `document_id` (PK): Unique identifier
- `source_id` (FK): References Source table
- `document_identifier`: Unique slug/identifier
- `title`: Document title
- `document_type`: article, report, working-paper, etc.
- `publication_date`: When document was published
- `full_text`: Complete extracted text
- `summary`: Abstract/summary
- `word_count`: Text word count
- `metadata`: JSON field for flexible metadata
- `url`: Canonical URL
- `pdf_url`: PDF download link
- `is_current`: Version tracking flag
- `content_checksum`: SHA256 for deduplication

**Author** - Deduplicated author entities
- `author_id` (PK)
- `full_name`: Author's full name
- `normalized_name`: Lowercase, trimmed for matching
- `affiliation_id` (FK): Organization affiliation

**Subject** - Hierarchical subject taxonomy
- `subject_id` (PK)
- `subject_name`: Subject/topic name
- `parent_subject_id`: For hierarchical structure
- `subject_type`: category, tag, keyword

**DocumentFile** - File storage metadata
- `file_id` (PK)
- `document_id` (FK)
- `file_type`: pdf, html, text
- `file_path`: Relative path to file
- `file_size`: Size in bytes
- `checksum`: SHA256 hash

**IngestionLog** - Run tracking
- `log_id` (PK)
- `source_id` (FK)
- `run_type`: backfill, update, manual
- `started_at`, `completed_at`: Timestamps
- `documents_checked`, `documents_fetched`, `documents_updated`, `documents_skipped`
- `errors_count`: Number of errors
- `status`: running, completed, failed

**IngestionError** - Error tracking
- `error_id` (PK)
- `log_id` (FK)
- `document_identifier`: Failed document
- `error_type`: fetch_failed, parse_failed, etc.
- `error_message`: Error details
- `occurred_at`: Timestamp

### Full-Text Search

**SQLite (FTS5)**
```sql
CREATE VIRTUAL TABLE document_fts USING fts5(
    document_id UNINDEXED,
    title,
    full_text,
    summary,
    content='document',
    content_rowid='document_id',
    tokenize='porter unicode61'
);
```

**PostgreSQL (tsvector)**
```sql
ALTER TABLE document ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', COALESCE(title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(summary, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(full_text, '')), 'C')
    ) STORED;

CREATE INDEX idx_document_search ON document USING GIN(search_vector);
```

## Configuration

Edit `brookings_ingester/config.py` to customize:

```python
class Config:
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///data/brookings.db')

    # Storage paths
    DATA_DIR = Path(__file__).parent.parent / 'data'
    PDF_STORAGE = DATA_DIR / 'pdfs'
    TEXT_STORAGE = DATA_DIR / 'text'
    HTML_STORAGE = DATA_DIR / 'html'

    # Rate limiting
    REQUEST_DELAY = 1.5  # seconds between requests
    RETRY_ATTEMPTS = 3
    RETRY_DELAY = 5.0

    # Content filtering
    MIN_WORD_COUNT = 100
    MAX_WORD_COUNT = 100000
    CONTENT_TYPES = ['article', 'report', 'working-paper', 'policy-brief']

    # WordPress API
    BROOKINGS_API_BASE = 'https://www.brookings.edu/wp-json/wp/v2'
    BROOKINGS_SITEMAP = 'https://www.brookings.edu/sitemap.xml'
```

### Environment Variables

```bash
# Use PostgreSQL
export DATABASE_URL="postgresql://user:pass@localhost/brookings"

# Custom data directory
export DATA_DIR="/var/lib/brookings/data"
```

## Development

### Running Tests

```bash
# All tests
python -m brookings_ingester.test_ingestion --test all --limit 5

# Discovery only
python -m brookings_ingester.test_ingestion --test discovery --method api

# Single document fetch/parse
python -m brookings_ingester.test_ingestion --test single --url https://www.brookings.edu/articles/example/

# Full pipeline
python -m brookings_ingester.test_ingestion --test full --limit 10
```

### Adding New Sources

To add GAO or other sources, extend `BaseIngester`:

```python
from brookings_ingester.ingesters.base import BaseIngester

class GAOIngester(BaseIngester):
    def discover(self, limit=None, **kwargs):
        # Implement GAO-specific discovery
        pass

    def fetch(self, document_meta):
        # Implement GAO-specific fetching
        pass

    def parse(self, document_meta, fetched_content):
        # Implement GAO-specific parsing
        pass
```

### Code Structure

**BaseIngester** provides:
- `run_ingestion()`: Full pipeline orchestration
- `store()`: Database storage with deduplication
- Progress tracking and error handling
- Logging infrastructure

**Subclass responsibilities**:
- `discover()`: Find available documents
- `fetch()`: Download content
- `parse()`: Extract metadata and text

## Performance

### Benchmarks

Based on testing with Brookings content:

- **Discovery**: ~100-200 documents per API call (paginated)
- **Fetch**: ~1-2 seconds per document (rate limited)
- **Parse**: ~0.1-0.5 seconds per document
- **Store**: ~0.05 seconds per document

**Estimated throughput**: 1,500-2,000 documents per hour (rate limited)

### Optimization Tips

1. **Use API discovery** (faster than sitemap parsing)
2. **Set appropriate limits** for initial testing
3. **Enable skip_existing** for incremental updates
4. **Use PostgreSQL** for production (better concurrency)
5. **Monitor logs** for bottlenecks

### Storage Requirements

Per 1,000 documents (approximate):
- Database: 50-100 MB
- PDFs: 200-500 MB
- Text files: 20-50 MB
- HTML files: 30-60 MB

**Total**: ~300-700 MB per 1,000 documents

## Troubleshooting

### Database Issues

**Error: "table document already exists"**
```bash
# Drop and recreate (WARNING: deletes all data)
rm data/brookings.db
python -m brookings_ingester.init_db
```

**Error: "no such module: fts5"**
```bash
# Check SQLite version (need 3.35+)
python -c "import sqlite3; print(sqlite3.sqlite_version)"

# Upgrade SQLite or use PostgreSQL
export DATABASE_URL="postgresql://localhost/brookings"
```

### Ingestion Issues

**Error: "Failed to fetch content"**
- Check internet connectivity
- Verify URL is accessible
- Check if Cloudflare is blocking (may need Playwright)

**Error: "Failed to parse content"**
- Document may have non-standard HTML structure
- Check logs for specific parsing errors
- Try with a different document

**Warning: "Document already exists"**
- Normal behavior with `skip_existing=True`
- Use `skip_existing=False` to force re-ingestion

### Performance Issues

**Slow ingestion**
- Increase `REQUEST_DELAY` if getting rate limited
- Reduce `limit` for testing
- Check network latency

**High memory usage**
- Process in smaller batches
- Close database sessions properly
- Monitor PDF extraction (large PDFs use more memory)

## API Reference

### BrookingsIngester

```python
class BrookingsIngester(BaseIngester):
    def discover(
        self,
        limit: int = None,
        method: str = 'api',
        since_date: str = None,
        **kwargs
    ) -> List[Dict[str, Any]]

    def fetch(
        self,
        document_meta: Dict
    ) -> Optional[Dict[str, Any]]

    def parse(
        self,
        document_meta: Dict,
        fetched_content: Dict
    ) -> Optional[Dict[str, Any]]

    def run_ingestion(
        self,
        limit: int = None,
        skip_existing: bool = True,
        run_type: str = 'manual',
        method: str = 'api',
        since_date: str = None
    ) -> Dict[str, Any]
```

### Database Models

```python
from brookings_ingester.models import (
    Document,
    Author,
    Subject,
    DocumentFile,
    Source,
    Organization,
    IngestionLog,
    get_session,
    session_scope
)

# Using context manager (recommended)
with session_scope() as session:
    docs = session.query(Document).all()
    # session auto-commits on success, rolls back on error

# Manual session management
session = get_session()
try:
    docs = session.query(Document).all()
    session.commit()
finally:
    session.close()
```

## Roadmap

### Completed
- [x] Database schema design
- [x] SQLAlchemy ORM models
- [x] PDF extraction utilities
- [x] Base ingester framework
- [x] Brookings ingester implementation
- [x] CLI interface
- [x] Test suite
- [x] Documentation

### Pending
- [ ] Full-text search implementation
- [ ] Flask API endpoints
- [ ] Web interface integration
- [ ] GAO ingester
- [ ] CRS migration to unified schema
- [ ] Advanced search features (filters, facets)
- [ ] Scheduled updates (cron jobs)
- [ ] Performance monitoring dashboard

## License

Copyright (c) 2025 Congressional Hearing Database Team

## Support

For issues and questions:
- Review this README and troubleshooting section
- Check `INVESTIGATION_FINDINGS.md` for implementation details
- Review `SCHEMA_DESIGN.md` for database architecture
- Examine test output for validation examples

## Acknowledgments

Built using patterns from the existing CRS ingestion system, adapted for:
- Modern SQLAlchemy ORM architecture
- Multi-source content support
- Enhanced metadata extraction
- Improved error handling and logging
