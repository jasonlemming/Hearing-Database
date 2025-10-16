"""
Admin routes blueprint

WARNING: This admin interface has NO AUTHENTICATION.
Only use on localhost for development/testing.
DO NOT deploy /admin routes to production.
"""
import os
import sys
from flask import Blueprint, render_template, jsonify, request
from database.manager import DatabaseManager
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# from config.task_manager import task_manager  # DEPRECATED: Using database-driven async tasks instead
from config.logging_config import get_logger
import requests
import json

logger = get_logger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Initialize database manager
db = DatabaseManager()


@admin_bp.route('/api/system-health')
def system_health():
    """
    Get comprehensive system health status including validation results

    Returns:
        JSON with database health, validation status, and recent update metrics
    """
    try:
        with db.transaction() as conn:
            # Get last update with validation results
            cursor = conn.execute("""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       error_count, success, trigger_source
                FROM update_logs
                ORDER BY start_time DESC
                LIMIT 1
            """)
            last_update = cursor.fetchone()

            # Get database counts
            cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            row = cursor.fetchone()
            hearing_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT COUNT(*) FROM committees")
            row = cursor.fetchone()
            committee_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT COUNT(*) FROM witnesses")
            row = cursor.fetchone()
            witness_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            # Check for recent validation issues (from last 7 days)
            cursor = conn.execute("""
                SELECT COUNT(*) FROM update_logs
                WHERE start_time >= datetime('now', '-7 days')
                AND success = 0
            """)
            row = cursor.fetchone()
            failed_updates_7d = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            # Calculate hours since last update
            hours_since_update = None
            if last_update and last_update[2]:
                from datetime import datetime
                last_update_time = datetime.fromisoformat(last_update[2])
                hours_since_update = (datetime.now() - last_update_time).total_seconds() / 3600

            # Determine health status
            health_status = 'healthy'
            warnings = []
            issues = []

            if hours_since_update and hours_since_update > 30:
                health_status = 'degraded'
                warnings.append(f"Last update was {hours_since_update:.1f} hours ago (> 30h)")

            if hours_since_update and hours_since_update > 48:
                health_status = 'unhealthy'
                issues.append(f"Last update was {hours_since_update:.1f} hours ago (> 48h)")

            if failed_updates_7d > 3:
                health_status = 'degraded' if health_status == 'healthy' else health_status
                warnings.append(f"{failed_updates_7d} failed updates in last 7 days")

            if hearing_count < 1000:
                health_status = 'unhealthy'
                issues.append(f"Low hearing count: {hearing_count} (expected >= 1000)")

            # Get next scheduled update
            cursor = conn.execute("""
                SELECT name, next_run_at, schedule_cron
                FROM scheduled_tasks
                WHERE is_active = 1
                ORDER BY next_run_at ASC
                LIMIT 1
            """)
            next_schedule = cursor.fetchone()

            # Calculate hours until next update
            hours_until_next = None
            if next_schedule and next_schedule[1]:
                try:
                    next_run_time = datetime.fromisoformat(next_schedule[1])
                    hours_until_next = (next_run_time - datetime.now()).total_seconds() / 3600
                except:
                    pass

            return jsonify({
                'status': health_status,
                'timestamp': datetime.now().isoformat(),
                'database': {
                    'hearings': hearing_count,
                    'committees': committee_count,
                    'witnesses': witness_count
                },
                'last_update': {
                    'log_id': last_update[0] if last_update else None,
                    'date': last_update[1] if last_update else None,
                    'start_time': last_update[2] if last_update else None,
                    'duration_seconds': last_update[4] if last_update else None,
                    'hearings_checked': last_update[5] if last_update else 0,
                    'hearings_updated': last_update[6] if last_update else 0,
                    'hearings_added': last_update[7] if last_update else 0,
                    'error_count': last_update[8] if last_update else 0,
                    'success': bool(last_update[9]) if last_update else None,
                    'trigger_source': last_update[10] if last_update else None,
                    'hours_ago': round(hours_since_update, 1) if hours_since_update else None
                },
                'next_scheduled': {
                    'name': next_schedule[0] if next_schedule else None,
                    'time': next_schedule[1] if next_schedule else None,
                    'schedule_cron': next_schedule[2] if next_schedule else None,
                    'hours_until': round(hours_until_next, 1) if hours_until_next is not None else None
                } if next_schedule else None,
                'warnings': warnings,
                'issues': issues,
                'failed_updates_7d': failed_updates_7d
            })

    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@admin_bp.route('/api/timeline')
