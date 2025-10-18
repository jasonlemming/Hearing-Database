#!/usr/bin/env python3
"""
Scheduled Congressional Data Update Cron Job for Vercel
Integrates with the admin scheduling system and uses DailyUpdater
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
    from updaters.daily_updater import DailyUpdater
    from updaters.policy_library_updater import PolicyLibraryUpdater
    from updaters.crs_updater import CRSUpdater
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


def _extract_provided_secret() -> tuple[str | None, str]:
    """Retrieve any cron authentication token and describe its source for logging."""

    auth_header = request.headers.get('Authorization')
    if auth_header:
        scheme_value = auth_header.split(' ', 1)
        if len(scheme_value) == 2:
            scheme, value = scheme_value
            if scheme.lower() in {"bearer", "token", "basic"}:
                return value.strip(), "authorization"
        # Fallback: treat entire header as the secret (supports raw tokens)
        return auth_header.strip(), "authorization"

    for header_name in ("X-Cron-Secret", "X-CRON-SECRET", "X-Vercel-Cron-Secret"):
        header_value = request.headers.get(header_name)
        if header_value:
            return header_value.strip(), header_name.lower()

    query_secret = request.args.get('cron_secret') or request.args.get('token')
    if query_secret:
        return query_secret.strip(), "querystring"

    return None, "missing"


def _mask_secret(secret: str | None) -> str:
    """Return a masked representation of a secret for safe logging."""

    if not secret:
        return "<none>"
    if len(secret) <= 4:
        return "*" * len(secret)
    return f"{secret[:2]}***{secret[-2:]}"


def verify_cron_auth():
    """Verify the request is from Vercel cron with valid auth"""
    expected_secret = os.environ.get('CRON_SECRET')

    if not expected_secret:
        logger.debug("CRON_SECRET not configured; skipping auth validation")
        return True

    provided_secret, source = _extract_provided_secret()

    if provided_secret == expected_secret:
        logger.debug("Cron authentication succeeded via %s", source)
        return True

    logger.warning(
        "Cron authentication failed (source=%s, provided=%s)",
        source,
        _mask_secret(provided_secret),
    )
    return False


def get_schedule_config(task_id):
    """
    Retrieve schedule configuration from database

    Args:
        task_id: ID of the scheduled task

    Returns:
        dict: Schedule configuration or None if not found/enabled
    """
    db = DatabaseManager()

    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT task_id, name, lookback_days, mode, components,
                   schedule_cron, is_active, chamber
            FROM scheduled_tasks
            WHERE task_id = ? AND is_active = TRUE
        ''', (task_id,))

        row = cursor.fetchone()

        if not row:
            return None

        # Parse components JSON - may be string or already parsed
        try:
            components_raw = row[4]
            if isinstance(components_raw, str):
                components = json.loads(components_raw)
            else:
                components = components_raw if components_raw else ['hearings', 'witnesses', 'committees']
        except Exception as e:
            logger.warning(f"Failed to parse components for task {row[0]}: {e}")
            components = ['hearings', 'witnesses', 'committees']

        return {
            'task_id': row[0],
            'schedule_name': row[1],
            'congress': 119,  # Currently hardcoded to current congress
            'lookback_days': row[2],
            'update_mode': row[3],
            'enabled_components': components,
            'cron_expression': row[5],
            'is_active': row[6],
            'chamber': row[7]
        }


def update_last_run_timestamp(task_id):
    """Update the last_run_at timestamp for a scheduled task"""
    db = DatabaseManager()

    with db.transaction() as conn:
        conn.execute('''
            UPDATE scheduled_tasks
            SET last_run_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (task_id,))


def create_execution_log(schedule_id, log_id, success, error_message=None, config_snapshot=None):
    """
    Create a record in schedule_execution_logs linking schedule to execution

    Args:
        schedule_id: ID of the scheduled task
        log_id: ID of the update_logs entry
        success: Whether execution succeeded
        error_message: Error message if failed
        config_snapshot: JSON snapshot of schedule config at execution time
    """
    db = DatabaseManager()

    with db.transaction() as conn:
        conn.execute('''
            INSERT OR IGNORE INTO schedule_execution_logs
            (schedule_id, log_id, execution_time, success, error_message, config_snapshot)
            VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
        ''', (schedule_id, log_id, success, error_message, json.dumps(config_snapshot) if config_snapshot else None))


def run_scheduled_update(schedule_config):
    """
    Execute a scheduled update using DailyUpdater

    Args:
        schedule_config: Dict containing schedule configuration

    Returns:
        dict: Update results including metrics and status
    """
    task_id = schedule_config['task_id']
    schedule_name = schedule_config['schedule_name']

    try:
        logger.info(f"Starting scheduled update: {schedule_name} (ID: {task_id})")

        # Create DailyUpdater with schedule configuration
        updater = DailyUpdater(
            congress=schedule_config['congress'],
            lookback_days=schedule_config['lookback_days'],
            update_mode=schedule_config['update_mode'],
            components=schedule_config['enabled_components']
        )

        # Inject schedule context for tracking
        updater.schedule_id = task_id
        updater.trigger_source = 'vercel_cron'

        # Run the update
        logger.info(f"Running DailyUpdater with: congress={schedule_config['congress']}, "
                   f"lookback={schedule_config['lookback_days']}, "
                   f"mode={schedule_config['update_mode']}, "
                   f"components={schedule_config['enabled_components']}")

        updater.run_daily_update()

        # Update last run timestamp
        update_last_run_timestamp(task_id)

        # Get the log_id that was just created
        db = DatabaseManager()
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT log_id FROM update_logs
                WHERE schedule_id = ?
                ORDER BY start_time DESC
                LIMIT 1
            ''', (task_id,))
            row = cursor.fetchone()
            log_id = row[0] if row else None

        # Create execution log entry (with error handling to avoid duplicate update_logs)
        if log_id:
            try:
                create_execution_log(
                    schedule_id=task_id,
                    log_id=log_id,
                    success=True,
                    config_snapshot=schedule_config
                )
            except Exception as exec_log_error:
                logger.warning(f"Failed to create execution log for successful run: {exec_log_error}")
                # Don't fail the entire update just because execution log creation failed

        # Get metrics from the update
        metrics = updater.metrics.to_dict() if hasattr(updater, 'metrics') else {}

        logger.info(f"Scheduled update completed successfully: {schedule_name}")

        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'success',
            'schedule_id': task_id,
            'schedule_name': schedule_name,
            'metrics': metrics,
            'log_id': log_id
        }

    except Exception as e:
        logger.error(f"Scheduled update failed: {schedule_name} - {e}")

        # Try to create execution log for the failure
        try:
            db = DatabaseManager()

            # Check if DailyUpdater already created an update_logs entry
            log_id = None
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT log_id, success FROM update_logs
                    WHERE schedule_id = ?
                    ORDER BY start_time DESC
                    LIMIT 1
                ''', (task_id,))
                row = cursor.fetchone()

                # If there's a recent log from this run, use it
                if row and not row[1]:  # If exists and not successful
                    log_id = row[0]
                else:
                    # Create a minimal update_logs entry for the failure
                    cursor = conn.execute('''
                        INSERT INTO update_logs
                        (update_date, start_time, end_time, success, error_count, errors,
                         trigger_source, schedule_id)
                        VALUES (DATE('now'), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 1, ?, 'vercel_cron', ?)
                    ''', (json.dumps([str(e)]), task_id))
                    log_id = cursor.lastrowid

            # Create execution log
            if log_id:
                create_execution_log(
                    schedule_id=task_id,
                    log_id=log_id,
                    success=False,
                    error_message=str(e),
                    config_snapshot=schedule_config
                )

        except Exception as log_error:
            logger.error(f"Failed to create error log: {log_error}")

        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'schedule_id': task_id,
            'schedule_name': schedule_name,
            'error': str(e)
        }


@app.route('/api/cron/scheduled-update/<int:task_id>', methods=['GET', 'POST'])
def scheduled_update(task_id):
    """
    Vercel cron job endpoint for scheduled Congressional data updates

    Args:
        task_id: ID of the scheduled task to execute

    Returns:
        JSON response with update results
    """
    try:
        # Log ALL incoming requests for debugging
        logger.info(f"[CRON DIAGNOSTIC] Received request for task_id={task_id}")
        logger.info(f"[CRON DIAGNOSTIC] Method: {request.method}")
        logger.info(f"[CRON DIAGNOSTIC] Headers: {dict(request.headers)}")
        logger.info(f"[CRON DIAGNOSTIC] Remote addr: {request.remote_addr}")
        logger.info(f"[CRON DIAGNOSTIC] User agent: {request.user_agent}")

        # Check if CRON_SECRET is configured
        expected_secret = os.environ.get('CRON_SECRET')
        logger.info(f"[CRON DIAGNOSTIC] CRON_SECRET configured: {bool(expected_secret)}")
        if expected_secret:
            logger.info(f"[CRON DIAGNOSTIC] CRON_SECRET value (first 5 chars): {expected_secret[:5]}...")

        # Verify authentication
        cron_secret = request.headers.get('Authorization')
        logger.info(f"[CRON DIAGNOSTIC] Authorization header present: {bool(cron_secret)}")
        if cron_secret:
            logger.info(f"[CRON DIAGNOSTIC] Authorization header (first 10 chars): {cron_secret[:10]}...")

        if not verify_cron_auth():
            logger.warning(f"[CRON DIAGNOSTIC] Authentication FAILED for task {task_id}")
            return jsonify({'error': 'Unauthorized'}), 401

        logger.info(f"[CRON DIAGNOSTIC] Authentication SUCCESS for task {task_id}")

        # Get schedule configuration
        schedule_config = get_schedule_config(task_id)

        if not schedule_config:
            logger.warning(f"Schedule not found or inactive: {task_id}")
            return jsonify({
                'error': 'Schedule not found or inactive',
                'task_id': task_id
            }), 404

        # Run the scheduled update
        result = run_scheduled_update(schedule_config)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Cron job failed for task {task_id}: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }), 500


@app.route('/api/cron/test-schedule/<int:task_id>', methods=['POST'])
def test_schedule(task_id):
    """
    Test endpoint to manually trigger a scheduled update (from admin dashboard)
    Does not require cron auth, but could be restricted to admin users

    Args:
        task_id: ID of the scheduled task to test

    Returns:
        JSON response with update results
    """
    try:
        # Get schedule configuration
        schedule_config = get_schedule_config(task_id)

        if not schedule_config:
            return jsonify({
                'error': 'Schedule not found or inactive',
                'task_id': task_id
            }), 404

        # Override trigger source for test runs
        logger.info(f"Test run initiated for schedule: {schedule_config['schedule_name']}")

        # Run the update with test context
        result = run_scheduled_update(schedule_config)

        # Update trigger source in the log
        if result.get('log_id'):
            db = DatabaseManager()
            with db.transaction() as conn:
                conn.execute('''
                    UPDATE update_logs
                    SET trigger_source = 'test'
                    WHERE log_id = ?
                ''', (result['log_id'],))

        return jsonify(result)

    except Exception as e:
        logger.error(f"Test schedule failed for task {task_id}: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'task_id': task_id,
            'error': str(e)
        }), 500


@app.route('/api/cron/health', methods=['GET'])
def health_check():
    """
    Health check endpoint for monitoring system status

    Returns comprehensive system health information:
    - Database connectivity and size
    - Last update status and timing
    - Scheduled tasks status
    - Data statistics
    - Error rates

    Returns:
        JSON response with health status
    """
    try:
        db = DatabaseManager()
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'status': 'healthy',
            'checks': {},
            'warnings': [],
            'errors': []
        }

        # Check 1: Database connectivity
        try:
            with db.transaction() as conn:
                conn.execute('SELECT 1').fetchone()
            health_status['checks']['database'] = 'connected'
        except Exception as e:
            health_status['checks']['database'] = 'error'
            health_status['errors'].append(f'Database connection failed: {str(e)}')
            health_status['status'] = 'unhealthy'

        # Check 2: Database size
        try:
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
                    FROM pragma_page_count('main'), pragma_page_size()
                ''')
                size_mb = cursor.fetchone()[0]
                health_status['checks']['database_size_mb'] = round(size_mb, 2)

                # Warn if database is getting large (> 50 MB)
                if size_mb > 50:
                    health_status['warnings'].append(f'Database size ({size_mb:.2f} MB) approaching SQLite limits')
        except Exception as e:
            health_status['errors'].append(f'Failed to check database size: {str(e)}')

        # Check 3: Last update status
        try:
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT update_date, start_time, end_time, duration_seconds,
                           hearings_updated, hearings_added, error_count, success, trigger_source
                    FROM update_logs
                    ORDER BY start_time DESC
                    LIMIT 1
                ''')
                last_update = cursor.fetchone()

                if last_update:
                    health_status['checks']['last_update'] = {
                        'date': last_update[0],
                        'start_time': last_update[1],
                        'end_time': last_update[2],
                        'duration_seconds': last_update[3],
                        'hearings_updated': last_update[4],
                        'hearings_added': last_update[5],
                        'error_count': last_update[6],
                        'success': bool(last_update[7]),
                        'trigger_source': last_update[8]
                    }

                    # Check if last update failed
                    if not last_update[7]:
                        health_status['errors'].append('Last update failed')
                        health_status['status'] = 'degraded'

                    # Check if last update was more than 48 hours ago
                    if last_update[1]:
                        last_update_time = datetime.fromisoformat(last_update[1])
                        hours_since_update = (datetime.now() - last_update_time).total_seconds() / 3600
                        health_status['checks']['hours_since_last_update'] = round(hours_since_update, 1)

                        if hours_since_update > 48:
                            health_status['warnings'].append(f'No updates in {hours_since_update:.1f} hours')
                            health_status['status'] = 'degraded'
                else:
                    health_status['warnings'].append('No update logs found')
        except Exception as e:
            health_status['errors'].append(f'Failed to check last update: {str(e)}')

        # Check 4: Scheduled tasks status
        try:
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT task_id, name, schedule_cron, is_active, is_deployed, last_run_at
                    FROM scheduled_tasks
                    WHERE is_active = TRUE
                ''')
                active_tasks = cursor.fetchall()

                health_status['checks']['active_tasks'] = len(active_tasks)
                health_status['checks']['tasks'] = []

                for task in active_tasks:
                    task_info = {
                        'id': task[0],
                        'name': task[1],
                        'schedule': task[2],
                        'deployed': bool(task[4]),
                        'last_run': task[5]
                    }
                    health_status['checks']['tasks'].append(task_info)

                    # Warn if active task is not deployed
                    if not task[4]:
                        health_status['warnings'].append(f'Task "{task[1]}" (ID: {task[0]}) is active but not deployed')
        except Exception as e:
            health_status['errors'].append(f'Failed to check scheduled tasks: {str(e)}')

        # Check 5: Data statistics
        try:
            counts = db.get_table_counts()
            health_status['checks']['data_counts'] = counts

            # Warn if hearing count seems low (< 1000 for 119th Congress)
            if counts.get('hearings', 0) < 1000:
                health_status['warnings'].append(f'Hearing count ({counts["hearings"]}) seems low')
        except Exception as e:
            health_status['errors'].append(f'Failed to get data counts: {str(e)}')

        # Check 6: Error rate (last 10 updates)
        try:
            with db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) as total, SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed
                    FROM update_logs
                    WHERE start_time >= datetime('now', '-7 days')
                ''')
                stats = cursor.fetchone()
                total_updates = stats[0]
                failed_updates = stats[1] or 0

                if total_updates > 0:
                    error_rate = (failed_updates / total_updates) * 100
                    health_status['checks']['error_rate_7days'] = {
                        'total_updates': total_updates,
                        'failed_updates': failed_updates,
                        'error_rate_pct': round(error_rate, 2)
                    }

                    # Warn if error rate > 10%
                    if error_rate > 10:
                        health_status['warnings'].append(f'High error rate: {error_rate:.1f}%')
                        health_status['status'] = 'degraded'
        except Exception as e:
            health_status['errors'].append(f'Failed to calculate error rate: {str(e)}')

        # Check 7: Circuit breaker status (if enabled)
        try:
            from api.client import CongressAPIClient
            from config.settings import Settings
            settings = Settings()

            # Create temporary API client to check circuit breaker stats
            api_client = CongressAPIClient(api_key=settings.api_key)

            if api_client.circuit_breaker:
                cb_stats = api_client.get_circuit_breaker_stats()
                if cb_stats:
                    health_status['checks']['circuit_breaker'] = cb_stats

                    # Critical alert if circuit breaker is open
                    if cb_stats['state'] == 'open':
                        health_status['errors'].append(f"Circuit breaker is OPEN - API requests blocked")
                        health_status['status'] = 'unhealthy'
                    elif cb_stats['state'] == 'half_open':
                        health_status['warnings'].append(f"Circuit breaker is HALF_OPEN - testing recovery")

                    # Warn on high failure rate
                    if cb_stats.get('failure_rate_pct', 0) > 20:
                        health_status['warnings'].append(f"High circuit breaker failure rate: {cb_stats['failure_rate_pct']}%")
            else:
                health_status['checks']['circuit_breaker'] = {'enabled': False}
        except Exception as e:
            logger.warning(f'Failed to check circuit breaker status: {str(e)}')
            # Don't add to health_status errors - circuit breaker check is optional

        # Check 8: Retry statistics (last 24 hours)
        try:
            from api.client import CongressAPIClient
            from config.settings import Settings
            settings = Settings()

            # Create temporary API client to check retry stats
            api_client = CongressAPIClient(api_key=settings.api_key)
            retry_stats = api_client.get_retry_stats()

            if retry_stats:
                health_status['checks']['retry_stats'] = retry_stats

                # Info only - high retry count isn't necessarily a problem
                # (indicates resilience is working)
                if retry_stats.get('total_retries', 0) > 100:
                    health_status['warnings'].append(f"High retry count: {retry_stats['total_retries']} (indicates API instability)")
        except Exception as e:
            logger.warning(f'Failed to check retry statistics: {str(e)}')
            # Don't add to health_status errors - retry stats check is optional

        # Set overall status based on errors/warnings
        if health_status['errors']:
            health_status['status'] = 'unhealthy'
        elif health_status['warnings']:
            health_status['status'] = 'degraded'

        # Return appropriate HTTP status code
        if health_status['status'] == 'healthy':
            return jsonify(health_status), 200
        elif health_status['status'] == 'degraded':
            return jsonify(health_status), 200  # Still return 200 for degraded
        else:
            return jsonify(health_status), 503  # Service Unavailable for unhealthy

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'unhealthy',
            'error': str(e)
        }), 503


@app.route('/api/cron/policy-library-update', methods=['GET', 'POST'])
def policy_library_update():
    """
    Vercel cron job endpoint for Policy Library (Jamie Dupree Substack) updates

    Runs daily to fetch new posts from RSS feed and add them to the database.

    Returns:
        JSON response with update results
    """
    try:
        # Verify authentication
        if not verify_cron_auth():
            logger.warning("Authentication failed for policy library update")
            return jsonify({'error': 'Unauthorized'}), 401

        logger.info("Starting policy library scheduled update")

        # Check if BROOKINGS_DATABASE_URL is set
        if not os.environ.get('BROOKINGS_DATABASE_URL'):
            error_msg = "BROOKINGS_DATABASE_URL environment variable not set"
            logger.error(error_msg)
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': error_msg
            }), 500

        # Create PolicyLibraryUpdater with default settings
        updater = PolicyLibraryUpdater(
            lookback_days=7,  # Check last 7 days for new posts
            publication='jamiedupree.substack.com',
            author='Jamie Dupree'
        )

        # Run the update
        result = updater.run_daily_update()

        if result['success']:
            logger.info("Policy library update completed successfully")
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'status': 'success',
                'service': 'policy_library',
                'metrics': result['metrics']
            }), 200
        else:
            logger.error(f"Policy library update failed: {result.get('error')}")
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'service': 'policy_library',
                'error': result.get('error'),
                'metrics': result['metrics']
            }), 500

    except Exception as e:
        logger.error(f"Policy library cron job failed: {e}", exc_info=True)
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'service': 'policy_library',
            'error': str(e)
        }), 500


@app.route('/api/cron/crs-library-update', methods=['GET', 'POST'])
def crs_library_update():
    """
    Vercel cron job endpoint for CRS Library updates

    Runs daily to fetch updated CRS report content from congress.gov
    and add them to the database with version tracking.

    Returns:
        JSON response with update results
    """
    try:
        # Verify authentication
        if not verify_cron_auth():
            logger.warning("Authentication failed for CRS library update")
            return jsonify({'error': 'Unauthorized'}), 401

        logger.info("Starting CRS library scheduled update")

        # Create CRSUpdater with default settings
        updater = CRSUpdater(
            lookback_days=30,  # Check last 30 days for updates
            max_products=100   # Update up to 100 products per run
        )

        # Run the update
        result = updater.run_daily_update()

        if result['success']:
            logger.info("CRS library update completed successfully")
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'status': 'success',
                'service': 'crs_library',
                'metrics': result['metrics']
            }), 200
        else:
            logger.error(f"CRS library update failed: {result.get('error')}")
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'service': 'crs_library',
                'error': result.get('error'),
                'metrics': result['metrics']
            }), 500

    except Exception as e:
        logger.error(f"CRS library cron job failed: {e}", exc_info=True)
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'service': 'crs_library',
            'error': str(e)
        }), 500


# Legacy endpoint for backwards compatibility (will be deprecated)
@app.route('/api/cron/daily-update', methods=['GET', 'POST'])
def legacy_daily_update():
    """
    Legacy endpoint - redirects to the first active schedule or returns error
    This maintains backwards compatibility while migrating to schedule-based updates
    """
    try:
        if not verify_cron_auth():
            return jsonify({'error': 'Unauthorized'}), 401

        db = DatabaseManager()

        # Try to find the first active schedule
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT task_id FROM scheduled_tasks
                WHERE is_active = TRUE
                ORDER BY created_at ASC
                LIMIT 1
            ''')
            row = cursor.fetchone()

        if row:
            task_id = row[0]
            logger.info(f"Legacy endpoint redirecting to schedule {task_id}")
            return scheduled_update(task_id)
        else:
            logger.warning("Legacy endpoint called but no active schedules found")
            return jsonify({
                'error': 'No active schedules configured. Please create a schedule in the admin dashboard.',
                'timestamp': datetime.now().isoformat()
            }), 404

    except Exception as e:
        logger.error(f"Legacy cron job failed: {e}")
        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }), 500


# For local testing
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Test scheduled updates locally')
    parser.add_argument('--task-id', type=int, help='Schedule task ID to test')
    parser.add_argument('--list', action='store_true', help='List all active schedules')

    args = parser.parse_args()

    if args.list:
        db = DatabaseManager()
        with db.transaction() as conn:
            cursor = conn.execute('''
                SELECT task_id, name, lookback_days, mode, components,
                       schedule_cron, is_active, chamber
                FROM scheduled_tasks
                ORDER BY task_id
            ''')
            schedules = cursor.fetchall()

        print("\nActive Schedules:")
        print("-" * 80)
        for row in schedules:
            active = "✓" if row[6] else "✗"
            print(f"{active} ID: {row[0]} | {row[1]} | Congress: 119 | "
                  f"Lookback: {row[2]} days | Mode: {row[3]} | Cron: {row[5]}")
        print("-" * 80)

    elif args.task_id:
        print(f"\nTesting schedule {args.task_id}...")
        config = get_schedule_config(args.task_id)

        if not config:
            print(f"ERROR: Schedule {args.task_id} not found or inactive")
            sys.exit(1)

        print(f"Schedule: {config['schedule_name']}")
        print(f"Config: {json.dumps(config, indent=2)}")
        print("\nRunning update...")

        result = run_scheduled_update(config)
        print(json.dumps(result, indent=2))

    else:
        print("Usage:")
        print("  --list          List all schedules")
        print("  --task-id N     Test schedule N")
