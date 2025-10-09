# Investigation Findings: Existing CRS App

**Date:** October 9, 2025
**Purpose:** Document existing CRS app architecture for Brookings ingestion system design

---

## Executive Summary

The existing Congressional Hearing Database includes a **CRS content ingestion system** that fetches, parses, and stores HTML content from CRS reports. The system uses:
- **SQLite** database with separate `crs_products.db`
- **Playwright** for headless browser scraping (bypasses Cloudflare)
- **BeautifulSoup** for HTML parsing
- **FTS5** (SQLite Full-Text Search) for search functionality
- **Click** for CLI commands
- **Flask** for web interface (already integrated)

The CRS system serves as an excellent **template** for the Brookings ingestion system, with proven patterns for content fetching, parsing, and storage.

---

## 1. Technology Stack

### Core Framework & Language
- **Language:** Python 3.x
- **Web Framework:** Flask 3.0+
- **CLI Framework:** Click 8.1+
- **Database:** SQLite (no ORM - raw SQL via custom DatabaseManager)
- **Validation:** Pydantic 2.0+
- **Environment:** python-dotenv

### Data Fetching & Parsing
- **HTTP Client:** `requests` + `aiohttp` (async support)
- **Browser Automation:** Playwright 1.40+ (for Cloudflare bypass)
- **HTML Parsing:** BeautifulSoup4 4.12+
- **PDF Parsing:** Not yet implemented (placeholder for future)

### Full-Text Search
- **SQLite FTS5** with Porter stemming tokenizer
- Column-weighted BM25 ranking (title: 5x, headings: 3x, text: 1x)

### Testing & Code Quality
- **Testing:** pytest 7.4+
- **Formatting:** black 23.0+

---

## 2. Database Architecture

### Database Files
The system uses **two separate SQLite databases**:

1. **`congressional_hearings.db`** (main database)
   - Hearings, committees, members, witnesses, bills
   - Schema: `database/schema.sql`
   - Complex relational structure with foreign keys

2. **`crs_products.db`** (CRS content database)
   - CRS products metadata and content
   - Separate to isolate CRS-specific data
   - Uses gzip compression for production deployment

### CRS Database Schema

#### Table: `products`
Main metadata table for CRS products:
```sql
- product_id (VARCHAR, PK)
- title (TEXT)
- product_type (VARCHAR) -- Report, In Focus, Insight
- status (VARCHAR) -- Active, Archived
- publication_date (DATE)
- updated_at (DATETIME)
- authors (JSON) -- Array of author names
- topics (JSON) -- Array of topic strings
- summary (TEXT)
- url_html (VARCHAR)
- url_pdf (VARCHAR)
- version (INTEGER)
```

#### Table: `product_versions`
Stores version history and content for each CRS product:
```sql
- version_id (INTEGER, PK, AUTOINCREMENT)
- product_id (VARCHAR, FK → products)
- version_number (INTEGER)
- html_content (TEXT) -- Cleaned HTML for display
- text_content (TEXT) -- Plain text for FTS
- structure_json (JSON) -- TOC, headings, sections
- html_url (VARCHAR)
- content_hash (VARCHAR) -- SHA256 for deduplication
- word_count (INTEGER)
- ingested_at (DATETIME)
- is_current (BOOLEAN) -- Only one version per product
- UNIQUE(product_id, version_number)
```

#### Table: `product_content_fts`
Full-text search index (FTS5 virtual table):
```sql
CREATE VIRTUAL TABLE product_content_fts USING fts5(
    product_id UNINDEXED,
    version_id UNINDEXED,
    title,          -- Weight: 5.0
    headings,       -- Weight: 3.0
    text_content,   -- Weight: 1.0
    tokenize='porter'
);
```

#### Table: `content_ingestion_logs`
Tracks ingestion runs:
```sql
- log_id (INTEGER, PK, AUTOINCREMENT)
- run_type (VARCHAR) -- backfill, update, manual
- started_at (DATETIME)
- completed_at (DATETIME)
- products_checked (INTEGER)
- content_fetched (INTEGER)
- content_updated (INTEGER)
- content_skipped (INTEGER)
- errors_count (INTEGER)
- error_details (JSON)
- status (VARCHAR) -- running, completed, failed, partial
- total_size_bytes (INTEGER)
- avg_fetch_time_ms (REAL)
- total_duration_seconds (REAL)
```

