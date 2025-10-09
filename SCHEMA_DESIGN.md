# Unified Research Document Schema Design

**Date:** October 9, 2025
**Purpose:** Design a flexible, extensible schema for CRS, Brookings, and GAO research documents

---

## Table of Contents
1. [Design Philosophy](#design-philosophy)
2. [Entity-Relationship Diagram](#entity-relationship-diagram)
3. [Table Definitions](#table-definitions)
4. [Index Strategy](#index-strategy)
5. [Full-Text Search](#full-text-search)
6. [Migration Path](#migration-path)
7. [Implementation Notes](#implementation-notes)

---

## 1. Design Philosophy

### Core Principles

1. **Source-Agnostic Core, Source-Specific Extensions**
   - Common fields in main `documents` table
   - Source-specific metadata in JSONB `metadata` field
   - Flexible enough for CRS, Brookings, GAO, and future sources

2. **Version Tracking**
   - Documents can have multiple versions
   - One version marked as `is_current = TRUE`
   - Preserves history while providing canonical reference

3. **Dual Storage Strategy**
   - Structured data in database (fast queries)
   - Files on disk (PDFs, extracted text)
   - Database stores file paths, not content blobs

4. **Multi-Backend Support**
   - SQLite for development (single-file, portable)
   - PostgreSQL for production (scalable, JSONB, tsvector)
   - Schema compatible with both via abstraction layer

5. **Rich Metadata**
   - Many-to-many relationships for authors, subjects, topics
   - Deduplicated entities (authors, organizations)
   - Structured document classification

6. **Comprehensive Search**
   - SQLite: FTS5 virtual tables with BM25
   - PostgreSQL: Generated `tsvector` columns with GIN indexes
   - Weighted search (title > headings > body)

7. **Audit & Provenance**
   - Track ingestion runs, errors, metrics
   - Timestamp all records (created_at, updated_at)
   - Preserve source URLs and checksums

---

## 2. Entity-Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED DOCUMENT SCHEMA                          │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────┐       ┌──────────────────┐       ┌────────────────┐
│   sources    │◄──────│    documents     │──────►│ document_files │
└──────────────┘       └──────────────────┘       └────────────────┘
                              │      │
                  ┌───────────┘      └───────────┐
                  │                              │
                  ▼                              ▼
        ┌─────────────────┐          ┌─────────────────┐
        │ document_authors│          │ document_subjects│
        └─────────────────┘          └─────────────────┘
                  │                              │
                  ▼                              ▼
           ┌──────────┐                  ┌──────────┐
           │ authors  │                  │ subjects │
           └──────────┘                  └──────────┘

┌──────────────────┐       ┌──────────────────────┐
│document_versions │◄──────│     documents        │
└──────────────────┘       └──────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────┐        ┌─────────────────────┐
│documents_fts    │        │ documents_metadata  │
│(SQLite FTS5)    │        │(PostgreSQL tsvector)│
└─────────────────┘        └─────────────────────┘

┌──────────────────┐       ┌──────────────────────┐
│  organizations   │       │  ingestion_logs      │
└──────────────────┘       └──────────────────────┘
```

### Relationships

- **documents** ↔ **sources**: Many-to-One (each document has one source)
- **documents** ↔ **authors**: Many-to-Many (via `document_authors`)
- **documents** ↔ **subjects**: Many-to-Many (via `document_subjects`)
- **documents** ↔ **document_versions**: One-to-Many (version history)
- **documents** ↔ **document_files**: One-to-Many (PDF, HTML, text files)
- **authors** ↔ **organizations**: Many-to-One (optional affiliation)

---

## 3. Table Definitions

### 3.1 Core Tables

#### `sources`
Defines document sources (CRS, Brookings, GAO, etc.)

**SQLite:**
```sql
CREATE TABLE sources (
    source_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code VARCHAR(20) NOT NULL UNIQUE,  -- 'CRS', 'BROOKINGS', 'GAO'
    name VARCHAR(100) NOT NULL,               -- 'Congressional Research Service'
    short_name VARCHAR(50),                   -- 'CRS'
    description TEXT,
    url VARCHAR(500),                          -- Base URL
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**PostgreSQL:**
```sql
CREATE TABLE sources (
    source_id SERIAL PRIMARY KEY,
    source_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    description TEXT,
    url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Seed Data:**
```sql
INSERT INTO sources (source_code, name, short_name, url) VALUES
('CRS', 'Congressional Research Service', 'CRS', 'https://www.congress.gov'),
('BROOKINGS', 'Brookings Institution', 'Brookings', 'https://www.brookings.edu'),
('GAO', 'Government Accountability Office', 'GAO', 'https://www.gao.gov');
```

---

#### `documents`
Main document table (source-agnostic core)

**SQLite:**
```sql
CREATE TABLE documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    document_identifier VARCHAR(100) NOT NULL,  -- Source's internal ID (product_id, URL slug, etc.)
    title TEXT NOT NULL,
    document_type VARCHAR(50),                  -- 'Report', 'Policy Brief', 'In Focus', 'Insight'
    status VARCHAR(20) DEFAULT 'Active',        -- 'Active', 'Archived', 'Superseded'
    publication_date DATE,
    summary TEXT,                                -- Abstract/description
    full_text TEXT,                              -- Extracted plain text (for search)
    url VARCHAR(500),                            -- Primary URL (HTML page)
    pdf_url VARCHAR(500),                        -- Direct PDF link
    page_count INTEGER,
    word_count INTEGER,
    checksum VARCHAR(64),                        -- SHA256 of full_text (for deduplication)
    metadata TEXT,                               -- JSON: source-specific fields

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    -- Foreign keys
    FOREIGN KEY (source_id) REFERENCES sources(source_id),

    -- Constraints
    UNIQUE(source_id, document_identifier)
);
```

**PostgreSQL:**
```sql
CREATE TABLE documents (
    document_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    document_identifier VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    document_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'Active',
    publication_date DATE,
    summary TEXT,
    full_text TEXT,
    url VARCHAR(500),
    pdf_url VARCHAR(500),
    page_count INTEGER,
    word_count INTEGER,
    checksum VARCHAR(64),
    metadata JSONB,                              -- Native JSONB for PostgreSQL

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (source_id) REFERENCES sources(source_id),
    UNIQUE(source_id, document_identifier)
);

-- Add trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

**Metadata JSON Examples:**

*CRS Document:*
```json
{
  "crs_version": 42,
  "crs_topics": ["Healthcare", "Medicare"],
  "crs_programs": ["Health Policy"],
  "crs_product_type": "Report"
}
```

*Brookings Document:*
```json
{
  "brookings_programs": ["Economic Studies", "Foreign Policy"],
  "brookings_research_areas": ["Economy & Fiscal Policy"],
  "brookings_formats": ["Report"],
  "brookings_series": "Brookings Papers on Economic Activity"
}
```

*GAO Document:*
```json
{
  "gao_product_number": "GAO-25-1234",
  "gao_engagement_type": "Audit",
  "gao_agencies": ["Department of Defense"],
  "gao_recommendations": 12
}
```

---

#### `document_versions`
Version history for documents (supports content updates)

**SQLite:**
```sql
CREATE TABLE document_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    html_content TEXT,                          -- Cleaned HTML for display
    text_content TEXT,                          -- Plain text for search
    structure_json TEXT,                        -- JSON: TOC, headings, sections
    content_hash VARCHAR(64),                   -- SHA256 of text_content
    word_count INTEGER,
    page_count INTEGER,
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,           -- Only one current version per document
    notes TEXT,                                 -- Change description

    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    UNIQUE(document_id, version_number)
);

-- Index to ensure only one current version
CREATE UNIQUE INDEX idx_document_versions_current
ON document_versions(document_id)
WHERE is_current = TRUE;
```

**PostgreSQL:**
```sql
CREATE TABLE document_versions (
    version_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    html_content TEXT,
    text_content TEXT,
    structure_json JSONB,                        -- Native JSONB
    content_hash VARCHAR(64),
    word_count INTEGER,
    page_count INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,
    notes TEXT,

    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    UNIQUE(document_id, version_number)
);

CREATE UNIQUE INDEX idx_document_versions_current
ON document_versions(document_id)
WHERE is_current = TRUE;
```

---

#### `document_files`
File storage metadata (PDFs, text files, HTML)

**SQLite:**
```sql
CREATE TABLE document_files (
    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    file_type VARCHAR(20) NOT NULL,             -- 'PDF', 'HTML', 'TEXT'
    file_path VARCHAR(500) NOT NULL,            -- Relative path: data/pdfs/brookings/12345.pdf
    file_size INTEGER,                          -- Bytes
    mime_type VARCHAR(100),                     -- 'application/pdf', 'text/html'
    checksum VARCHAR(64),                       -- SHA256 of file
    downloaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    CHECK (file_type IN ('PDF', 'HTML', 'TEXT', 'XML'))
);
```

**PostgreSQL:** *(Same as SQLite, replace INTEGER PRIMARY KEY with SERIAL)*

---

### 3.2 Relationship Tables

#### `authors`
Deduplicated author entities

**SQLite:**
```sql
CREATE TABLE authors (
    author_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name VARCHAR(200) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    organization_id INTEGER,                    -- Optional affiliation
    email VARCHAR(200),
    orcid VARCHAR(50),                          -- ORCID identifier (if available)
    bio TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id)
);
```

**PostgreSQL:** *(Same, replace INTEGER PRIMARY KEY with SERIAL)*

---

#### `document_authors`
Many-to-many: documents ↔ authors

**SQLite:**
```sql
CREATE TABLE document_authors (
    document_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_order INTEGER,                       -- Position in author list (1, 2, 3...)
    role VARCHAR(50),                           -- 'Lead Author', 'Contributing Author'

    PRIMARY KEY (document_id, author_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE CASCADE
);
```

**PostgreSQL:** *(Same)*

---

#### `subjects`
Subject/topic taxonomy (shared across sources)

**SQLite:**
```sql
CREATE TABLE subjects (
    subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    parent_subject_id INTEGER,                  -- Hierarchical taxonomy
    description TEXT,
    source_vocabulary VARCHAR(50),              -- 'CRS', 'LCSH', 'Custom'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_subject_id) REFERENCES subjects(subject_id)
);
```

**PostgreSQL:** *(Same, replace INTEGER PRIMARY KEY with SERIAL)*

**Example Hierarchy:**
```
Healthcare (parent_subject_id: NULL)
├── Medicare (parent_subject_id: 1)
├── Medicaid (parent_subject_id: 1)
└── Health Insurance (parent_subject_id: 1)
```

---

#### `document_subjects`
Many-to-many: documents ↔ subjects

**SQLite:**
```sql
CREATE TABLE document_subjects (
    document_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    relevance_score REAL DEFAULT 1.0,           -- Optional: weight for ranking

    PRIMARY KEY (document_id, subject_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);
```

**PostgreSQL:** *(Same)*

---

#### `organizations`
Organizations (author affiliations, publishers)

**SQLite:**
```sql
CREATE TABLE organizations (
    organization_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL UNIQUE,
    short_name VARCHAR(100),
    organization_type VARCHAR(50),              -- 'Think Tank', 'Government Agency', 'University'
    url VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**PostgreSQL:** *(Same, replace INTEGER PRIMARY KEY with SERIAL)*

**Seed Data:**
```sql
INSERT INTO organizations (name, short_name, organization_type, url) VALUES
('Brookings Institution', 'Brookings', 'Think Tank', 'https://www.brookings.edu'),
('Congressional Research Service', 'CRS', 'Government Agency', 'https://www.congress.gov'),
('Government Accountability Office', 'GAO', 'Government Agency', 'https://www.gao.gov');
```

---

### 3.3 Audit & Logging Tables

#### `ingestion_logs`
Tracks ingestion runs (backfills, updates)

**SQLite:**
```sql
CREATE TABLE ingestion_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    run_type VARCHAR(20) NOT NULL,              -- 'backfill', 'update', 'manual'
    started_at DATETIME NOT NULL,
    completed_at DATETIME,

    -- Metrics
    documents_checked INTEGER DEFAULT 0,
    documents_fetched INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_skipped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    -- Details
    status VARCHAR(20) NOT NULL,                -- 'running', 'completed', 'failed', 'partial'
    error_details TEXT,                         -- JSON array of error objects

    -- Performance
    total_size_bytes INTEGER,
    avg_fetch_time_ms REAL,
    total_duration_seconds REAL,

    FOREIGN KEY (source_id) REFERENCES sources(source_id),
    CHECK (run_type IN ('backfill', 'update', 'manual')),
    CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);
```

**PostgreSQL:** *(Same, replace INTEGER PRIMARY KEY with SERIAL, TEXT with JSONB for error_details)*

---

#### `ingestion_errors`
Individual error records

**SQLite:**
```sql
CREATE TABLE ingestion_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL,
    document_identifier VARCHAR(100),           -- Source's internal ID (if known)
    url VARCHAR(500),
    error_type VARCHAR(50) NOT NULL,            -- 'fetch_error', 'parse_error', 'validation_error'
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (log_id) REFERENCES ingestion_logs(log_id) ON DELETE CASCADE,
    CHECK (error_type IN ('fetch_error', 'parse_error', 'validation_error', 'storage_error'))
);
```

**PostgreSQL:** *(Same, replace INTEGER PRIMARY KEY with SERIAL)*

---

## 4. Index Strategy

### Primary Indexes (Automatic)
- All primary keys (automatically indexed)
- All foreign keys (should be indexed)

### Secondary Indexes

**SQLite:**
```sql
-- documents table
CREATE INDEX idx_documents_source ON documents(source_id);
CREATE INDEX idx_documents_date ON documents(publication_date DESC);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_checksum ON documents(checksum);
CREATE INDEX idx_documents_identifier ON documents(source_id, document_identifier);

-- document_versions table
CREATE INDEX idx_versions_document ON document_versions(document_id);
CREATE INDEX idx_versions_current ON document_versions(is_current) WHERE is_current = TRUE;
CREATE INDEX idx_versions_ingested ON document_versions(ingested_at DESC);

-- document_files table
CREATE INDEX idx_files_document ON document_files(document_id);
CREATE INDEX idx_files_type ON document_files(file_type);

-- authors table
CREATE INDEX idx_authors_name ON authors(last_name, first_name);
CREATE INDEX idx_authors_organization ON authors(organization_id);

-- document_authors table
CREATE INDEX idx_doc_authors_author ON document_authors(author_id);
CREATE INDEX idx_doc_authors_document ON document_authors(document_id);

-- subjects table
CREATE INDEX idx_subjects_parent ON subjects(parent_subject_id);

-- document_subjects table
CREATE INDEX idx_doc_subjects_subject ON document_subjects(subject_id);
CREATE INDEX idx_doc_subjects_document ON document_subjects(document_id);

-- ingestion_logs table
CREATE INDEX idx_ingestion_logs_source ON ingestion_logs(source_id);
CREATE INDEX idx_ingestion_logs_date ON ingestion_logs(started_at DESC);
CREATE INDEX idx_ingestion_logs_status ON ingestion_logs(status);
```

**PostgreSQL (additional):**
```sql
-- JSONB indexes for metadata queries
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);

-- Full-text search (see next section)
CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);
```

---

## 5. Full-Text Search

### SQLite: FTS5 Virtual Tables

#### Metadata FTS (fast, lightweight)
```sql
CREATE VIRTUAL TABLE documents_fts USING fts5(
    document_id UNINDEXED,
    source_code UNINDEXED,
    title,              -- Weight: 3.0
    summary,            -- Weight: 1.0
    authors,            -- Weight: 2.0
    subjects,           -- Weight: 2.0
    tokenize='porter'
);

-- Populate trigger
CREATE TRIGGER documents_fts_insert AFTER INSERT ON documents
BEGIN
    INSERT INTO documents_fts(document_id, source_code, title, summary, authors, subjects)
    SELECT
        NEW.document_id,
        s.source_code,
        NEW.title,
        COALESCE(NEW.summary, ''),
        COALESCE(GROUP_CONCAT(a.full_name, ' '), ''),
        COALESCE(GROUP_CONCAT(sub.name, ' '), '')
    FROM sources s
    LEFT JOIN document_authors da ON NEW.document_id = da.document_id
    LEFT JOIN authors a ON da.author_id = a.author_id
    LEFT JOIN document_subjects ds ON NEW.document_id = ds.document_id
    LEFT JOIN subjects sub ON ds.subject_id = sub.subject_id
    WHERE s.source_id = NEW.source_id;
END;
```

#### Content FTS (full-text)
```sql
CREATE VIRTUAL TABLE document_content_fts USING fts5(
    version_id UNINDEXED,
    document_id UNINDEXED,
    title,              -- Weight: 5.0
    headings,           -- Weight: 3.0
    text_content,       -- Weight: 1.0
    tokenize='porter'
);

-- Populate trigger
CREATE TRIGGER document_versions_fts_insert AFTER INSERT ON document_versions
BEGIN
    INSERT INTO document_content_fts(version_id, document_id, title, headings, text_content)
    SELECT
        NEW.version_id,
        NEW.document_id,
        d.title,
        COALESCE(json_extract(NEW.structure_json, '$.headings'), ''),
        COALESCE(NEW.text_content, '')
    FROM documents d
    WHERE d.document_id = NEW.document_id;
END;
```

#### Search Query (SQLite)
```sql
-- Combined metadata + content search
WITH content_matches AS (
    SELECT
        document_id,
        bm25(document_content_fts, 5.0, 3.0, 1.0) as content_score
    FROM document_content_fts
    WHERE document_content_fts MATCH ?
),
metadata_matches AS (
    SELECT
        document_id,
        bm25(documents_fts, 3.0, 1.0, 2.0, 2.0) as metadata_score
    FROM documents_fts
    WHERE documents_fts MATCH ?
)
SELECT
    d.*,
    COALESCE(cm.content_score, 0) + COALESCE(mm.metadata_score, 0) as combined_score
FROM documents d
LEFT JOIN content_matches cm ON d.document_id = cm.document_id
LEFT JOIN metadata_matches mm ON d.document_id = mm.document_id
WHERE cm.document_id IS NOT NULL OR mm.document_id IS NOT NULL
ORDER BY combined_score
LIMIT 50;
```

---

### PostgreSQL: Generated tsvector Column

```sql
-- Add search_vector column to documents
ALTER TABLE documents
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(full_text, '')), 'C')
) STORED;

