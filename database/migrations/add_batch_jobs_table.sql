-- Migration: Add admin_task_batches table for async batch processing
-- This enables long-running tasks to be split into multiple serverless invocations

CREATE TABLE IF NOT EXISTS admin_task_batches (
    batch_id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES admin_tasks(task_id),
    batch_number INTEGER NOT NULL,
    total_batches INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- pending, running, completed, failed
    batch_data JSONB, -- Contains the subset of work for this batch
    result JSONB, -- Results from this batch
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    UNIQUE(task_id, batch_number)
);

CREATE INDEX IF NOT EXISTS idx_batch_task_status ON admin_task_batches(task_id, status);
CREATE INDEX IF NOT EXISTS idx_batch_status ON admin_task_batches(status);

-- Add batch tracking columns to admin_tasks
ALTER TABLE admin_tasks
ADD COLUMN IF NOT EXISTS is_batched BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS total_batches INTEGER,
ADD COLUMN IF NOT EXISTS completed_batches INTEGER DEFAULT 0;

COMMENT ON TABLE admin_task_batches IS 'Tracks individual batch jobs for long-running admin tasks';
COMMENT ON COLUMN admin_task_batches.batch_data IS 'Contains hearing IDs or date ranges to process in this batch';
COMMENT ON COLUMN admin_task_batches.result IS 'Metrics and results from processing this batch';
