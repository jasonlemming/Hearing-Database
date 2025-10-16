#!/usr/bin/env python3
"""
Clear old update_logs data to fix duplicate key constraint issues.
This script truncates the update_logs table to start fresh.
"""

import os
from database.manager import DatabaseManager

def main():
    db = DatabaseManager()

    print("Checking current update_logs...")
    with db.transaction() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM update_logs")
        count = cursor.fetchone()[0]
        print(f"Found {count} existing records in update_logs table")

        if count > 0:
            response = input(f"\nDelete all {count} records from update_logs? (yes/no): ")
            if response.lower() == 'yes':
                print("\nDeleting all records...")
                conn.execute("DELETE FROM update_logs")
                print("✓ All records deleted")

                # Reset the sequence for PostgreSQL
                print("\nResetting auto-increment sequence...")
                try:
                    # For PostgreSQL
                    conn.execute("ALTER SEQUENCE update_logs_log_id_seq RESTART WITH 1")
                    print("✓ PostgreSQL sequence reset")
                except Exception as e:
                    # For SQLite, the sequence resets automatically
                    print(f"Note: {e}")
                    print("(SQLite auto-increment will reset automatically)")

                print("\n✓ update_logs table cleared and ready for new records")
            else:
                print("Cancelled - no changes made")
        else:
            print("Table is already empty")

if __name__ == '__main__':
    main()