-- Create GIN index
CREATE INDEX idx_documents_search ON documents USING GIN (search_vector);

-- Search query (PostgreSQL)
SELECT
    d.*,
    ts_rank_cd(d.search_vector, query) AS rank
FROM documents d,
     to_tsquery('english', ?) AS query
WHERE d.search_vector @@ query
ORDER BY rank DESC
LIMIT 50;
```

---

## 6. Migration Path

### Phase 1: Keep Separate Databases (Current)
**Timeframe:** Immediate

**Status:**
- `crs_products.db` (existing)
- `brookings_products.db` (new, this project)
- Main `congressional_hearings.db` (unchanged)

**Rationale:**
- Minimal disruption
- Independent development
- Easy to test and deploy

**Limitations:**
- No cross-source search
- Duplicate infrastructure
- Manual synchronization

---

### Phase 2: Create Unified Database (Future)
**Timeframe:** After Brookings system is stable

**Steps:**

1. **Create unified database**
   ```bash
   sqlite3 research_documents.db < schema_design.sql
   ```

2. **Migrate CRS data**
   ```python
   # Migration script: migrate_crs.py
   - Read from crs_products.db
   - Insert into research_documents.db
   - Set source_id = 1 (CRS)
   - Map product_id → document_identifier
   - Preserve version history
   ```

3. **Migrate Brookings data**
   ```python
   # Migration script: migrate_brookings.py
   - Read from brookings_products.db
   - Insert into research_documents.db
   - Set source_id = 2 (BROOKINGS)
   ```

4. **Update applications**
   - Update CLI commands to use new database
   - Update Flask blueprints
   - Add unified search UI

5. **Deprecate old databases**
   - Archive `crs_products.db` and `brookings_products.db`
   - Remove old code paths

---

### Phase 3: PostgreSQL Migration (Production)
**Timeframe:** When scaling beyond 100K documents

**Steps:**

1. **Install PostgreSQL**
   ```bash
   brew install postgresql  # macOS
   sudo apt install postgresql  # Ubuntu
   ```

2. **Convert schema**
   - Replace `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
   - Replace `TEXT` → `JSONB` (for metadata fields)
   - Add `tsvector` columns for search
   - Add triggers for `updated_at`