### Main Database Schema Highlights

**Key Tables:**
- `hearings` - Congressional hearings (18 columns)
- `committees` - Committees and subcommittees (hierarchical)
- `members` - Members of Congress (bioguide_id as key)
- `witnesses` - Witness entities
- `witness_appearances` - Junction table (hearing ↔ witness)
- `bills` - Bill metadata
- `hearing_bills` - Links hearings to bills
- `hearing_committees` - Links hearings to committees
- `sync_tracking` - Tracks sync operations
- `import_errors` - Error logging
- `update_logs` - Detailed update metrics

**Database Management:**
- No ORM (SQLAlchemy) - uses custom `DatabaseManager` class
- Context manager pattern for transactions
- Row factory for dict-like access
- Foreign keys enabled via `PRAGMA foreign_keys = ON`

---

## 3. CRS Content Ingestion System

### 3.1 Content Fetcher: `fetchers/crs_content_fetcher.py`

**Class:** `CRSContentFetcher`

**Key Features:**
- Rate limiting (default: 0.5s delay between requests)
- Retry logic with exponential backoff (max 3 attempts)
- Two fetch methods:
  1. **HTTP fetch** (`fetch_html`) - Fast, standard requests
  2. **Browser fetch** (`fetch_html_with_browser`) - Playwright, bypasses Cloudflare
- Statistics tracking (requests, success rate, total bytes)
- User-Agent: `Congressional-Hearing-Database-Bot/1.0 (Educational/Research)`

**Fetch Priority System:**
```python
1. New products (no version in database)
2. Updated products (version_number > stored version)
3. Recently published products (within last 30 days)
4. Oldest unfetched products
```

**Cloudflare Bypass:**
- Uses Playwright with Chromium
- Mimics real browser (viewport, user-agent)
- Waits for `networkidle` and selector
- 2-second additional wait for dynamic content

### 3.2 HTML Parser: `parsers/crs_html_parser.py`

**Class:** `CRSHTMLParser`

**Parsing Steps:**
1. **Extract content area** - Removes navigation, headers, footers
2. **Build structure** - Extracts headings (h1-h6), creates TOC
3. **Clean HTML** - Removes empty tags, fixes image paths
4. **Extract plain text** - For full-text search
5. **Calculate metrics** - SHA256 hash, word count

**Content Selectors:**
```python
['main', 'article', 'div.report-content', 'div.crs-report',
 'div#report-content', 'div.main-content', 'div[role="main"]']
```

**Remove Selectors:**
```python
['nav', 'header', 'footer', '.breadcrumb', '.navigation',
 'script', 'style', 'noscript', '.advertisement', '#sidebar']
```

**Output:** `ParsedContent` dataclass
- `html_content` (str)
- `text_content` (str)
- `structure_json` (dict) - TOC, sections, headings
- `content_hash` (str) - SHA256
- `word_count` (int)

### 3.3 Content Manager: `database/crs_content_manager.py`

**Class:** `CRSContentManager`

**Key Methods:**
- `upsert_version()` - Insert/update version, mark as current, update FTS
- `get_current_version()` - Get active version for product
- `get_version_history()` - List all versions
- `needs_update()` - Check if fetch needed (7-day freshness rule)
- `get_products_needing_content()` - Find products without content
- `start_ingestion_log()` / `complete_ingestion_log()` - Track runs
- `get_ingestion_stats()` - Overall statistics

**Deduplication:**
- Checks `content_hash` (SHA256) before updating
- Skips if content unchanged
- Only one `is_current = 1` version per product

---

## 4. CLI Integration

### CRS Commands in `cli.py`

**Command Group:** `crs-content`

**Subcommands:**

