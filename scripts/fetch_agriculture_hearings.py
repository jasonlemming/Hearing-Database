#!/usr/bin/env python3
"""
Specifically fetch Agriculture Committee hearings using targeted API calls
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.logging_config import get_logger
import time

logger = get_logger(__name__)

def fetch_agriculture_hearings():
    """Fetch Agriculture Committee hearings directly"""

    db = DatabaseManager()
    client = CongressAPIClient()

    # Get Agriculture Committee system code
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT system_code FROM committees
            WHERE name LIKE '%Agriculture%' AND parent_committee_id IS NULL
        ''')
        ag_result = cursor.fetchone()

        if not ag_result:
            print("Agriculture Committee not found!")
            return

        ag_system_code = ag_result[0]
        print(f"Agriculture Committee system code: {ag_system_code}")

    # Try to fetch committee meetings specifically for Agriculture
    try:
        print("Fetching Agriculture Committee meetings...")

        # Try direct committee endpoint
        endpoint = f"committee/house/{ag_system_code}/committee-meeting"

        try:
            meetings = list(client.paginate(endpoint, {'congress': 118}))
            print(f"Found {len(meetings)} Agriculture committee meetings")

            new_hearings = 0
            for meeting in meetings:
                event_id = meeting.get('eventId')
                if not event_id:
                    continue

                # Check if we have this hearing
                with db.transaction() as conn:
                    cursor = conn.execute('''
                        SELECT hearing_id FROM hearings WHERE event_id = ?
                    ''', (str(event_id),))

                    if not cursor.fetchone():
                        # Insert new hearing
                        cursor = conn.execute('''
                            INSERT INTO hearings (
                                event_id, congress, chamber,
                                created_at, updated_at
                            ) VALUES (?, 118, 'House', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ''', (str(event_id),))

                        new_hearings += 1
                        print(f"Added hearing with event ID: {event_id}")

            print(f"Added {new_hearings} new Agriculture hearings")

        except Exception as e:
            logger.warning(f"Direct committee endpoint failed: {e}")

            # Fallback: Try searching by date range
            print("Trying fallback approach...")

            # Try fetching recent house meetings and filter for Agriculture
            endpoint = "committee-meeting"
            params = {
                'congress': 118,
                'chamber': 'house',
                'limit': 50  # Smaller batch
            }

            meetings = []
            try:
                for meeting in client.paginate(endpoint, params):
                    meetings.append(meeting)
                    if len(meetings) >= 100:  # Limit to avoid API overload
                        break

                print(f"Found {len(meetings)} recent House meetings to check")

                # Filter for Agriculture-related meetings
                ag_meetings = []
                for meeting in meetings:
                    # Check if meeting relates to Agriculture
                    committees = meeting.get('committees', [])
                    for committee in committees:
                        if isinstance(committee, dict):
                            system_code = committee.get('systemCode', '')
                            if system_code.startswith('hsag'):
                                ag_meetings.append(meeting)
                                break

                print(f"Found {len(ag_meetings)} Agriculture-related meetings")

                # Add these to database
                new_hearings = 0
                for meeting in ag_meetings:
                    event_id = meeting.get('eventId')
                    if not event_id:
                        continue

                    with db.transaction() as conn:
                        cursor = conn.execute('''
                            SELECT hearing_id FROM hearings WHERE event_id = ?
                        ''', (str(event_id),))

                        if not cursor.fetchone():
                            cursor = conn.execute('''
                                INSERT INTO hearings (
                                    event_id, congress, chamber,
                                    created_at, updated_at
                                ) VALUES (?, 118, 'House', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            ''', (str(event_id),))

                            new_hearings += 1

                print(f"Added {new_hearings} new Agriculture hearings via fallback")

            except Exception as e2:
                logger.error(f"Fallback approach also failed: {e2}")
                print("Unable to fetch recent hearings due to API issues")
                return

    except Exception as e:
        logger.error(f"Error fetching Agriculture hearings: {e}")
        return

    # Get updated count
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE event_id NOT IN (
                SELECT DISTINCT h.event_id FROM hearings h
                JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                JOIN committees c ON hc.committee_id = c.committee_id
                WHERE c.system_code LIKE 'hsag%'
            )
            AND event_id IS NOT NULL
        ''')
        unassigned_count = cursor.fetchone()[0]

        print(f"\nNext steps:")
        print(f"1. Run enhance_hearings.py to get details for new hearings")
        print(f"2. Run infer_committees.py to link unassigned hearings ({unassigned_count} remaining)")

if __name__ == "__main__":
    fetch_agriculture_hearings()