3. **Migrate data**
   ```bash
   # Use pgloader or custom Python script
   python migrate_to_postgres.py
   ```

4. **Update connection string**
   ```python
   # .env
   DATABASE_URL=postgresql://user:pass@localhost/research_documents
   ```

5. **Test thoroughly**
   - Verify all queries work
   - Test full-text search
   - Benchmark performance

---

## 7. Implementation Notes

### 7.1 Source-Specific Metadata Examples

#### CRS Metadata Schema
```json
{
  "crs_version": 42,
  "crs_topics": ["Healthcare", "Medicare", "Aging"],
  "crs_programs": ["Health Policy"],
  "crs_product_type": "Report",
  "crs_classification": "RL31980",
  "crs_updates": [
    {"date": "2025-01-15", "description": "Updated statistics"},
    {"date": "2024-10-01", "description": "Initial publication"}
  ]
}
```

#### Brookings Metadata Schema
```json
{
  "brookings_programs": ["Economic Studies", "Foreign Policy"],
  "brookings_research_areas": ["Economy & Fiscal Policy", "Taxes and Budgets"],
  "brookings_formats": ["Report"],
  "brookings_series": "Brookings Papers on Economic Activity",
  "brookings_event": "BPEA Conference, Fall 2024",
  "brookings_slug": "economic-mobility-united-states"
}
```

