-- Admin Tasks Table Migration
-- Lightweight task tracking for manual admin updates

CREATE TABLE IF NOT EXISTS admin_tasks (
    task_id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,  -- 'manual_update', 'test_update', etc.
    status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed'

    -- Task parameters (JSON for flexibility)
    parameters JSONB NOT NULL DEFAULT '{}',

    -- Execution tracking
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,

    -- Results and logs
    result JSONB,  -- Success metrics, error details, etc.
    logs TEXT,  -- Captured output for debugging
    progress JSONB,  -- Current progress state

    -- Metadata
    triggered_by VARCHAR(100),  -- 'admin_dashboard', 'api_call', etc.
    environment VARCHAR(20)  -- 'production', 'development'
);

-- Index for quick status lookups
CREATE INDEX idx_admin_tasks_status ON admin_tasks(status);
CREATE INDEX idx_admin_tasks_created_at ON admin_tasks(created_at DESC);

-- View for recent tasks
CREATE OR REPLACE VIEW recent_admin_tasks AS
SELECT
    task_id,
    task_type,
    status,
    parameters,
    created_at,
    started_at,
    completed_at,
    EXTRACT(EPOCH FROM (COALESCE(completed_at, NOW()) - created_at)) as duration_seconds,
    result,
    triggered_by
FROM admin_tasks
ORDER BY created_at DESC
LIMIT 100;
