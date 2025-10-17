#!/usr/bin/env python3
"""
Reset update_logs table - delete old records and reset sequence.
"""

import os
import psycopg2

def main():
    # Get the database URL from environment - prefer POSTGRES_URL for hearing database
    db_url = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL')

    if not db_url:
        print("Error: POSTGRES_URL or DATABASE_URL environment variable not set")
        return

    print(f"Connecting to Hearing Database PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        # Check existing records
        cursor.execute("SELECT COUNT(*) FROM update_logs")
        count = cursor.fetchone()[0]
        print(f"Found {count} existing records in update_logs table")

        if count > 0:
            # Show a few recent ones
            cursor.execute("""
                SELECT log_id, update_date, success
                FROM update_logs
                ORDER BY log_id DESC
                LIMIT 5
            """)
            recent = cursor.fetchall()
            print("\nMost recent records:")
            for row in recent:
                print(f"  log_id={row[0]}, date={row[1]}, success={row[2]}")

            print(f"\nDeleting all {count} records...")
            cursor.execute("DELETE FROM update_logs")
            print("✓ All records deleted")

            # Reset the sequence for PostgreSQL
            print("\nResetting auto-increment sequence...")
            cursor.execute("ALTER SEQUENCE update_logs_log_id_seq RESTART WITH 1")
            print("✓ PostgreSQL sequence reset to start at 1")

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
