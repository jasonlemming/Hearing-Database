#!/usr/bin/env python3
"""
Fetch recent hearings from Congress.gov API to fill gaps in our data
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.logging_config import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)

def fetch_recent_hearings():
    """Fetch recent hearings from Congress.gov API"""

    db = DatabaseManager()
    client = CongressAPIClient()

    # Get current latest hearing date
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT MAX(hearing_date_only) FROM hearings
            WHERE hearing_date_only IS NOT NULL
        ''')
        latest_date = cursor.fetchone()[0]
        print(f"Latest hearing in database: {latest_date}")

    # Fetch recent hearings for both chambers
    chambers = ['house', 'senate']
    new_hearings = 0

    for chamber in chambers:
        print(f"\nFetching recent {chamber} committee meetings...")

        try:
            # Get committee meetings from API
            endpoint = f"committee-meeting"
            params = {
                'congress': 118,
                'chamber': chamber,
                'limit': 250  # Get more results
            }

            meetings_data = list(client.paginate(endpoint, params))
            print(f"Found {len(meetings_data)} {chamber} committee meetings from API")

            for meeting in meetings_data:
                event_id = meeting.get('eventId')
                congress = meeting.get('congress')
                chamber_name = meeting.get('chamber')

                if not event_id or not congress:
                    continue

                # Check if we already have this hearing
                with db.transaction() as conn:
                    cursor = conn.execute('''
                        SELECT hearing_id FROM hearings
                        WHERE event_id = ? AND congress = ?
                    ''', (str(event_id), congress))

                    if cursor.fetchone():
                        continue  # Already have this hearing

                    # Insert new hearing
                    chamber_title = chamber_name.title() if chamber_name else chamber.title()

                    cursor = conn.execute('''
                        INSERT INTO hearings (
                            event_id, congress, chamber,
                            created_at, updated_at
                        ) VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ''', (str(event_id), congress, chamber_title))

                    hearing_id = cursor.lastrowid
                    new_hearings += 1

                    if new_hearings % 50 == 0:
                        print(f"  Added {new_hearings} new hearings...")

        except Exception as e:
            logger.error(f"Error fetching {chamber} hearings: {e}")
            continue

    print(f"\n=== Fetch Results ===")
    print(f"New hearings added: {new_hearings}")

    # Get updated statistics
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN hearing_date_only IS NOT NULL THEN 1 END) as with_dates,
                COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_titles,
                MAX(hearing_date_only) as latest_date
            FROM hearings
        ''')

        stats = cursor.fetchone()
        print(f"Total hearings: {stats[0]}")
        print(f"With dates: {stats[1]}")
        print(f"With titles: {stats[2]}")
        print(f"Latest date: {stats[3]}")

    if new_hearings > 0:
        print(f"\nNext step: Run enhance_hearings.py to get details for {new_hearings} new hearings")

if __name__ == "__main__":
    fetch_recent_hearings()