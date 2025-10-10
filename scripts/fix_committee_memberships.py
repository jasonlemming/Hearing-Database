#!/usr/bin/env python3
"""
Fix committee memberships by clearing old data and re-importing
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)

def fix_committee_memberships():
    """Clear old committee memberships and prepare for re-import"""

    db = DatabaseManager()

    print("=" * 60)
    print("FIXING COMMITTEE MEMBERSHIPS")
    print("=" * 60)

    with db.transaction() as conn:
        # Check current state
        cursor = conn.execute('SELECT COUNT(*) FROM committee_memberships')
        old_count = cursor.fetchone()[0]
        print(f"\nCurrent committee_memberships: {old_count}")

        # Check orphaned memberships
        cursor = conn.execute('''
            SELECT COUNT(*)
            FROM committee_memberships cm
            WHERE NOT EXISTS (
                SELECT 1 FROM committees c WHERE c.committee_id = cm.committee_id
            )
        ''')
        orphaned = cursor.fetchone()[0]
        print(f"Orphaned memberships (invalid committee_id): {orphaned}")

        # Check valid memberships
        valid = old_count - orphaned
        print(f"Valid memberships: {valid}")

        if orphaned > 0:
            print(f"\n⚠️  Found {orphaned} orphaned committee memberships")
            print("These have committee_ids that don't exist in the committees table")
            print("This happened because committee IDs changed during PostgreSQL migration")

            response = input("\nDelete ALL committee_memberships and re-import? (yes/no): ")

            if response.lower() == 'yes':
                # Delete all committee memberships
                cursor = conn.execute('DELETE FROM committee_memberships')
                conn.commit()

                deleted = cursor.rowcount
                print(f"\n✓ Deleted {deleted} committee memberships")

                print("\n" + "=" * 60)
                print("NEXT STEPS:")
                print("=" * 60)
                print("Run the following command to re-import committee memberships:")
                print("\n  python3 scripts/fetch_committee_memberships.py")
                print("\nThis will fetch fresh data from Congress.gov API with correct IDs")
            else:
                print("\nOperation cancelled. No changes made.")
        else:
            print("\n✓ No orphaned memberships found. Data is consistent.")

if __name__ == "__main__":
    fix_committee_memberships()
