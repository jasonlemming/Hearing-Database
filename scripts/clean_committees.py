#!/usr/bin/env python3
"""
Clean up committee data to only include current, legitimate committees
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager

def clean_committees():
    """Remove obsolete and historical committees, keep only current ones"""

    db = DatabaseManager()

    # Known current House committees (from the user's list)
    current_house_committees = {
        'hsag00': 'Agriculture Committee',
        'hsap00': 'Appropriations Committee',
        'hsas00': 'Armed Services Committee',
        'hsbu00': 'Budget Committee',
        'hsed00': 'Education and Workforce Committee',
        'hsif00': 'Energy and Commerce Committee',
        'hsso00': 'Ethics Committee',
        'hsba00': 'Financial Services Committee',
        'hsfa00': 'Foreign Affairs Committee',
        'hshm00': 'Homeland Security Committee',
        'hsha00': 'House Administration Committee',
        'hsju00': 'Judiciary Committee',
        'hsii00': 'Natural Resources Committee',
        'hsgo00': 'Oversight and Government Reform Committee',
        'hsru00': 'Rules Committee',
        'hssy00': 'Science, Space, and Technology Committee',
        'hssm00': 'Small Business Committee',
        'hspw00': 'Transportation and Infrastructure Committee',
        'hsvr00': "Veterans' Affairs Committee",
        'hswm00': 'Ways and Means Committee',
        'hlig00': 'Permanent Select Committee on Intelligence',
        'hlse00': 'Select Committee on the Strategic Competition Between the United States and the Chinese Communist Party'
    }

    # Known current Senate committees (major ones)
    current_senate_committees = {
        'ssaf00': 'Agriculture, Nutrition, and Forestry Committee',
        'ssap00': 'Appropriations Committee',
        'ssas00': 'Armed Services Committee',
        'ssbk00': 'Banking, Housing, and Urban Affairs Committee',
        'ssbu00': 'Budget Committee',
        'sscm00': 'Commerce, Science, and Transportation Committee',
        'ssev00': 'Environment and Public Works Committee',
        'ssfi00': 'Finance Committee',
        'ssfr00': 'Foreign Relations Committee',
        'sshr00': 'Health, Education, Labor and Pensions Committee',
        'ssga00': 'Homeland Security and Governmental Affairs Committee',
        'ssju00': 'Judiciary Committee',
        'ssru00': 'Rules and Administration Committee',
        'sssb00': 'Small Business and Entrepreneurship Committee',
        'ssvr00': "Veterans' Affairs Committee",
        'slin00': 'Select Committee on Intelligence'
    }

    # Known Joint committees
    joint_committees = {
        'jsec00': 'Joint Economic Committee',
        'jslb00': 'Joint Committee on the Library',
        'jspr00': 'Joint Committee on Printing',
        'jstx00': 'Joint Committee on Taxation'
    }

    current_committees = {}
    current_committees.update(current_house_committees)
    current_committees.update(current_senate_committees)
    current_committees.update(joint_committees)

    with db.transaction() as conn:
        # Get current count
        cursor = conn.execute('SELECT COUNT(*) FROM committees')
        before_count = cursor.fetchone()[0]

        # First, mark all committees that should be removed
        # Remove historical, obsolete, and duplicate committees

        # Delete obviously historical committees
        cursor = conn.execute('''
            DELETE FROM committees WHERE
            name LIKE '%194%' OR name LIKE '%195%' OR name LIKE '%196%' OR
            name LIKE '%197%' OR name LIKE '%198%' OR name LIKE '%199%' OR
            name LIKE '%200%' OR name LIKE '%Alcoholic%' OR name LIKE '%Bicentenary%' OR
            name LIKE '%Inaugural Ceremonies%' OR name LIKE '%Year 2000%' OR
            name LIKE '%Accounts Committee%' OR
            name LIKE '%Aeronautical and Space Sciences%' OR
            name LIKE '%Assassinations%' OR
            name LIKE '%Census Committee%'
        ''')
        deleted_historical = cursor.rowcount

        # Delete committees with problematic system codes (too many parts)
        cursor = conn.execute('''
            DELETE FROM committees WHERE
            system_code LIKE '%_%_%_%_%' OR
            length(system_code) > 10
        ''')
        deleted_problematic_codes = cursor.rowcount

        # Delete committees that are clearly not current based on naming patterns
        cursor = conn.execute('''
            DELETE FROM committees WHERE
            name LIKE '%Special Committee%' OR
            name LIKE '%Select Committee to Investigate%' OR
            name LIKE '%Task Force on%' OR
            (name LIKE '%Subcommittee%' AND system_code NOT LIKE '%[0-9][0-9]')
        ''')
        deleted_special = cursor.rowcount

        # Keep only committees that are either:
        # 1. In our known current list
        # 2. Are subcommittees of known current committees
        cursor = conn.execute('''
            DELETE FROM committees WHERE
            system_code NOT IN (''' + ','.join(['?' for _ in current_committees]) + ''') AND
            parent_committee_id NOT IN (
                SELECT committee_id FROM committees
                WHERE system_code IN (''' + ','.join(['?' for _ in current_committees]) + ''')
            )
        ''', list(current_committees.keys()) + list(current_committees.keys()))
        deleted_unknown = cursor.rowcount

        # Update names for known committees to ensure consistency
        for system_code, correct_name in current_committees.items():
            cursor = conn.execute('''
                UPDATE committees
                SET name = ?
                WHERE system_code = ?
            ''', (correct_name, system_code))

        # Get final count
        cursor = conn.execute('SELECT COUNT(*) FROM committees')
        after_count = cursor.fetchone()[0]

        # Get breakdown
        cursor = conn.execute('''
            SELECT chamber,
                   COUNT(CASE WHEN parent_committee_id IS NULL THEN 1 END) as parents,
                   COUNT(CASE WHEN parent_committee_id IS NOT NULL THEN 1 END) as subs,
                   COUNT(*) as total
            FROM committees
            GROUP BY chamber
            ORDER BY chamber
        ''')
        breakdown = cursor.fetchall()

        print(f"=== Committee Cleanup Results ===")
        print(f"Committees before: {before_count}")
        print(f"Committees after: {after_count}")
        print(f"Deleted {before_count - after_count} committees:")
        print(f"  - Historical: {deleted_historical}")
        print(f"  - Problematic codes: {deleted_problematic_codes}")
        print(f"  - Special/Task Forces: {deleted_special}")
        print(f"  - Unknown/Non-current: {deleted_unknown}")

        print(f"\\nFinal breakdown:")
        for row in breakdown:
            print(f"  {row[0]}: {row[1]} parent committees, {row[2]} subcommittees")

        # Show sample of remaining committees
        cursor = conn.execute('''
            SELECT system_code, name, chamber
            FROM committees
            WHERE parent_committee_id IS NULL
            ORDER BY chamber, name
            LIMIT 15
        ''')
        samples = cursor.fetchall()

        print(f"\\nSample remaining parent committees:")
        for sample in samples:
            print(f"  {sample[0]} | {sample[1]} | {sample[2]}")

if __name__ == "__main__":
    clean_committees()