#!/usr/bin/env python3
"""
Batch Orchestrator - Cron job to trigger pending batches

This runs every minute via Vercel Cron to check for pending batches
and trigger the next one for each running task.
"""
import os
import sys
import requests

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from flask import Flask, jsonify
    from database.unified_manager import UnifiedDatabaseManager
    from config.logging_config import get_logger
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

app = Flask(__name__)
logger = get_logger(__name__)


@app.route('/api/batch/orchestrator', methods=['GET', 'POST'])
def orchestrate_batches():
    """
    Check for running tasks with pending batches and trigger the next one
    """
    try:
        logger.info("Batch orchestrator running...")
        
        # Initialize database
        db = UnifiedDatabaseManager(prefer_postgres=True)
        
        # Find all running tasks with batches
        tasks = db.fetch_all("""
            SELECT DISTINCT t.task_id, t.task_type
            FROM admin_tasks t
            INNER JOIN admin_task_batches b ON b.task_id = t.task_id
            WHERE t.status = 'running' AND t.is_batched = TRUE
        """)
        
        logger.info(f"Found {len(tasks)} running batched tasks")
        
        triggered = []
        
        for task in tasks:
            task_id = task['task_id']
            
            # Check if there's a batch currently running
            running = db.fetch_one("""
                SELECT COUNT(*) as count
                FROM admin_task_batches
                WHERE task_id = %s AND status = 'running'
            """, (task_id,))
            
            if running['count'] > 0:
                logger.info(f"Task {task_id}: batch already running, skipping")
                continue
            
            # Find next pending batch
            next_batch = db.fetch_one("""
                SELECT batch_id, batch_number
                FROM admin_task_batches
                WHERE task_id = %s AND status = 'pending'
                ORDER BY batch_number
                LIMIT 1
            """, (task_id,))
            
            if next_batch:
                batch_id = next_batch['batch_id']
                batch_num = next_batch['batch_number']
                
                # Trigger it
                base_url = os.environ.get('VERCEL_URL', 'www.capitollabsllc.com')
                if not base_url.startswith('http'):
                    base_url = f"https://{base_url}"
                
                url = f"{base_url}/api/batch/process/{batch_id}"
                logger.info(f"Triggering task {task_id} batch {batch_num} (ID {batch_id})")
                
                try:
                    # Fire and forget with short timeout
                    requests.post(url, timeout=2)
                    triggered.append({'task_id': task_id, 'batch_id': batch_id, 'batch_number': batch_num})
                except:
                    # Timeout expected - batch is triggered
                    triggered.append({'task_id': task_id, 'batch_id': batch_id, 'batch_number': batch_num})
        
        return jsonify({
            'success': True,
            'running_tasks': len(tasks),
            'triggered_batches': len(triggered),
            'batches': triggered
        }), 200
        
    except Exception as e:
        logger.error(f"Batch orchestrator error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5002)
