#!/usr/bin/env python3
"""
Admin Task Executor - Separate Vercel Serverless Function

This runs as an independent serverless function to bypass the 60-second
timeout limit on HTTP responses. Tasks are triggered via HTTP, execute
asynchronously, and store results in the database for polling.

Similar architecture to cron-update.py but for manual admin tasks.
"""
import os
import sys
import json
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from flask import Flask, jsonify, request
    from database.unified_manager import UnifiedDatabaseManager
    from updaters.daily_updater import DailyUpdater
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


def update_task_status(db, task_id, status, **kwargs):
    """Update task status in database"""
    updates = ['status = %s']
    params = [status]

    if status == 'running':
        updates.append('started_at = %s')
        params.append(datetime.now())
    elif status in ('completed', 'failed'):
        updates.append('completed_at = %s')
        params.append(datetime.now())

    # Add any additional fields (result, logs, progress)
    for key, value in kwargs.items():
        if key in ('result', 'progress'):
            updates.append(f'{key} = %s')
            params.append(json.dumps(value))
        elif key == 'logs':
            updates.append('logs = %s')
            params.append(value)

    params.append(task_id)
    query = f"UPDATE admin_tasks SET {', '.join(updates)} WHERE task_id = %s"

    db.execute(query, tuple(params))


def execute_manual_update(db, task_id, parameters):
    """Execute manual update task"""
    try:
        # Extract parameters
        lookback_days = parameters.get('lookback_days', 7)
        components = parameters.get('components', ['hearings', 'witnesses', 'committees'])
        mode = parameters.get('mode', 'incremental')
        dry_run = parameters.get('dry_run', False)

        logger.info(f"Starting manual update task {task_id}: lookback={lookback_days}, mode={mode}, components={components}, dry_run={dry_run}")

        # Mark as running
        update_task_status(db, task_id, 'running')

        # Create updater instance
        updater = DailyUpdater(
            congress=119,
            lookback_days=lookback_days,
            update_mode=mode,
            components=components
        )

        updater.trigger_source = 'admin_manual'
        updater.task_id = task_id

        # Define progress callback to update database
        def progress_callback(progress_data):
            """
            Progress callback that receives a dict with progress information
            from DailyUpdater and stores it in the database
            """
            if isinstance(progress_data, dict):
                progress_data['timestamp'] = datetime.now().isoformat()
                update_task_status(db, task_id, 'running', progress=progress_data)
            else:
                # Fallback for old-style calls (shouldn't happen)
                logger.warning(f"progress_callback received non-dict: {progress_data}")
                update_task_status(db, task_id, 'running', progress={'message': str(progress_data)})

        # Run the update
        result = updater.run_daily_update(dry_run=dry_run, progress_callback=progress_callback)

        # Store result
        if result.get('success'):
            update_task_status(db, task_id, 'completed', result=result)
            logger.info(f"Manual update task {task_id} completed successfully")
        else:
            update_task_status(db, task_id, 'failed', result=result)
            logger.error(f"Manual update task {task_id} failed: {result.get('error')}")

        return result

    except Exception as e:
        error_result = {
            'success': False,
            'error': str(e)
        }
        update_task_status(db, task_id, 'failed', result=error_result)
        logger.error(f"Manual update task {task_id} exception: {e}", exc_info=True)
        return error_result


@app.route('/api/admin/run-task/<int:task_id>', methods=['POST', 'GET'])
def run_task(task_id):
    """
    Vercel serverless function endpoint to execute admin tasks

    Args:
        task_id: ID of the task to execute

    Returns:
        JSON response with task execution results
    """
    try:
        logger.info(f"Admin task executor received request for task {task_id}")

        # Initialize database
        db = UnifiedDatabaseManager(prefer_postgres=True)

        # Fetch task from database
        task = db.fetch_one('SELECT * FROM admin_tasks WHERE task_id = %s', (task_id,))

        if not task:
            return jsonify({'error': f'Task {task_id} not found'}), 404

        # Parse parameters
        parameters = task.get('parameters', task.get('parameters'))
        if isinstance(parameters, str):
            parameters = json.loads(parameters)

        task_type = task.get('task_type', task.get('task_type'))

        # Execute based on task type
        if task_type == 'manual_update':
            result = execute_manual_update(db, task_id, parameters)
        else:
            return jsonify({'error': f'Unknown task type: {task_type}'}), 400

        return jsonify({
            'task_id': task_id,
            'result': result
        }), 200

    except Exception as e:
        logger.error(f"Admin task handler error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
