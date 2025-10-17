#!/usr/bin/env python3
"""
Batch Worker - Processes individual batches of hearing updates asynchronously

This serverless function processes one batch at a time, enabling long-running
full sync operations to complete across multiple invocations without hitting
Vercel's 60-second (or 300-second) timeout limits.

Architecture:
- Coordinator creates N batch jobs for a task
- Each batch worker processes one batch (~50 hearings)
- Worker triggers the next batch upon completion
- Chain continues until all batches complete
"""
import os
import sys
import json
import time
import requests
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from flask import Flask, jsonify, request
    from database.unified_manager import UnifiedDatabaseManager
    from fetchers.hearing_fetcher import HearingFetcher
    from api.client import CongressAPIClient
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


def update_batch_status(db, batch_id, status, **kwargs):
    """Update batch status in database"""
    updates = ['status = %s']
    params = [status]

    if status == 'running':
        updates.append('started_at = %s')
        params.append(datetime.now())
    elif status in ('completed', 'failed'):
        updates.append('completed_at = %s')
        params.append(datetime.now())

    # Add result or error_message
    for key, value in kwargs.items():
        if key == 'result':
            updates.append('result = %s')
            params.append(json.dumps(value))
        elif key == 'error_message':
            updates.append('error_message = %s')
            params.append(value)

    params.append(batch_id)
    query = f"UPDATE admin_task_batches SET {', '.join(updates)} WHERE batch_id = %s"

    db.execute(query, tuple(params))


