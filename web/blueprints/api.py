"""
API routes blueprint
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, jsonify
from database.manager import DatabaseManager
from datetime import datetime

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Initialize database manager
db = DatabaseManager()



@api_bp.route('/stats')
def stats():
    """API endpoint for database statistics"""
    try:
        with db.transaction() as conn:
            stats = {}
            tables = ['committees', 'members', 'hearings', 'hearing_committees', 'policy_areas']

            for table in tables:
                cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                stats[table] = cursor.fetchone()[0]

        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/update-status')
def update_status():
    """API endpoint to get daily update status and history"""
    try:
        with db.transaction() as conn:
            # Check if update_logs table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='update_logs'
            """)

            if not cursor.fetchone():
                return jsonify({
                    'status': 'no_logs',
                    'message': 'Update logging not yet configured',
                    'last_update': None,
                    'recent_updates': []
                })

            # Get most recent update
            cursor = conn.execute("""
                SELECT * FROM update_logs
                ORDER BY start_time DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()

            # Get recent updates (last 7 days)
            cursor = conn.execute("""
                SELECT update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, success
                FROM update_logs
                WHERE update_date >= date('now', '-7 days')
                ORDER BY start_time DESC
            """)
            recent_updates = []
            for row in cursor.fetchall():
                recent_updates.append({
                    'date': row[0],
                    'start_time': row[1],
                    'end_time': row[2],
                    'duration_seconds': row[3],
                    'hearings_checked': row[4],
                    'hearings_updated': row[5],
                    'hearings_added': row[6],
                    'committees_updated': row[7],
                    'witnesses_updated': row[8],
                    'api_requests': row[9],
                    'error_count': row[10],
                    'success': bool(row[11])
                })

            last_update = None
            if latest:
                last_update = {
                    'date': latest[1],  # update_date
                    'start_time': latest[2],  # start_time
                    'end_time': latest[3],  # end_time
                    'duration_seconds': latest[4],
                    'hearings_checked': latest[5],
                    'hearings_updated': latest[6],
                    'hearings_added': latest[7],
                    'success': bool(latest[12])
                }

            # Calculate status
            status = 'unknown'
            if latest:
                if latest[12]:  # success
                    # Check if update was today
                    update_date = datetime.fromisoformat(latest[2]).date()
                    if update_date == datetime.now().date():
                        status = 'updated_today'
                    else:
                        status = 'last_update_successful'
                else:
                    status = 'last_update_failed'

            return jsonify({
                'status': status,
                'last_update': last_update,
                'recent_updates': recent_updates,
                'total_recent_updates': len(recent_updates)
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500