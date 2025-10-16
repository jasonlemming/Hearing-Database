-- Policy Library PostgreSQL Schema Migration
-- Generated from SQLAlchemy models in brookings_ingester/models/
-- Compatible with PostgreSQL 12+
-- Apply with: psql $BROOKINGS_DATABASE_URL -f database/migrations/policy_library_001_initial_schema.sql

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- For fuzzy text search

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Sources table (CRS, Brookings, GAO, Substack, etc.)
CREATE TABLE IF NOT EXISTS sources (
    source_id SERIAL PRIMARY KEY,
    source_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    description TEXT,
    url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sources_active ON sources(is_active);
CREATE INDEX idx_sources_code ON sources(source_code);

-- Organizations table (author affiliations, publishers)
CREATE TABLE IF NOT EXISTS organizations (
    organization_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    short_name VARCHAR(100),
    organization_type VARCHAR(50),
    url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_organizations_name ON organizations(name);
CREATE INDEX idx_organizations_type ON organizations(organization_type);

-- Authors table (deduplicated author entities)
CREATE TABLE IF NOT EXISTS authors (
    author_id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    organization_id INTEGER REFERENCES organizations(organization_id) ON DELETE SET NULL,
    email VARCHAR(200),
    orcid VARCHAR(50),
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_authors_full_name ON authors(full_name);
CREATE INDEX idx_authors_last_name ON authors(last_name);
CREATE INDEX idx_authors_org ON authors(organization_id);

-- Subjects table (hierarchical taxonomy)
CREATE TABLE IF NOT EXISTS subjects (
    subject_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    parent_subject_id INTEGER REFERENCES subjects(subject_id) ON DELETE SET NULL,
    description TEXT,
    source_vocabulary VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_subjects_name ON subjects(name);
CREATE INDEX idx_subjects_parent ON subjects(parent_subject_id);
CREATE INDEX idx_subjects_vocab ON subjects(source_vocabulary);

-- Documents table (main entity - source-agnostic)
CREATE TABLE IF NOT EXISTS documents (
    document_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
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
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Full-text search column (PostgreSQL tsvector)
    search_vector tsvector,

    CONSTRAINT uq_source_document UNIQUE (source_id, document_identifier)
);

-- Indexes for documents
CREATE INDEX idx_documents_source ON documents(source_id);
CREATE INDEX idx_documents_date ON documents(publication_date DESC);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_title ON documents USING gin(to_tsvector('english', title));
CREATE INDEX idx_documents_search_vector ON documents USING gin(search_vector);

-- Trigger to automatically update search_vector
CREATE OR REPLACE FUNCTION documents_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.full_text, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER documents_search_vector_trigger
BEFORE INSERT OR UPDATE ON documents
FOR EACH ROW
EXECUTE FUNCTION documents_search_vector_update();

-- ============================================================================
-- JUNCTION TABLES (Many-to-Many Relationships)
-- ============================================================================

-- Document-Author relationship
CREATE TABLE IF NOT EXISTS document_authors (
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(author_id) ON DELETE CASCADE,
    author_order INTEGER,
    role VARCHAR(50),
    PRIMARY KEY (document_id, author_id)
);

CREATE INDEX idx_document_authors_doc ON document_authors(document_id);
CREATE INDEX idx_document_authors_author ON document_authors(author_id);

-- Document-Subject relationship
CREATE TABLE IF NOT EXISTS document_subjects (
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
    relevance_score REAL DEFAULT 1.0,
    PRIMARY KEY (document_id, subject_id)
);

CREATE INDEX idx_document_subjects_doc ON document_subjects(document_id);
CREATE INDEX idx_document_subjects_subject ON document_subjects(subject_id);

-- ============================================================================
-- VERSION & FILE MANAGEMENT TABLES
-- ============================================================================

-- Document versions (version history tracking)
CREATE TABLE IF NOT EXISTS document_versions (
    version_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    html_content TEXT,
    text_content TEXT,
    structure_json TEXT,
    content_hash VARCHAR(64),
    word_count INTEGER,
    page_count INTEGER,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current BOOLEAN DEFAULT FALSE,
    notes TEXT,
    CONSTRAINT uq_document_version UNIQUE (document_id, version_number)
);

CREATE INDEX idx_document_versions_doc ON document_versions(document_id);
CREATE INDEX idx_document_versions_current ON document_versions(document_id, is_current);

-- Document files (PDF, HTML, text storage metadata)
CREATE TABLE IF NOT EXISTS document_files (
    file_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
    file_type VARCHAR(20) NOT NULL CHECK (file_type IN ('PDF', 'HTML', 'TEXT', 'XML')),
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    checksum VARCHAR(64),
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_document_files_doc ON document_files(document_id);
CREATE INDEX idx_document_files_type ON document_files(file_type);

-- ============================================================================
-- INGESTION TRACKING TABLES
-- ============================================================================

-- Ingestion logs (track ingestion runs)
CREATE TABLE IF NOT EXISTS ingestion_logs (
    log_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    run_type VARCHAR(20) NOT NULL CHECK (run_type IN ('backfill', 'update', 'manual')),
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    -- Metrics
    documents_checked INTEGER DEFAULT 0,
    documents_fetched INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_skipped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    -- Status and details
    status VARCHAR(20) NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    error_details TEXT,

    -- Performance metrics
    total_size_bytes INTEGER,
    avg_fetch_time_ms REAL,
    total_duration_seconds REAL
);

CREATE INDEX idx_ingestion_logs_source ON ingestion_logs(source_id);
CREATE INDEX idx_ingestion_logs_started ON ingestion_logs(started_at DESC);
CREATE INDEX idx_ingestion_logs_status ON ingestion_logs(status);

-- Ingestion errors (individual error records)
CREATE TABLE IF NOT EXISTS ingestion_errors (
    error_id SERIAL PRIMARY KEY,
    log_id INTEGER NOT NULL REFERENCES ingestion_logs(log_id) ON DELETE CASCADE,
    document_identifier VARCHAR(100),
    url VARCHAR(500),
    error_type VARCHAR(50) NOT NULL CHECK (error_type IN ('fetch_error', 'parse_error', 'validation_error', 'storage_error')),
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ingestion_errors_log ON ingestion_errors(log_id);
CREATE INDEX idx_ingestion_errors_type ON ingestion_errors(error_type);

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Insert default sources
INSERT INTO sources (source_code, name, short_name, description, url, is_active)
VALUES
    ('BROOKINGS', 'Brookings Institution', 'Brookings', 'Independent research and policy solutions', 'https://www.brookings.edu', TRUE),
    ('SUBSTACK', 'Substack Publications', 'Substack', 'Newsletter and independent journalism platform', 'https://substack.com', TRUE),
    ('CRS', 'Congressional Research Service', 'CRS', 'Public policy research for U.S. Congress', 'https://www.congress.gov', TRUE),
    ('GAO', 'Government Accountability Office', 'GAO', 'Independent, nonpartisan federal agency', 'https://www.gao.gov', TRUE)
ON CONFLICT (source_code) DO NOTHING;

-- ============================================================================
-- FUNCTIONS & VIEWS
-- ============================================================================

-- View: Recent documents with author names
CREATE OR REPLACE VIEW vw_recent_documents AS
SELECT
    d.document_id,
    d.title,
    d.publication_date,
    d.document_type,
    s.name AS source_name,
    s.source_code,
    STRING_AGG(a.full_name, ', ' ORDER BY da.author_order) AS authors,
    d.url,
    d.summary
FROM documents d
JOIN sources s ON d.source_id = s.source_id
LEFT JOIN document_authors da ON d.document_id = da.document_id
LEFT JOIN authors a ON da.author_id = a.author_id
GROUP BY d.document_id, d.title, d.publication_date, d.document_type, s.name, s.source_code, d.url, d.summary
ORDER BY d.publication_date DESC;

-- Function: Search documents with ranking
CREATE OR REPLACE FUNCTION search_documents(search_query TEXT, source_filter TEXT DEFAULT NULL, limit_count INTEGER DEFAULT 50)
RETURNS TABLE (
    document_id INTEGER,
    title TEXT,
    summary TEXT,
    publication_date DATE,
    source_name VARCHAR(100),
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.document_id,
        d.title,
        d.summary,
        d.publication_date,
        s.name AS source_name,
        ts_rank(d.search_vector, websearch_to_tsquery('english', search_query)) AS rank
    FROM documents d
    JOIN sources s ON d.source_id = s.source_id
    WHERE d.search_vector @@ websearch_to_tsquery('english', search_query)
        AND (source_filter IS NULL OR s.source_code = source_filter)
    ORDER BY rank DESC, d.publication_date DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- COMPLETION
-- ============================================================================

-- Summary
DO $$
BEGIN
    RAISE NOTICE 'Policy Library schema created successfully!';
    RAISE NOTICE 'Tables created: 11';
    RAISE NOTICE 'Views created: 1';
    RAISE NOTICE 'Functions created: 2';
    RAISE NOTICE 'Default sources inserted: 4';
END $$;
