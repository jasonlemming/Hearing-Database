#!/usr/bin/env python3
"""
Delete invalid hearing records

This script deletes hearings that have:
- NULL or empty title
- NULL hearing_date_only
- No committee links

These are incomplete records from failed imports that cannot be recovered.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)


def delete_invalid_hearings():
    """Find and delete invalid hearing records"""
    db = DatabaseManager()

    with db.transaction() as conn:
        # Find invalid hearings
        cursor = conn.execute('''
            SELECT hearing_id, event_id, chamber, status
            FROM hearings
            WHERE (title IS NULL OR title = '')
              AND hearing_date_only IS NULL
            ORDER BY event_id
        ''')

        invalid_hearings = cursor.fetchall()

        if not invalid_hearings:
            print("No invalid hearings found.")
            return

        print(f"Found {len(invalid_hearings)} invalid hearings:")
        print()

        for hearing_id, event_id, chamber, status in invalid_hearings:
            print(f"  Hearing {hearing_id} | Event ID: {event_id} | {chamber} | {status}")

        print()
        print(f"Deleting {len(invalid_hearings)} invalid hearings...")

        # Delete related records first to avoid foreign key constraints
        for hearing_id, event_id, chamber, status in invalid_hearings:
            # Delete from all related tables
            conn.execute('DELETE FROM hearing_committees WHERE hearing_id = ?', (hearing_id,))
            conn.execute('DELETE FROM hearing_bills WHERE hearing_id = ?', (hearing_id,))
            conn.execute('DELETE FROM witness_appearances WHERE hearing_id = ?', (hearing_id,))
            conn.execute('DELETE FROM hearing_transcripts WHERE hearing_id = ?', (hearing_id,))
            conn.execute('DELETE FROM supporting_documents WHERE hearing_id = ?', (hearing_id,))

            # Now delete the hearing
            conn.execute('DELETE FROM hearings WHERE hearing_id = ?', (hearing_id,))
            logger.info(f"Deleted invalid hearing {hearing_id} (event_id: {event_id})")

        print(f"✓ Deleted {len(invalid_hearings)} invalid hearings")
        print()

        # Show final counts
        cursor = conn.execute('SELECT COUNT(*) FROM hearings')
        total_hearings = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE hearing_date_only IS NULL
        ''')
        null_dates = cursor.fetchone()[0]

        cursor = conn.execute('''
            SELECT COUNT(DISTINCT h.hearing_id)
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.committee_id IS NULL
        ''')
        no_committees = cursor.fetchone()[0]

        print("Database statistics:")
        print(f"  Total hearings: {total_hearings}")
        print(f"  Hearings with NULL date: {null_dates}")
        print(f"  Hearings without committees: {no_committees}")


if __name__ == "__main__":
    delete_invalid_hearings()