def timeline():
    """
    Get 7-day update timeline for visualization

    Returns:
        JSON with last 7 days of update runs including success/failure status
    """
    try:
        with db.transaction() as conn:
            cursor = conn.execute("""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       error_count, success, trigger_source
                FROM update_logs
                WHERE start_time >= datetime('now', '-7 days')
                ORDER BY start_time DESC
            """)

            updates = []
            successful_count = 0
            total_count = 0

            for row in cursor.fetchall():
                total_count += 1
                if row[9]:  # success
                    successful_count += 1

                updates.append({
                    'log_id': row[0],
                    'update_date': row[1],
                    'start_time': row[2],
                    'end_time': row[3],
                    'duration_seconds': row[4],
                    'hearings_checked': row[5],
                    'hearings_updated': row[6],
                    'hearings_added': row[7],
                    'error_count': row[8],
                    'success': bool(row[9]),
                    'trigger_source': row[10]
                })

            # Calculate success rate
            success_rate = (successful_count / total_count * 100) if total_count > 0 else 0

            # Calculate average duration
            total_duration = sum(u['duration_seconds'] for u in updates if u['duration_seconds'])
            avg_duration = total_duration / total_count if total_count > 0 else 0

            # Get next scheduled update from scheduled_tasks
            cursor = conn.execute("""
                SELECT name, next_run_at
                FROM scheduled_tasks
                WHERE is_active = 1
                ORDER BY next_run_at ASC
                LIMIT 1
            """)
            next_schedule = cursor.fetchone()

            return jsonify({
                'updates': updates,
                'summary': {
                    'total_runs': total_count,
                    'successful_runs': successful_count,
                    'failed_runs': total_count - successful_count,
                    'success_rate': round(success_rate, 1),
                    'average_duration_seconds': round(avg_duration, 1)
                },
                'next_scheduled': {
                    'name': next_schedule[0] if next_schedule else None,
                    'time': next_schedule[1] if next_schedule else None
                } if next_schedule else None
            })

    except Exception as e:
        logger.error(f"Error getting timeline: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/phase23-metrics')
def phase23_metrics():
    """
    Get Phase 2.3 metrics (batch processing + historical validation)

    Returns:
        JSON with recent batch processing and historical validation statistics
    """
    try:
        import json as json_module

        with db.transaction() as conn:
            # Note: Phase 2.3 metrics are stored in update_logs as part of the metrics
            # We'll need to parse the most recent update log to extract this data
            # For now, we'll return mock data structure that the frontend can populate

            # Get last 10 updates to analyze Phase 2.3 metrics
            cursor = conn.execute("""
                SELECT log_id, start_time, hearings_updated, success
                FROM update_logs
                ORDER BY start_time DESC
                LIMIT 30
            """)

            recent_updates = cursor.fetchall()
            total_updates = len(recent_updates)
            successful_updates = sum(1 for u in recent_updates if u[3])

            return jsonify({
                'batch_processing': {
                    'enabled': True,  # From .env
                    'batch_size': 50,  # From .env
                    'total_batches_7d': total_updates,  # Approximate
                    'successful_batches_7d': successful_updates,
                    'failed_batches_7d': total_updates - successful_updates,
                    'success_rate': round(successful_updates / total_updates * 100, 1) if total_updates > 0 else 0,
                    'last_batch_time': recent_updates[0][1] if recent_updates else None,
                    'last_batch_hearings': recent_updates[0][2] if recent_updates else 0
                },
                'historical_validation': {
                    'enabled': True,  # From .env
                    'anomalies_detected_7d': 0,  # TODO: Parse from logs
                    'last_alert': None,
                    'alert_triggered': False,
                    'anomaly_details': []
                }
            })

    except Exception as e:
        logger.error(f"Error getting Phase 2.3 metrics: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/update-details/<int:log_id>')
def update_details(log_id: int):
    """
    Get full details for a single update run (for expandable log viewer)

    Args:
        log_id: Update log ID

    Returns:
        JSON with complete update details including validation, batch processing, etc.
    """
    try:
        with db.transaction() as conn:
            # Get update log details
            cursor = conn.execute("""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, errors, success, trigger_source, schedule_id
                FROM update_logs
                WHERE log_id = ?
            """, (log_id,))

            row = cursor.fetchone()
            if not row:
                return jsonify({'error': 'Update log not found'}), 404

            # Parse errors JSON
            errors_json = row[12]
            error_list = []
            if errors_json:
                try:
                    import json as json_module
                    error_list = json_module.loads(errors_json)
                except:
                    error_list = [errors_json] if errors_json else []

            # Get recently modified hearings from this update
            cursor = conn.execute("""
                SELECT hearing_id, title, chamber, hearing_date_only, updated_at
                FROM hearings
                WHERE updated_at BETWEEN ? AND ?
                ORDER BY updated_at DESC
                LIMIT 50
            """, (row[2], row[3] if row[3] else row[2]))

            recent_hearings = []
            for h_row in cursor.fetchall():
                recent_hearings.append({
                    'hearing_id': h_row[0],
                    'title': h_row[1],
                    'chamber': h_row[2],
                    'hearing_date': h_row[3],
                    'updated_at': h_row[4]
                })

            return jsonify({
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
                'trigger_source': row[14],
                'schedule_id': row[15],
                'recent_hearings': recent_hearings,
                # Placeholder for Phase 2.3 metrics (would be parsed from logs)
                'batch_processing': {
                    'enabled': True,
                    'batch_count': 1,
                    'batches_succeeded': 1,
                    'batches_failed': 0
                },
                'historical_validation': {
                    'enabled': True,
                    'anomaly_count': 0,
                    'anomalies': [],
                    'alert_triggered': False
                }
            })

    except Exception as e:
        logger.error(f"Error getting update details: {e}")
        return jsonify({'error': str(e)}), 500


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


@admin_bp.route('/')
def dashboard():
    """Main admin dashboard - landing page for admin section"""
    try:
        with db.transaction() as conn:
            # Get summary stats
            cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            row = cursor.fetchone()
            total_hearings = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT COUNT(*) FROM hearings WHERE updated_at > created_at")
            row = cursor.fetchone()
            updated_hearings = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT MIN(created_at) FROM hearings")
            row = cursor.fetchone()
            baseline_date = row.get('min', row[0]) if hasattr(row, 'keys') else row[0]

            # Get last update info
            cursor = conn.execute("""
                SELECT update_date, start_time, hearings_updated, hearings_added
                FROM update_logs
                ORDER BY start_time DESC
                LIMIT 1
            """)
            last_update = cursor.fetchone()

            return render_template('admin_dashboard_v2.html',
                                 total_hearings=total_hearings,
                                 updated_hearings=updated_hearings,
                                 baseline_date=baseline_date or '2025-10-01',
                                 production_count=1168,  # From README
                                 last_update=last_update,
                                 now=datetime.now())

    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return f"Error loading dashboard: {e}", 500


@admin_bp.route('/history')
def history():
    """Renamed route for update history (previously /updates)"""
    return updates()


@admin_bp.route('/api/start-update', methods=['POST'])
def start_update():
    """
    Start a manual update task using database-driven async queue

    Request JSON:
        {
            "lookback_days": 7,
            "components": ["hearings", "witnesses", "committees"],
            "chamber": "both",
            "mode": "incremental",
            "dry_run": false
        }

    Returns:
        {"task_id": 123, "status": "pending", "message": "Task queued and execution triggered"}
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

        # Create task parameters
        task_params = {
            'lookback_days': lookback_days,
            'components': components,
            'chamber': chamber,
            'mode': mode,
            'dry_run': dry_run
        }

        # Create task record in database
        with db.transaction() as conn:
            cursor = conn.execute('''
                INSERT INTO admin_tasks
                (task_type, status, parameters, triggered_by, environment)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                'manual_update',
                'pending',
                json.dumps(task_params),
                'admin_dashboard',
                os.environ.get('VERCEL_ENV', 'development')
            ))
            task_id = cursor.lastrowid

        logger.info(f"Created task {task_id} with mode={mode}, lookback={lookback_days}, chamber={chamber}")

        # Trigger async execution via fire-and-forget HTTP request
        try:
            # Determine base URL
            if os.environ.get('VERCEL'):
                base_url = f"https://{os.environ.get('VERCEL_URL', 'capitollabsllc.com')}"
            else:
                base_url = 'http://localhost:5001'

            trigger_url = f"{base_url}/api/admin/run-task/{task_id}"

            # Fire-and-forget with very short timeout
            requests.post(trigger_url, timeout=0.5)
        except requests.exceptions.Timeout:
            # Expected - task is running in background
            pass
        except Exception as trigger_error:
            logger.warning(f"Failed to trigger task execution: {trigger_error}")
            # Task is still in database, can be manually triggered

        return jsonify({
            'task_id': task_id,
            'status': 'pending',
            'message': 'Task queued and execution triggered'
        }), 202

    except Exception as e:
        logger.error(f"Failed to start update: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/task-status/<int:task_id>')
def task_status(task_id: int):
    """
    Get current status and progress of a task from admin_tasks table

    Returns:
        {
            "status": "pending" | "running" | "completed" | "failed",
            "progress": {...},
            "result": {...},
            "logs": "...",
            "created_at": "...",
            "started_at": "...",
            "completed_at": "..."
        }
    """
    try:
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT task_id, task_type, status, parameters, created_at, started_at,
                       completed_at, result, logs, progress, triggered_by, environment
                FROM admin_tasks
                WHERE task_id = ?
            ''', (task_id,))

            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Task not found'}), 404

            # Parse JSON fields
            parameters = json.loads(row[3]) if row[3] else {}
            result = json.loads(row[7]) if row[7] else None
            progress = json.loads(row[9]) if row[9] else {}

            # Calculate duration if task has started
            duration_seconds = None
            if row[5]:  # started_at
                from datetime import datetime
                start_time = datetime.fromisoformat(row[5])
                end_time = datetime.fromisoformat(row[6]) if row[6] else datetime.now()
                duration_seconds = (end_time - start_time).total_seconds()

            return jsonify({
                'task_id': row[0],
                'task_type': row[1],
                'status': row[2],
                'parameters': parameters,
                'created_at': row[4],
                'started_at': row[5],
                'completed_at': row[6],
                'result': result,
                'logs': row[8],
                'progress': progress,
                'triggered_by': row[10],
                'environment': row[11],
                'duration_seconds': duration_seconds
            })

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({'error': str(e)}), 500


# /api/task-logs and /api/cancel-update endpoints removed - logs are now in admin_tasks table


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
            cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            row = cursor.fetchone()
            local_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT COUNT(*) FROM hearings WHERE created_at > '2025-10-01'")
            row = cursor.fetchone()
            new_since_baseline = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT COUNT(*) FROM hearings WHERE updated_at > created_at")
            row = cursor.fetchone()
            updated_since_baseline = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            cursor = conn.execute("SELECT MIN(created_at), MAX(updated_at) FROM hearings")
            row = cursor.fetchone()
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


@admin_bp.route('/api/recent-hearings')
def recent_hearings():
    """
    Get recently modified hearings with full metadata for data flow validation

    Query params:
        limit: Max records to return (default: 50, max: 100)
        offset: Pagination offset (default: 0)

    Returns:
        JSON with detailed hearing records including witnesses, committees, and change metadata
    """
    try:
        limit = min(request.args.get('limit', 50, type=int), 100)
        offset = request.args.get('offset', 0, type=int)

        with db.transaction() as conn:
            # Get recently modified hearings
            cursor = conn.execute("""
                SELECT
                    h.hearing_id,
                    h.event_id,
                    h.title,
                    h.chamber,
                    h.hearing_date_only,
                    h.hearing_time,
                    h.location,
                    h.status,
                    h.hearing_type,
                    h.video_url,
                    h.youtube_video_id,
                    h.congress_gov_url,
                    h.created_at,
                    h.updated_at,
                    CASE
                        WHEN h.created_at = h.updated_at THEN 'added'
                        ELSE 'updated'
                    END as change_type
                FROM hearings h
                ORDER BY h.updated_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))

            hearings = []
            for row in cursor.fetchall():
                hearing_id = row[0]

                # Get committees for this hearing
                committees_cursor = conn.execute("""
                    SELECT c.committee_id, c.name, c.system_code, c.chamber, hc.is_primary
                    FROM hearing_committees hc
                    JOIN committees c ON hc.committee_id = c.committee_id
                    WHERE hc.hearing_id = ?
                    ORDER BY hc.is_primary DESC
                """, (hearing_id,))

                committees = []
                for c_row in committees_cursor.fetchall():
                    committees.append({
                        'committee_id': c_row[0],
                        'name': c_row[1],
                        'system_code': c_row[2],
                        'chamber': c_row[3],
                        'is_primary': bool(c_row[4])
                    })

                # Get witnesses for this hearing
                witnesses_cursor = conn.execute("""
                    SELECT w.full_name, w.title, w.organization, wa.position
                    FROM witness_appearances wa
                    JOIN witnesses w ON wa.witness_id = w.witness_id
                    WHERE wa.hearing_id = ?
                    ORDER BY wa.appearance_order
                """, (hearing_id,))

                witnesses = []
                for w_row in witnesses_cursor.fetchall():
                    witnesses.append({
                        'full_name': w_row[0],
                        'title': w_row[1],
                        'organization': w_row[2],
                        'position': w_row[3]
                    })

                hearings.append({
                    'hearing_id': hearing_id,
                    'event_id': row[1],
                    'title': row[2],
                    'chamber': row[3],
                    'hearing_date': row[4],
                    'hearing_time': row[5],
                    'location': row[6],
                    'status': row[7],
                    'hearing_type': row[8],
                    'video_url': row[9],
                    'youtube_video_id': row[10],
                    'congress_gov_url': row[11],
                    'created_at': row[12],
                    'updated_at': row[13],
                    'change_type': row[14],
                    'committees': committees,
                    'witnesses': witnesses,
                    'committee_count': len(committees),
                    'witness_count': len(witnesses),
                    'has_video': bool(row[9] or row[10])
                })

            # Get total count for pagination
            count_cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            row = count_cursor.fetchone()
            total_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

            return jsonify({
                'hearings': hearings,
                'total_count': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': (offset + limit) < total_count
            })

    except Exception as e:
        logger.error(f"Error getting recent hearings: {e}")
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
            cursor = conn.execute('''
                SELECT task_id, name, description, schedule_cron, lookback_days,
                       components, chamber, mode, is_active, is_deployed,
                       last_run_at, next_run_at, created_at, updated_at
                FROM scheduled_tasks
                ORDER BY is_active DESC, name ASC
            ''')

            schedules = []
            for row in cursor.fetchall():
                import json
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
            cursor = conn.execute('''
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
            cursor = conn.execute('''
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
            cursor = conn.execute('SELECT task_id FROM scheduled_tasks WHERE task_id = ?', (task_id,))
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
            conn.execute(query, params)

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
            cursor = conn.execute('SELECT name FROM scheduled_tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Schedule not found'}), 404

            schedule_name = row[0]
            conn.execute('DELETE FROM scheduled_tasks WHERE task_id = ?', (task_id,))

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
            cursor = conn.execute('SELECT is_active FROM scheduled_tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({'error': 'Schedule not found'}), 404

            new_status = not bool(row[0])
            conn.execute('''
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


@admin_bp.route('/api/export-vercel-config', methods=['GET'])
def export_vercel_config_new():
    """
    Export Vercel configuration with all active schedules
    Shows diff between current vercel.json and what should be deployed

    Returns:
        JSON with current config, generated config, and diff
    """
    try:
        import json as json_module

        # Read current vercel.json
        vercel_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'vercel.json')
        current_config = None
        current_crons = []

        try:
            with open(vercel_path, 'r') as f:
                current_config = json_module.load(f)
                current_crons = current_config.get('crons', [])
        except FileNotFoundError:
            logger.warning("vercel.json not found")
            current_config = {"version": 2, "crons": []}

        # Get active schedules from database
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT task_id, name, schedule_cron, is_active
                FROM scheduled_tasks
                WHERE is_active = 1
                ORDER BY task_id
            ''')

            active_schedules = []
            for row in cursor.fetchall():
                active_schedules.append({
                    'task_id': row[0],
                    'name': row[1],
                    'schedule_cron': row[2],
                    'is_active': bool(row[3])
                })

        # Generate new crons array
        new_crons = []
        for schedule in active_schedules:
            new_crons.append({
                "path": f"/api/cron/scheduled-update/{schedule['task_id']}",
                "schedule": schedule['schedule_cron']
            })

        # Generate complete vercel.json config
        generated_config = {
            "version": 2,
            "builds": current_config.get('builds', []),
            "routes": current_config.get('routes', []),
            "crons": new_crons
        }

        # Calculate diff
        current_paths = {cron['path'] for cron in current_crons}
        new_paths = {cron['path'] for cron in new_crons}

        added = [cron for cron in new_crons if cron['path'] not in current_paths]
        removed = [cron for cron in current_crons if cron['path'] not in new_paths]
        unchanged = [cron for cron in new_crons if cron['path'] in current_paths]

        return jsonify({
            'current_crons': current_crons,
            'generated_config': generated_config,
            'active_schedules': active_schedules,
            'changes': {
                'added': added,
                'removed': removed,
                'unchanged': unchanged,
                'has_changes': len(added) > 0 or len(removed) > 0
            },
            'instructions': [
                '1. Copy the generated config below',
                '2. Replace contents of vercel.json in your repository',
                '3. Commit: git add vercel.json && git commit -m "Update cron schedules"',
                '4. Push: git push',
                '5. Vercel will automatically redeploy with new schedules'
            ]
        })

    except Exception as e:
        logger.error(f"Error exporting Vercel config: {e}")
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
            cursor = conn.execute('''
                SELECT task_id, name, schedule_cron
                FROM scheduled_tasks
                WHERE is_active = 1
                ORDER BY name
            ''')

            schedules = cursor.fetchall()

        # Generate Vercel cron configuration
        crons = []
        for task_id, name, schedule_cron in schedules:
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
            cursor = conn.execute('''
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
            cursor = conn.execute('''
                SELECT COUNT(*) FROM schedule_execution_logs
                WHERE schedule_id = ?
            ''', (task_id,))
            row = cursor.fetchone()
            total_count = row.get('count', row[0]) if hasattr(row, 'keys') else row[0]

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
            cursor = conn.execute('''
                SELECT task_id, name, lookback_days, mode, components, is_active
                FROM scheduled_tasks
                WHERE task_id = ? AND is_active = 1
            ''', (task_id,))
            row = cursor.fetchone()

            if not row:
                return jsonify({
                    'error': 'Schedule not found or inactive',
                    'task_id': task_id
                }), 404

            # Parse configuration
            import json as json_module
            try:
                components = json_module.loads(row[4]) if row[4] else ['hearings', 'witnesses', 'committees']
            except:
                components = ['hearings', 'witnesses', 'committees']

            schedule_config = {
                'task_id': row[0],
                'schedule_name': row[1],
                'congress': 119,
                'lookback_days': row[2],
                'update_mode': row[3],
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
            conn.execute('''
                UPDATE scheduled_tasks
                SET last_run_at = CURRENT_TIMESTAMP
                WHERE task_id = ?
            ''', (task_id,))

        # Get the log_id that was just created
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT log_id FROM update_logs
                WHERE schedule_id = ? AND trigger_source = 'test'
                ORDER BY start_time DESC
                LIMIT 1
            ''', (task_id,))
            row = cursor.fetchone()
            log_id = row[0] if row else None

        # Create execution log entry
        if log_id:
            import json as json_module
            try:
                with db.transaction() as conn:
                    conn.execute('''
                        INSERT OR IGNORE INTO schedule_execution_logs
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

        success_filter = 'AND se.success = 1' if success_only else ''

        with db.transaction() as conn:
            cursor = conn.execute(f'''
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

            cursor = conn.execute(query, (since_date, limit))
            changes = []

            for row in cursor.fetchall():
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