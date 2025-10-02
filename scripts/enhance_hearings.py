#!/usr/bin/env python3
"""
Enhance hearing data by fetching detailed information from Congress.gov API
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from typing import List, Dict, Any
from database.manager import DatabaseManager
from api.client import CongressAPIClient
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


def enhance_hearings():
    """Enhance existing hearings with detailed information"""

    db = DatabaseManager()
    client = CongressAPIClient()

    # Get hearings that need enhancement (missing titles, dates, or committees)
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT DISTINCT h.hearing_id, h.event_id, h.congress, h.chamber
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE (h.title IS NULL OR h.title = ''
                   OR h.hearing_date IS NULL
                   OR hc.hearing_id IS NULL)
            AND h.event_id IS NOT NULL
            ORDER BY h.hearing_id
            LIMIT 200
        ''')
        hearings_to_enhance = cursor.fetchall()

    logger.info(f"Found {len(hearings_to_enhance)} hearings to enhance")

    enhanced_count = 0
    errors = 0

    for hearing_id, event_id, congress, chamber in hearings_to_enhance:
        try:
            logger.info(f"Enhancing hearing {hearing_id} (event {event_id})")

            # Fetch detailed hearing data
            detailed_data = client.get_hearing_details(congress, chamber.lower(), event_id)

            if not detailed_data or 'committeeMeeting' not in detailed_data:
                logger.warning(f"No detailed data for hearing {hearing_id}")
                continue

            meeting_data = detailed_data['committeeMeeting']
            logger.debug(f"Meeting data keys: {list(meeting_data.keys())}")

            # Extract enhanced information
            title = meeting_data.get('title')
            hearing_date = None
            location_data = meeting_data.get('location')
            location = None
            if isinstance(location_data, str):
                location = location_data
            elif isinstance(location_data, dict) and 'description' in location_data:
                location = location_data['description']

            # Try to extract date from various fields
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

            # Extract committee information for relationship creation
            committees = []
            if 'committees' in meeting_data:
                committees = meeting_data['committees']
            elif 'committee' in meeting_data:
                committees = [meeting_data['committee']]

            # Parse date into separate date and time
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
                updates['hearing_date'] = date_only  # Store only date part, not full datetime
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

                    # Create committee relationships
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

            enhanced_count += 1
            logger.info(f"Enhanced hearing {hearing_id}: {len(updates)} fields updated, {len(committees)} committee relationships")

            # Rate limiting
            time.sleep(0.2)

        except Exception as e:
            logger.error(f"Error enhancing hearing {hearing_id}: {e}")
            errors += 1
            continue

    logger.info(f"Enhancement complete: {enhanced_count} hearings enhanced, {errors} errors")

    # Print final statistics
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT COUNT(*) as total_hearings,
                   COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_titles,
                   COUNT(CASE WHEN hearing_date IS NOT NULL THEN 1 END) as with_dates
            FROM hearings
        ''')
        stats = cursor.fetchone()

        cursor = conn.execute('SELECT COUNT(*) FROM hearing_committees')
        relationships = cursor.fetchone()[0]

        print(f"\nFinal statistics:")
        print(f"Total hearings: {stats[0]}")
        print(f"With titles: {stats[1]}")
        print(f"With dates: {stats[2]}")
        print(f"Committee relationships: {relationships}")


if __name__ == "__main__":
    enhance_hearings()