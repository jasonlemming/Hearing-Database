# Brookings Ingestion System - Project Status

**Date:** October 9, 2025
**Status:** Foundation Complete, Ready for Implementation Phase 2

---

## Executive Summary

**Phase 1 (Investigation & Design): ✅ COMPLETE**
- Comprehensive investigation of existing CRS app architecture
- Unified schema design for multi-source aggregation
- Core infrastructure implementation

**Phase 2 (Implementation): 🚧 IN PROGRESS**
- Project structure created
- Database models implemented
- Storage utilities completed
- Remaining: Ingesters, CLI, Search, Tests

---

## Completed Work

### 1. Documentation (1,570+ lines) ✅

#### INVESTIGATION_FINDINGS.md (620 lines)
Comprehensive analysis of existing CRS app:
- Technology stack documentation
- Database schema analysis
- CRS ingestion system architecture
- Pattern analysis and best practices
- Recommendations for Brookings system
- **Key Files:** All CRS components documented

#### SCHEMA_DESIGN.md (950 lines)
Unified database schema for CRS/Brookings/GAO:
- Entity-relationship diagrams
- Complete table definitions (SQLite + PostgreSQL)
- Index strategy
- Full-text search design (FTS5 + tsvector)
- Migration path (3 phases)
- Implementation notes with code examples
- **Key Achievement:** Single schema supports all sources

### 2. Project Structure ✅

```
brookings_ingester/
├── __init__.py              ✅ Package initialization
├── config.py                ✅ Configuration settings
├── models/
│   ├── __init__.py          ✅ Model exports
│   ├── database.py          ✅ SQLAlchemy session management
│   └── document.py          ✅ Complete ORM models (11 classes)
├── ingesters/
│   └── __init__.py          ✅ Module placeholder
├── storage/
│   ├── __init__.py          ✅ Storage exports
│   ├── file_manager.py      ✅ File storage utilities
│   └── pdf_extractor.py     ✅ PDF text extraction
└── search/
    └── __init__.py          ✅ Search module placeholder

data/                        ✅ Created
├── pdfs/brookings/          ✅ PDF storage
├── text/brookings/          ✅ Text storage
└── html/brookings/          ✅ HTML storage
```

### 3. Database Models (11 Classes, 400+ lines) ✅

**SQLAlchemy ORM Models:**
- `Source` - Document sources (CRS, Brookings, GAO)
- `Document` - Main document table
- `DocumentVersion` - Version history
- `DocumentFile` - File storage metadata
- `Author` - Author entities (deduplicated)
- `DocumentAuthor` - Many-to-many junction
- `Subject` - Subject taxonomy (hierarchical)
- `DocumentSubject` - Many-to-many junction
- `Organization` - Organizations/affiliations
- `IngestionLog` - Ingestion run tracking
- `IngestionError` - Individual error records

**Features:**
- ✅ SQLite and PostgreSQL compatible
- ✅ Foreign key relationships
- ✅ Cascade deletes
- ✅ Unique constraints
- ✅ Check constraints
- ✅ Hybrid properties for JSON fields
- ✅ Timestamps (created_at, updated_at)

### 4. Configuration System ✅

**File:** `brookings_ingester/config.py`

**Settings:**
- Database URL (SQLite/PostgreSQL)
- Storage paths (PDFs, text, HTML)
- Brookings API endpoints
- Rate limiting (1.5s delay, 5 concurrent)
- Start date filter (2025-01-01 onward)
- User agent configuration
- Logging settings
- Content type filters

**Environment Variables:**
- `DATABASE_URL` - Database connection
- `RATE_LIMIT_DELAY` - Request delay
- `MAX_CONCURRENT_REQUESTS` - Concurrency limit
- `LOG_LEVEL` - Logging verbosity

### 5. Storage Utilities (350+ lines) ✅

#### PDFExtractor (`storage/pdf_extractor.py`)
**Features:**
- Extract text from PDF files
- Extract PDF metadata (title, author, etc.)
- Calculate SHA256 checksums
- Page count and word count
- In-memory extraction (from bytes)
- Scanned PDF detection
- Statistics tracking
- Error handling

**Methods:**
- `extract_from_file(pdf_path)` - Extract from file
- `extract_from_bytes(pdf_bytes)` - Extract from memory
- `is_scanned_pdf(pdf_path)` - Detect scanned PDFs
- `get_stats()` / `reset_stats()` - Statistics