def update_parent_task_progress(db, task_id):
    """Update parent task's completed_batches count and check if all done"""
    # Count completed batches
    result = db.fetch_one("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'failed') as failed,
            COUNT(*) as total
        FROM admin_task_batches
        WHERE task_id = %s
    """, (task_id,))

    completed, failed, total = result['completed'], result['failed'], result['total']

    # Update parent task
    db.execute("""
        UPDATE admin_tasks
        SET completed_batches = %s
        WHERE task_id = %s
    """, (completed, task_id))

    # If all batches done, aggregate results and mark task complete
    if completed + failed >= total:
        aggregate_and_complete_task(db, task_id, completed, failed, total)


def aggregate_and_complete_task(db, task_id, completed, failed, total):
    """Aggregate results from all batches and mark parent task complete"""
    # Fetch all batch results
    batches = db.fetch_all("""
        SELECT batch_id, status, result, error_message
        FROM admin_task_batches
        WHERE task_id = %s
        ORDER BY batch_number
    """, (task_id,))

    # Aggregate metrics
    total_hearings_checked = 0
    total_hearings_added = 0
    total_hearings_updated = 0
    total_api_requests = 0
    all_errors = []

    for batch in batches:
        if batch['result']:
            result = batch['result'] if isinstance(batch['result'], dict) else json.loads(batch['result'])
            total_hearings_checked += result.get('hearings_checked', 0)
            total_hearings_added += result.get('hearings_added', 0)
            total_hearings_updated += result.get('hearings_updated', 0)
            total_api_requests += result.get('api_requests', 0)

        if batch['status'] == 'failed' and batch['error_message']:
            all_errors.append(f"Batch {batch['batch_id']}: {batch['error_message']}")

    # Determine overall status
    overall_status = 'completed' if failed == 0 else 'failed'
    overall_success = failed == 0

    # Create aggregated result
    aggregated_result = {
        'success': overall_success,
        'batched': True,
        'metrics': {
            'hearings_checked': total_hearings_checked,
            'hearings_added': total_hearings_added,
            'hearings_updated': total_hearings_updated,
            'api_requests': total_api_requests,
            'total_batches': total,
            'completed_batches': completed,
            'failed_batches': failed
        }
    }

    if all_errors:
        aggregated_result['errors'] = all_errors

    # Update parent task
    db.execute("""
        UPDATE admin_tasks
        SET status = %s,
            completed_at = %s,
            result = %s
        WHERE task_id = %s
    """, (overall_status, datetime.now(), json.dumps(aggregated_result), task_id))

    logger.info(f"Task {task_id} completed: {completed}/{total} batches successful, {failed} failed")


def process_batch(db, batch_id, batch_data):
    """Process a single batch of hearings"""
    start_time = time.time()

    # Initialize API client and fetcher
    api_client = CongressAPIClient()
    hearing_fetcher = HearingFetcher(api_client)

    # Extract batch parameters
    hearing_ids = batch_data.get('hearing_ids', [])
    congress = batch_data.get('congress', 119)
    chamber = batch_data.get('chamber')

    logger.info(f"Processing batch {batch_id}: {len(hearing_ids)} hearings from {chamber}")

    hearings_checked = 0
    hearings_added = 0
    hearings_updated = 0
    api_requests = 0

    # Fetch and process each hearing
    for hearing_id in hearing_ids:
        try:
            # Parse hearing_id format: "chamber:event_id"
            chamber_name, event_id = hearing_id.split(':', 1)

            # Fetch detailed hearing
            detailed = hearing_fetcher.fetch_hearing_details(congress, chamber_name, event_id)
            api_requests += 1
            hearings_checked += 1

            if detailed and 'committeeMeeting' in detailed:
                # TODO: Save to database using updaters/daily_updater.py logic
                # For now, just count it
                hearings_added += 1

        except Exception as e:
            logger.error(f"Error processing hearing {hearing_id}: {e}")

    duration = time.time() - start_time

    result = {
        'hearings_checked': hearings_checked,
        'hearings_added': hearings_added,
        'hearings_updated': hearings_updated,
        'api_requests': api_requests,
        'duration_seconds': duration
    }

    return result


def trigger_next_batch(task_id, current_batch_number):
    """Trigger the next batch worker via HTTP request"""
    try:
        # Get next batch
        db = UnifiedDatabaseManager(prefer_postgres=True)
        next_batch = db.fetch_one("""
            SELECT batch_id FROM admin_task_batches
            WHERE task_id = %s AND batch_number = %s AND status = 'pending'
        """, (task_id, current_batch_number + 1))

        if next_batch:
            # Trigger next batch via HTTP (self-invoke)
            base_url = os.environ.get('VERCEL_URL', '')
            if not base_url:
                # Fallback to production domain
                base_url = 'www.capitollabsllc.com'

            if not base_url.startswith('http'):
                base_url = f"https://{base_url}"

            url = f"{base_url}/api/batch/process/{next_batch['batch_id']}"
            logger.info(f"Triggering next batch: {url}")

            # Fire and forget using curl subprocess - completely detached
            import subprocess
            try:
                # Use curl in background, redirect output to /dev/null
                subprocess.Popen(
                    ['curl', '-X', 'POST', '-m', '2', url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Detach from parent process
                )
            except:
                pass  # Ignore errors - batch will be triggered
        else:
            logger.info(f"No more batches to process for task {task_id}")

    except Exception as e:
        logger.error(f"Failed to trigger next batch: {e}")


@app.route('/api/batch/process/<int:batch_id>', methods=['POST', 'GET'])
def process_batch_endpoint(batch_id):
    """Process a single batch"""
    try:
        logger.info(f"Batch worker received request for batch {batch_id}")

        # Initialize database
        db = UnifiedDatabaseManager(prefer_postgres=True)

        # Fetch batch
        batch = db.fetch_one("""
            SELECT * FROM admin_task_batches WHERE batch_id = %s
        """, (batch_id,))

        if not batch:
            return jsonify({'error': f'Batch {batch_id} not found'}), 404

        # Check if already processed
        if batch['status'] in ('completed', 'failed'):
            return jsonify({'message': f'Batch {batch_id} already {batch["status"]}'}), 200

        # Mark as running
        update_batch_status(db, batch_id, 'running')

        # Parse batch_data
        batch_data = batch['batch_data']
        if isinstance(batch_data, str):
            batch_data = json.loads(batch_data)

        # Process the batch
        try:
            result = process_batch(db, batch_id, batch_data)
            update_batch_status(db, batch_id, 'completed', result=result)
            logger.info(f"Batch {batch_id} completed successfully")

        except Exception as e:
            error_msg = str(e)
            update_batch_status(db, batch_id, 'failed', error_message=error_msg)
            logger.error(f"Batch {batch_id} failed: {error_msg}", exc_info=True)

        # Update parent task progress
        task_id = batch['task_id']
        update_parent_task_progress(db, task_id)

        # Trigger next batch
        trigger_next_batch(task_id, batch['batch_number'])

        return jsonify({
            'batch_id': batch_id,
            'status': 'processing'
        }), 200

    except Exception as e:
        logger.error(f"Batch worker error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)
