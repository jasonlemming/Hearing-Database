-- PostgreSQL Migration: CRS Library Enhancements
-- Date: 2025-10-17
-- Description: Add missing fields for CRS updater compatibility
--
-- Apply with: psql DATABASE_URL -f database/migrations/postgres_003_crs_enhancements.sql

-- =============================================================================
-- Add missing fields to products table
-- =============================================================================

-- Add update_date if it doesn't exist (alias for updated_at, used by CRS scrapers)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'update_date'
    ) THEN
        ALTER TABLE products ADD COLUMN update_date TIMESTAMP;

        -- Populate update_date from updated_at for existing rows
        UPDATE products SET update_date = updated_at WHERE update_date IS NULL;

        -- Create index for update_date (used by CRS updater for lookback queries)
        CREATE INDEX idx_products_update_date ON products(update_date);

        COMMENT ON COLUMN products.update_date IS 'Date product was last updated (from CRS API)';
    END IF;
END $$;

-- Add product_number if it doesn't exist (CRS report number like R12345)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'product_number'
    ) THEN
        ALTER TABLE products ADD COLUMN product_number VARCHAR(50);

        -- Create index for product_number
        CREATE INDEX idx_products_product_number ON products(product_number);

        COMMENT ON COLUMN products.product_number IS 'CRS report number (e.g., R12345)';
    END IF;
END $$;

-- Add html_url if it doesn't exist (alias for url_html, used by some scrapers)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'products' AND column_name = 'html_url'
    ) THEN
        ALTER TABLE products ADD COLUMN html_url VARCHAR(500);

        -- Populate html_url from url_html for existing rows
        UPDATE products SET html_url = url_html WHERE html_url IS NULL;

        COMMENT ON COLUMN products.html_url IS 'URL to HTML version of report (alias for url_html)';
    END IF;
END $$;

-- =============================================================================
-- Ensure product_content_fts has correct structure
-- =============================================================================

-- Verify product_content_fts table has all required columns
DO $$
BEGIN
    -- Ensure version_id column exists and has correct foreign key
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'product_content_fts' AND column_name = 'version_id'
    ) THEN
        ALTER TABLE product_content_fts
        ADD COLUMN version_id INTEGER REFERENCES product_versions(version_id) ON DELETE CASCADE;
    END IF;
END $$;

-- =============================================================================
-- Update triggers to sync update_date with updated_at
-- =============================================================================

-- Modify products trigger to also update update_date
CREATE OR REPLACE FUNCTION products_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||  -- Weight: A (highest)
        setweight(to_tsvector('english', COALESCE(NEW.summary, '')), 'B') ||  -- Weight: B
        setweight(to_tsvector('english', COALESCE(NEW.topics::text, '')), 'C');  -- Weight: C
    NEW.updated_at := CURRENT_TIMESTAMP;

    -- Also update update_date for consistency
    IF NEW.update_date IS NULL THEN
        NEW.update_date := NEW.updated_at;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Migration Complete
-- =============================================================================

-- Verify migration
DO $$
DECLARE
    v_product_columns INTEGER;
    v_fts_columns INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_product_columns
    FROM information_schema.columns
    WHERE table_name = 'products'
    AND column_name IN ('update_date', 'product_number', 'html_url');

    SELECT COUNT(*) INTO v_fts_columns
    FROM information_schema.columns
    WHERE table_name = 'product_content_fts'
    AND column_name IN ('version_id', 'search_vector');

    IF v_product_columns >= 3 AND v_fts_columns >= 2 THEN
        RAISE NOTICE '✅ Migration postgres_003_crs_enhancements completed successfully';
        RAISE NOTICE '   - Added % columns to products table', v_product_columns;
        RAISE NOTICE '   - Verified % columns in product_content_fts', v_fts_columns;
    ELSE
        RAISE WARNING '⚠️  Migration may be incomplete. Check table structures.';
    END IF;
END $$;

-- =============================================================================
-- Usage Notes
-- =============================================================================
--
-- Key Changes:
-- 1. Added update_date column to products (for CRS updater lookback queries)
-- 2. Added product_number column to products (CRS report numbers)
-- 3. Added html_url column to products (alternative field name used by scrapers)
-- 4. Updated trigger to sync update_date with updated_at
-- 5. Verified product_content_fts has version_id foreign key
--
-- These changes ensure compatibility between:
-- - CRS scrapers that use update_date/html_url
-- - Admin dashboard that uses updated_at/url_html
-- - Content manager that uses both conventions
--
-- =============================================================================
