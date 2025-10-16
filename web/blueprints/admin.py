"""
Admin routes blueprint

WARNING: This admin interface has NO AUTHENTICATION.
Only use on localhost for development/testing.
DO NOT deploy /admin routes to production.
"""
import os
import sys
from flask import Blueprint, render_template, jsonify, request
from database.unified_manager import UnifiedDatabaseManager
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.logging_config import get_logger
from updaters.daily_updater import DailyUpdater

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize database manager (auto-detects Postgres if POSTGRES_URL is set)
db = UnifiedDatabaseManager()


@admin_bp.route('/updates')
def updates():
    """Admin page to view update history and status"""
    try:
        with db.transaction() as conn:
            # Check if update_logs table exists (database-agnostic)
            try:
                if db.db_type == 'postgres':
                    cursor = conn.cursor()
                else:
                    cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM update_logs LIMIT 1")
                table_exists = True
            except Exception:
                table_exists = False

            if not table_exists:
                return render_template('admin_updates.html',
                                     updates=[],
                                     table_exists=False,
                                     now=datetime.now())

            # Get update history (last 30 days) - database-agnostic date handling
            if db.db_type == 'postgres':
                date_clause = "CURRENT_DATE - INTERVAL '30 days'"
            else:
                date_clause = "date('now', '-30 days')"

            query = f"""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, errors, success, created_at
                FROM update_logs
                WHERE update_date >= {date_clause}
                ORDER BY start_time DESC
                LIMIT 50
            """

            if db.db_type == 'postgres':
                cursor = conn.cursor(cursor_factory=__import__('psycopg2.extras', fromlist=['RealDictCursor']).RealDictCursor)
            else:
                cursor = conn.cursor()
            cursor.execute(query)

            updates = []
            for row in cursor.fetchall():
                # Handle both Postgres (dict-like) and SQLite (tuple) rows
                if db.db_type == 'postgres':
                    errors_json = row['errors']
                    error_list = []
                    if errors_json:
                        try:
                            import json
                            error_list = json.loads(errors_json) if isinstance(errors_json, str) else errors_json
                        except:
                            error_list = [str(errors_json)]

                    updates.append({
                        'log_id': row['log_id'],
                        'update_date': str(row['update_date']) if row['update_date'] else None,
                        'start_time': str(row['start_time']) if row['start_time'] else None,
                        'end_time': str(row['end_time']) if row['end_time'] else None,
                        'duration_seconds': row['duration_seconds'],
                        'hearings_checked': row['hearings_checked'],
                        'hearings_updated': row['hearings_updated'],
                        'hearings_added': row['hearings_added'],
                        'committees_updated': row['committees_updated'],
                        'witnesses_updated': row['witnesses_updated'],
                        'api_requests': row['api_requests'],
                        'error_count': row['error_count'],
                        'errors': error_list,
                        'success': bool(row['success']),
                        'created_at': str(row['created_at']) if row['created_at'] else None
                    })
                else:
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


@admin_bp.route('/')
def dashboard():
    """Main admin dashboard - landing page for admin section"""
    try:
        with db.transaction() as conn:
            # Create cursor based on database type
            if db.db_type == 'postgres':
                import psycopg2.extras
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            # Get summary stats
            cursor.execute("SELECT COUNT(*) FROM hearings")
            result = cursor.fetchone()
            total_hearings = result['count'] if db.db_type == 'postgres' else result[0]

            cursor.execute("SELECT COUNT(*) FROM hearings WHERE updated_at > created_at")
            result = cursor.fetchone()
            updated_hearings = result['count'] if db.db_type == 'postgres' else result[0]

            cursor.execute("SELECT MIN(created_at) FROM hearings")
            result = cursor.fetchone()
            baseline_date = result[0] if db.db_type == 'sqlite' else str(result['min']) if result else None

            # Get last update info
            cursor.execute("""
                SELECT update_date, start_time, hearings_updated, hearings_added
                FROM update_logs
                ORDER BY start_time DESC
                LIMIT 1
            """)
            last_update = cursor.fetchone()

            return render_template('admin_dashboard.html',
                                 total_hearings=total_hearings,
                                 updated_hearings=updated_hearings,
                                 baseline_date=baseline_date or '2025-10-01',
                                 production_count=1168,  # From README
                                 last_update=last_update,
                                 now=datetime.now())

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return f"Error loading dashboard: {e}", 500


