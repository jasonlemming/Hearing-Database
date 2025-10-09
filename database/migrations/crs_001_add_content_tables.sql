-- Migration: Add content storage tables to CRS database
-- Date: 2025-10-09
-- Description: Adds product_versions and content_ingestion_logs tables for HTML content storage
--              Supports version tracking and full-text search on CRS report content

-- =============================================================================
-- Table: product_versions
-- Stores HTML content for each version of a CRS product
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id VARCHAR NOT NULL,
    version_number INTEGER NOT NULL,

    -- Content storage (hybrid approach: HTML + text + structure)
    html_content TEXT,              -- Cleaned HTML for display
    text_content TEXT,              -- Plain text for full-text search
    structure_json JSON,            -- Table of contents, sections, headings

    -- Metadata
    html_url VARCHAR,               -- Source URL (e.g., https://www.congress.gov/crs_external_products/RL/HTML/RL31980.html)
    content_hash VARCHAR,           -- SHA256 hash of text_content (detect changes)
    word_count INTEGER,             -- Word count for analytics

    -- Tracking
    ingested_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_current BOOLEAN DEFAULT 1,  -- Only one version per product should be current

    -- Foreign key constraint (references products table)
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,

    -- Uniqueness constraint
    UNIQUE(product_id, version_number)
);

-- Indexes for product_versions
CREATE INDEX IF NOT EXISTS idx_versions_product ON product_versions(product_id);
CREATE INDEX IF NOT EXISTS idx_versions_current ON product_versions(is_current) WHERE is_current = 1;
CREATE INDEX IF NOT EXISTS idx_versions_ingested ON product_versions(ingested_at);
CREATE INDEX IF NOT EXISTS idx_versions_hash ON product_versions(content_hash);

-- =============================================================================
-- Table: content_ingestion_logs
-- Tracks all content ingestion runs (backfills and updates)
-- =============================================================================

CREATE TABLE IF NOT EXISTS content_ingestion_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type VARCHAR NOT NULL,      -- 'backfill', 'update', 'manual'
    started_at DATETIME NOT NULL,
    completed_at DATETIME,

    -- Metrics
    products_checked INTEGER DEFAULT 0,
    content_fetched INTEGER DEFAULT 0,
    content_updated INTEGER DEFAULT 0,
    content_skipped INTEGER DEFAULT 0,
    errors_count INTEGER DEFAULT 0,

    -- Details
    status VARCHAR NOT NULL,        -- 'running', 'completed', 'failed', 'partial'
    error_details JSON,             -- Array of error objects

    -- Performance stats
    total_size_bytes INTEGER,
    avg_fetch_time_ms REAL,
    total_duration_seconds REAL,

    -- Constraints
    CHECK (run_type IN ('backfill', 'update', 'manual')),
    CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

-- Indexes for content_ingestion_logs
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_date ON content_ingestion_logs(started_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_type ON content_ingestion_logs(run_type);
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_status ON content_ingestion_logs(status);

-- =============================================================================
-- FTS Table: product_content_fts
-- Full-text search index for CRS content with weighted columns
-- =============================================================================

CREATE VIRTUAL TABLE IF NOT EXISTS product_content_fts USING fts5(
    product_id UNINDEXED,
    version_id UNINDEXED,
    title,                          -- Weight: 5.0 (most important)
    headings,                       -- Weight: 3.0 (section headings)
    text_content,                   -- Weight: 1.0 (body text)
    tokenize='porter'
);

-- =============================================================================
-- Migration Notes
-- =============================================================================
--
-- To apply this migration to the CRS database:
--   sqlite3 crs_products.db < database/migrations/crs_001_add_content_tables.sql
--
-- To verify:
--   sqlite3 crs_products.db ".schema product_versions"
--   sqlite3 crs_products.db ".schema content_ingestion_logs"
--   sqlite3 crs_products.db ".schema product_content_fts"
--
-- Storage estimates:
--   - 6,500 products × ~200KB avg = ~1.3GB for current versions
--   - Version history will add ~10-20% over time
--   - FTS index adds ~30-40% of text content size
--
-- =============================================================================
