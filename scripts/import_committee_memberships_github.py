#!/usr/bin/env python3
"""
Import committee memberships from unitedstates/congress-legislators GitHub repository
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import yaml
from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)

MEMBERSHIP_URL = "https://raw.githubusercontent.com/unitedstates/congress-legislators/main/committee-membership-current.yaml"

def import_committee_memberships():
    """Import current committee memberships from GitHub"""

    db = DatabaseManager()

    print("=" * 60)
    print("IMPORTING COMMITTEE MEMBERSHIPS FROM GITHUB")
    print("=" * 60)

    # Fetch YAML data
    print(f"\nFetching data from: {MEMBERSHIP_URL}")
    response = requests.get(MEMBERSHIP_URL, timeout=30)
    response.raise_for_status()

    membership_data = yaml.safe_load(response.text)
    print(f"Loaded membership data for {len(membership_data)} committees")

    congress = 119  # Current congress
    total_memberships = 0
    committees_processed = 0
    committees_not_found = 0
    members_not_found = 0

    with db.transaction() as conn:
        for committee_code, members in membership_data.items():
            # Convert committee code to lowercase for matching
            # GitHub uses uppercase (e.g., "SSAF"), we use lowercase (e.g., "ssaf00")
            system_code = committee_code.lower()

            # Find committee in database
            # Try exact match first (for subcommittees)
            cursor = conn.execute(
                'SELECT committee_id, name, chamber FROM committees WHERE system_code = ?',
                (system_code,)
            )
            committee = cursor.fetchone()

            # If not found, try with "00" suffix (for parent committees)
            if not committee and not system_code.endswith(('00', '01', '02', '03', '04', '05', '06', '07', '08', '09')):
                system_code_with_suffix = system_code + '00'
                cursor = conn.execute(
                    'SELECT committee_id, name, chamber FROM committees WHERE system_code = ?',
                    (system_code_with_suffix,)
                )
                committee = cursor.fetchone()
                if committee:
                    system_code = system_code_with_suffix

            if not committee:
                print(f"  ⚠️  Committee not found: {committee_code.lower()}")
                committees_not_found += 1
                continue

            committee_id, committee_name, chamber = committee
            print(f"\n[{committees_processed + 1}] {chamber} {committee_name}")
            print(f"  System code: {system_code}")
            print(f"  Members: {len(members)}")

            imported_count = 0

            for member_info in members:
                bioguide_id = member_info.get('bioguide')
                title = member_info.get('title', 'Member')

                # Map title to our role format
                if title == 'Chairman' or title == 'Chair':
                    role = 'Chair'
                elif title == 'Ranking Member':
                    role = 'Ranking Member'
                elif title == 'Vice Chairman' or title == 'Vice Chair':
                    role = 'Vice Chair'
                else:
                    role = 'Member'

                # Find member by bioguide_id
                cursor = conn.execute(
                    'SELECT member_id FROM members WHERE bioguide_id = ?',
                    (bioguide_id,)
                )
                member = cursor.fetchone()

                if not member:
                    logger.warning(f"Member not found: {bioguide_id} ({member_info.get('name')})")
                    members_not_found += 1
                    continue

                member_id = member[0]

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

            print(f"  ✓ Imported {imported_count} memberships")
            committees_processed += 1

    print(f"\n" + "=" * 60)
    print("IMPORT COMPLETE")
    print("=" * 60)
    print(f"Committees processed: {committees_processed}")
    print(f"Committees not found in database: {committees_not_found}")
    print(f"Members not found in database: {members_not_found}")
    print(f"Total memberships imported: {total_memberships}")

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
        print(f"Total committee memberships in database: {total_memberships_db}")
        print(f"Members with committee assignments: {members_with_committees}/{total_current_members}")
        print(f"Coverage: {members_with_committees/total_current_members*100:.1f}%")

        # Show sample committees
        cursor = conn.execute('''
            SELECT c.name, c.chamber, COUNT(*) as member_count
            FROM committees c
            JOIN committee_memberships cm ON c.committee_id = cm.committee_id
            WHERE cm.is_active = 1 AND c.parent_committee_id IS NULL
            GROUP BY c.committee_id, c.name, c.chamber
            ORDER BY member_count DESC
            LIMIT 5
        ''')

        print(f"\nTop 5 committees by membership:")
        for name, chamber, count in cursor.fetchall():
            name_short = name[:50] + "..." if len(name) > 50 else name
            print(f"  {chamber:8} {name_short:55} {count:3} members")

if __name__ == "__main__":
    try:
        import_committee_memberships()
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise
