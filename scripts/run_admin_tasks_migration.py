#!/usr/bin/env python3
"""
Run admin_tasks table migration
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.unified_manager import UnifiedDatabaseManager

def main():
    # Get database URL from environment
    db_url = os.environ.get('POSTGRES_URL')

    if not db_url:
        print("ERROR: POSTGRES_URL environment variable not set")
        sys.exit(1)

    print(f"Connecting to Postgres database...")

    db = UnifiedDatabaseManager(db_url=db_url)

    # Read migration SQL
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'database/migrations/postgres_002_admin_tasks.sql'
    )

    print(f"Reading migration from: {migration_file}")

    with open(migration_file, 'r') as f:
        migration_sql = f.read()

    # Execute migration
    print("Executing migration...")

    try:
        with db.transaction() as conn:
            # Execute the entire SQL as one block (Postgres supports this)
            cursor = conn.cursor()
            cursor.execute(migration_sql)

        print("✅ Migration completed successfully!")

        # Verify table was created
        with db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM admin_tasks")
            result = cursor.fetchone()
            print(f"✅ admin_tasks table verified (currently {result[0]} rows)")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
