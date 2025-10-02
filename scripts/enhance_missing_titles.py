#!/usr/bin/env python3
"""
Target hearings without titles for enhancement
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.logging_config import get_logger

logger = get_logger(__name__)

def enhance_missing_titles():
    """Focus on hearings without titles that show as 'Event #XXXXX'"""

    db = DatabaseManager()
    client = CongressAPIClient()

    print("=" * 60)
    print("ENHANCING HEARINGS WITHOUT TITLES")
    print("=" * 60)

    # Get hearings without titles
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT hearing_id, event_id, congress, chamber
            FROM hearings
            WHERE (title IS NULL OR title = '') AND event_id IS NOT NULL
            ORDER BY CAST(event_id AS INTEGER)
            LIMIT 100
        ''')
        missing_title_hearings = cursor.fetchall()

    print(f"Found {len(missing_title_hearings)} hearings without titles")

    enhanced_count = 0
    errors = 0

    for i, (hearing_id, event_id, congress, chamber) in enumerate(missing_title_hearings, 1):
        try:
            print(f"[{i}/{len(missing_title_hearings)}] Enhancing {chamber} hearing {hearing_id} (event {event_id})")

            # Try to fetch detailed hearing data
            detailed_data = client.get_hearing_details(congress, chamber.lower(), event_id)

            if not detailed_data or 'committeeMeeting' not in detailed_data:
                print(f"  ⚠️  No detailed data available for event {event_id}")
                continue

            meeting_data = detailed_data['committeeMeeting']

            # Extract information
            title = meeting_data.get('title')
            hearing_date = None
            location_data = meeting_data.get('location')
            location = None

            if isinstance(location_data, str):
                location = location_data
            elif isinstance(location_data, dict) and 'description' in location_data:
                location = location_data['description']

            # Extract date
            if 'date' in meeting_data:
                date_val = meeting_data['date']
                if isinstance(date_val, str):
                    hearing_date = date_val
                elif isinstance(date_val, dict) and 'date' in date_val:
                    hearing_date = date_val['date']
            elif 'eventDate' in meeting_data:
                date_val = meeting_data['eventDate']
                if isinstance(date_val, str):
                    hearing_date = date_val
                elif isinstance(date_val, dict) and 'date' in date_val:
                    hearing_date = date_val['date']

            # Parse date
            date_only = None
            time_only = None
            if hearing_date:
                try:
                    from datetime import datetime
                    if hearing_date.endswith('Z'):
                        dt = datetime.fromisoformat(hearing_date.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(hearing_date)
                    date_only = dt.date().isoformat()
                    time_only = dt.time().isoformat()
                except Exception as e:
                    logger.warning(f"Could not parse date {hearing_date}: {e}")

            # Update hearing record
            updates = {}
            if title and title.strip():
                updates['title'] = title.strip()
            if date_only:
                updates['hearing_date'] = date_only
                updates['hearing_date_only'] = date_only
            if time_only:
                updates['hearing_time'] = time_only
            if location:
                updates['location'] = location

            if updates:
                with db.transaction() as conn:
                    # Build update query
                    set_clauses = []
                    values = []
                    for field, value in updates.items():
                        set_clauses.append(f"{field} = ?")
                        values.append(value)

                    if set_clauses:
                        query = f"UPDATE hearings SET {', '.join(set_clauses)} WHERE hearing_id = ?"
                        values.append(hearing_id)
                        conn.execute(query, values)

                    # Handle committee relationships
                    committees = []
                    if 'committees' in meeting_data:
                        committees = meeting_data['committees']
                    elif 'committee' in meeting_data:
                        committees = [meeting_data['committee']]

                    # Create committee relationships
                    new_relationships = 0
                    for committee_data in committees:
                        if isinstance(committee_data, dict):
                            committee_code = committee_data.get('systemCode')
                            if committee_code:
                                # Find committee by system code
                                cursor = conn.execute(
                                    'SELECT committee_id FROM committees WHERE system_code = ?',
                                    (committee_code,)
                                )
                                committee_result = cursor.fetchone()

                                if committee_result:
                                    committee_id = committee_result[0]

                                    # Check if relationship already exists
                                    cursor = conn.execute('''
                                        SELECT 1 FROM hearing_committees
                                        WHERE hearing_id = ? AND committee_id = ?
                                    ''', (hearing_id, committee_id))

                                    if not cursor.fetchone():
                                        # Insert relationship
                                        conn.execute('''
                                            INSERT INTO hearing_committees
                                            (hearing_id, committee_id, is_primary)
                                            VALUES (?, ?, 1)
                                        ''', (hearing_id, committee_id))
                                        new_relationships += 1

                enhanced_count += 1
                title_display = title[:50] + "..." if title and len(title) > 50 else title
                print(f"  ✓ Enhanced: '{title_display}' | Date: {date_only} | Committees: {new_relationships}")

            else:
                print(f"  ⚠️  No enhancement data available")

            # Rate limiting
            time.sleep(0.2)

        except Exception as e:
            logger.error(f"Error enhancing hearing {hearing_id}: {e}")
            errors += 1
            continue

    print(f"\n" + "=" * 60)
    print("ENHANCEMENT COMPLETE")
    print("=" * 60)
    print(f"Enhanced: {enhanced_count} hearings")
    print(f"Errors: {errors}")

    # Check remaining hearings without titles
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE title IS NULL OR title = ''
        ''')
        remaining = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE title IS NOT NULL AND title != ''
        ''')
        with_titles = cursor.fetchone()[0]

        total = remaining + with_titles
        print(f"\nFinal status:")
        print(f"Hearings with titles: {with_titles}/{total} ({with_titles/total*100:.1f}%)")
        print(f"Still missing titles: {remaining}")

if __name__ == "__main__":
    enhance_missing_titles()