#### GAO Metadata Schema
```json
{
  "gao_product_number": "GAO-25-1234",
  "gao_engagement_type": "Audit",
  "gao_agencies": ["Department of Defense", "Department of Homeland Security"],
  "gao_topics": ["Defense Capabilities and Management"],
  "gao_recommendations": 12,
  "gao_recommendations_implemented": 8,
  "gao_report_to": ["Committee on Armed Services", "Committee on Homeland Security"]
}
```

---

### 7.2 Database Abstraction Layer

To support both SQLite and PostgreSQL, create an abstraction layer:

**File:** `database/connection.py`
```python
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class DatabaseConnection:
    def __init__(self):
        db_url = os.getenv('DATABASE_URL', 'sqlite:///research_documents.db')

        if db_url.startswith('sqlite'):
            # SQLite-specific options
            self.engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False},
                echo=False
            )
        else:
            # PostgreSQL-specific options
            self.engine = create_engine(
                db_url,
                pool_size=10,
                max_overflow=20,
                echo=False
            )

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )

    def get_session(self):
        return self.SessionLocal()

    def is_postgresql(self):
        return 'postgresql' in str(self.engine.url)

    def is_sqlite(self):
        return 'sqlite' in str(self.engine.url)
```

---

### 7.3 Full-Text Search Abstraction

**File:** `search/full_text.py`
```python
class FullTextSearch:
    def __init__(self, db_connection):
        self.db = db_connection

    def search(self, query: str, limit: int = 50):
        if self.db.is_sqlite():
            return self._search_sqlite(query, limit)
        else:
            return self._search_postgresql(query, limit)

    def _search_sqlite(self, query, limit):
        # Use FTS5 tables
        sql = """
        SELECT d.*, bm25(documents_fts) as score
        FROM documents_fts
        JOIN documents d ON documents_fts.document_id = d.document_id
        WHERE documents_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """
        # Execute and return results

    def _search_postgresql(self, query, limit):
        # Use tsvector
        sql = """
        SELECT *, ts_rank_cd(search_vector, query) AS rank
        FROM documents, to_tsquery('english', ?) AS query
        WHERE search_vector @@ query
        ORDER BY rank DESC
        LIMIT ?
        """
        # Execute and return results
```

---

### 7.4 Deduplication Strategy

**Checksum-based deduplication:**
```python
import hashlib

def calculate_checksum(text_content: str) -> str:
    """Calculate SHA256 checksum of text content"""
    return hashlib.sha256(text_content.encode('utf-8')).hexdigest()

def document_exists(source_id: int, document_identifier: str) -> bool:
    """Check if document already exists"""
    query = """
    SELECT document_id FROM documents
    WHERE source_id = ? AND document_identifier = ?
    """
    # Execute query

def needs_update(document_id: int, new_checksum: str) -> bool:
    """Check if document content has changed"""
    query = """
    SELECT checksum FROM documents WHERE document_id = ?
    """
    # Execute query, compare checksums
```

