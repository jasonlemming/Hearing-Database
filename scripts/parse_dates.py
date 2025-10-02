#!/usr/bin/env python3
"""
Parse hearing dates into separate date and time columns
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from datetime import datetime
import re

def parse_hearing_dates():
    """Parse existing hearing dates into separate date and time columns"""

    db = DatabaseManager()

    with db.transaction() as conn:
        # Get hearings with dates to parse
        cursor = conn.execute('''
            SELECT hearing_id, hearing_date
            FROM hearings
            WHERE hearing_date IS NOT NULL
            AND (hearing_date_only IS NULL OR hearing_time IS NULL)
        ''')
        hearings = cursor.fetchall()

        print(f"Found {len(hearings)} hearings with dates to parse")

        updated = 0
        for hearing_id, hearing_date in hearings:
            try:
                # Parse ISO format datetime
                if isinstance(hearing_date, str):
                    # Handle various ISO formats
                    if hearing_date.endswith('Z'):
                        dt = datetime.fromisoformat(hearing_date.replace('Z', '+00:00'))
                    elif '+' in hearing_date or hearing_date.endswith('T'):
                        dt = datetime.fromisoformat(hearing_date)
                    else:
                        # Try parsing as date only
                        dt = datetime.strptime(hearing_date, '%Y-%m-%d')

                    # Extract date and time components
                    date_only = dt.date().isoformat()
                    time_only = dt.time().isoformat()

                    # Update the record
                    conn.execute('''
                        UPDATE hearings
                        SET hearing_date_only = ?, hearing_time = ?
                        WHERE hearing_id = ?
                    ''', (date_only, time_only, hearing_id))

                    updated += 1
                    if updated % 10 == 0:
                        print(f"Updated {updated} hearings...")

            except Exception as e:
                print(f"Error parsing date for hearing {hearing_id}: {hearing_date} - {e}")
                continue

        print(f"Successfully parsed {updated} hearing dates")

        # Show sample results
        cursor = conn.execute('''
            SELECT hearing_date, hearing_date_only, hearing_time, title
            FROM hearings
            WHERE hearing_date_only IS NOT NULL
            LIMIT 5
        ''')

        print("\nSample parsed dates:")
        for row in cursor.fetchall():
            print(f"  Original: {row[0]}")
            print(f"  Date: {row[1]}, Time: {row[2]}")
            print(f"  Title: {row[3][:50]}...")
            print()

if __name__ == "__main__":
    parse_hearing_dates()