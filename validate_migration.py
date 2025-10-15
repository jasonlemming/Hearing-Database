#!/usr/bin/env python3
"""
Comprehensive validation script for Postgres migration

Tests all blueprints and database operations to ensure everything works correctly.
"""
import sys
import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.unified_manager import UnifiedDatabaseManager


def test_database_connection():
    """Test basic database connectivity"""
    print("\n" + "="*70)
    print("TEST 1: Database Connection")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()

        print(f"✓ Database Type: {db.db_type}")
        print(f"✓ Connection URL: {db._safe_url()}")

        if db.db_type != 'postgres':
            print(f"⚠️  WARNING: Expected postgres but got {db.db_type}")
            print(f"   Check that POSTGRES_URL is set in .env")
            return False

        return True

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def test_health_check():
    """Test database health check"""
    print("\n" + "="*70)
    print("TEST 2: Health Check")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()
        health = db.health_check()

        if health['status'] == 'healthy':
            print(f"✓ Status: {health['status']}")
            print(f"✓ Version: {health['version']}")
            print(f"✓ Total Records: {health['total_records']:,}")

            # Verify expected tables exist
            expected_tables = [
                'hearings', 'committees', 'members', 'witnesses',
                'products', 'documents', 'sources'
            ]

            missing = []
            for table in expected_tables:
                count = health['table_counts'].get(table, 0)
                if count > 0:
                    print(f"  ✓ {table}: {count:,} records")
                else:
                    print(f"  ✗ {table}: 0 records (MISSING!)")
                    missing.append(table)

            if missing:
                print(f"\n⚠️  WARNING: Missing data in tables: {', '.join(missing)}")
                return False

            return True
        else:
            print(f"✗ Database unhealthy: {health.get('error')}")
            return False

    except Exception as e:
        print(f"✗ Health check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hearing_queries():
    """Test hearing database queries"""
    print("\n" + "="*70)
    print("TEST 3: Hearing Database Queries")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()

        # Test 1: Count hearings
        result = db.fetch_one("SELECT COUNT(*) as count FROM hearings")
        count = result['count'] if db.db_type == 'postgres' else result[0]
        print(f"✓ Total hearings: {count:,}")

        # Test 2: Sample hearing with joins
        query = """
        SELECT h.hearing_id, h.title, h.hearing_date, c.name as committee_name
        FROM hearings h
        LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
        LEFT JOIN committees c ON hc.committee_id = c.committee_id
        WHERE h.title IS NOT NULL
        LIMIT 1
        """
        result = db.fetch_one(query)
        if result:
            print(f"✓ Sample hearing:")
            print(f"  Title: {result['title'][:60]}...")
            print(f"  Committee: {result['committee_name']}")
        else:
            print("✗ No hearings found")
            return False

        # Test 3: Committees count
        result = db.fetch_one("SELECT COUNT(*) as count FROM committees")
        count = result['count'] if db.db_type == 'postgres' else result[0]
        print(f"✓ Total committees: {count:,}")

        # Test 4: Witnesses count
        result = db.fetch_one("SELECT COUNT(*) as count FROM witnesses")
        count = result['count'] if db.db_type == 'postgres' else result[0]
        print(f"✓ Total witnesses: {count:,}")

        return True

    except Exception as e:
        print(f"✗ Hearing queries failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_crs_queries():
    """Test CRS product queries"""
    print("\n" + "="*70)
    print("TEST 4: CRS Products Queries")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()

        # Test 1: Count products
        result = db.fetch_one("SELECT COUNT(*) as count FROM products")
        count = result['count'] if db.db_type == 'postgres' else result[0]
        print(f"✓ Total CRS products: {count:,}")

        # Test 2: Sample product
        query = "SELECT product_id, title, product_type, publication_date FROM products LIMIT 1"
        result = db.fetch_one(query)
        if result:
            print(f"✓ Sample product:")
            print(f"  Title: {result['title'][:60]}...")
            print(f"  Type: {result['product_type']}")
        else:
            print("⚠️  No CRS products found (table may be empty)")

        return True

    except Exception as e:
        print(f"✗ CRS queries failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_policy_library_queries():
    """Test policy library (Brookings/Substack) queries"""
    print("\n" + "="*70)
    print("TEST 5: Policy Library Queries")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()

        # Test 1: Count documents
        result = db.fetch_one("SELECT COUNT(*) as count FROM documents")
        count = result['count'] if db.db_type == 'postgres' else result[0]
        print(f"✓ Total documents: {count:,}")

        # Test 2: Count by source
        query = """
        SELECT s.source_code, s.name, COUNT(d.document_id) as doc_count
        FROM sources s
        LEFT JOIN documents d ON s.source_id = d.source_id
        GROUP BY s.source_id, s.source_code, s.name
        ORDER BY doc_count DESC
        """
        results = db.fetch_all(query)
        if results:
            print(f"✓ Documents by source:")
            for row in results:
                print(f"  {row['source_code']:12} ({row['name']}): {row['doc_count']:,} documents")
        else:
            print("⚠️  No sources found")

        return True

    except Exception as e:
        print(f"✗ Policy library queries failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cross_project_queries():
    """Test queries that span multiple projects"""
    print("\n" + "="*70)
    print("TEST 6: Cross-Project Queries")
    print("="*70)

    try:
        db = UnifiedDatabaseManager()

        # Get total records across all projects
        tables_by_project = {
            'Hearing Database': ['hearings', 'committees', 'members', 'witnesses'],
            'CRS Products': ['products'],
            'Policy Library': ['documents']
        }

        print("✓ Record counts by project:")
        for project, tables in tables_by_project.items():
            total = 0
            for table in tables:
                result = db.fetch_one(f"SELECT COUNT(*) as count FROM {table}")
                count = result['count'] if db.db_type == 'postgres' else result[0]
                total += count
            print(f"  {project:20} {total:>8,} records")

        return True

    except Exception as e:
        print(f"✗ Cross-project queries failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_blueprint_imports():
    """Test that all blueprints can be imported"""
    print("\n" + "="*70)
    print("TEST 7: Blueprint Imports")
    print("="*70)

    try:
        from web.blueprints.hearings import hearings_bp
        print("✓ hearings_bp imported")

        from web.blueprints.committees import committees_bp
        print("✓ committees_bp imported")

        from web.blueprints.main_pages import main_pages_bp
        print("✓ main_pages_bp imported")

        from web.blueprints.api import api_bp
        print("✓ api_bp imported")

        from web.blueprints.admin import admin_bp
        print("✓ admin_bp imported")

        from web.blueprints.crs import crs_bp
        print("✓ crs_bp imported")

        from web.blueprints.policy_library import policy_library_bp
        print("✓ policy_library_bp imported")

        print(f"\n✓ All 7 blueprints imported successfully")
        return True

    except Exception as e:
        print(f"✗ Blueprint import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all validation tests"""
    print("\n" + "="*70)
    print("POSTGRES MIGRATION VALIDATION")
    print("="*70)

    tests = [
        ("Database Connection", test_database_connection),
        ("Health Check", test_health_check),
        ("Hearing Queries", test_hearing_queries),
        ("CRS Queries", test_crs_queries),
        ("Policy Library Queries", test_policy_library_queries),
        ("Cross-Project Queries", test_cross_project_queries),
        ("Blueprint Imports", test_blueprint_imports),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ Test '{name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name:30} {status}")

    print("="*70)
    print(f"Result: {passed}/{total} tests passed")
    print("="*70)

    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Migration validated successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - review errors above")
        return 1


if __name__ == '__main__':
    sys.exit(main())
