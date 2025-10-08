#!/usr/bin/env python3
"""
Backfill committee links for hearings

This script re-fetches committee data from the API for hearings that have no
committee links, and restores the links using the current committee structure.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from parsers.hearing_parser import HearingParser
from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


def backfill_hearing_committees():
    """Backfill committee links for hearings without committees"""
    db = DatabaseManager()
    client = CongressAPIClient()
    parser = HearingParser()

    # Get hearings without committees
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT h.hearing_id, h.event_id, h.chamber, h.title
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.committee_id IS NULL
              AND h.title IS NOT NULL  -- Exclude invalid records
            ORDER BY h.chamber, h.hearing_date_only DESC
        ''')

        hearings_without_committees = cursor.fetchall()

    if not hearings_without_committees:
        print("All hearings have committee links!")
        return

    print(f"Found {len(hearings_without_committees)} hearings without committees")
    print()

    stats = {
        'success': 0,
        'no_committees_in_api': 0,
        'committee_not_found': 0,
        'api_error': 0,
        'parse_error': 0
    }

    for i, (hearing_id, event_id, chamber, title) in enumerate(hearings_without_committees, 1):
        if i % 50 == 0:
            print(f"Processed {i}/{len(hearings_without_committees)} hearings...")
            print(f"  Success: {stats['success']}, No API committees: {stats['no_committees_in_api']}, "
                  f"Committee not found: {stats['committee_not_found']}, Errors: {stats['api_error'] + stats['parse_error']}")

        try:
            # Fetch full hearing details from API
            endpoint = f"committee-meeting/{settings.target_congress}/{chamber.lower()}/{event_id}"

            try:
                hearing_data = client.get(endpoint)
            except Exception as e:
                logger.warning(f"API error for hearing {event_id}: {e}")
                stats['api_error'] += 1
                continue

            if not hearing_data:
                logger.warning(f"No data returned from API for hearing {event_id}")
                stats['api_error'] += 1
                continue

            # Extract the committeeMeeting object from API response
            # API returns: {"committeeMeeting": {...}}
            # Parser expects: {...} (the inner object)
            if 'committeeMeeting' in hearing_data:
                meeting_data = hearing_data['committeeMeeting']
            else:
                # Fallback for unexpected structure
                meeting_data = hearing_data

            # Extract committee references
            try:
                committee_refs = parser.extract_committee_references(meeting_data)
            except Exception as e:
                logger.error(f"Parser error for hearing {event_id}: {e}")
                stats['parse_error'] += 1
                continue

            if not committee_refs:
                logger.debug(f"No committees found in API for hearing {event_id}")
                stats['no_committees_in_api'] += 1
                continue

            # Link committees
            linked_count = 0
            for committee_ref in committee_refs:
                system_code = committee_ref.get('system_code')
                if not system_code:
                    continue

                # Get committee from database
                committee = db.get_committee_by_system_code(system_code)
                if committee:
                    # Link committee to hearing
                    try:
                        db.link_hearing_committee(
                            hearing_id,
                            committee['committee_id'],
                            committee_ref.get('is_primary', False)
                        )
                        linked_count += 1
                        logger.debug(f"Linked committee {system_code} to hearing {event_id}")
                    except Exception as e:
                        logger.error(f"Error linking committee {system_code} to hearing {event_id}: {e}")
                else:
                    logger.warning(f"Committee {system_code} not found in database for hearing {event_id}")
                    stats['committee_not_found'] += 1

            if linked_count > 0:
                stats['success'] += 1
                logger.info(f"Backfilled {linked_count} committee links for hearing {event_id}")

        except Exception as e:
            logger.error(f"Unexpected error processing hearing {event_id}: {e}")
            stats['api_error'] += 1

    print()
    print("=== Backfill Complete ===")
    print(f"Total hearings processed: {len(hearings_without_committees)}")
    print(f"Successfully linked: {stats['success']}")
    print(f"No committees in API: {stats['no_committees_in_api']}")
    print(f"Committee not found in database: {stats['committee_not_found']}")
    print(f"API errors: {stats['api_error']}")
    print(f"Parse errors: {stats['parse_error']}")
    print()

    # Show final statistics
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT COUNT(DISTINCT h.hearing_id)
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.committee_id IS NULL
              AND h.title IS NOT NULL
        ''')
        remaining = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM hearings WHERE title IS NOT NULL')
        total = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(DISTINCT h.hearing_id)
            FROM hearings h
            JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE h.title IS NOT NULL
        ''')
        with_committees = cursor.fetchone()[0]

        print("Final statistics:")
        print(f"  Total hearings (valid): {total}")
        print(f"  Hearings with committees: {with_committees}")
        print(f"  Hearings without committees: {remaining}")
        print(f"  Coverage: {(with_committees/total*100):.1f}%")


if __name__ == "__main__":
    backfill_hearing_committees()
