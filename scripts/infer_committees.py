#!/usr/bin/env python3
"""
Infer committee relationships for hearings without committees
using event ID patterns, chamber, and proximity analysis
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from collections import defaultdict, Counter

def infer_committee_relationships():
    """Infer committee relationships using various heuristics"""

    db = DatabaseManager()

    with db.transaction() as conn:
        # Get hearings with known committee relationships
        cursor = conn.execute('''
            SELECT h.hearing_id, h.event_id, h.chamber, c.committee_id, c.system_code
            FROM hearings h
            JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            JOIN committees c ON hc.committee_id = c.committee_id
            WHERE h.event_id IS NOT NULL
            ORDER BY h.event_id
        ''')
        known_relationships = cursor.fetchall()

        # Get hearings without committee relationships
        cursor = conn.execute('''
            SELECT h.hearing_id, h.event_id, h.chamber, h.title
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.hearing_id IS NULL
            AND h.event_id IS NOT NULL
            ORDER BY h.event_id
        ''')
        orphan_hearings = cursor.fetchall()

        print(f"Found {len(known_relationships)} hearings with known committees")
        print(f"Found {len(orphan_hearings)} hearings without committees")

        # Build proximity maps for each chamber
        chamber_maps = defaultdict(list)
        for hearing_id, event_id, chamber, committee_id, system_code in known_relationships:
            chamber_maps[chamber].append((event_id, committee_id, system_code))

        # Sort by event_id for proximity analysis
        for chamber in chamber_maps:
            chamber_maps[chamber].sort()

        inferred_relationships = []

        # For each orphan hearing, find the closest committee by event ID
        for hearing_id, event_id, chamber, title in orphan_hearings:
            if chamber not in chamber_maps:
                continue

            # Convert event_id to int for comparison
            try:
                event_id_int = int(event_id)
            except (ValueError, TypeError):
                continue

            # Find closest event IDs in same chamber
            closest_committees = []
            chamber_events = chamber_maps[chamber]

            for known_event_id, committee_id, system_code in chamber_events:
                try:
                    known_event_id_int = int(known_event_id)
                    distance = abs(event_id_int - known_event_id_int)
                    closest_committees.append((distance, committee_id, system_code))
                except (ValueError, TypeError):
                    continue

            # Sort by distance and get top 3 closest
            closest_committees.sort()

            if closest_committees:
                # Use the closest committee as primary candidate
                best_distance, best_committee_id, best_system_code = closest_committees[0]

                # Additional heuristics can be added here:
                # - Title keyword matching
                # - Date proximity
                # - Committee specialization patterns

                # Only infer if the distance is reasonable (within 100 event IDs)
                if best_distance <= 100:
                    inferred_relationships.append({
                        'hearing_id': hearing_id,
                        'event_id': event_id,
                        'committee_id': best_committee_id,
                        'system_code': best_system_code,
                        'distance': best_distance,
                        'confidence': 'proximity'
                    })

        print(f"\nInferred {len(inferred_relationships)} potential committee relationships")

        # Show sample inferences
        print("\nSample inferences:")
        for inference in inferred_relationships[:10]:
            print(f"  Event {inference['event_id']} -> {inference['system_code']} (distance: {inference['distance']})")

        # Apply the inferences to database
        if inferred_relationships:
            print(f"\nApplying {len(inferred_relationships)} inferred relationships to database...")
            if True:  # Auto-apply
                applied = 0
                for inference in inferred_relationships:
                    try:
                        # Check if relationship already exists
                        cursor = conn.execute('''
                            SELECT 1 FROM hearing_committees
                            WHERE hearing_id = ? AND committee_id = ?
                        ''', (inference['hearing_id'], inference['committee_id']))

                        if not cursor.fetchone():
                            # Insert the inferred relationship
                            conn.execute('''
                                INSERT INTO hearing_committees
                                (hearing_id, committee_id, is_primary)
                                VALUES (?, ?, 1)
                            ''', (inference['hearing_id'], inference['committee_id']))
                            applied += 1
                    except Exception as e:
                        print(f"Error applying inference for hearing {inference['hearing_id']}: {e}")

                print(f"Applied {applied} inferred committee relationships")

                # Show final statistics
                cursor = conn.execute('''
                    SELECT COUNT(*) as total_hearings,
                           COUNT(CASE WHEN hc.hearing_id IS NOT NULL THEN 1 END) as with_committees
                    FROM hearings h
                    LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                ''')
                stats = cursor.fetchone()
                print(f"\nFinal statistics:")
                print(f"Total hearings: {stats[0]}")
                print(f"With committees: {stats[1]}")
                print(f"Missing committees: {stats[0] - stats[1]}")

if __name__ == "__main__":
    infer_committee_relationships()