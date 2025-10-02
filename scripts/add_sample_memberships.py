#!/usr/bin/env python3
"""
Add sample committee memberships to test the members page functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager

def add_sample_memberships():
    """Add sample committee memberships for testing"""

    db = DatabaseManager()

    print("Adding sample committee memberships...")

    # Sample mapping: we'll assign first 20 members to Agriculture Committee
    # and next 20 to Appropriations, etc.

    with db.transaction() as conn:
        # Get some committees
        cursor = conn.execute('''
            SELECT committee_id, name, system_code FROM committees
            WHERE parent_committee_id IS NULL
            AND chamber = 'House'
            ORDER BY name
            LIMIT 5
        ''')
        committees = cursor.fetchall()

        # Get some members
        cursor = conn.execute('''
            SELECT member_id, full_name FROM members
            WHERE current_member = 1
            ORDER BY full_name
            LIMIT 100
        ''')
        members = cursor.fetchall()

        print(f"Found {len(committees)} committees and {len(members)} members")

        # Assign members to committees (roughly 20 per committee)
        memberships_created = 0
        members_per_committee = 20

        for i, (committee_id, committee_name, system_code) in enumerate(committees):
            start_idx = i * members_per_committee
            end_idx = min(start_idx + members_per_committee, len(members))

            committee_members = members[start_idx:end_idx]

            for j, (member_id, member_name) in enumerate(committee_members):
                # First member is chair, second is ranking member
                if j == 0:
                    role = 'Chair'
                elif j == 1:
                    role = 'Ranking Member'
                else:
                    role = 'Member'

                cursor = conn.execute('''
                    INSERT INTO committee_memberships (
                        committee_id, member_id, role, congress, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 119, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (committee_id, member_id, role))

                memberships_created += 1

            print(f"  {committee_name}: {len(committee_members)} members assigned")

        print(f"\nCreated {memberships_created} sample committee memberships")

        # Show statistics
        cursor = conn.execute('''
            SELECT COUNT(DISTINCT m.member_id)
            FROM members m
            JOIN committee_memberships cm ON m.member_id = cm.member_id
            WHERE cm.is_active = 1
        ''')
        members_with_committees = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM members WHERE current_member = 1')
        total_current_members = cursor.fetchone()[0]

        print(f"Members with committee assignments: {members_with_committees}/{total_current_members}")
        print(f"Coverage: {members_with_committees/total_current_members*100:.1f}%")

if __name__ == "__main__":
    add_sample_memberships()