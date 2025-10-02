#!/usr/bin/env python3
"""
Fetch and populate committee memberships from Congress.gov API
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from database.manager import DatabaseManager
from api.client import CongressAPIClient
from fetchers.committee_fetcher import CommitteeFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)

def fetch_committee_memberships():
    """Fetch committee rosters and populate member relationships"""

    db = DatabaseManager()
    client = CongressAPIClient()
    committee_fetcher = CommitteeFetcher(client)

    print("=" * 60)
    print("FETCHING COMMITTEE MEMBERSHIPS")
    print("=" * 60)

    congress = 119  # Current congress

    with db.transaction() as conn:
        # Get all committees that don't have member relationships yet
        cursor = conn.execute('''
            SELECT c.committee_id, c.system_code, c.name, c.chamber
            FROM committees c
            WHERE c.parent_committee_id IS NULL  -- Only parent committees
            AND c.is_current = 1
            ORDER BY c.chamber, c.name
        ''')
        committees = cursor.fetchall()

    print(f"Found {len(committees)} parent committees to process")

    total_memberships = 0
    committees_with_rosters = 0
    errors = 0

    for i, (committee_id, system_code, name, chamber) in enumerate(committees, 1):
        try:
            print(f"[{i}/{len(committees)}] Processing {chamber} {name[:50]}...")

            # Fetch committee details including roster
            committee_details = committee_fetcher.fetch_committee_details(chamber.lower(), system_code)

            if committee_details:
                # Extract roster information
                roster = committee_fetcher.extract_committee_roster(committee_details)

                if roster:
                    committees_with_rosters += 1
                    print(f"  Found {len(roster)} members")

                    # Import roster memberships
                    imported_count = 0
                    for member_info in roster:
                        bioguide_id = member_info.get('bioguide_id')
                        if bioguide_id:
                            # Find member by bioguide_id
                            with db.transaction() as conn:
                                cursor = conn.execute(
                                    'SELECT member_id FROM members WHERE bioguide_id = ?',
                                    (bioguide_id,)
                                )
                                member = cursor.fetchone()

                                if member:
                                    member_id = member[0]
                                    role = member_info.get('role', 'Member')

                                    # Check if membership already exists
                                    cursor = conn.execute('''
                                        SELECT 1 FROM committee_memberships
                                        WHERE member_id = ? AND committee_id = ? AND congress = ?
                                    ''', (member_id, committee_id, congress))

                                    if not cursor.fetchone():
                                        # Create membership
                                        cursor = conn.execute('''
                                            INSERT INTO committee_memberships (
                                                committee_id, member_id, role, congress, is_active,
                                                created_at, updated_at
                                            ) VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                        ''', (committee_id, member_id, role, congress))

                                        imported_count += 1
                                        total_memberships += 1

                    print(f"  ✓ Imported {imported_count} new memberships")
                else:
                    print(f"  ⚠️  No roster data available")
            else:
                print(f"  ⚠️  Could not fetch committee details")

            # Rate limiting
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error processing committee {system_code}: {e}")
            errors += 1
            continue

    print(f"\n" + "=" * 60)
    print("COMMITTEE MEMBERSHIP IMPORT COMPLETE")
    print("=" * 60)
    print(f"Committees processed: {len(committees)}")
    print(f"Committees with rosters: {committees_with_rosters}")
    print(f"Total memberships imported: {total_memberships}")
    print(f"Errors: {errors}")

    # Show summary statistics
    with db.transaction() as conn:
        cursor = conn.execute('SELECT COUNT(*) FROM committee_memberships')
        total_memberships_db = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(DISTINCT m.member_id)
            FROM members m
            JOIN committee_memberships cm ON m.member_id = cm.member_id
            WHERE cm.is_active = 1
        ''')
        members_with_committees = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM members WHERE current_member = 1')
        total_current_members = cursor.fetchone()[0]

        print(f"\nFinal statistics:")
        print(f"Total committee memberships: {total_memberships_db}")
        print(f"Members with committee assignments: {members_with_committees}/{total_current_members}")
        print(f"Coverage: {members_with_committees/total_current_members*100:.1f}%")

if __name__ == "__main__":
    fetch_committee_memberships()