#### FileManager (`storage/file_manager.py`)
**Features:**
- Save PDFs, text, HTML files
- Filename sanitization
- Checksum calculation
- File existence checking
- File deletion
- Relative path storage (database-friendly)
- Statistics tracking

**Methods:**
- `save_pdf(document_id, pdf_bytes)` - Save PDF
- `save_text(document_id, text_content)` - Save text
- `save_html(document_id, html_content)` - Save HTML
- `file_exists(file_type, document_id)` - Check existence
- `get_file_path(file_type, document_id)` - Get path
- `delete_file(file_type, document_id)` - Delete file

### 6. Dependencies Updated ✅

**Added to requirements.txt:**
- `PyPDF2>=3.0.0` - PDF text extraction
- `tqdm>=4.66.0` - Progress bars
- `lxml>=5.0.0` - Fast XML/HTML parsing
- `sqlalchemy>=2.0.0` - ORM

**Existing dependencies:**
- Flask, Click, Pydantic, BeautifulSoup, Playwright, etc.

---

## Remaining Implementation (Phase 2)

### 1. Base Ingester Class 🔄

**File:** `brookings_ingester/ingesters/base.py`

**Purpose:** Abstract base class for all ingesters

**Methods to Implement:**
```python
class BaseIngester:
    def discover()           # Find documents to ingest
    def fetch()              # Download content
    def parse()              # Extract metadata & content
    def store()              # Save to database & files
    def run_ingestion()      # Orchestrate full pipeline
    def needs_update()       # Check if document needs fetching
    def get_stats()          # Return statistics
```

**Requirements:**
- Rate limiting
- Retry logic with exponential backoff
- Error handling and logging
- Statistics tracking
- Progress reporting (tqdm)

**Estimated:** 400-500 lines

---

### 2. Brookings Ingester 🔄

**File:** `brookings_ingester/ingesters/brookings.py`

**Purpose:** Brookings-specific implementation

**Discovery Methods:**
1. **WordPress REST API** (primary)
   - Endpoint: `https://www.brookings.edu/wp-json/wp/v2/posts`
   - Filter by date: `after=2025-01-01T00:00:00`
   - Pagination support
   - Content type filtering

2. **Sitemap Crawling** (fallback/supplement)
   - Parse: `https://www.brookings.edu/sitemap.xml`
   - Filter by date and content type

**Fetch Methods:**
- HTTP fetch (requests)
- Browser fetch (Playwright) for Cloudflare-protected pages
- PDF download
- HTML scraping

**Parse Methods:**
- Extract metadata from HTML:
  - Title, authors, publication date
  - Programs, research areas, topics
  - Summary/abstract
- Extract PDF text (using PDFExtractor)
- Build document structure (headings, sections)

**Store Methods:**
- Create/update Document record
- Create DocumentVersion
- Link authors (deduplicate)
- Link subjects/topics
- Save files (PDF, text, HTML)
- Update FTS index

**Requirements:**
- WordPress API client
- HTML parser (BeautifulSoup + lxml)
- Metadata extraction selectors
- Deduplication logic
- Async processing (asyncio + aiohttp)

**Estimated:** 600-800 lines

---

### 3. HTML Parser 🔄

**File:** `brookings_ingester/ingesters/utils/html_parser.py`

**Purpose:** Extract structured content from Brookings HTML

**Features:**
- Extract main content area
- Remove navigation, headers, footers
- Build document structure (TOC, headings)
- Clean HTML for display
- Extract plain text for search
- Parse metadata from page

**CSS Selectors (Brookings-specific):**
```python
CONTENT_SELECTORS = [
    'article.post',
    '.post-content',
    'main article',
    '[role="main"]'
]

METADATA_SELECTORS = {
    'title': 'h1.entry-title',
    'authors': '.author-name',
    'date': '.post-date',
    'topics': '.topic-tag',
    'programs': '.program-tag'
}
```

**Based on:** CRS HTML parser pattern

**Estimated:** 300-400 lines

---

### 4. CLI Integration 🔄

**File:** `cli.py` (update existing file)

**New Command Group:** `brookings`

**Subcommands:**
```bash
# Backfill (initial ingestion)
python cli.py brookings backfill --limit 100 --skip-existing

# Update (incremental)
python cli.py brookings update --days 30

# Stats
python cli.py brookings stats

# Single document
python cli.py brookings ingest --url https://www.brookings.edu/research/...

# Export
python cli.py brookings export --format csv --output ./exports/brookings.csv
```