---

### 7.5 Version Management

**Creating new version:**
```python
def create_new_version(document_id: int, content: dict) -> int:
    """
    Create new version, mark as current, and demote old versions
    """
    # 1. Get current max version number
    max_version = get_max_version_number(document_id)
    new_version_number = max_version + 1

    # 2. Insert new version
    version_id = insert_version(
        document_id=document_id,
        version_number=new_version_number,
        html_content=content['html'],
        text_content=content['text'],
        structure_json=content['structure'],
        content_hash=calculate_checksum(content['text']),
        is_current=False
    )

    # 3. Mark all versions as not current
    mark_all_versions_not_current(document_id)

    # 4. Mark new version as current
    mark_version_current(version_id)

    # 5. Update FTS index
    update_fts_index(version_id)

    return version_id
```

---

## 8. Storage Recommendations

### File System Layout
```
data/
├── pdfs/
│   ├── crs/
│   │   ├── RL31980.pdf
│   │   ├── R45678.pdf
│   │   └── ...
│   ├── brookings/
│   │   ├── economic-mobility-2025.pdf
│   │   ├── foreign-policy-brief-001.pdf
│   │   └── ...
│   └── gao/
│       ├── GAO-25-1234.pdf
│       └── ...
├── text/
│   ├── crs/
│   │   ├── RL31980.txt
│   │   └── ...
│   ├── brookings/
│   │   └── ...
│   └── gao/
│       └── ...
└── html/
    ├── crs/
    ├── brookings/
    └── gao/
```

