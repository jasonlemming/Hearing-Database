"""
Database connection and session management
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from brookings_ingester.config import config

# Create base class for declarative models
Base = declarative_base()

# Database engine (created on first import)
engine = None
SessionLocal = None


def init_database(db_url: str = None, echo: bool = False):
    """
    Initialize database engine and session factory

    Args:
        db_url: Database URL (defaults to config.DATABASE_URL)
        echo: Echo SQL statements (for debugging)
    """
    global engine, SessionLocal

    if db_url is None:
        db_url = config.DATABASE_URL

    # SQLite-specific connection args
    connect_args = {}
    if db_url.startswith('sqlite'):
        connect_args = {"check_same_thread": False}

    # Create engine
    engine = create_engine(
        db_url,
        connect_args=connect_args,
        echo=echo
    )

    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """
    Get database session

    Returns:
        SQLAlchemy session
    """
    if SessionLocal is None:
        init_database()

    return SessionLocal()


@contextmanager
def session_scope():
    """
    Context manager for database sessions with automatic commit/rollback

    Usage:
        with session_scope() as session:
            session.add(obj)
            # Auto-commits on success, auto-rolls back on error
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def is_postgresql() -> bool:
    """Check if using PostgreSQL backend"""
    if engine is None:
        init_database()
    return 'postgresql' in str(engine.url)


def is_sqlite() -> bool:
    """Check if using SQLite backend"""
    if engine is None:
        init_database()
    return 'sqlite' in str(engine.url)