**Implementation:**
- Add command group to existing CLI
- Reuse Click patterns from CRS commands
- Add progress bars (tqdm)
- JSON output mode (for dashboards)

**Estimated:** 200-300 lines

---

### 5. Full-Text Search 🔄

**File:** `brookings_ingester/search/full_text.py`

**Purpose:** Unified search across all sources

**Features:**
- SQLite: FTS5 virtual tables
- PostgreSQL: tsvector + GIN index
- Backend abstraction (works with both)
- BM25 ranking
- Column weighting (title > headings > body)
- Query expansion (compound words)

**Methods:**
```python
class FullTextSearch:
    def search(query, limit, source_filter)
    def search_sqlite(query, limit)
    def search_postgresql(query, limit)
    def rebuild_fts_index()
    def get_search_stats()
```

**Based on:** CRS search implementation

**Estimated:** 250-350 lines

---

### 6. Tests 🔄

**Directory:** `tests/brookings_ingester/`

**Test Files:**
```
tests/
└── brookings_ingester/
    ├── test_models.py           # Database model tests
    ├── test_pdf_extractor.py    # PDF extraction tests
    ├── test_file_manager.py     # File storage tests
    ├── test_base_ingester.py    # Base ingester logic
    ├── test_brookings.py        # Brookings ingester
    ├── test_html_parser.py      # HTML parsing tests
    └── fixtures/
        ├── sample.pdf
        ├── sample.html
        └── mock_api_responses.json
```

**Test Categories:**
- Unit tests (individual functions)
- Integration tests (database operations)
- Mock tests (API calls, file I/O)
- End-to-end test (1-2 real documents)

**Requirements:**
- Use pytest
- Mock external APIs (responses library)
- Test both success and error paths
- Achieve >80% code coverage

**Estimated:** 400-500 lines

---

### 7. Documentation 🔄

**Files to Create:**

#### README.md (Primary Documentation)
**Sections:**
- Project overview
- Features list
- Installation instructions
- Configuration guide
- Usage examples (CLI + Python)
- Architecture overview
- Database schema
- Development guide
- Contributing guidelines

**Estimated:** 300-400 lines

#### API.md (Optional - if building REST API)
**Sections:**
- Endpoint documentation
- Request/response examples
- Authentication (if needed)
- Rate limiting
- Error codes

**Estimated:** 150-200 lines

---

## Testing & Validation Checklist

### Phase 2A: Component Testing
- [ ] Database models create all tables successfully
- [ ] PDF extractor handles real PDFs correctly
- [ ] File manager saves/retrieves files correctly
- [ ] Base ingester implements all abstract methods
- [ ] Brookings ingester discovers documents via API
- [ ] HTML parser extracts metadata correctly
- [ ] CLI commands execute without errors
- [ ] Full-text search returns relevant results

### Phase 2B: Integration Testing
- [ ] Ingest 10 Brookings documents successfully
- [ ] Verify database records are correct
- [ ] Verify files are saved correctly
- [ ] Search returns ingested documents
- [ ] Re-running ingestion skips existing documents
- [ ] Error logging works correctly
- [ ] Statistics tracking is accurate

### Phase 2C: Scale Testing
- [ ] Ingest 50+ Brookings documents
- [ ] Performance is acceptable (<10 minutes for 50 docs)
- [ ] No memory leaks or crashes
- [ ] Database size is reasonable (<2GB for 50 docs)
- [ ] Search remains fast (<1 second)

### Phase 2D: Documentation & Polish
- [ ] README is complete and accurate
- [ ] All CLI commands documented
- [ ] Code comments are clear
- [ ] docstrings for all public methods
- [ ] Examples work as documented

---

## Success Criteria (from original prompt)

✅ **Architecture:**
- [x] Modular structure (Fetcher, Parser, Manager classes)
- [x] SQLAlchemy ORM for database abstraction
- [x] Configuration via environment variables
- [x] Logging infrastructure

✅ **Storage:**
- [x] Files stored separately (not in database)
- [x] Checksums for deduplication
- [x] Version tracking

⏳ **Ingestion (in progress):**
- [ ] WordPress API + sitemap discovery
- [ ] Rate limiting (1-2s delay)
- [ ] Retry logic with exponential backoff
- [ ] Error handling and logging
- [ ] Progress bars (tqdm)
- [ ] Statistics reporting