### File Naming Convention
- **CRS:** `{product_id}.{ext}` (e.g., `RL31980.pdf`)
- **Brookings:** `{slug}.{ext}` (e.g., `economic-mobility-2025.pdf`)
- **GAO:** `{product_number}.{ext}` (e.g., `GAO-25-1234.pdf`)

### Database Storage
- **Paths stored as relative paths:** `data/pdfs/brookings/economic-mobility-2025.pdf`
- **Checksums stored for integrity:** SHA256
- **File sizes tracked:** For storage audits

---

## 9. Query Examples

### Find all Brookings documents on healthcare
```sql
SELECT d.*, s.name as source_name
FROM documents d
JOIN sources s ON d.source_id = s.source_id
JOIN document_subjects ds ON d.document_id = ds.document_id
JOIN subjects sub ON ds.subject_id = sub.subject_id
WHERE s.source_code = 'BROOKINGS'
  AND sub.name LIKE '%Healthcare%'
ORDER BY d.publication_date DESC;
```

### Find documents by author across all sources
```sql
SELECT d.*, s.name as source_name, a.full_name as author_name
FROM documents d
JOIN sources s ON d.source_id = s.source_id
JOIN document_authors da ON d.document_id = da.document_id
JOIN authors a ON da.author_id = a.author_id
WHERE a.full_name LIKE '%Smith%'
ORDER BY d.publication_date DESC;
```

### Get document with current version and all files
```sql
SELECT
    d.*,
    dv.version_number,
    dv.word_count,
    dv.ingested_at as version_date,
    GROUP_CONCAT(df.file_type || ':' || df.file_path, '; ') as files
FROM documents d
LEFT JOIN document_versions dv ON d.document_id = dv.document_id AND dv.is_current = TRUE
LEFT JOIN document_files df ON d.document_id = df.document_id
WHERE d.document_id = ?
GROUP BY d.document_id;
```

### Ingestion statistics by source
```sql
SELECT
    s.name as source_name,
    COUNT(DISTINCT d.document_id) as total_documents,
    COUNT(DISTINCT dv.version_id) as total_versions,
    SUM(dv.word_count) as total_words,
    AVG(dv.word_count) as avg_words_per_doc,
    MIN(d.publication_date) as earliest_doc,
    MAX(d.publication_date) as latest_doc
FROM sources s
LEFT JOIN documents d ON s.source_id = d.source_id
LEFT JOIN document_versions dv ON d.document_id = dv.document_id AND dv.is_current = TRUE
GROUP BY s.source_id
ORDER BY total_documents DESC;
```

---

## 10. Summary

This unified schema design provides:

✅ **Flexibility** - Accommodates CRS, Brookings, GAO, and future sources
✅ **Consistency** - Common core with source-specific extensions
✅ **Scalability** - Supports both SQLite (dev) and PostgreSQL (prod)
✅ **Searchability** - Dual FTS strategy (metadata + content)
✅ **Auditability** - Version tracking, ingestion logs, error tracking
✅ **Extensibility** - Easy to add new sources and metadata fields
✅ **Performance** - Comprehensive indexes for fast queries

**Next Steps:**
1. ✅ Complete schema design document
2. → Implement schema in SQLite (for Brookings project)
3. → Create SQLAlchemy models
4. → Build database manager with abstraction layer
5. → Test with sample data from each source
6. → Plan migration strategy from separate databases