1. **`backfill`** - Initial content ingestion
   ```bash
   python cli.py crs-content backfill --limit 100 --skip-existing
   ```
   - Fetches HTML for all products
   - Uses Playwright (headless browser)
   - Rate limited (1.0s delay)
   - Logs errors and metrics

2. **`update`** - Incremental updates
   ```bash
   python cli.py crs-content update --days 30
   ```
   - Updates recently modified products
   - Checks `needs_update()` to avoid unnecessary fetches

3. **`stats`** - Display statistics
   ```bash
   python cli.py crs-content stats
   ```
   - Shows coverage %, avg word count, storage size

**CLI Framework:** Click with option decorators

---

## 5. Web Interface

### Flask Blueprint: `web/blueprints/crs.py`

**Routes:**

1. **`/crs/`** - Browse CRS products
   - Filters: product_type, status, topic, date range
   - Pagination (50 per page)
   - Decompresses `crs_products.db.gz` on Vercel

2. **`/crs/search`** - Full-text search
   - Query expansion (e.g., "healthcare" → "healthcare OR health")
   - Dual FTS tables: `product_content_fts` + `products_fts`
   - BM25 ranking with column weights
   - Highlights content matches

3. **`/crs/product/<product_id>`** - Product detail
   - Displays metadata + current version content
   - Renders HTML content in page
   - Shows structure (TOC, headings)

4. **`/crs/api/export`** - CSV export
   - Export search results or filtered products
   - Limit: 1000 products

**Database Decompression:**
- Production: Decompresses `crs_products.db.gz` to `/tmp/` on Vercel
- Development: Uses local `crs_products.db`

---

## 6. Full-Text Search Implementation

### Dual FTS Architecture

#### Products FTS (`products_fts`)
Metadata-only search:
```sql
CREATE VIRTUAL TABLE products_fts USING fts5(
    product_id UNINDEXED,
    title,      -- Weight: 3.0
    summary,    -- Weight: 1.0
    topics,     -- Weight: 2.0
    tokenize='porter'
);
```

#### Content FTS (`product_content_fts`)
Full HTML content search:
```sql
CREATE VIRTUAL TABLE product_content_fts USING fts5(
    product_id UNINDEXED,
    version_id UNINDEXED,
    title,          -- Weight: 5.0
    headings,       -- Weight: 3.0
    text_content,   -- Weight: 1.0
    tokenize='porter'
);
```

### Search Query
Combines both FTS tables with BM25 scoring:
```sql
WITH content_matches AS (
    SELECT product_id, bm25(product_content_fts, 5.0, 3.0, 1.0) as content_score
    FROM product_content_fts
    WHERE product_content_fts MATCH ?
),
metadata_matches AS (
    SELECT product_id, bm25(products_fts, 3.0, 1.0, 2.0) as metadata_score
    FROM products_fts
    WHERE products_fts MATCH ?
)
SELECT p.*, COALESCE(cm.content_score, 0) + COALESCE(mm.metadata_score, 0) as combined_score
FROM products p
LEFT JOIN content_matches cm ON p.product_id = cm.product_id
LEFT JOIN metadata_matches mm ON p.product_id = mm.product_id
WHERE cm.product_id IS NOT NULL OR mm.product_id IS NOT NULL
ORDER BY combined_score
```

**Key Features:**
- Porter stemming tokenizer (handles plurals, tenses)
- BM25 relevance ranking (superior to default FTS ranking)
- Column weights prioritize titles > headings > body text
- Query expansion for better results

---

## 7. Data Flow

### Ingestion Flow
```
1. CLI Command (`python cli.py crs-content backfill`)
   ↓
2. CRSContentManager.start_ingestion_log()
   ↓
3. Get products to fetch (products without content)
   ↓
4. For each product:
   a. CRSContentFetcher.fetch_html_with_browser(html_url)
   b. CRSHTMLParser.parse(html, product_id)
   c. CRSContentManager.upsert_version(...)
   d. Update FTS index
   ↓
5. CRSContentManager.complete_ingestion_log()
   ↓
6. Display statistics
```

