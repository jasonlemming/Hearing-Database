#!/usr/bin/env python3
"""
Fix duplicate hearing display by removing orphaned committee links

This script deletes committee links in hearing_committees where the committee_id
no longer exists in the committees table. These orphaned links cause duplicate
hearing entries in the web interface (one with valid committee, one with null).
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)


def fix_orphaned_committee_links():
    """Delete orphaned committee links that cause duplicate hearing display"""
    db = DatabaseManager()

    with db.transaction() as conn:
        # Find orphaned committee links (committee_id doesn't exist in committees table)
        cursor = conn.execute('''
            SELECT hc.hearing_id, hc.committee_id, h.event_id, h.title
            FROM hearing_committees hc
            JOIN hearings h ON hc.hearing_id = h.hearing_id
            WHERE hc.committee_id NOT IN (SELECT committee_id FROM committees)
            ORDER BY hc.hearing_id
        ''')

        orphaned_links = cursor.fetchall()

        if not orphaned_links:
            print("No orphaned committee links found.")
            return

        print(f"Found {len(orphaned_links)} orphaned committee links:")
        print()

        # Group by hearing
        from collections import defaultdict
        by_hearing = defaultdict(list)
        for hearing_id, committee_id, event_id, title in orphaned_links:
            by_hearing[hearing_id].append((committee_id, event_id, title))

        for hearing_id, links in by_hearing.items():
            committee_id, event_id, title = links[0]
            print(f"Hearing {hearing_id} (Event ID: {event_id})")
            print(f"  Title: {title[:70]}...")
            print(f"  Orphaned committee IDs: {[c[0] for c in links]}")
            print()

        print(f"Deleting {len(orphaned_links)} orphaned committee links...")

        # Delete all orphaned links
        cursor = conn.execute('''
            DELETE FROM hearing_committees
            WHERE committee_id NOT IN (SELECT committee_id FROM committees)
        ''')

        deleted_count = cursor.rowcount
        print(f"✓ Deleted {deleted_count} orphaned committee links")
        print()

        # Show final statistics
        cursor = conn.execute('''
            SELECT
                COUNT(DISTINCT hearing_id) as total_hearings,
                COUNT(DISTINCT CASE WHEN is_primary = 1 THEN hearing_id END) as hearings_with_primary,
                COUNT(*) as total_links
            FROM hearing_committees
        ''')

        total_hearings, hearings_with_primary, total_links = cursor.fetchone()

        print("Committee link statistics:")
        print(f"  Total hearings with committees: {total_hearings}")
        print(f"  Hearings with primary committee: {hearings_with_primary}")
        print(f"  Total committee links: {total_links}")

        # Check for any remaining duplicate primary committees
        cursor = conn.execute('''
            SELECT COUNT(*) as hearings_with_multiple_primaries
            FROM (
                SELECT hearing_id, COUNT(*) as primary_count
                FROM hearing_committees
                WHERE is_primary = 1
                GROUP BY hearing_id
                HAVING COUNT(*) > 1
            )
        ''')

        remaining_dupes = cursor.fetchone()[0]
        if remaining_dupes > 0:
            print(f"\n⚠ Warning: {remaining_dupes} hearings still have multiple primary committees")
        else:
            print("\n✓ No hearings with multiple primary committees")


if __name__ == "__main__":
    fix_orphaned_committee_links()
