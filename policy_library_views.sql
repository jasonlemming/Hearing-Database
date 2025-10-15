-- PostgreSQL Views for Policy Library (CRS)
-- These views map the normalized schema (documents, document_authors, document_subjects)
-- to the expected schema used by the CRS blueprint (products with JSONB columns)

-- Products View - Main view that maps documents to products with aggregated columns
CREATE OR REPLACE VIEW products AS
SELECT
    d.document_id AS product_id,
    d.source_id,
    d.document_identifier,
    d.title,
    d.document_type AS product_type,
    d.status,
    d.publication_date,
    d.summary,
    d.full_text,
    d.url,
    d.pdf_url,
    d.page_count,
    d.word_count,
    d.checksum,
    d.metadata_json,
    d.created_at,
    d.updated_at,
    -- Aggregate subjects into a JSONB array for topics
    COALESCE(
        (SELECT jsonb_agg(s.name)
         FROM document_subjects ds
         JOIN subjects s ON ds.subject_id = s.subject_id
         WHERE ds.document_id = d.document_id),
        '[]'::jsonb
    ) AS topics,
    -- Aggregate authors into a JSONB array
    COALESCE(
        (SELECT jsonb_agg(a.full_name ORDER BY da.author_order)
         FROM document_authors da
         JOIN authors a ON da.author_id = a.author_id
         WHERE da.document_id = d.document_id),
        '[]'::jsonb
    ) AS authors
FROM documents d;

-- Product Versions View - Maps document_versions to product_versions
CREATE OR REPLACE VIEW product_versions AS
SELECT
    version_id,
    document_id AS product_id,
    version_number,
    html_content,
    text_content,
    structure_json,
    content_hash,
    word_count,
    page_count,
    ingested_at,
    is_current,
    notes
FROM document_versions;
