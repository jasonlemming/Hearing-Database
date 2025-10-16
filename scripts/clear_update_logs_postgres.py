#!/usr/bin/env python3
"""
Clear old update_logs data from PostgreSQL to fix duplicate key constraint issues.
"""

import os
import psycopg2

def main():
    # Get the database URL from environment
    db_url = os.environ.get('BROOKINGS_DATABASE_URL') or os.environ.get('DATABASE_URL')

    if not db_url:
        print("Error: BROOKINGS_DATABASE_URL or DATABASE_URL environment variable not set")
        return

    print(f"Connecting to PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        # Check existing records
        cursor.execute("SELECT COUNT(*) FROM update_logs")
        count = cursor.fetchone()[0]
        print(f"Found {count} existing records in update_logs table")

        if count > 0:
            print(f"\nDeleting all {count} records...")
            cursor.execute("DELETE FROM update_logs")
            print("✓ All records deleted")

            # Reset the sequence for PostgreSQL
            print("\nResetting auto-increment sequence...")
            cursor.execute("ALTER SEQUENCE update_logs_log_id_seq RESTART WITH 1")
            print("✓ PostgreSQL sequence reset")

            conn.commit()
            print("\n✓ update_logs table cleared and ready for new records")
        else:
            print("Table is already empty")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