### Search Flow
```
1. User enters search query in web UI
   ↓
2. Query expansion (compound words)
   ↓
3. Search both FTS tables (content + metadata)
   ↓
4. Combine scores with BM25 ranking
   ↓
5. Return ranked results with snippets
```

---

## 8. Existing Patterns & Best Practices

### ✅ Patterns to Reuse for Brookings

1. **Separate Database per Source**
   - `crs_products.db` isolated from main `congressional_hearings.db`
   - Easier to manage, backup, and deploy separately

2. **Dual FTS Tables**
   - One for metadata (fast, lightweight)
   - One for full content (comprehensive)

3. **Version Tracking**
   - `product_versions` table with `is_current` flag
   - Preserves history while marking canonical version

4. **Content Deduplication**
   - SHA256 hash comparison
   - Skip re-ingestion if content unchanged

5. **Ingestion Logging**
   - Detailed metrics per run
   - Error tracking with JSON details

6. **Rate Limiting**
   - Respectful delay between requests
   - Exponential backoff on retries

7. **Browser Fallback**
   - Try HTTP first (fast)
   - Fall back to Playwright if blocked (Cloudflare)

8. **CLI + Web UI**
   - CLI for management/automation
   - Flask blueprints for user-facing features

9. **Transaction Management**
   - Context managers for database operations
   - Automatic rollback on errors

10. **Modular Architecture**
    - Separate Fetcher, Parser, Manager classes
    - Easy to test and extend

---

## 9. Dependencies Analysis

### From `requirements.txt`:
```
requests>=2.31.0          # HTTP client
aiohttp>=3.9.0            # Async HTTP (not yet used in CRS)
pydantic>=2.0.0           # Data validation
python-dotenv>=1.0.0      # Environment variables
click>=8.1.0              # CLI framework
pyyaml>=6.0               # Config files
pytest>=7.4.0             # Testing
black>=23.0.0             # Code formatting
flask>=3.0.0              # Web framework
pydantic-settings>=2.0.0  # Settings management
playwright>=1.40.0        # Browser automation
beautifulsoup4>=4.12.0    # HTML parsing
```

### Missing for Brookings (need to add):
```
PyPDF2>=3.0               # PDF text extraction
tqdm>=4.66                # Progress bars
lxml>=5.0                 # XML/HTML parsing (faster than html.parser)
```

---

## 10. Storage Patterns

### File Storage
Currently, CRS system **does not store files locally**:
- HTML content stored directly in database (TEXT column)
- No `/data/pdfs/` or `/data/text/` directories
- Relies on congress.gov for PDF hosting

### For Brookings:
**Recommendation:** Store PDFs locally for reliability
- `/data/pdfs/brookings/{document_id}.pdf`
- `/data/text/brookings/{document_id}.txt` (extracted text backup)
- Add `pdf_path` and `file_size` columns

---

## 11. Configuration & Settings

### Configuration Files
- `config/settings.py` - Application settings (Pydantic BaseSettings)
- `config/logging_config.py` - Logging setup
- `.env` - Environment variables (API keys, paths)

### Key Settings Pattern:
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_path: str = "congressional_hearings.db"
    api_key: str = ""
    # ... other settings

    class Config:
        env_file = ".env"
