"""
PostgreSQL Configuration and Connection Management
Handles database connections with connection pooling for CRS database
"""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import psycopg2


def get_database_url():
    """
    Get PostgreSQL connection URL from environment

    Returns:
        str: PostgreSQL connection URL
    """
    # Check for CRS-specific database URL first, then fall back to DATABASE_URL
    database_url = os.environ.get('CRS_DATABASE_URL') or os.environ.get('DATABASE_URL')

    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable not set.\n"
            "Set it to your Neon PostgreSQL connection string:\n"
            "export DATABASE_URL='postgresql://user:password@host/database'\n"
            "Or add it to your .env file"
        )

    # Fix for some hosting platforms that use postgres:// instead of postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)

    return database_url


def create_postgres_engine(pool_size=5, max_overflow=10):
    """
    Create SQLAlchemy engine with connection pooling

    Args:
        pool_size: Number of connections to keep in pool
        max_overflow: Max connections beyond pool_size

    Returns:
        sqlalchemy.Engine: Database engine with connection pooling
    """
    database_url = get_database_url()

    # Create engine with optimized settings for serverless
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=300,  # Recycle connections after 5 minutes
        echo=False,  # Set to True for SQL query logging
        connect_args={
            'connect_timeout': 10,
            'options': '-c timezone=utc'
        }
    )

    # Add event listener to optimize connection settings
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Optimize PostgreSQL connection settings"""
        with dbapi_conn.cursor() as cursor:
            # Set search_path to public schema
            cursor.execute("SET search_path TO public")
            # Disable synchronous commit for better performance (safe for non-critical apps)
            # cursor.execute("SET synchronous_commit TO OFF")  # Uncomment if needed

    return engine


def get_direct_connection():
    """
    Get a direct psycopg2 connection (for migrations and admin tasks)

    Returns:
        psycopg2.connection: Direct database connection
    """
    database_url = get_database_url()
    return psycopg2.connect(database_url)


@contextmanager
def get_connection():
    """
    Context manager for database connections

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products")
            rows = cursor.fetchall()
    """
    conn = get_direct_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def check_database_health():
    """
    Check if database is accessible and healthy

    Returns:
        dict: Health check results
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Check basic connectivity
            cursor.execute("SELECT 1")

            # Check if tables exist
            cursor.execute("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('products', 'product_versions')
            """)
            table_count = cursor.fetchone()[0]

            # Get product count
            if table_count >= 1:
                cursor.execute("SELECT COUNT(*) FROM products")
                product_count = cursor.fetchone()[0]
            else:
                product_count = 0

            return {
                'status': 'healthy',
                'tables_found': table_count,
                'product_count': product_count,
                'message': 'Database connection successful'
            }

    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'message': f'Database connection failed: {e}'
        }


def init_database(schema_file='database/migrations/postgres_001_initial_schema.sql'):
    """
    Initialize database with schema

    Args:
        schema_file: Path to SQL schema file
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Read and execute schema file
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        cursor.execute(schema_sql)
        print("✅ Database schema initialized successfully")


if __name__ == '__main__':
    # Test database connection
    print("Testing PostgreSQL connection...")
    health = check_database_health()

    if health['status'] == 'healthy':
        print(f"✅ {health['message']}")
        print(f"   Tables found: {health['tables_found']}")
        print(f"   Products: {health['product_count']}")
    else:
        print(f"❌ {health['message']}")
        print(f"   Error: {health.get('error', 'Unknown')}")
