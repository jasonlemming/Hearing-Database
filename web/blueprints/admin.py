"""
Admin routes blueprint
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, render_template
from database.manager import DatabaseManager
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize database manager
db = DatabaseManager()


@admin_bp.route('/updates')
def updates():
    """Admin page to view update history and status"""
    try:
        with db.transaction() as conn:
            # Check if update_logs table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='update_logs'
            """)

            if not cursor.fetchone():
                return render_template('admin_updates.html',
                                     updates=[],
                                     table_exists=False,
                                     now=datetime.now())

            # Get update history (last 30 days)
            cursor = conn.execute("""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, errors, success, created_at
                FROM update_logs
                WHERE update_date >= date('now', '-30 days')
                ORDER BY start_time DESC
                LIMIT 50
            """)

            updates = []
            for row in cursor.fetchall():
                errors_json = row[12]
                error_list = []
                if errors_json:
                    try:
                        import json
                        error_list = json.loads(errors_json)
                    except:
                        error_list = [errors_json]

                updates.append({
                    'log_id': row[0],
                    'update_date': row[1],
                    'start_time': row[2],
                    'end_time': row[3],
                    'duration_seconds': row[4],
                    'hearings_checked': row[5],
                    'hearings_updated': row[6],
                    'hearings_added': row[7],
                    'committees_updated': row[8],
                    'witnesses_updated': row[9],
                    'api_requests': row[10],
                    'error_count': row[11],
                    'errors': error_list,
                    'success': bool(row[13]),
                    'created_at': row[14]
                })

            return render_template('admin_updates.html',
                                 updates=updates,
                                 table_exists=True,
                                 now=datetime.now())

    except Exception as e:
        return f"Error: {e}", 500