```

---

## 12. Gaps & Opportunities

### Current CRS Limitations

1. **No PDF Extraction**
   - CRS only fetches HTML
   - Brookings will need PDF → text pipeline

2. **No Async Processing**
   - `aiohttp` imported but not used
   - Sequential fetching (slow for large batches)

3. **No Deduplication Across Sources**
   - Each source in separate database
   - No unified document table

4. **No API Endpoints**
   - Web UI only (Flask templates)
   - Could add REST API for programmatic access

5. **Limited Error Recovery**
   - Logs errors but doesn't retry failed items
   - No "resume from checkpoint" for large batches

### Opportunities for Brookings System

1. **Unified Document Schema**
   - Design schema to accommodate CRS + Brookings + GAO
   - Add `source` discriminator field
   - Share FTS infrastructure

2. **Async Ingestion**
   - Use `asyncio` + `aiohttp` for concurrent fetching
   - Process 5-10 documents in parallel

3. **Progress Tracking**
   - Add `tqdm` progress bars
   - Real-time status display

4. **PDF Pipeline**
   - PyPDF2 for text extraction
   - OCR fallback for scanned PDFs (optional)

5. **REST API**
   - Flask-RESTful or FastAPI
   - Enable programmatic access to documents

---

## 13. Key Takeaways for Brookings Design

### Architecture Decisions

| **Component** | **CRS Approach** | **Recommended for Brookings** |
|---------------|------------------|-------------------------------|
| Database | Separate SQLite (`crs_products.db`) | **Separate** (`brookings_products.db`) initially, unify later |
| Database Backend | SQLite only | **SQLite + PostgreSQL** support via env var |
| ORM | None (raw SQL) | **SQLAlchemy** for flexibility and PostgreSQL support |
| Content Storage | In-database (TEXT column) | **Hybrid:** DB + file storage (`/data/pdfs/`) |
| Fetching | `requests` + Playwright | **Same** (WordPress API + scraping) |
| Parsing | BeautifulSoup | **Same** + PyPDF2 |
| Search | FTS5 (SQLite only) | **FTS5 (SQLite) + tsvector (PostgreSQL)** |
| CLI | Click | **Same** (Click) |
| Async | Not implemented | **Implement** (`asyncio` + `aiohttp`) |
| Progress Tracking | Basic logging | **Add tqdm** progress bars |
| Error Handling | Log to DB | **Same** + retry logic |

### Migration Path

**Phase 1:** Build Brookings system (this project)
- Separate database (`brookings_products.db`)
- Reuse CRS patterns (Fetcher, Parser, Manager)
- Add missing features (PDF extraction, async, progress bars)

**Phase 2:** Unify schema (future)
- Create unified `documents` table
- Migrate CRS + Brookings to unified structure
- Add `source` discriminator (`CRS`, `Brookings`, `GAO`)

**Phase 3:** PostgreSQL support (production)
- Add SQLAlchemy ORM
- Support both SQLite (dev) and PostgreSQL (prod)
- Use tsvector for full-text search on PostgreSQL

---

## 14. Files to Review (Key Components)

### Core CRS Files
```
fetchers/crs_content_fetcher.py       # HTTP + browser fetching
parsers/crs_html_parser.py            # HTML parsing + structure extraction
database/crs_content_manager.py       # Database operations
database/migrations/crs_001_add_content_tables.sql  # Schema
cli.py (lines 787-1075)               # CLI commands
web/blueprints/crs.py                 # Web routes
```

### Main Database Files
```
database/schema.sql                   # Main hearings database schema
database/manager.py                   # Database manager class
parsers/models.py                     # Pydantic models
config/settings.py                    # Application config
config/logging_config.py              # Logging setup
```

---

## 15. Summary

The existing CRS content ingestion system provides a **proven, production-ready template** for building the Brookings system. Key strengths include:

✅ **Modular architecture** (Fetcher, Parser, Manager)
✅ **Robust fetching** (Playwright for Cloudflare bypass)
✅ **Content deduplication** (SHA256 hashing)
✅ **Full-text search** (FTS5 with BM25)
✅ **Version tracking** (history preservation)
✅ **CLI integration** (Click commands)
✅ **Web UI** (Flask blueprints)
✅ **Logging & metrics** (ingestion tracking)

**Recommended Enhancements for Brookings:**
- Add **PDF extraction** (PyPDF2)
- Implement **async fetching** (`asyncio` + `aiohttp`)
- Support **PostgreSQL** alongside SQLite (via SQLAlchemy)
- Store **PDFs locally** (file system + DB path)
- Add **progress bars** (`tqdm`)
- Create **unified schema** for multi-source aggregation

**Next Steps:**
1. ✅ Complete this investigation document
2. → Design unified schema (`SCHEMA_DESIGN.md`)
3. → Build Brookings ingester (reuse CRS patterns)
4. → Integrate with existing CLI
5. → Test with 50+ Brookings documents
6. → Plan migration to unified document database