@admin_bp.route('/history')
def history():
    """Renamed route for update history (previously /updates)"""
    return updates()


@admin_bp.route('/api/start-update', methods=['POST'])
def start_update():
    """
    Start a manual update task (synchronous execution)

    Request JSON:
        {
            "lookback_days": 7,
            "components": ["hearings", "witnesses", "committees"],
            "chamber": "both",
            "mode": "incremental",
            "dry_run": false
        }

    Returns:
        {
            "success": true/false,
            "metrics": {...},
            "error": "error message" (if failed)
        }
    """
    try:
        params = request.get_json() or {}

        lookback_days = params.get('lookback_days', 7)
        components = params.get('components', ['hearings', 'witnesses', 'committees'])
        chamber = params.get('chamber', 'both')
        mode = params.get('mode', 'incremental')
        dry_run = params.get('dry_run', False)

        # Validate inputs
        if not isinstance(lookback_days, int) or not (1 <= lookback_days <= 90):
            return jsonify({'error': 'lookback_days must be between 1 and 90'}), 400

        if chamber not in ['both', 'house', 'senate']:
            return jsonify({'error': 'chamber must be both, house, or senate'}), 400

        if mode not in ['incremental', 'full']:
            return jsonify({'error': 'mode must be incremental or full'}), 400

        # Validate and normalize components
        valid_components = {'hearings', 'witnesses', 'committees'}
        if isinstance(components, list):
            components = [c for c in components if c in valid_components]
        else:
            components = ['hearings', 'witnesses', 'committees']

        # Ensure hearings is always included (required)
        if 'hearings' not in components:
            components.insert(0, 'hearings')

        if not components:
            return jsonify({'error': 'At least one component required'}), 400

        # Log the start of manual update
        logger.info(f"Starting manual update: mode={mode}, lookback={lookback_days}, chamber={chamber}, components={components}, dry_run={dry_run}")

        # Create updater instance
        updater = DailyUpdater(
            congress=119,
            lookback_days=lookback_days,
            update_mode=mode,
            components=components
        )

        # Set trigger source for tracking
        updater.trigger_source = 'manual'

        # Run the update synchronously
        result = updater.run_daily_update(dry_run=dry_run)

        # Log completion
        if result.get('success'):
            logger.info(f"Manual update completed successfully")
        else:
            logger.error(f"Manual update failed: {result.get('error', 'Unknown error')}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to start manual update: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@admin_bp.route('/api/recent-changes')
def recent_changes():
    """
    Get hearings modified since a date

    Query params:
        since: Date in YYYY-MM-DD format (default: baseline date)
        limit: Max records to return (default: 50)

    Returns:
        List of hearing records with change info
    """
    try:
        since_date = request.args.get('since', '2025-10-01')
        limit = request.args.get('limit', 50, type=int)

        changes = _get_hearing_changes(since_date, limit)

        return jsonify({
            'since_date': since_date,
            'count': len(changes),
            'changes': changes
        })

    except Exception as e:
        logger.error(f"Error getting recent changes: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/production-diff')
def production_diff():
    """
    Compare local database with production

    Returns:
        Statistics showing difference from production baseline
    """
    try:
        with db.transaction() as conn:
            # Create cursor based on database type
            if db.db_type == 'postgres':
                import psycopg2.extras
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM hearings")
            result = cursor.fetchone()
            local_count = result['count'] if db.db_type == 'postgres' else result[0]

            cursor.execute("SELECT COUNT(*) FROM hearings WHERE created_at > '2025-10-01'")
            result = cursor.fetchone()
            new_since_baseline = result['count'] if db.db_type == 'postgres' else result[0]

            cursor.execute("SELECT COUNT(*) FROM hearings WHERE updated_at > created_at")
            result = cursor.fetchone()
            updated_since_baseline = result['count'] if db.db_type == 'postgres' else result[0]

            cursor.execute("SELECT MIN(created_at) as min_created, MAX(updated_at) as max_updated FROM hearings")
            row = cursor.fetchone()
            if db.db_type == 'postgres':
                baseline_date = str(row['min_created']) if row and row['min_created'] else None
                last_update_date = str(row['max_updated']) if row and row['max_updated'] else None
            else:
                baseline_date = row[0] if row else None
                last_update_date = row[1] if row else None

            # Production count from README
            production_count = 1168

            return jsonify({
                'local_count': local_count,
                'production_count': production_count,
                'difference': local_count - production_count,
                'new_hearings': new_since_baseline,
                'updated_hearings': updated_since_baseline,
                'baseline_date': baseline_date,
                'last_update': last_update_date
            })

    except Exception as e:
        logger.error(f"Error getting production diff: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SCHEDULING API ENDPOINTS
# ============================================================================

@admin_bp.route('/api/schedules', methods=['GET'])
def list_schedules():
    """
    Get all scheduled tasks

    Returns:
        List of scheduled task configurations
    """
    try:
        with db.transaction() as conn:
            # Create cursor based on database type
            if db.db_type == 'postgres':
                import psycopg2.extras
                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            else:
                cursor = conn.cursor()

            cursor.execute('''
                SELECT task_id, name, description, schedule_cron, lookback_days,
                       components, chamber, mode, is_active, is_deployed,
                       last_run_at, next_run_at, created_at, updated_at
                FROM scheduled_tasks
                ORDER BY is_active DESC, name ASC
            ''')

            schedules = []
            for row in cursor.fetchall():
                import json
                if db.db_type == 'postgres':
                    schedules.append({
                        'task_id': row['task_id'],
                        'name': row['name'],
                        'description': row['description'],
                        'schedule_cron': row['schedule_cron'],
                        'lookback_days': row['lookback_days'],
                        'components': json.loads(row['components']) if row['components'] else [],
                        'chamber': row['chamber'],
                        'mode': row['mode'],
                        'is_active': bool(row['is_active']),
                        'is_deployed': bool(row['is_deployed']),
                        'last_run_at': str(row['last_run_at']) if row['last_run_at'] else None,
                        'next_run_at': str(row['next_run_at']) if row['next_run_at'] else None,
                        'created_at': str(row['created_at']) if row['created_at'] else None,
                        'updated_at': str(row['updated_at']) if row['updated_at'] else None
                    })
                else:
                    schedules.append({
                        'task_id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'schedule_cron': row[3],
                        'lookback_days': row[4],
                        'components': json.loads(row[5]) if row[5] else [],
                        'chamber': row[6],
                        'mode': row[7],
                        'is_active': bool(row[8]),
                        'is_deployed': bool(row[9]),
                        'last_run_at': row[10],
                        'next_run_at': row[11],
                        'created_at': row[12],
                        'updated_at': row[13]
                    })

            return jsonify({'schedules': schedules})

    except Exception as e:
        logger.error(f"Error listing schedules: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>', methods=['GET'])
def get_schedule(task_id: int):
    """Get a single scheduled task by ID"""
    try:
        with db.transaction() as conn:
            cursor = _execute_query(conn, '''
                SELECT task_id, name, description, schedule_cron, lookback_days,
                       components, chamber, mode, is_active, is_deployed,
                       last_run_at, next_run_at, created_at, updated_at
                FROM scheduled_tasks
                WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Schedule not found'}), 404

            import json
            if db.db_type == 'postgres':
                schedule = {
                    'task_id': row['task_id'],
                    'name': row['name'],
                    'description': row['description'],
                    'schedule_cron': row['schedule_cron'],
                    'lookback_days': row['lookback_days'],
                    'components': json.loads(row['components']) if row['components'] else [],
                    'chamber': row['chamber'],
                    'mode': row['mode'],
                    'is_active': bool(row['is_active']),
                    'is_deployed': bool(row['is_deployed']),
                    'last_run_at': str(row['last_run_at']) if row['last_run_at'] else None,
                    'next_run_at': str(row['next_run_at']) if row['next_run_at'] else None,
                    'created_at': str(row['created_at']) if row['created_at'] else None,
                    'updated_at': str(row['updated_at']) if row['updated_at'] else None
                }
            else:
                schedule = {
                    'task_id': row[0],
                    'name': row[1],
                    'description': row[2],
                    'schedule_cron': row[3],
                    'lookback_days': row[4],
                    'components': json.loads(row[5]) if row[5] else [],
                    'chamber': row[6],
                    'mode': row[7],
                    'is_active': bool(row[8]),
                    'is_deployed': bool(row[9]),
                    'last_run_at': row[10],
                    'next_run_at': row[11],
                    'created_at': row[12],
                    'updated_at': row[13]
                }

            return jsonify({'schedule': schedule})

    except Exception as e:
        logger.error(f"Error getting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules', methods=['POST'])
def create_schedule():
    """
    Create a new scheduled task

    Request JSON:
        {
            "name": "Daily Update",
            "description": "...",
            "schedule_cron": "0 6 * * *",
            "lookback_days": 7,
            "components": ["hearings", "committees"],
            "chamber": "both",
            "mode": "incremental",
            "is_active": true
        }
    """
    try:
        data = request.get_json()

        # Validation
        required_fields = ['name', 'schedule_cron', 'lookback_days', 'components']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        # Validate lookback_days
        if not isinstance(data['lookback_days'], int) or not (1 <= data['lookback_days'] <= 90):
            return jsonify({'error': 'lookback_days must be between 1 and 90'}), 400

        # Validate chamber
        if data.get('chamber', 'both') not in ['both', 'house', 'senate']:
            return jsonify({'error': 'chamber must be both, house, or senate'}), 400

        # Validate mode
        if data.get('mode', 'incremental') not in ['incremental', 'full']:
            return jsonify({'error': 'mode must be incremental or full'}), 400

        import json
        with db.transaction() as conn:
            cursor = _execute_query(conn, '''
                INSERT INTO scheduled_tasks
                (name, description, schedule_cron, lookback_days, components,
                 chamber, mode, is_active, is_deployed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['name'],
                data.get('description', ''),
                data['schedule_cron'],
                data['lookback_days'],
                json.dumps(data['components']),
                data.get('chamber', 'both'),
                data.get('mode', 'incremental'),
                data.get('is_active', True),
                False  # New schedules start as not deployed
            ))

            # Get the inserted task_id
            if db.db_type == 'postgres':
                cursor.execute('SELECT lastval()')
                task_id = cursor.fetchone()[0] if db.db_type == 'sqlite' else cursor.fetchone()['lastval']
            else:
                task_id = cursor.lastrowid

            logger.info(f"Created new schedule: {data['name']} (ID: {task_id})")

            return jsonify({
                'task_id': task_id,
                'message': 'Schedule created successfully'
            }), 201

    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>', methods=['PUT'])
def update_schedule(task_id: int):
    """Update an existing scheduled task"""
    try:
        data = request.get_json()

        # Validate if schedule exists
        with db.transaction() as conn:
            cursor = _execute_query(conn, 'SELECT task_id FROM scheduled_tasks WHERE task_id = ?', (task_id,))
            if not cursor.fetchone():
                return jsonify({'error': 'Schedule not found'}), 404

        # Build update query dynamically based on provided fields
        update_fields = []
        params = []

        if 'name' in data:
            update_fields.append('name = ?')
            params.append(data['name'])

        if 'description' in data:
            update_fields.append('description = ?')
            params.append(data['description'])

        if 'schedule_cron' in data:
            update_fields.append('schedule_cron = ?')
            params.append(data['schedule_cron'])

        if 'lookback_days' in data:
            if not isinstance(data['lookback_days'], int) or not (1 <= data['lookback_days'] <= 90):
                return jsonify({'error': 'lookback_days must be between 1 and 90'}), 400
            update_fields.append('lookback_days = ?')
            params.append(data['lookback_days'])

        if 'components' in data:
            import json
            update_fields.append('components = ?')
            params.append(json.dumps(data['components']))

        if 'chamber' in data:
            if data['chamber'] not in ['both', 'house', 'senate']:
                return jsonify({'error': 'chamber must be both, house, or senate'}), 400
            update_fields.append('chamber = ?')
            params.append(data['chamber'])

        if 'mode' in data:
            if data['mode'] not in ['incremental', 'full']:
                return jsonify({'error': 'mode must be incremental or full'}), 400
            update_fields.append('mode = ?')
            params.append(data['mode'])

        if 'is_active' in data:
            update_fields.append('is_active = ?')
            params.append(data['is_active'])

        if 'is_deployed' in data:
            update_fields.append('is_deployed = ?')
            params.append(data['is_deployed'])

        # Always update updated_at
        update_fields.append('updated_at = CURRENT_TIMESTAMP')

        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400

        params.append(task_id)

        with db.transaction() as conn:
            query = f"UPDATE scheduled_tasks SET {', '.join(update_fields)} WHERE task_id = ?"
            _execute_query(conn, query, tuple(params))

        logger.info(f"Updated schedule ID: {task_id}")
        return jsonify({'message': 'Schedule updated successfully'})

    except Exception as e:
        logger.error(f"Error updating schedule: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>', methods=['DELETE'])
def delete_schedule(task_id: int):
    """Delete a scheduled task"""
    try:
        with db.transaction() as conn:
            cursor = _execute_query(conn, 'SELECT name FROM scheduled_tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Schedule not found'}), 404

            schedule_name = row['name'] if db.db_type == 'postgres' else row[0]
            _execute_query(conn, 'DELETE FROM scheduled_tasks WHERE task_id = ?', (task_id,))

        logger.info(f"Deleted schedule: {schedule_name} (ID: {task_id})")
        return jsonify({'message': 'Schedule deleted successfully'})

    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>/toggle', methods=['POST'])
def toggle_schedule(task_id: int):
    """Toggle a schedule's active status"""
    try:
        with db.transaction() as conn:
            cursor = _execute_query(conn, 'SELECT is_active FROM scheduled_tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Schedule not found'}), 404

            current_status = row['is_active'] if db.db_type == 'postgres' else row[0]
            new_status = not bool(current_status)
            _execute_query(conn, '''
                UPDATE scheduled_tasks
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            ''', (new_status, task_id))

        logger.info(f"Toggled schedule ID {task_id} to {'active' if new_status else 'inactive'}")
        return jsonify({
            'message': 'Schedule status updated',
            'is_active': new_status
        })

    except Exception as e:
        logger.error(f"Error toggling schedule: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/export-vercel', methods=['GET'])
def export_vercel_config():
    """
    Export active schedules as Vercel cron configuration

    Returns:
        JSON configuration for vercel.json crons section
    """
    try:
        with db.transaction() as conn:
            cursor = _execute_query(conn, '''
                SELECT task_id, name, schedule_cron
                FROM scheduled_tasks
                WHERE is_active = TRUE
                ORDER BY name
            ''')

            schedules = cursor.fetchall()

        # Generate Vercel cron configuration
        crons = []
        for row in schedules:
            if db.db_type == 'postgres':
                task_id = row['task_id']
                schedule_cron = row['schedule_cron']
            else:
                task_id = row[0]
                schedule_cron = row[2]
            crons.append({
                "path": f"/api/cron/scheduled-update/{task_id}",
                "schedule": schedule_cron
            })

        # Generate full vercel.json structure
        vercel_config = {
            "version": 2,
            "builds": [
                {
                    "src": "api/index.py",
                    "use": "@vercel/python"
                },
                {
                    "src": "api/cron-update.py",
                    "use": "@vercel/python"
                }
            ],
            "routes": [
                {
                    "src": "/api/cron/scheduled-update/(.*)",
                    "dest": "api/cron-update.py"
                },
                {
                    "src": "/(.*)",
                    "dest": "api/index.py"
                }
            ],
            "crons": crons
        }

        return jsonify({
            'config': vercel_config,
            'schedule_count': len(crons),
            'instructions': 'Copy this configuration to your vercel.json file and redeploy to Vercel'
        })

    except Exception as e:
        logger.error(f"Error exporting Vercel config: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>/executions', methods=['GET'])
def get_schedule_executions(task_id):
    """
    Get execution history for a specific schedule

    Args:
        task_id: Schedule task ID

    Query Parameters:
        limit: Maximum number of executions to return (default: 50)
        offset: Number of executions to skip (default: 0)

    Returns:
        JSON with execution history including metrics and status
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        with db.transaction() as conn:
            # Get execution history with metrics
            cursor = _execute_query(conn, '''
                SELECT
                    se.execution_id,
                    se.execution_time,
                    se.success,
                    se.error_message,
                    ul.log_id,
                    ul.update_date,
                    ul.start_time,
                    ul.end_time,
                    ul.duration_seconds,
                    ul.hearings_checked,
                    ul.hearings_updated,
                    ul.hearings_added,
                    ul.committees_updated,
                    ul.witnesses_updated,
                    ul.api_requests,
                    ul.error_count,
                    ul.errors
                FROM schedule_execution_logs se
                JOIN update_logs ul ON se.log_id = ul.log_id
                WHERE se.schedule_id = ?
                ORDER BY se.execution_time DESC
                LIMIT ? OFFSET ?
            ''', (task_id, limit, offset))

            executions = []
            for row in cursor.fetchall():
                import json
                if db.db_type == 'postgres':
                    executions.append({
                        'execution_id': row['execution_id'],
                        'execution_time': str(row['execution_time']) if row['execution_time'] else None,
                        'success': bool(row['success']),
                        'error_message': row['error_message'],
                        'log_id': row['log_id'],
                        'update_date': str(row['update_date']) if row['update_date'] else None,
                        'start_time': str(row['start_time']) if row['start_time'] else None,
                        'end_time': str(row['end_time']) if row['end_time'] else None,
                        'duration_seconds': row['duration_seconds'],
                        'hearings_checked': row['hearings_checked'],
                        'hearings_updated': row['hearings_updated'],
                        'hearings_added': row['hearings_added'],
                        'committees_updated': row['committees_updated'],
                        'witnesses_updated': row['witnesses_updated'],
                        'api_requests': row['api_requests'],
                        'error_count': row['error_count'],
                        'errors': json.loads(row['errors']) if isinstance(row['errors'], str) else (row['errors'] if row['errors'] else [])
                    })
                else:
                    executions.append({
                        'execution_id': row[0],
                        'execution_time': row[1],
                        'success': bool(row[2]),
                        'error_message': row[3],
                        'log_id': row[4],
                        'update_date': row[5],
                        'start_time': row[6],
                        'end_time': row[7],
                        'duration_seconds': row[8],
                        'hearings_checked': row[9],
                        'hearings_updated': row[10],
                        'hearings_added': row[11],
                        'committees_updated': row[12],
                        'witnesses_updated': row[13],
                        'api_requests': row[14],
                        'error_count': row[15],
                        'errors': json.loads(row[16]) if row[16] else []
                    })

            # Get total count
            cursor = _execute_query(conn, '''
                SELECT COUNT(*) FROM schedule_execution_logs
                WHERE schedule_id = ?
            ''', (task_id,))
            result = cursor.fetchone()
            total_count = result['count'] if db.db_type == 'postgres' else result[0]

            return jsonify({
                'executions': executions,
                'total_count': total_count,
                'limit': limit,
                'offset': offset
            })

    except Exception as e:
        logger.error(f"Error getting schedule executions: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/schedules/<int:task_id>/test', methods=['POST'])
def test_schedule(task_id):
    """
    Test a schedule by running it immediately

    Args:
        task_id: Schedule task ID to test

    Returns:
        JSON with test execution results
    """
    from updaters.daily_updater import DailyUpdater

    try:
        # Get schedule configuration from database
        with db.transaction() as conn:
            cursor = _execute_query(conn, '''
                SELECT task_id, name, lookback_days, mode, components, is_active
                FROM scheduled_tasks
                WHERE task_id = ? AND is_active = TRUE
            ''', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({
                    'error': 'Schedule not found or inactive',
                    'task_id': task_id
                }), 404

            # Parse configuration
            import json as json_module
            if db.db_type == 'postgres':
                task_id_val = row['task_id']
                name = row['name']
                lookback_days = row['lookback_days']
                mode = row['mode']
                components_str = row['components']
            else:
                task_id_val = row[0]
                name = row[1]
                lookback_days = row[2]
                mode = row[3]
                components_str = row[4]

            try:
                components = json_module.loads(components_str) if components_str else ['hearings', 'witnesses', 'committees']
            except:
                components = ['hearings', 'witnesses', 'committees']

            schedule_config = {
                'task_id': task_id_val,
                'schedule_name': name,
                'congress': 119,
                'lookback_days': lookback_days,
                'update_mode': mode,
                'enabled_components': components,
            }

        # Run the scheduled update
        logger.info(f"Test run initiated for schedule: {schedule_config['schedule_name']}")

        updater = DailyUpdater(
            congress=schedule_config['congress'],
            lookback_days=schedule_config['lookback_days'],
            update_mode=schedule_config['update_mode'],
            components=schedule_config['enabled_components']
        )

        # Inject schedule context for tracking
        updater.schedule_id = task_id
        updater.trigger_source = 'test'

        # Run the update
        updater.run_daily_update()

        # Update last run timestamp
        with db.transaction() as conn:
            _execute_query(conn, '''
                UPDATE scheduled_tasks
                SET last_run_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            ''', (task_id,))

        # Get the log_id that was just created
        with db.transaction() as conn:
            cursor = _execute_query(conn, '''
                SELECT log_id FROM update_logs
                WHERE schedule_id = ? AND trigger_source = 'test'
                ORDER BY start_time DESC
                LIMIT 1
            ''', (task_id,))
            row = cursor.fetchone()
            log_id = row['log_id'] if db.db_type == 'postgres' and row else (row[0] if row else None)

        # Create execution log entry
        if log_id:
            import json as json_module
            try:
                with db.transaction() as conn:
                    _execute_query(conn, '''
                        INSERT INTO schedule_execution_logs
                        (schedule_id, log_id, execution_time, success, config_snapshot)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 1, ?)
                    ''', (task_id, log_id, json_module.dumps(schedule_config)))
            except Exception as exec_log_error:
                logger.warning(f"Failed to create execution log: {exec_log_error}")

        # Get metrics
        metrics = updater.metrics.to_dict() if hasattr(updater, 'metrics') else {}

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'schedule_id': task_id,
            'schedule_name': schedule_config['schedule_name'],
            'metrics': metrics,
            'log_id': log_id
        })

    except Exception as e:
        logger.error(f"Test schedule failed for task {task_id}: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }), 500


@admin_bp.route('/api/executions', methods=['GET'])
def get_all_executions():
    """
    Get execution history across all schedules

    Query Parameters:
        limit: Maximum number of executions to return (default: 100)
        success_only: Only show successful executions (default: false)

    Returns:
        JSON with recent execution history
    """
    try:
        limit = request.args.get('limit', 100, type=int)
        success_only = request.args.get('success_only', 'false').lower() == 'true'

        success_filter = 'AND se.success = TRUE' if success_only else ''

        with db.transaction() as conn:
            cursor = _execute_query(conn, f'''
                SELECT
                    se.execution_id,
                    se.schedule_id,
                    st.name as schedule_name,
                    se.execution_time,
                    se.success,
                    se.error_message,
                    ul.log_id,
                    ul.duration_seconds,
                    ul.hearings_checked,
                    ul.hearings_updated,
                    ul.hearings_added,
                    ul.trigger_source
                FROM schedule_execution_logs se
                JOIN scheduled_tasks st ON se.schedule_id = st.task_id
                JOIN update_logs ul ON se.log_id = ul.log_id
                WHERE 1=1 {success_filter}
                ORDER BY se.execution_time DESC
                LIMIT ?
            ''', (limit,))

            executions = []
            for row in cursor.fetchall():
                if db.db_type == 'postgres':
                    executions.append({
                        'execution_id': row['execution_id'],
                        'schedule_id': row['schedule_id'],
                        'schedule_name': row['schedule_name'],
                        'execution_time': str(row['execution_time']) if row['execution_time'] else None,
                        'success': bool(row['success']),
                        'error_message': row['error_message'],
                        'log_id': row['log_id'],
                        'duration_seconds': row['duration_seconds'],
                        'hearings_checked': row['hearings_checked'],
                        'hearings_updated': row['hearings_updated'],
                        'hearings_added': row['hearings_added'],
                        'trigger_source': row['trigger_source']
                    })
                else:
                    executions.append({
                        'execution_id': row[0],
                        'schedule_id': row[1],
                        'schedule_name': row[2],
                        'execution_time': row[3],
                        'success': bool(row[4]),
                        'error_message': row[5],
                        'log_id': row[6],
                        'duration_seconds': row[7],
                        'hearings_checked': row[8],
                        'hearings_updated': row[9],
                        'hearings_added': row[10],
                        'trigger_source': row[11]
                    })

            return jsonify({'executions': executions})

    except Exception as e:
        logger.error(f"Error getting all executions: {e}")
        return jsonify({'error': str(e)}), 500


# Helper functions

def _execute_query(conn, query: str, params: tuple = None):
    """
    Execute a database query with proper cursor handling for both SQLite and Postgres

    Args:
        conn: Database connection
        query: SQL query string (use ? for SQLite, %s for Postgres)
        params: Query parameters

    Returns:
        Cursor with results
    """
    if db.db_type == 'postgres':
        import psycopg2.extras
        # Convert ? placeholders to %s for Postgres
        postgres_query = query.replace('?', '%s')
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if params:
            cursor.execute(postgres_query, params)
        else:
            cursor.execute(postgres_query)
    else:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
    return cursor


def _get_hearing_changes(since_date: str, limit: int) -> List[Dict[str, Any]]:
    """
    Query hearings modified since a date

    Args:
        since_date: Date string in YYYY-MM-DD format
        limit: Maximum number of records

    Returns:
        List of hearing change records
    """
    try:
        with db.transaction() as conn:
            query = """
                SELECT
                    event_id,
                    title,
                    chamber,
                    hearing_date,
                    CASE
                        WHEN created_at = updated_at THEN 'added'
                        ELSE 'updated'
                    END as change_type,
                    created_at,
                    updated_at
                FROM hearings
                WHERE updated_at > ?
                ORDER BY updated_at DESC
                LIMIT ?
            """

            cursor = _execute_query(conn, query, (since_date, limit))
            changes = []

            for row in cursor.fetchall():
                if db.db_type == 'postgres':
                    changes.append({
                        'event_id': row['event_id'],
                        'title': row['title'] or '(No title)',
                        'chamber': row['chamber'],
                        'hearing_date': str(row['hearing_date']) if row['hearing_date'] else None,
                        'change_type': row['change_type'],
                        'created_at': str(row['created_at']) if row['created_at'] else None,
                        'updated_at': str(row['updated_at']) if row['updated_at'] else None
                    })
                else:
                    changes.append({
                        'event_id': row[0],
                        'title': row[1] or '(No title)',
                        'chamber': row[2],
                        'hearing_date': row[3],
                        'change_type': row[4],
                        'created_at': row[5],
                        'updated_at': row[6]
                    })

            return changes

    except Exception as e:
        logger.error(f"Error querying hearing changes: {e}")
        return []