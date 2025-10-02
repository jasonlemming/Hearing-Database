#!/usr/bin/env python3
"""
Refresh committee data from Congress.gov API to ensure complete coverage
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.logging_config import get_logger

logger = get_logger(__name__)

def refresh_committees():
    """Fetch fresh committee data from Congress.gov API"""

    db = DatabaseManager()
    client = CongressAPIClient()

    # Get current committee count
    with db.transaction() as conn:
        cursor = conn.execute('SELECT COUNT(*) FROM committees')
        current_count = cursor.fetchone()[0]
        print(f"Current committees in database: {current_count}")

    # Fetch committees from API for both chambers
    chambers = ['house', 'senate', 'joint']
    new_committees = []
    updated_committees = []

    for chamber in chambers:
        print(f"\nFetching {chamber} committees...")

        try:
            # Get committees for this chamber
            endpoint = f"committee/{chamber}"
            committees_data = list(client.paginate(endpoint))

            print(f"Found {len(committees_data)} {chamber} committees from API")

            for committee in committees_data:
                system_code = committee.get('systemCode')
                name = committee.get('name')

                # Map API type to database constraint values
                api_type = committee.get('type', {}).get('name') if committee.get('type') else None
                valid_types = ['Standing', 'Select', 'Special', 'Joint', 'Task Force', 'Other', 'Subcommittee', 'Commission or Caucus']

                if api_type and api_type in valid_types:
                    committee_type = api_type
                elif chamber.lower() == 'joint':
                    committee_type = 'Joint'
                else:
                    committee_type = 'Standing'  # Most committees are standing committees

                # Use current congress (118th as of 2024)
                congress = 118

                if not system_code or not name:
                    continue

                # Check if committee exists
                with db.transaction() as conn:
                    cursor = conn.execute(
                        'SELECT committee_id FROM committees WHERE system_code = ?',
                        (system_code,)
                    )
                    existing = cursor.fetchone()

                    if existing:
                        # Update existing committee
                        conn.execute('''
                            UPDATE committees
                            SET name = ?, chamber = ?, type = ?, congress = ?
                            WHERE system_code = ?
                        ''', (name, chamber.title(), committee_type, congress, system_code))
                        updated_committees.append(system_code)
                    else:
                        # Insert new committee
                        conn.execute('''
                            INSERT INTO committees (system_code, name, chamber, type, parent_committee_id, congress)
                            VALUES (?, ?, ?, ?, NULL, ?)
                        ''', (system_code, name, chamber.title(), committee_type, congress))
                        new_committees.append(system_code)

                # Get subcommittees for this committee
                if 'subcommittees' in committee and committee['subcommittees']:
                    subcommittees = committee['subcommittees']
                    print(f"  Committee {system_code} has {len(subcommittees)} subcommittees")

                    for subcommittee in subcommittees:
                        sub_system_code = subcommittee.get('systemCode')
                        sub_name = subcommittee.get('name')

                        if not sub_system_code or not sub_name:
                            continue

                        # Get parent committee ID
                        with db.transaction() as conn:
                            cursor = conn.execute(
                                'SELECT committee_id FROM committees WHERE system_code = ?',
                                (system_code,)
                            )
                            parent_id = cursor.fetchone()[0]

                            # Check if subcommittee exists
                            cursor = conn.execute(
                                'SELECT committee_id FROM committees WHERE system_code = ?',
                                (sub_system_code,)
                            )
                            existing_sub = cursor.fetchone()

                            if existing_sub:
                                # Update existing subcommittee
                                conn.execute('''
                                    UPDATE committees
                                    SET name = ?, chamber = ?, type = ?, parent_committee_id = ?, congress = ?
                                    WHERE system_code = ?
                                ''', (sub_name, chamber.title(), 'Subcommittee', parent_id, congress, sub_system_code))
                                updated_committees.append(sub_system_code)
                            else:
                                # Insert new subcommittee
                                conn.execute('''
                                    INSERT INTO committees (system_code, name, chamber, type, parent_committee_id, congress)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (sub_system_code, sub_name, chamber.title(), 'Subcommittee', parent_id, congress))
                                new_committees.append(sub_system_code)

        except Exception as e:
            logger.error(f"Error fetching {chamber} committees: {e}")
            continue

    # Get final statistics
    with db.transaction() as conn:
        cursor = conn.execute('SELECT COUNT(*) FROM committees')
        final_count = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NULL')
        parent_count = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NOT NULL')
        sub_count = cursor.fetchone()[0]

        # Show sample of new committees
        cursor = conn.execute('''
            SELECT system_code, name, chamber, type,
                   CASE WHEN parent_committee_id IS NULL THEN 'Parent' ELSE 'Sub' END as level
            FROM committees
            ORDER BY chamber, parent_committee_id IS NOT NULL, name
            LIMIT 10
        ''')
        samples = cursor.fetchall()

    print(f"\n=== Refresh Results ===")
    print(f"New committees added: {len(new_committees)}")
    print(f"Committees updated: {len(updated_committees)}")
    print(f"Total committees: {final_count} (was {current_count})")
    print(f"Parent committees: {parent_count}")
    print(f"Subcommittees: {sub_count}")

    print(f"\nSample committees:")
    for sample in samples:
        print(f"  {sample[0]} | {sample[1][:50]} | {sample[2]} | {sample[4]}")

    if new_committees:
        print(f"\nNew committee codes added:")
        for code in new_committees[:20]:  # Show first 20
            print(f"  {code}")
        if len(new_committees) > 20:
            print(f"  ... and {len(new_committees) - 20} more")

if __name__ == "__main__":
    refresh_committees()