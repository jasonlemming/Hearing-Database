#!/usr/bin/env python3
"""
Task Scheduler - Master cron job that executes scheduled tasks from database

Runs every minute to check for scheduled tasks that are due to execute.
This allows dynamic scheduling without redeployment - just activate/deactivate
tasks in the admin UI and they'll run according to their cron schedule.
"""
import os
import sys
import requests
from datetime import datetime, timezone

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from flask import Flask, jsonify
    from database.unified_manager import UnifiedDatabaseManager
    from config.logging_config import get_logger
    from croniter import croniter
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


def should_task_run(schedule_cron: str, last_run_at: str | None) -> tuple[bool, datetime]:
    """
    Determine if a task should run based on its cron schedule

    Args:
        schedule_cron: Cron expression (e.g., "0 6 * * *")
        last_run_at: ISO timestamp of last execution, or None

    Returns:
        Tuple of (should_run, next_run_time)
    """
    now = datetime.now(timezone.utc)

    try:
        # Create croniter instance
        cron = croniter(schedule_cron, now)

        # Get the previous scheduled time (most recent time this cron should have run)
        prev_scheduled = cron.get_prev(datetime)

        # If never run before, run it if the scheduled time has passed
        if not last_run_at:
            # Only run if the scheduled time was within the last hour
            # (prevents running old schedules on first activation)
            time_since_scheduled = (now - prev_scheduled).total_seconds()
            should_run = 0 < time_since_scheduled < 3600  # Within last hour
            next_run = cron.get_next(datetime)
            return should_run, next_run

        # Parse last run time
        try:
            last_run = datetime.fromisoformat(last_run_at.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            # If parsing fails, treat as never run
            time_since_scheduled = (now - prev_scheduled).total_seconds()
            should_run = 0 < time_since_scheduled < 3600
            next_run = cron.get_next(datetime)
            return should_run, next_run

        # Task should run if:
        # 1. The most recent scheduled time is AFTER the last run
        # 2. The scheduled time is in the past (not future)
        should_run = prev_scheduled > last_run and prev_scheduled < now

        # Calculate next run time
        next_run = cron.get_next(datetime)

        return should_run, next_run

    except Exception as e:
        logger.error(f"Error parsing cron expression '{schedule_cron}': {e}")
        # If we can't parse the cron, don't run the task
        return False, now


@app.route('/api/cron/task-scheduler', methods=['GET', 'POST'])
def schedule_tasks():
    """
    Check database for scheduled tasks that are due and execute them

    This runs every minute via Vercel Cron. It:
    1. Queries for active schedules
    2. Checks if each is due to run (based on cron expression and last_run_at)
    3. Triggers the cron-update endpoint for tasks that are due
    4. Updates last_run_at and next_run_at timestamps
    """
    try:
        now = datetime.now(timezone.utc)
        logger.info(f"Task scheduler running at {now.isoformat()}")

        # Initialize database
        db = UnifiedDatabaseManager(prefer_postgres=True)

        # Get all active scheduled tasks
        tasks = db.fetch_all("""
            SELECT task_id, name, schedule_cron, lookback_days, components,
                   chamber, mode, last_run_at
            FROM scheduled_tasks
            WHERE is_active = TRUE
            ORDER BY task_id
        """)

        logger.info(f"Found {len(tasks)} active scheduled tasks")

        executed = []
        skipped = []

        cron_secret = os.environ.get("CRON_SECRET")
        auth_headers = None
        if cron_secret:
            auth_headers = {"Authorization": f"Bearer {cron_secret}"}
            logger.info("CRON_SECRET found; Authorization header will be attached to scheduler requests")
        else:
            logger.info("CRON_SECRET not set; scheduler requests will be sent without Authorization header")

        for task in tasks:
            task_id = task['task_id']
            task_name = task['name']
            schedule_cron = task['schedule_cron']
            last_run_at = task['last_run_at']

            # Check if task should run
            should_run, next_run = should_task_run(schedule_cron, last_run_at)

            # Always update next_run_at for display purposes
            db.execute("""
                UPDATE scheduled_tasks
                SET next_run_at = %s
                WHERE task_id = %s
            """, (next_run, task_id))

            if should_run:
                logger.info(f"Executing scheduled task: {task_name} (ID {task_id})")

                try:
                    # Trigger the cron-update endpoint with the task's schedule ID
                    base_url = os.environ.get('VERCEL_URL', 'www.capitollabsllc.com')
                    if not base_url.startswith('http'):
                        base_url = f"https://{base_url}"

                    url = f"{base_url}/api/cron/scheduled-update/{task_id}"

                    # Fire and forget with short timeout
                    try:
                        if auth_headers:
                            logger.debug(f"Attaching Authorization header for task {task_name} (ID {task_id})")
                        else:
                            logger.debug(f"No Authorization header for task {task_name} (ID {task_id})")

                        response = requests.post(url, timeout=5, headers=auth_headers)
                        logger.info(f"Triggered {task_name}: HTTP {response.status_code}")
                    except requests.exceptions.Timeout:
                        # Timeout is OK - the cron job is running
                        logger.info(f"Triggered {task_name} (timeout expected)")

                    # Update last_run_at
                    db.execute("""
                        UPDATE scheduled_tasks
                        SET last_run_at = %s
                        WHERE task_id = %s
                    """, (now, task_id))

                    executed.append({
                        'task_id': task_id,
                        'name': task_name,
                        'schedule': schedule_cron
                    })

                except Exception as e:
                    logger.error(f"Error executing {task_name}: {e}")
                    skipped.append({
                        'task_id': task_id,
                        'name': task_name,
                        'error': str(e)
                    })
            else:
                time_until = (next_run - now).total_seconds()
                logger.debug(f"Skipping {task_name}: next run in {time_until:.0f}s")
                skipped.append({
                    'task_id': task_id,
                    'name': task_name,
                    'reason': 'not_due',
                    'next_run': next_run.isoformat()
                })

        return jsonify({
            'success': True,
            'timestamp': now.isoformat(),
            'active_tasks': len(tasks),
            'executed': len(executed),
            'skipped': len(skipped),
            'executed_tasks': executed,
            'skipped_tasks': skipped[:5]  # Limit to avoid large responses
        }), 200

    except Exception as e:
        logger.error(f"Task scheduler error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5003)