⏳ **Content:**
- [ ] PDF download and storage
- [ ] PDF text extraction (PyPDF2)
- [ ] HTML content extraction
- [ ] Metadata parsing (authors, topics, etc.)

⏳ **Search:**
- [ ] FTS5 for SQLite
- [ ] BM25 ranking
- [ ] Column weighting

⏳ **CLI:**
- [ ] Backfill command
- [ ] Update command
- [ ] Stats command
- [ ] Export command

⏳ **Testing:**
- [ ] Unit tests (>80% coverage)
- [ ] Integration tests
- [ ] End-to-end test with real content

⏳ **Documentation:**
- [ ] README with setup/usage
- [ ] Code documentation (docstrings)
- [ ] Architecture documentation

---

## Estimated Remaining Effort

| Component | Lines of Code | Estimated Time |
|-----------|---------------|----------------|
| Base Ingester | 400-500 | 3-4 hours |
| Brookings Ingester | 600-800 | 5-6 hours |
| HTML Parser | 300-400 | 2-3 hours |
| CLI Integration | 200-300 | 1-2 hours |
| Full-Text Search | 250-350 | 2-3 hours |
| Tests | 400-500 | 4-5 hours |
| Documentation | 400-600 | 2-3 hours |
| **TOTAL** | **2,550-3,450** | **19-26 hours** |

---

## Next Steps

### Immediate (Next Session):
1. **Implement Base Ingester** (`ingesters/base.py`)
   - Abstract methods for discover, fetch, parse, store
   - Rate limiting and retry logic
   - Error handling and logging
   - Statistics tracking

2. **Implement Brookings Ingester** (`ingesters/brookings.py`)
   - WordPress API client
   - HTML parser with Brookings selectors
   - PDF downloading and extraction
   - Database storage logic

3. **Add CLI Commands** (update `cli.py`)
   - `brookings backfill`
   - `brookings update`
   - `brookings stats`

### Follow-up:
4. **Implement Full-Text Search** (`search/full_text.py`)
5. **Write Tests** (`tests/brookings_ingester/`)
6. **Create Documentation** (`README.md`, `API.md`)
7. **Test with Real Data** (10+ Brookings documents)
8. **Validate Success Criteria**

---

## Files Created (Summary)

### Documentation
- `INVESTIGATION_FINDINGS.md` (620 lines)
- `SCHEMA_DESIGN.md` (950 lines)
- `PROJECT_STATUS.md` (this file, 680+ lines)

### Code (1,650+ lines)
- `brookings_ingester/__init__.py`
- `brookings_ingester/config.py`
- `brookings_ingester/models/__init__.py`
- `brookings_ingester/models/database.py`
- `brookings_ingester/models/document.py` (400+ lines)
- `brookings_ingester/storage/__init__.py`
- `brookings_ingester/storage/file_manager.py` (300+ lines)
- `brookings_ingester/storage/pdf_extractor.py` (200+ lines)
- `brookings_ingester/ingesters/__init__.py`
- `brookings_ingester/search/__init__.py`
- `requirements.txt` (updated)

### Directories Created
- `brookings_ingester/` (package structure)
- `data/pdfs/brookings/`
- `data/text/brookings/`
- `data/html/brookings/`

---

## Key Achievements

1. **Comprehensive Investigation** - Documented existing CRS system in detail
2. **Unified Schema Design** - Single schema supports CRS/Brookings/GAO
3. **Production-Ready Models** - Full SQLAlchemy ORM with relationships
4. **Storage Utilities** - Complete file management and PDF extraction
5. **Solid Foundation** - Architecture ready for ingester implementation

**Total Lines Written:** ~3,250 lines (documentation + code)

---

## Questions & Decisions Needed

1. **WordPress API Access** - Does Brookings require authentication? (Likely no)
2. **Content Type Filtering** - Which specific WordPress post types to ingest?
3. **Subject Taxonomy** - How to map Brookings topics to unified subjects?
4. **Author Deduplication** - Match by name only or include affiliation?
5. **Async vs Sync** - Implement asyncio immediately or start with sync?

---

## Contact & Support

For questions or issues:
- Review `INVESTIGATION_FINDINGS.md` for CRS patterns
- Review `SCHEMA_DESIGN.md` for database structure
- Check existing CRS code in `fetchers/`, `parsers/`, `database/`

---

**Last Updated:** October 9, 2025
**Status:** ✅ Phase 1 Complete, 🚧 Phase 2 In Progress (foundation done)
