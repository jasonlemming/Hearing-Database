#!/usr/bin/env python3
"""
Comprehensive hearing enhancement script with improved error handling and Senate focus
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

def comprehensive_enhancement():
    """Comprehensive enhancement targeting all gaps identified in audit"""

    db = DatabaseManager()
    client = CongressAPIClient()

    print("=" * 80)
    print("COMPREHENSIVE HEARING ENHANCEMENT")
    print("=" * 80)

    # Phase 1: Target hearings without titles/dates (prioritizing Senate)
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT DISTINCT h.hearing_id, h.event_id, h.congress, h.chamber
            FROM hearings h
            WHERE h.event_id IS NOT NULL
            AND (h.title IS NULL OR h.title = '' OR h.hearing_date IS NULL)
            ORDER BY
                CASE WHEN h.chamber = 'Senate' THEN 1 ELSE 2 END,  -- Prioritize Senate
                h.hearing_id
            LIMIT 500
        ''')
        hearings_to_enhance = cursor.fetchall()

    print(f"Phase 1: Enhancing {len(hearings_to_enhance)} hearings without titles/dates")

    enhanced_count = 0
    errors = 0
    senate_enhanced = 0
    house_enhanced = 0

    for i, (hearing_id, event_id, congress, chamber) in enumerate(hearings_to_enhance, 1):
        try:
            print(f"[{i}/{len(hearings_to_enhance)}] Enhancing {chamber} hearing {hearing_id} (event {event_id})")

            # Fetch detailed hearing data
            detailed_data = client.get_hearing_details(congress, chamber.lower(), event_id)

            if not detailed_data or 'committeeMeeting' not in detailed_data:
                logger.warning(f"No detailed data for hearing {hearing_id}")
                continue

            meeting_data = detailed_data['committeeMeeting']

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

                    # Extract committee information for relationship creation
                    committees = []
                    if 'committees' in meeting_data:
                        committees = meeting_data['committees']
                    elif 'committee' in meeting_data:
                        committees = [meeting_data['committee']]

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
            if chamber == 'Senate':
                senate_enhanced += 1
            else:
                house_enhanced += 1

            print(f"  ✓ Enhanced: {len(updates)} fields updated, {len(committees)} committee relationships")

            # Rate limiting - be more aggressive for Senate
            if chamber == 'Senate':
                time.sleep(0.15)  # Faster for Senate since they need more help
            else:
                time.sleep(0.25)

        except Exception as e:
            logger.error(f"Error enhancing hearing {hearing_id}: {e}")
            errors += 1
            # Continue with next hearing
            continue

    print(f"\nPhase 1 Complete:")
    print(f"  Enhanced: {enhanced_count} hearings")
    print(f"  Senate: {senate_enhanced}, House: {house_enhanced}")
    print(f"  Errors: {errors}")

    # Phase 2: Apply advanced committee relationship inference
    print(f"\nPhase 2: Advanced Committee Relationship Inference")
    print("-" * 50)

    with db.transaction() as conn:
        # Get hearings without committee assignments that have titles
        cursor = conn.execute('''
            SELECT h.hearing_id, h.title, h.chamber, h.event_id
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.hearing_id IS NULL
            AND h.title IS NOT NULL
            AND h.title != ''
            ORDER BY h.chamber
        ''')

        unassigned_with_titles = cursor.fetchall()

    print(f"Found {len(unassigned_with_titles)} unassigned hearings with titles")

    # Apply keyword-based committee matching
    keyword_matches = 0

    committee_keywords = {
        'hsag00': ['agriculture', 'farm', 'crop', 'livestock', 'dairy', 'rural', 'food', 'nutrition', 'snap'],
        'hsap00': ['appropriation', 'budget', 'funding', 'spending'],
        'hsas00': ['armed services', 'defense', 'military', 'army', 'navy', 'air force', 'marines'],
        'hsba00': ['financial services', 'banking', 'finance', 'monetary', 'federal reserve'],
        'hsed00': ['education', 'workforce', 'school', 'student', 'teacher'],
        'hsif00': ['energy', 'commerce', 'trade', 'environment'],
        'hsfa00': ['foreign affairs', 'international', 'diplomatic', 'embassy'],
        'hshm00': ['homeland security', 'terrorism', 'border', 'immigration'],
        'hsju00': ['judiciary', 'justice', 'court', 'legal', 'constitutional'],
        'hsii00': ['natural resources', 'environment', 'interior', 'wildlife'],
        'hsgo00': ['oversight', 'government reform', 'inspector general'],
        'hssy00': ['science', 'technology', 'research', 'innovation', 'space'],
        'hspw00': ['transportation', 'infrastructure', 'highway', 'aviation'],
        'hsvr00': ['veterans', 'va hospital', 'veteran affairs'],
        'hswm00': ['ways and means', 'tax', 'revenue', 'irs'],
        # Senate committees
        'ssaf00': ['agriculture', 'nutrition', 'forestry'],
        'ssap00': ['appropriation'],
        'ssas00': ['armed services', 'defense', 'military'],
        'ssbk00': ['banking', 'housing', 'urban affairs'],
        'sscm00': ['commerce', 'science', 'transportation'],
        'ssev00': ['environment', 'public works'],
        'ssfi00': ['finance'],
        'ssfr00': ['foreign relations'],
        'sshr00': ['health', 'education', 'labor', 'pensions'],
        'ssga00': ['homeland security', 'governmental affairs'],
        'ssju00': ['judiciary'],
        'sssb00': ['small business']
    }

    with db.transaction() as conn:
        for hearing_id, title, chamber, event_id in unassigned_with_titles:
            title_lower = title.lower()
            best_match = None

            for committee_code, keywords in committee_keywords.items():
                # Match chamber
                if (chamber == 'House' and not committee_code.startswith('hs')) or \
                   (chamber == 'Senate' and not committee_code.startswith('ss')):
                    continue

                for keyword in keywords:
                    if keyword in title_lower:
                        # Find committee ID
                        cursor = conn.execute(
                            'SELECT committee_id FROM committees WHERE system_code = ?',
                            (committee_code,)
                        )
                        committee_result = cursor.fetchone()

                        if committee_result:
                            committee_id = committee_result[0]

                            # Insert relationship
                            cursor = conn.execute('''
                                INSERT OR IGNORE INTO hearing_committees
                                (hearing_id, committee_id, is_primary)
                                VALUES (?, ?, 1)
                            ''', (hearing_id, committee_id))

                            if cursor.rowcount > 0:
                                keyword_matches += 1
                                print(f"  ✓ Matched '{keyword}' in title -> {committee_code}")
                            break

                if best_match:
                    break

    print(f"Applied {keyword_matches} keyword-based committee relationships")

    # Final statistics
    print(f"\n" + "=" * 80)
    print("COMPREHENSIVE ENHANCEMENT COMPLETE")
    print("=" * 80)

    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT COUNT(*) as total_hearings,
                   COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_titles,
                   COUNT(CASE WHEN hearing_date_only IS NOT NULL THEN 1 END) as with_dates
            FROM hearings
        ''')
        stats = cursor.fetchone()

        cursor = conn.execute('SELECT COUNT(*) FROM hearing_committees')
        relationships = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(DISTINCT h.hearing_id)
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.hearing_id IS NULL
        ''')
        still_unassigned = cursor.fetchone()[0]

        print(f"Final statistics:")
        print(f"Total hearings: {stats[0]}")
        print(f"With titles: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
        print(f"With dates: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
        print(f"Committee relationships: {relationships}")
        print(f"Still unassigned: {still_unassigned}")

        # Chamber breakdown
        cursor = conn.execute('''
            SELECT
                h.chamber,
                COUNT(*) as total,
                COUNT(CASE WHEN h.title IS NOT NULL AND h.title != '' THEN 1 END) as titles,
                COUNT(CASE WHEN hc.hearing_id IS NOT NULL THEN 1 END) as committees
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            GROUP BY h.chamber
        ''')

        print(f"\nBy chamber:")
        for row in cursor.fetchall():
            chamber, total, titles, committees = row
            print(f"  {chamber}: {titles}/{total} titles ({titles/total*100:.1f}%), {committees}/{total} committees ({committees/total*100:.1f}%)")

if __name__ == "__main__":
    comprehensive_enhancement()