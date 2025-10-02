#!/usr/bin/env python3
"""
Daily Congressional Data Update Cron Job for Vercel
"""
import sys
import os
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from flask import Flask, jsonify, request
    from database.manager import DatabaseManager
    from fetchers.hearing_fetcher import HearingFetcher
    from fetchers.committee_fetcher import CommitteeFetcher
    from fetchers.member_fetcher import MemberFetcher
    from fetchers.witness_fetcher import WitnessFetcher
    from parsers.hearing_parser import HearingParser
    from parsers.committee_parser import CommitteeParser
    from parsers.member_parser import MemberParser
    from parsers.witness_parser import WitnessParser
    from api.client import CongressAPIClient
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)

def update_congressional_data():
    """Run daily Congressional data update"""
    try:
        # Initialize components
        api_client = CongressAPIClient()
        db = DatabaseManager()

        # Initialize fetchers and parsers
        hearing_fetcher = HearingFetcher(api_client)
        committee_fetcher = CommitteeFetcher(api_client)
        member_fetcher = MemberFetcher(api_client)
        witness_fetcher = WitnessFetcher(api_client)

        hearing_parser = HearingParser()
        committee_parser = CommitteeParser()
        member_parser = MemberParser()
        witness_parser = WitnessParser()

        update_results = {
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'updates': {}
        }

        # Update hearings (most recent data)
        logger.info("Updating hearings...")
        try:
            recent_hearings = hearing_fetcher.fetch_recent_hearings(119, days_back=2)
            hearing_count = 0

            for hearing_data in recent_hearings:
                parsed_hearing = hearing_parser.parse(hearing_data)
                if parsed_hearing:
                    with db.transaction() as conn:
                        # Insert or update hearing
                        conn.execute('''
                            INSERT OR REPLACE INTO hearings
                            (event_id, title, hearing_date, chamber, congress, location, status, hearing_type)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            parsed_hearing.event_id,
                            parsed_hearing.title,
                            parsed_hearing.hearing_date,
                            parsed_hearing.chamber,
                            parsed_hearing.congress,
                            parsed_hearing.location,
                            parsed_hearing.status,
                            parsed_hearing.hearing_type
                        ))
                        hearing_count += 1

            update_results['updates']['hearings'] = hearing_count
            logger.info(f"Updated {hearing_count} hearings")

        except Exception as e:
            logger.error(f"Error updating hearings: {e}")
            update_results['updates']['hearings'] = f"Error: {str(e)}"

        # Update committees
        logger.info("Updating committees...")
        try:
            committees = committee_fetcher.fetch_all_committees(119)
            committee_count = 0

            for committee_data in committees[:50]:  # Limit for daily updates
                parsed_committee = committee_parser.parse(committee_data)
                if parsed_committee:
                    with db.transaction() as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO committees
                            (system_code, name, chamber, type, parent_committee_id, congress)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            parsed_committee.system_code,
                            parsed_committee.name,
                            parsed_committee.chamber,
                            parsed_committee.type,
                            parsed_committee.parent_committee_id,
                            parsed_committee.congress
                        ))
                        committee_count += 1

            update_results['updates']['committees'] = committee_count
            logger.info(f"Updated {committee_count} committees")

        except Exception as e:
            logger.error(f"Error updating committees: {e}")
            update_results['updates']['committees'] = f"Error: {str(e)}"

        # Update members
        logger.info("Updating members...")
        try:
            members = member_fetcher.fetch_current_members(119)
            member_count = 0

            for member_data in members[:100]:  # Limit for daily updates
                parsed_member = member_parser.parse(member_data)
                if parsed_member:
                    with db.transaction() as conn:
                        conn.execute('''
                            INSERT OR REPLACE INTO members
                            (bioguide_id, first_name, middle_name, last_name, full_name,
                             party, state, district, birth_year, current_member, congress)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            parsed_member.bioguide_id,
                            parsed_member.first_name,
                            parsed_member.middle_name,
                            parsed_member.last_name,
                            parsed_member.full_name,
                            parsed_member.party,
                            parsed_member.state,
                            parsed_member.district,
                            parsed_member.birth_year,
                            parsed_member.current_member,
                            parsed_member.congress
                        ))
                        member_count += 1

            update_results['updates']['members'] = member_count
            logger.info(f"Updated {member_count} members")

        except Exception as e:
            logger.error(f"Error updating members: {e}")
            update_results['updates']['members'] = f"Error: {str(e)}"

        # Update witnesses for recent hearings
        logger.info("Updating witnesses...")
        try:
            witness_count = 0

            # Get recent hearings with event IDs
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT hearing_id, event_id FROM hearings
                    WHERE event_id IS NOT NULL
                    AND hearing_date >= date('now', '-7 days')
                    LIMIT 20
                ''')
                recent_hearing_events = cursor.fetchall()

            for hearing_id, event_id in recent_hearing_events:
                try:
                    # Get chamber from database for this hearing
                    with db.transaction() as conn:
                        cursor = conn.execute('''
                            SELECT chamber FROM hearings WHERE hearing_id = ?
                        ''', (hearing_id,))
                        hearing_row = cursor.fetchone()

                    if not hearing_row or not hearing_row[0]:
                        continue

                    chamber = hearing_row[0].lower()
                    witnesses, documents = witness_fetcher.fetch_witnesses_for_hearing(119, chamber, event_id)

                    for witness_data in witnesses:
                        witness_info = witness_fetcher.extract_witness_info(witness_data)
                        if witness_info and witness_info.get('full_name'):
                            with db.transaction() as conn:
                                # Insert or get witness
                                cursor = conn.execute('''
                                    INSERT OR IGNORE INTO witnesses
                                    (first_name, last_name, full_name, title, organization)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (
                                    witness_info.get('first_name'),
                                    witness_info.get('last_name'),
                                    witness_info.get('full_name'),
                                    witness_info.get('title'),
                                    witness_info.get('organization')
                                ))

                                # Get witness ID
                                cursor = conn.execute('''
                                    SELECT witness_id FROM witnesses
                                    WHERE full_name = ? AND COALESCE(organization, '') = COALESCE(?, '')
                                ''', (witness_info.get('full_name'), witness_info.get('organization')))
                                witness_row = cursor.fetchone()

                                if witness_row:
                                    witness_id = witness_row[0]
                                    # Insert appearance record
                                    witness_type = witness_fetcher.infer_witness_type(witness_info)
                                    conn.execute('''
                                        INSERT OR IGNORE INTO witness_appearances
                                        (witness_id, hearing_id, witness_type, position)
                                        VALUES (?, ?, ?, ?)
                                    ''', (witness_id, hearing_id, witness_type, witness_info.get('title')))
                                    witness_count += 1

                except Exception as e:
                    logger.warning(f"Error updating witnesses for hearing {hearing_id}: {e}")
                    continue

            update_results['updates']['witnesses'] = witness_count
            logger.info(f"Updated {witness_count} witness records")

        except Exception as e:
            logger.error(f"Error updating witnesses: {e}")
            update_results['updates']['witnesses'] = f"Error: {str(e)}"

        # Log update to database
        try:
            with db.transaction() as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS update_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        update_date DATE,
                        start_time TIMESTAMP,
                        end_time TIMESTAMP,
                        duration_seconds INTEGER,
                        hearings_updated INTEGER,
                        committees_updated INTEGER,
                        members_updated INTEGER,
                        witnesses_updated INTEGER,
                        success BOOLEAN,
                        error_message TEXT
                    )
                ''')

                start_time = datetime.fromisoformat(update_results['timestamp'])
                end_time = datetime.now()
                duration = int((end_time - start_time).total_seconds())

                conn.execute('''
                    INSERT INTO update_logs
                    (update_date, start_time, end_time, duration_seconds,
                     hearings_updated, committees_updated, members_updated, witnesses_updated, success)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    start_time.date(),
                    start_time,
                    end_time,
                    duration,
                    update_results['updates'].get('hearings', 0),
                    update_results['updates'].get('committees', 0),
                    update_results['updates'].get('members', 0),
                    update_results['updates'].get('witnesses', 0),
                    True
                ))

        except Exception as e:
            logger.error(f"Error logging update: {e}")

        return update_results

    except Exception as e:
        logger.error(f"Daily update failed: {e}")
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }

@app.route('/api/cron/daily-update', methods=['GET', 'POST'])
def daily_update():
    """Vercel cron job endpoint for daily Congressional data updates"""
    try:
        # Verify this is from Vercel cron (check headers)
        cron_secret = request.headers.get('Authorization')
        expected_secret = os.environ.get('CRON_SECRET')

        if expected_secret and cron_secret != f"Bearer {expected_secret}":
            return jsonify({'error': 'Unauthorized'}), 401

        logger.info("Starting daily Congressional data update...")
        result = update_congressional_data()
        logger.info(f"Daily update completed: {result}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Cron job failed: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }), 500

# For local testing
if __name__ == '__main__':
    print("Running daily update locally...")
    result = update_congressional_data()
    print(json.dumps(result, indent=2))