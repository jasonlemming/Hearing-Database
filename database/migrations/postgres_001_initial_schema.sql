-- PostgreSQL Migration: Initial CRS Database Schema
-- Date: 2025-10-10
-- Description: Complete CRS schema with PostgreSQL full-text search
--
-- Apply with: psql DATABASE_URL -f database/migrations/postgres_001_initial_schema.sql

-- =============================================================================
-- Enable required extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- Fuzzy text search

-- =============================================================================
-- Table: products
-- Stores CRS product metadata
-- =============================================================================

CREATE TABLE IF NOT EXISTS products (
    product_id VARCHAR(50) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    product_type VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    publication_date TIMESTAMP,
    summary TEXT,
    authors JSONB,  -- PostgreSQL native JSON type
    topics JSONB,
    url_html VARCHAR(500),
    url_pdf VARCHAR(500),
    raw_json JSONB NOT NULL,

    -- Search vector (auto-updated by trigger)
    search_vector TSVECTOR,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for products
CREATE INDEX IF NOT EXISTS idx_products_publication_date ON products(publication_date);
CREATE INDEX IF NOT EXISTS idx_products_status_type ON products(status, product_type);
CREATE INDEX IF NOT EXISTS idx_products_product_type ON products(product_type);
CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);

-- GIN index for full-text search (equivalent to FTS5)
CREATE INDEX IF NOT EXISTS idx_products_search_vector ON products USING GIN(search_vector);

-- GIN indexes for JSON fields (for fast JSON queries)
CREATE INDEX IF NOT EXISTS idx_products_authors ON products USING GIN(authors);
CREATE INDEX IF NOT EXISTS idx_products_topics ON products USING GIN(topics);

-- Trigger to auto-update search_vector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||  -- Weight: A (highest)
        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||  -- Weight: B
        setweight(to_tsvector('english', COALESCE(NEW.topics::text, '')), 'C');  -- Weight: C
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER products_search_vector_trigger
    BEFORE INSERT OR UPDATE ON products
    FOR EACH ROW
    EXECUTE FUNCTION products_search_vector_update();

-- =============================================================================
-- Table: product_versions
-- Stores content versions for CRS products
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_versions (
    version_id SERIAL PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,

    -- Content metadata (HTML stored in R2, referenced by blob_url)
    structure_json JSONB,  -- Table of contents, sections, headings
    blob_url TEXT,  -- R2 URL for HTML content

    -- Metadata
    html_url VARCHAR(500),
    content_hash VARCHAR(64),  -- SHA256
    word_count INTEGER,

    -- Tracking
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_current BOOLEAN DEFAULT TRUE,

    -- Constraints
    UNIQUE(product_id, version_number)
);

-- Indexes for product_versions
CREATE INDEX IF NOT EXISTS idx_versions_product ON product_versions(product_id);
CREATE INDEX IF NOT EXISTS idx_versions_current ON product_versions(is_current) WHERE is_current = TRUE;
CREATE INDEX IF NOT EXISTS idx_versions_ingested ON product_versions(ingested_at);
CREATE INDEX IF NOT EXISTS idx_versions_hash ON product_versions(content_hash);
CREATE INDEX IF NOT EXISTS idx_versions_blob_url ON product_versions(blob_url) WHERE blob_url IS NOT NULL;

-- =============================================================================
-- Table: product_content_fts
-- Full-text search for content (extracted text from HTML)
-- Note: This uses a hybrid approach - JSONB for structure, TSVECTOR for search
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_content_fts (
    content_id SERIAL PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    version_id INTEGER REFERENCES product_versions(version_id) ON DELETE CASCADE,

    -- Searchable content
    title TEXT,
    headings TEXT,  -- Extracted section headings
    text_content TEXT,  -- Full plain text

    -- Search vector (auto-updated by trigger)
    search_vector TSVECTOR,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    UNIQUE(product_id, version_id)
);

-- GIN index for content full-text search
CREATE INDEX IF NOT EXISTS idx_content_search_vector ON product_content_fts USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS idx_content_product ON product_content_fts(product_id);

-- Trigger to auto-update content search_vector
CREATE OR REPLACE FUNCTION content_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||  -- Title: highest weight
        setweight(to_tsvector('english', COALESCE(NEW.headings, '')), 'B') ||  -- Headings: medium-high
        setweight(to_tsvector('english', COALESCE(NEW.text_content, '')), 'D');  -- Content: lower weight
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER content_search_vector_trigger
    BEFORE INSERT OR UPDATE ON product_content_fts
    FOR EACH ROW
    EXECUTE FUNCTION content_search_vector_update();

-- =============================================================================
-- Table: content_ingestion_logs
-- Tracks content ingestion runs
-- =============================================================================

CREATE TABLE IF NOT EXISTS content_ingestion_logs (
    log_id SERIAL PRIMARY KEY,
    run_type VARCHAR(20) NOT NULL CHECK (run_type IN ('backfill', 'update', 'manual')),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,

    -- Metrics
    products_checked INTEGER DEFAULT 0,
    content_fetched INTEGER DEFAULT 0,
    content_updated INTEGER DEFAULT 0,
    content_skipped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    -- Details
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    error_details JSONB,

    -- Performance stats
    total_size_bytes BIGINT,
    avg_fetch_time_ms REAL,
    total_duration_seconds REAL
);

-- Indexes for ingestion logs
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_date ON content_ingestion_logs(started_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_type ON content_ingestion_logs(run_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_status ON content_ingestion_logs(status);

-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to search products with ranking
CREATE OR REPLACE FUNCTION search_products(search_query TEXT, max_results INTEGER DEFAULT 50)
RETURNS TABLE (
    product_id VARCHAR,
    title VARCHAR,
    summary TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.product_id,
        p.title,
        p.summary,
        ts_rank(p.search_vector, websearch_to_tsquery('english', search_query)) as rank
    FROM products p
    WHERE p.search_vector @@ websearch_to_tsquery('english', search_query)
    ORDER BY rank DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Function to search content with ranking
CREATE OR REPLACE FUNCTION search_content(search_query TEXT, max_results INTEGER DEFAULT 50)
RETURNS TABLE (
    product_id VARCHAR,
    title TEXT,
    rank REAL,
    has_content_match BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.product_id,
        c.title,
        ts_rank(c.search_vector, websearch_to_tsquery('english', search_query)) as rank,
        TRUE as has_content_match
    FROM product_content_fts c
    WHERE c.search_vector @@ websearch_to_tsquery('english', search_query)
    ORDER BY rank DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Migration Notes
-- =============================================================================
--
-- PostgreSQL Full-Text Search vs SQLite FTS5:
--
-- SQLite FTS5:
--   SELECT * FROM products_fts WHERE products_fts MATCH 'query' ORDER BY bm25()
--
-- PostgreSQL equivalent:
--   SELECT * FROM products WHERE search_vector @@ websearch_to_tsquery('query')
--   ORDER BY ts_rank(search_vector, websearch_to_tsquery('query'))
--
-- Key advantages:
--   - TSVECTOR auto-updates via triggers (no separate sync needed)
--   - Native JSONB support (faster than SQLite JSON)
--   - Better concurrent write performance
--   - websearch_to_tsquery supports "phrase matching" and -exclusions
--   - GIN indexes are very fast for full-text search
--
-- =============================================================================
