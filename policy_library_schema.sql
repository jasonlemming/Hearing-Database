-- PostgreSQL Schema for Policy Library (CRS, Brookings, GAO, Substack)
-- Converted from SQLite schema

-- Sources Table
CREATE TABLE IF NOT EXISTS sources (
    source_id SERIAL PRIMARY KEY,
    source_code VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    short_name VARCHAR(50),
    description TEXT,
    url VARCHAR(500),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Subjects Table
CREATE TABLE IF NOT EXISTS subjects (
    subject_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    parent_subject_id INTEGER,
    description TEXT,
    source_vocabulary VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_subject_id) REFERENCES subjects(subject_id)
);

-- Organizations Table
CREATE TABLE IF NOT EXISTS organizations (
    organization_id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    short_name VARCHAR(100),
    organization_type VARCHAR(50),
    url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents Table (was previously called "products" in some code)
CREATE TABLE IF NOT EXISTS documents (
    document_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    document_identifier VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    document_type VARCHAR(50),
    status VARCHAR(20),
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

    CONSTRAINT uq_source_document UNIQUE (source_id, document_identifier),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Authors Table
CREATE TABLE IF NOT EXISTS authors (
    author_id SERIAL PRIMARY KEY,
    full_name VARCHAR(200) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    organization_id INTEGER,
    email VARCHAR(200),
    orcid VARCHAR(50),
    bio TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (organization_id) REFERENCES organizations(organization_id)
);

-- Ingestion Logs Table
CREATE TABLE IF NOT EXISTS ingestion_logs (
    log_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    run_type VARCHAR(20) NOT NULL,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    documents_checked INTEGER,
    documents_fetched INTEGER,
    documents_updated INTEGER,
    documents_skipped INTEGER,
    errors_count INTEGER,
    status VARCHAR(20) NOT NULL,
    error_details TEXT,
    total_size_bytes INTEGER,
    avg_fetch_time_ms FLOAT,
    total_duration_seconds FLOAT,

    CONSTRAINT ck_run_type CHECK (run_type IN ('backfill', 'update', 'manual')),
    CONSTRAINT ck_status CHECK (status IN ('running', 'completed', 'failed', 'partial')),
    FOREIGN KEY (source_id) REFERENCES sources(source_id)
);

-- Document Versions Table
CREATE TABLE IF NOT EXISTS document_versions (
    version_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    html_content TEXT,
    text_content TEXT,
    structure_json TEXT,
    content_hash VARCHAR(64),
    word_count INTEGER,
    page_count INTEGER,
    ingested_at TIMESTAMP,
    is_current BOOLEAN DEFAULT true,
    notes TEXT,

    CONSTRAINT uq_document_version UNIQUE (document_id, version_number),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- Document Files Table
CREATE TABLE IF NOT EXISTS document_files (
    file_id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    mime_type VARCHAR(100),
    checksum VARCHAR(64),
    downloaded_at TIMESTAMP,

    CONSTRAINT ck_file_type CHECK (file_type IN ('PDF', 'HTML', 'TEXT', 'XML')),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

-- Document Authors Junction Table
CREATE TABLE IF NOT EXISTS document_authors (
    document_id INTEGER NOT NULL,
    author_id INTEGER NOT NULL,
    author_order INTEGER,
    role VARCHAR(50),

    PRIMARY KEY (document_id, author_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES authors(author_id) ON DELETE CASCADE
);

-- Document Subjects Junction Table
CREATE TABLE IF NOT EXISTS document_subjects (
    document_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    relevance_score FLOAT,

    PRIMARY KEY (document_id, subject_id),
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE
);

-- Ingestion Errors Table
CREATE TABLE IF NOT EXISTS ingestion_errors (
    error_id SERIAL PRIMARY KEY,
    log_id INTEGER NOT NULL,
    document_identifier VARCHAR(100),
    url VARCHAR(500),
    error_type VARCHAR(50) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    retry_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_error_type CHECK (error_type IN ('fetch_error', 'parse_error', 'validation_error', 'storage_error')),
    FOREIGN KEY (log_id) REFERENCES ingestion_logs(log_id) ON DELETE CASCADE
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_publication_date ON documents(publication_date);
CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_authors_organization ON authors(organization_id);
CREATE INDEX IF NOT EXISTS idx_subjects_parent ON subjects(parent_subject_id);
CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_document_files_document ON document_files(document_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_logs_source ON ingestion_logs(source_id);
CREATE INDEX IF NOT EXISTS idx_ingestion_errors_log ON ingestion_errors(log_id);
