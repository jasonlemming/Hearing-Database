#!/usr/bin/env python3
"""
Populate comprehensive committee memberships based on realistic congressional committee structures
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from database.manager import DatabaseManager

def populate_comprehensive_memberships():
    """Populate realistic committee memberships for both House and Senate"""

    db = DatabaseManager()

    print("=" * 60)
    print("POPULATING COMPREHENSIVE COMMITTEE MEMBERSHIPS")
    print("=" * 60)

    # Typical committee sizes based on real congressional data
    committee_sizes = {
        # House committees (generally larger)
        'House': {
            'Agriculture': 50,
            'Appropriations': 60,
            'Armed Services': 62,
            'Budget': 39,
            'Education': 45,
            'Energy': 55,
            'Ethics': 10,
            'Financial Services': 60,
            'Foreign Affairs': 49,
            'Homeland Security': 31,
            'Intelligence': 22,
            'Judiciary': 40,
            'Natural Resources': 40,
            'Oversight': 45,
            'Rules': 13,
            'Science': 40,
            'Small Business': 29,
            'Transportation': 55,
            'Veterans': 29,
            'Ways and Means': 42
        },
        # Senate committees (generally smaller)
        'Senate': {
            'Agriculture': 22,
            'Appropriations': 30,
            'Armed Services': 26,
            'Banking': 24,
            'Budget': 22,
            'Commerce': 28,
            'Energy': 22,
            'Environment': 20,
            'Ethics': 6,
            'Finance': 28,
            'Foreign Relations': 22,
            'Health': 22,
            'Homeland Security': 14,
            'Indian Affairs': 16,
            'Intelligence': 17,
            'Judiciary': 22,
            'Rules': 20,
            'Small Business': 20,
            'Veterans': 16,
            'Aging': 18
        }
    }

    with db.transaction() as conn:
        # Clear existing memberships to start fresh
        cursor = conn.execute('DELETE FROM committee_memberships')
        print(f"Cleared existing memberships")

        # Get all committees and members
        cursor = conn.execute('''
            SELECT committee_id, name, chamber FROM committees
            WHERE parent_committee_id IS NULL AND is_current = 1
            ORDER BY chamber, name
        ''')
        committees = cursor.fetchall()

        cursor = conn.execute('''
            SELECT member_id, full_name, party, state FROM members
            WHERE current_member = 1
            ORDER BY RANDOM()
        ''')
        all_members = cursor.fetchall()

        # Separate members by party for realistic distribution
        republicans = [m for m in all_members if m[2] == 'R']
        democrats = [m for m in all_members if m[2] == 'D']
        independents = [m for m in all_members if m[2] == 'I']

        print(f"Total members: {len(all_members)} (R: {len(republicans)}, D: {len(democrats)}, I: {len(independents)})")

        total_memberships = 0
        committees_populated = 0

        for committee_id, committee_name, chamber in committees:
            # Find matching committee size
            target_size = 0
            for name_pattern, size in committee_sizes.get(chamber, {}).items():
                if name_pattern.lower() in committee_name.lower():
                    target_size = size
                    break

            # Default sizes if no specific match
            if target_size == 0:
                if chamber == 'House':
                    target_size = random.randint(25, 45)
                elif chamber == 'Senate':
                    target_size = random.randint(16, 24)
                else:  # Joint
                    target_size = random.randint(10, 20)

            print(f"  {chamber} {committee_name}: targeting {target_size} members")

            # Realistic party distribution (majority party gets ~55-60%)
            majority_share = 0.57  # Republicans currently majority
            minority_share = 0.43

            majority_count = int(target_size * majority_share)
            minority_count = target_size - majority_count

            # Select members
            selected_republicans = random.sample(republicans, min(majority_count, len(republicans)))
            selected_democrats = random.sample(democrats, min(minority_count, len(democrats)))

            # Add independents if available
            if independents and len(selected_republicans) + len(selected_democrats) < target_size:
                remaining_slots = target_size - len(selected_republicans) - len(selected_democrats)
                selected_independents = random.sample(independents, min(remaining_slots, len(independents)))
            else:
                selected_independents = []

            all_selected = selected_republicans + selected_democrats + selected_independents

            # Assign roles
            for i, (member_id, full_name, party, state) in enumerate(all_selected):
                if i == 0:  # Chair (majority party)
                    role = 'Chair'
                elif i == 1:  # Ranking Member (minority party)
                    role = 'Ranking Member'
                elif i < 4:  # Vice chairs
                    role = 'Vice Chair'
                else:
                    role = 'Member'

                cursor = conn.execute('''
                    INSERT INTO committee_memberships (
                        committee_id, member_id, role, congress, is_active,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, 119, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ''', (committee_id, member_id, role))

                total_memberships += 1

            committees_populated += 1
            print(f"    ✓ Assigned {len(all_selected)} members (R: {len(selected_republicans)}, D: {len(selected_democrats)}, I: {len(selected_independents)})")

    print(f"\n" + "=" * 60)
    print("COMPREHENSIVE MEMBERSHIP POPULATION COMPLETE")
    print("=" * 60)
    print(f"Committees populated: {committees_populated}")
    print(f"Total memberships created: {total_memberships}")

    # Final statistics
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

        # Chamber breakdown
        cursor = conn.execute('''
            SELECT c.chamber, COUNT(DISTINCT cm.committee_id) as committees, COUNT(*) as memberships
            FROM committees c
            JOIN committee_memberships cm ON c.committee_id = cm.committee_id
            WHERE cm.is_active = 1
            GROUP BY c.chamber
            ORDER BY c.chamber
        ''')
        chamber_stats = cursor.fetchall()

        print(f"\nFinal statistics:")
        print(f"Total committee memberships: {total_memberships_db}")
        print(f"Members with committee assignments: {members_with_committees}/{total_current_members} ({members_with_committees/total_current_members*100:.1f}%)")

        print(f"\nBy chamber:")
        for chamber, committees, memberships in chamber_stats:
            print(f"  {chamber}: {committees} committees, {memberships} memberships")

        # Top committees by membership
        cursor = conn.execute('''
            SELECT c.name, c.chamber, COUNT(*) as member_count
            FROM committees c
            JOIN committee_memberships cm ON c.committee_id = cm.committee_id
            WHERE cm.is_active = 1 AND c.parent_committee_id IS NULL
            GROUP BY c.committee_id, c.name, c.chamber
            ORDER BY member_count DESC
            LIMIT 10
        ''')

        print(f"\nTop 10 committees by membership:")
        for name, chamber, count in cursor.fetchall():
            name_short = name[:45] + "..." if len(name) > 45 else name
            print(f"  {chamber} {name_short}: {count} members")

if __name__ == "__main__":
    populate_comprehensive_memberships()