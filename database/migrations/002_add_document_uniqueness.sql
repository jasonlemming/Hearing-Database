-- Migration 002: Add UNIQUE constraints to prevent duplicate documents
-- This migration:
-- 1. Removes existing duplicate documents (keeping oldest by document_id)
-- 2. Adds UNIQUE indexes to prevent future duplicates

-- Remove duplicate witness documents (keep lowest document_id for each unique appearance_id + document_url)
DELETE FROM witness_documents
WHERE document_id NOT IN (
    SELECT MIN(document_id)
    FROM witness_documents
    GROUP BY appearance_id, document_url
);

-- Remove duplicate hearing transcripts (keep lowest transcript_id for each unique hearing_id + document_url)
DELETE FROM hearing_transcripts
WHERE transcript_id NOT IN (
    SELECT MIN(transcript_id)
    FROM hearing_transcripts
    GROUP BY hearing_id, document_url
);

-- Remove duplicate supporting documents (keep lowest document_id for each unique hearing_id + document_url)
DELETE FROM supporting_documents
WHERE document_id NOT IN (
    SELECT MIN(document_id)
    FROM supporting_documents
    GROUP BY hearing_id, document_url
);

-- Add UNIQUE constraints to prevent future duplicates
CREATE UNIQUE INDEX IF NOT EXISTS idx_witness_docs_unique ON witness_documents(appearance_id, document_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_unique ON hearing_transcripts(hearing_id, document_url);
CREATE UNIQUE INDEX IF NOT EXISTS idx_supporting_docs_unique ON supporting_documents(hearing_id, document_url);
