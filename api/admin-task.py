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
    from fetchers.hearing_fetcher import HearingFetcher
    from api.client import CongressAPIClient
    from config.logging_config import get_logger
    import requests
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


def create_batched_update(db, task_id, parameters):
    """Create batches for a full sync update"""
    congress = 119
    batch_size = 50  # Hearings per batch

    logger.info(f"Creating batches for task {task_id}")

    # Initialize API client and fetcher
    api_client = CongressAPIClient()
    hearing_fetcher = HearingFetcher(api_client)

    # Fetch basic hearing list (no details) for both chambers
    house_hearings = hearing_fetcher.fetch_hearings(congress, chamber='house')
    senate_hearings = hearing_fetcher.fetch_hearings(congress, chamber='senate')

    logger.info(f"Found {len(house_hearings)} House and {len(senate_hearings)} Senate hearings")

    # Create hearing ID list
    all_hearing_ids = []
    for hearing in house_hearings:
        event_id = hearing.get('eventId')
        if event_id:
            all_hearing_ids.append(f"house:{event_id}")

    for hearing in senate_hearings:
        event_id = hearing.get('eventId')
        if event_id:
            all_hearing_ids.append(f"senate:{event_id}")

    # Split into batches
    total_hearings = len(all_hearing_ids)
    total_batches = (total_hearings + batch_size - 1) // batch_size  # Ceiling division

    logger.info(f"Creating {total_batches} batches of ~{batch_size} hearings each")

    # Update parent task to mark as batched
    db.execute("""
        UPDATE admin_tasks
        SET is_batched = TRUE,
            total_batches = %s,
            status = 'running',
            started_at = %s
        WHERE task_id = %s
    """, (total_batches, datetime.now(), task_id))

    # Create batch records
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, total_hearings)
        batch_hearing_ids = all_hearing_ids[start_idx:end_idx]

        batch_data = {
            'congress': congress,
            'hearing_ids': batch_hearing_ids,
            'chamber': 'both'
        }

        db.execute("""
            INSERT INTO admin_task_batches
            (task_id, batch_number, total_batches, status, batch_data)
            VALUES (%s, %s, %s, %s, %s)
        """, (task_id, batch_num, total_batches, 'pending', json.dumps(batch_data)))

    logger.info(f"Created {total_batches} batch records for task {task_id}")

    # Trigger first batch
    first_batch = db.fetch_one("""
        SELECT batch_id FROM admin_task_batches
        WHERE task_id = %s AND batch_number = 0
    """, (task_id,))

    if first_batch:
        trigger_batch_worker(first_batch['batch_id'])

    return {
        'success': True,
        'message': f'Created {total_batches} batches, processing started',
        'total_batches': total_batches,
        'total_hearings': total_hearings
    }


def trigger_batch_worker(batch_id):
    """Trigger batch worker via HTTP"""
    try:
        base_url = os.environ.get('VERCEL_URL', '')
        if not base_url:
            # Fallback to production domain
            base_url = 'www.capitollabsllc.com'

        if not base_url.startswith('http'):
            base_url = f"https://{base_url}"

        url = f"{base_url}/api/batch/process/{batch_id}"
        logger.info(f"Triggering batch worker: {url}")

        # Fire and forget - use timeout to prevent blocking
        requests.post(url, timeout=5)

    except Exception as e:
        logger.error(f"Failed to trigger batch worker: {e}")


def execute_manual_update(db, task_id, parameters):
    """Execute manual update task"""
    try:
        # Extract parameters
        lookback_days = parameters.get('lookback_days', 7)
        components = parameters.get('components', ['hearings', 'witnesses', 'committees'])
        mode = parameters.get('mode', 'incremental')
        dry_run = parameters.get('dry_run', False)

        logger.info(f"Starting manual update task {task_id}: lookback={lookback_days}, mode={mode}, components={components}, dry_run={dry_run}")

        # For full mode, use batched processing
        if mode == 'full':
            logger.info(f"Using batched processing for full sync (task {task_id})")
            result = create_batched_update(db, task_id, parameters)
            return result

        # For incremental mode, use synchronous processing
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
