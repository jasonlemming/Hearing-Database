"""
SQLAlchemy models for unified research document database

Supports CRS, Brookings, GAO, and future sources with a flexible schema.
Compatible with both SQLite and PostgreSQL.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, Boolean,
    ForeignKey, CheckConstraint, UniqueConstraint, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
import json

from .database import Base


class Source(Base):
    """Document sources (CRS, Brookings, GAO, etc.)"""
    __tablename__ = 'sources'

    source_id = Column(Integer, primary_key=True, autoincrement=True)
    source_code = Column(String(20), nullable=False, unique=True)  # 'CRS', 'BROOKINGS', 'GAO'
    name = Column(String(100), nullable=False)
    short_name = Column(String(50))
    description = Column(Text)
    url = Column(String(500))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    documents = relationship('Document', back_populates='source')
    ingestion_logs = relationship('IngestionLog', back_populates='source')

    def __repr__(self):
        return f"<Source(code='{self.source_code}', name='{self.name}')>"


class Document(Base):
    """Main document table (source-agnostic core)"""
    __tablename__ = 'documents'

    document_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey('sources.source_id'), nullable=False)
    document_identifier = Column(String(100), nullable=False)  # Source's internal ID
    title = Column(Text, nullable=False)
    document_type = Column(String(50))  # 'Report', 'Policy Brief', etc.
    status = Column(String(20), default='Active')
    publication_date = Column(Date)
    summary = Column(Text)
    full_text = Column(Text)  # Extracted plain text
    url = Column(String(500))
    pdf_url = Column(String(500))
    page_count = Column(Integer)
    word_count = Column(Integer)
    checksum = Column(String(64))  # SHA256
    metadata_json = Column(Text)  # JSON string for source-specific fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship('Source', back_populates='documents')
    versions = relationship('DocumentVersion', back_populates='document', cascade='all, delete-orphan')
    files = relationship('DocumentFile', back_populates='document', cascade='all, delete-orphan')
    document_authors = relationship('DocumentAuthor', back_populates='document', cascade='all, delete-orphan')
    document_subjects = relationship('DocumentSubject', back_populates='document', cascade='all, delete-orphan')

    # Constraints
    __table_args__ = (
        UniqueConstraint('source_id', 'document_identifier', name='uq_source_document'),
    )

    @hybrid_property
    def metadata_dict(self):
        """Parse metadata JSON to dictionary"""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @metadata_dict.setter
    def metadata_dict(self, value):
        """Set metadata from dictionary"""
        if value:
            self.metadata_json = json.dumps(value)
        else:
            self.metadata_json = None

    def __repr__(self):
        return f"<Document(id={self.document_id}, title='{self.title[:50]}...')>"


class DocumentVersion(Base):
    """Version history for documents"""
    __tablename__ = 'document_versions'

    version_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False)
    version_number = Column(Integer, nullable=False)
    html_content = Column(Text)
    text_content = Column(Text)
    structure_json = Column(Text)  # JSON string for TOC, headings, sections
    content_hash = Column(String(64))  # SHA256 of text_content
    word_count = Column(Integer)
    page_count = Column(Integer)
    ingested_at = Column(DateTime, default=datetime.utcnow)
    is_current = Column(Boolean, default=False)
    notes = Column(Text)

    # Relationships
    document = relationship('Document', back_populates='versions')

    # Constraints
    __table_args__ = (
        UniqueConstraint('document_id', 'version_number', name='uq_document_version'),
    )

    @hybrid_property
    def structure(self):
        """Parse structure JSON to dictionary"""
        if self.structure_json:
            try:
                return json.loads(self.structure_json)
            except json.JSONDecodeError:
                return {}
        return {}

    @structure.setter
    def structure(self, value):
        """Set structure from dictionary"""
        if value:
            self.structure_json = json.dumps(value)
        else:
            self.structure_json = None

    def __repr__(self):
        return f"<DocumentVersion(id={self.version_id}, doc_id={self.document_id}, version={self.version_number})>"


class DocumentFile(Base):
    """File storage metadata (PDFs, text files, HTML)"""
    __tablename__ = 'document_files'

    file_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'), nullable=False)
    file_type = Column(String(20), nullable=False)  # 'PDF', 'HTML', 'TEXT'
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)  # Bytes
    mime_type = Column(String(100))
    checksum = Column(String(64))  # SHA256
    downloaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship('Document', back_populates='files')

    # Constraints
    __table_args__ = (
        CheckConstraint("file_type IN ('PDF', 'HTML', 'TEXT', 'XML')", name='ck_file_type'),
    )

    def __repr__(self):
        return f"<DocumentFile(id={self.file_id}, type='{self.file_type}', path='{self.file_path}')>"


class Author(Base):
    """Deduplicated author entities"""
    __tablename__ = 'authors'

    author_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(200), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    organization_id = Column(Integer, ForeignKey('organizations.organization_id'))
    email = Column(String(200))
    orcid = Column(String(50))
    bio = Column(Text)

    # Brookings-specific metadata (also useful for other sources)
    # NOTE: These columns don't exist in current schema - commented out for now
    # job_title = Column(String(200))  # e.g., "Senior Fellow", "President"
    # affiliation_text = Column(String(500))  # e.g., "Global Economy and Development"
    # profile_url = Column(String(500))  # Source's author profile page
    # linkedin_url = Column(String(500))  # LinkedIn profile

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship('Organization', back_populates='authors')
    document_authors = relationship('DocumentAuthor', back_populates='author')

    def __repr__(self):
        return f"<Author(id={self.author_id}, name='{self.full_name}')>"


class DocumentAuthor(Base):
    """Many-to-many: documents ↔ authors"""
    __tablename__ = 'document_authors'

    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'), primary_key=True)
    author_id = Column(Integer, ForeignKey('authors.author_id', ondelete='CASCADE'), primary_key=True)
    author_order = Column(Integer)  # Position in author list
    role = Column(String(50))  # 'Lead Author', 'Contributing Author'

    # Relationships
    document = relationship('Document', back_populates='document_authors')
    author = relationship('Author', back_populates='document_authors')

    def __repr__(self):
        return f"<DocumentAuthor(doc_id={self.document_id}, author_id={self.author_id})>"


class Subject(Base):
    """Subject/topic taxonomy"""
    __tablename__ = 'subjects'

    subject_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    parent_subject_id = Column(Integer, ForeignKey('subjects.subject_id'))
    description = Column(Text)
    source_vocabulary = Column(String(50))  # 'CRS', 'LCSH', 'Custom'
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships (self-referential for hierarchy)
    parent = relationship('Subject', remote_side=[subject_id], backref='children')
    document_subjects = relationship('DocumentSubject', back_populates='subject')

    def __repr__(self):
        return f"<Subject(id={self.subject_id}, name='{self.name}')>"


class DocumentSubject(Base):
    """Many-to-many: documents ↔ subjects"""
    __tablename__ = 'document_subjects'

    document_id = Column(Integer, ForeignKey('documents.document_id', ondelete='CASCADE'), primary_key=True)
    subject_id = Column(Integer, ForeignKey('subjects.subject_id', ondelete='CASCADE'), primary_key=True)
    relevance_score = Column(Float, default=1.0)

    # Relationships
    document = relationship('Document', back_populates='document_subjects')
    subject = relationship('Subject', back_populates='document_subjects')

    def __repr__(self):
        return f"<DocumentSubject(doc_id={self.document_id}, subject_id={self.subject_id})>"


class Organization(Base):
    """Organizations (author affiliations, publishers)"""
    __tablename__ = 'organizations'

    organization_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, unique=True)
    short_name = Column(String(100))
    organization_type = Column(String(50))  # 'Think Tank', 'Government Agency', 'University'
    url = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    authors = relationship('Author', back_populates='organization')

    def __repr__(self):
        return f"<Organization(id={self.organization_id}, name='{self.name}')>"


class IngestionLog(Base):
    """Tracks ingestion runs"""
    __tablename__ = 'ingestion_logs'

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(Integer, ForeignKey('sources.source_id'), nullable=False)
    run_type = Column(String(20), nullable=False)  # 'backfill', 'update', 'manual'
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Metrics
    documents_checked = Column(Integer, default=0)
    documents_fetched = Column(Integer, default=0)
    documents_updated = Column(Integer, default=0)
    documents_skipped = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)

    # Details
    status = Column(String(20), nullable=False, default='running')  # 'running', 'completed', 'failed', 'partial'
    error_details = Column(Text)  # JSON string

    # Performance
    total_size_bytes = Column(Integer)
    avg_fetch_time_ms = Column(Float)
    total_duration_seconds = Column(Float)

    # Relationships
    source = relationship('Source', back_populates='ingestion_logs')
    errors = relationship('IngestionError', back_populates='log', cascade='all, delete-orphan')

    # Constraints
    __table_args__ = (
        CheckConstraint("run_type IN ('backfill', 'update', 'manual')", name='ck_run_type'),
        CheckConstraint("status IN ('running', 'completed', 'failed', 'partial')", name='ck_status'),
    )

    def __repr__(self):
        return f"<IngestionLog(id={self.log_id}, source_id={self.source_id}, status='{self.status}')>"


class IngestionError(Base):
    """Individual error records"""
    __tablename__ = 'ingestion_errors'

    error_id = Column(Integer, primary_key=True, autoincrement=True)
    log_id = Column(Integer, ForeignKey('ingestion_logs.log_id', ondelete='CASCADE'), nullable=False)
    document_identifier = Column(String(100))
    url = Column(String(500))
    error_type = Column(String(50), nullable=False)  # 'fetch_error', 'parse_error', 'validation_error'
    error_message = Column(Text, nullable=False)
    stack_trace = Column(Text)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    log = relationship('IngestionLog', back_populates='errors')

    # Constraints
    __table_args__ = (
        CheckConstraint("error_type IN ('fetch_error', 'parse_error', 'validation_error', 'storage_error')",
                       name='ck_error_type'),
    )

    def __repr__(self):
        return f"<IngestionError(id={self.error_id}, type='{self.error_type}')>"
