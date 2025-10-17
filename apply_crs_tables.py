#!/usr/bin/env python3
"""Apply CRS-specific tables (content_ingestion_logs and product_content_fts)"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# SQL to create CRS-specific tables only
migration_sql = """
-- =============================================================================
-- Table: product_content_fts
-- Full-text search for content (extracted text from HTML)
-- =============================================================================

CREATE TABLE IF NOT EXISTS product_content_fts (
    content_id SERIAL PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    version_id INTEGER,

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
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.headings, '')), 'B') ||
        setweight(to_tsvector('english', COALESCE(NEW.text_content, '')), 'D');
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
"""

# Connect and execute
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute(migration_sql)
    print("✓ CRS-specific tables created successfully:")
    print("  - product_content_fts")
    print("  - content_ingestion_logs")
except Exception as e:
    print(f"✗ Migration error: {e}")
    import traceback
    traceback.print_exc()
finally:
    cur.close()
    conn.close()
