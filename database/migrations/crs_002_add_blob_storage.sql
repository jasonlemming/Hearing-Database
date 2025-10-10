-- Migration: Add blob storage support to CRS product_versions
-- Date: 2025-10-09
-- Purpose: Add blob_url column to store Vercel Blob URLs for HTML content

-- Add blob_url column to product_versions table
ALTER TABLE product_versions ADD COLUMN blob_url TEXT;

-- Add index for faster blob URL lookups
CREATE INDEX IF NOT EXISTS idx_product_versions_blob_url
ON product_versions(blob_url) WHERE blob_url IS NOT NULL;

-- Note: html_content and text_content columns will be dropped in a later migration
-- after all content has been successfully migrated to blob storage
