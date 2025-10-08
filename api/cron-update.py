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
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


def verify_cron_auth():
    """Verify the request is from Vercel cron with valid auth"""
    cron_secret = request.headers.get('Authorization')
    expected_secret = os.environ.get('CRON_SECRET')

    if expected_secret and cron_secret != f"Bearer {expected_secret}":
        return False
    return True


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
            WHERE task_id = ? AND is_active = 1
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
            INSERT INTO schedule_execution_logs
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
        # Verify authentication
        if not verify_cron_auth():
            logger.warning(f"Unauthorized cron request for task {task_id}")
            return jsonify({'error': 'Unauthorized'}), 401

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
                WHERE is_active = 1
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
