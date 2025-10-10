#!/usr/bin/env python3
"""
Validate PostgreSQL Setup
Checks that everything is configured correctly before deployment
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_environment_variable(var_name):
    """Check if environment variable is set"""
    value = os.environ.get(var_name)
    if value:
        # Mask sensitive parts
        if 'KEY' in var_name or 'SECRET' in var_name or 'URL' in var_name:
            display = value[:20] + '...' if len(value) > 20 else value
        else:
            display = value
        print(f"  ✅ {var_name}: {display}")
        return True
    else:
        print(f"  ❌ {var_name}: NOT SET")
        return False

def check_database_connection():
    """Check if database connection works"""
    try:
        from database.postgres_config import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            if result and result[0] == 1:
                print("  ✅ Database connection successful")
                return True
            else:
                print("  ❌ Database connection failed: unexpected result")
                return False
    except ImportError as e:
        print(f"  ❌ Cannot import postgres_config: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False

def check_database_tables():
    """Check if required tables exist"""
    try:
        from database.postgres_config import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ['products', 'product_versions']
            optional_tables = ['product_content_fts', 'content_ingestion_logs']

            all_good = True
            for table in required_tables:
                if table in tables:
                    print(f"  ✅ Table '{table}' exists")
                else:
                    print(f"  ❌ Table '{table}' MISSING (required)")
                    all_good = False

            for table in optional_tables:
                if table in tables:
                    print(f"  ✅ Table '{table}' exists")
                else:
                    print(f"  ⚠️  Table '{table}' not found (optional)")

            return all_good
    except Exception as e:
        print(f"  ❌ Cannot check tables: {e}")
        return False

def check_data_migrated():
    """Check if data has been migrated"""
    try:
        from database.postgres_config import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM products")
            product_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM product_versions")
            version_count = cursor.fetchone()[0]

            if product_count > 0:
                print(f"  ✅ Products migrated: {product_count:,}")
            else:
                print(f"  ⚠️  No products found - migration not complete")

            if version_count > 0:
                print(f"  ✅ Versions migrated: {version_count:,}")
            else:
                print(f"  ⚠️  No versions found - migration not complete")

            return product_count > 0
    except Exception as e:
        print(f"  ❌ Cannot check data: {e}")
        return False

def check_search_vectors():
    """Check if search vectors are populated"""
    try:
        from database.postgres_config import get_connection

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*)
                FROM products
                WHERE search_vector IS NOT NULL
            """)
            count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM products")
            total = cursor.fetchone()[0]

            if count == total and total > 0:
                print(f"  ✅ Search vectors populated: {count:,}/{total:,}")
                return True
            elif count > 0:
                print(f"  ⚠️  Search vectors partial: {count:,}/{total:,}")
                return False
            else:
                print(f"  ❌ Search vectors NOT populated")
                return False
    except Exception as e:
        print(f"  ❌ Cannot check search vectors: {e}")
        return False

def check_sqlite_database():
    """Check if SQLite database exists for migration"""
    db_path = 'crs_products.db'
    if os.path.exists(db_path):
        size_mb = os.path.getsize(db_path) / (1024 * 1024)
        print(f"  ✅ SQLite database found: {db_path} ({size_mb:.1f} MB)")
        return True
    else:
        print(f"  ⚠️  SQLite database not found: {db_path}")
        print(f"     (This is OK if migration is already complete)")
        return False

def main():
    """Run all validation checks"""
    print("\n" + "="*70)
    print("POSTGRESQL SETUP VALIDATION")
    print("="*70)

    all_checks = []

    # Check 1: Environment Variables
    print("\n1️⃣  ENVIRONMENT VARIABLES")
    env_vars = {
        'DATABASE_URL': check_environment_variable('DATABASE_URL'),
        'R2_ACCESS_KEY_ID': check_environment_variable('R2_ACCESS_KEY_ID'),
        'R2_SECRET_ACCESS_KEY': check_environment_variable('R2_SECRET_ACCESS_KEY'),
        'R2_ACCOUNT_ID': check_environment_variable('R2_ACCOUNT_ID'),
        'R2_BUCKET_NAME': check_environment_variable('R2_BUCKET_NAME'),
        'R2_PUBLIC_URL': check_environment_variable('R2_PUBLIC_URL'),
    }
    all_checks.append(env_vars['DATABASE_URL'])  # DATABASE_URL is required

    # Check 2: Database Connection
    print("\n2️⃣  DATABASE CONNECTION")
    conn_ok = check_database_connection()
    all_checks.append(conn_ok)

    if not conn_ok:
        print("\n❌ VALIDATION FAILED")
        print("\nDatabase connection failed. Please check:")
        print("  1. DATABASE_URL is set correctly")
        print("  2. Neon database is running")
        print("  3. Your IP is not blocked")
        print("\nRun: export DATABASE_URL='postgresql://...'")
        sys.exit(1)

    # Check 3: Database Tables
    print("\n3️⃣  DATABASE TABLES")
    tables_ok = check_database_tables()
    all_checks.append(tables_ok)

    if not tables_ok:
        print("\n⚠️  Required tables missing!")
        print("\nPlease run schema migration:")
        print("  psql $DATABASE_URL -f database/migrations/postgres_001_initial_schema.sql")
        sys.exit(1)

    # Check 4: Data Migration
    print("\n4️⃣  DATA MIGRATION")
    data_ok = check_data_migrated()

    if not data_ok:
        print("\n⚠️  No data found in database!")
        print("\nPlease run data migration:")
        print("  python3 scripts/migrate_to_postgres.py")
        check_sqlite_database()
        sys.exit(1)

    # Check 5: Search Vectors
    print("\n5️⃣  SEARCH FUNCTIONALITY")
    search_ok = check_search_vectors()

    if not search_ok:
        print("\n⚠️  Search vectors not fully populated")
        print("This may be normal during migration. Check triggers:")
        print("  psql $DATABASE_URL -c \"\\df products_search_vector_update\"")

    # Check 6: SQLite Source
    print("\n6️⃣  SOURCE DATABASE")
    check_sqlite_database()

    # Final Summary
    print("\n" + "="*70)
    if all(all_checks):
        print("✅ ALL CRITICAL CHECKS PASSED")
        print("="*70)
        print("\nYour PostgreSQL setup is ready!")
        print("\nNext steps:")
        print("  1. Test locally: python3 cli.py web serve")
        print("  2. Push to GitHub: git push -u origin postgres-migration")
        print("  3. Deploy to Vercel with DATABASE_URL environment variable")
        print("\nSee DEPLOYMENT_GUIDE.md for detailed instructions.")
    else:
        print("❌ SOME CHECKS FAILED")
        print("="*70)
        print("\nPlease fix the issues above before deploying.")
        print("See DEPLOYMENT_GUIDE.md for help.")
        sys.exit(1)

if __name__ == '__main__':
    main()
