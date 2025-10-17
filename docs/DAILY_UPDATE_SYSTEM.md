# Daily Update System Architecture

**Last Updated**: October 13, 2025
**Status**: Production-Ready with Monitoring
**Version**: 2.0

---

## Overview

The Congressional Hearing Database implements a fully automated daily update system that synchronizes data from the Congress.gov API. The system runs on Vercel's serverless infrastructure with cron-based scheduling.

### Key Features

- **Automated Daily Updates**: Runs at 6 AM UTC every day
- **Incremental Sync**: Only fetches changed/new data (7-day lookback window)
- **Health Monitoring**: Comprehensive health check endpoint
- **Data Validation**: Post-update validation script
- **Error Tracking**: Detailed logging and metrics
- **Admin Dashboard**: Real-time monitoring interface

### Current Performance

- **Update Frequency**: Daily at 6 AM UTC
- **Average Duration**: 5-10 minutes
- **API Requests**: ~1,500-2,000 per update (well under 5,000/hour limit)
- **Data Coverage**: 1,340+ hearings, 2,234+ witnesses, 239+ committees
- **Success Rate**: Target 99% (pending deployment)

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                   VERCEL CRON SCHEDULER                     │
│                                                             │
│  Schedule: "0 6 * * *" (6 AM UTC daily)                   │
│  Path: /api/cron/scheduled-update/3                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│            CRON ENDPOINT (api/cron-update.py)              │
│                                                             │
│  - Verifies auth (CRON_SECRET)                            │
│  - Loads schedule configuration from DB                     │
│  - Creates DailyUpdater instance                           │
│  - Logs execution to schedule_execution_logs               │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│          DAILY UPDATER (updaters/daily_updater.py)         │
│                                                             │
│  1. Fetch recent hearings (7-day lookback)                 │
│  2. Compare with database (identify changes)               │
│  3. Update/insert hearings                                 │
│  4. Extract embedded data:                                 │
│     - Video URLs                                           │
│     - Committee associations                               │
│     - Witnesses & documents                                │
│  5. Record metrics to update_logs                          │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  CONGRESS.GOV API CLIENT                    │
│                                                             │
│  - Rate limiting (5,000 req/hour)                          │
│  - Retry logic with backoff                                │
│  - Error handling                                          │
│  - Request tracking                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE                          │
│                                                             │
│  - 20 tables (hearings, committees, witnesses, etc.)       │
│  - 8.75 MB size (1,340 hearings)                          │
│  - Foreign key constraints enabled                         │
│  - Update tracking (update_logs, sync_tracking)            │
└─────────────────────────────────────────────────────────────┘
```

### Update Flow

```
1. TRIGGER (Vercel Cron)
   └─> Call /api/cron/scheduled-update/3

2. AUTHENTICATION
   └─> Verify CRON_SECRET header

3. LOAD CONFIGURATION
   └─> Query scheduled_tasks table (task_id = 3)
       - lookback_days: 7
       - components: ["hearings", "committees", "witnesses"]
       - mode: "incremental"
       - chamber: "both"

4. FETCH RECENT DATA
   └─> DailyUpdater.fetch_recent_hearings()
       - Fetch 90-day window of hearings
       - Filter by updateDate (last 7 days)
       - Fetch detailed info for each hearing
       - Extract embedded data (videos, committees, witnesses)

5. IDENTIFY CHANGES
   └─> DailyUpdater.identify_changes()
       - Compare API data with database
       - Check updateDate, title, status, location
       - Separate into updates vs additions

6. APPLY UPDATES
   └─> DailyUpdater.apply_updates()
       - Update existing hearings (using proper UPDATE)
       - Insert new hearings
       - Update video URLs
       - Link committees
       - Create/update witnesses & appearances

7. RECORD METRICS
   └─> update_logs table
       - Duration, counts, errors
       - API request count
       - Success/failure status

8. POST-UPDATE (Optional)
   └─> scripts/verify_updates.py
       - Validate data integrity
       - Check for anomalies
       - Send alerts if issues found
```

---

## Database Schema (Update-Relevant Tables)

### scheduled_tasks

Stores cron schedule configurations:

```sql
CREATE TABLE scheduled_tasks (
    task_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,                    -- "Daily at 6 AM UTC"
    schedule_cron TEXT NOT NULL,           -- "0 6 * * *"
    lookback_days INTEGER NOT NULL,        -- 7
    components TEXT NOT NULL,              -- JSON: ["hearings", ...]
    mode TEXT NOT NULL,                    -- "incremental" or "full"
    chamber TEXT DEFAULT 'both',           -- "both", "house", "senate"
    is_active BOOLEAN DEFAULT 1,           -- Enable/disable
    is_deployed BOOLEAN DEFAULT 0,         -- Deployed to Vercel?
    last_run_at TIMESTAMP,                 -- Last execution time
    next_run_at TIMESTAMP                  -- Calculated next run
);
```

### update_logs

Tracks all update operations:

```sql
CREATE TABLE update_logs (
    log_id INTEGER PRIMARY KEY,
    update_date DATE NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    duration_seconds REAL,
    hearings_checked INTEGER DEFAULT 0,
    hearings_updated INTEGER DEFAULT 0,
    hearings_added INTEGER DEFAULT 0,
    committees_updated INTEGER DEFAULT 0,
    witnesses_updated INTEGER DEFAULT 0,
    api_requests INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    errors TEXT,                           -- JSON array of errors
    success BOOLEAN DEFAULT 1,
    trigger_source TEXT DEFAULT 'manual',  -- "vercel_cron", "manual", "test"
    schedule_id INTEGER,                   -- FK to scheduled_tasks
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### schedule_execution_logs

Links schedules to execution results:

```sql
CREATE TABLE schedule_execution_logs (
    execution_id INTEGER PRIMARY KEY,
    schedule_id INTEGER NOT NULL,          -- FK to scheduled_tasks
    log_id INTEGER NOT NULL,               -- FK to update_logs
    execution_time DATETIME NOT NULL,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    config_snapshot TEXT,                  -- JSON snapshot of config
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Configuration

### Environment Variables

Required for Vercel deployment:

```bash
# Congress.gov API
CONGRESS_API_KEY=your_api_key_here
CONGRESS_API_BASE_URL=https://api.congress.gov/v3

# Cron Authentication
CRON_SECRET=your_secret_token_here

# Database
DATABASE_PATH=database.db

# Optional
LOG_LEVEL=INFO
RATE_LIMIT=5000
```

### Vercel Configuration (vercel.json)

```json
{
  "crons": [
    {
      "path": "/api/cron/scheduled-update/3",
      "schedule": "0 6 * * *"
    }
  ],
  "routes": [
    {
      "src": "/api/cron/scheduled-update/([0-9]+)",
      "dest": "api/cron-update.py"
    },
    {
      "src": "/api/cron/health",
      "dest": "api/cron-update.py"
    }
  ]
}
```

### Schedule Configuration (Database)

Task ID #3 (Daily at 6 AM UTC):

```sql
INSERT INTO scheduled_tasks (
    task_id, name, schedule_cron, lookback_days,
    components, mode, chamber, is_active, is_deployed
) VALUES (
    3,
    'Daily at 6 AM UTC',
    '0 6 * * *',
    7,
    '["hearings", "committees", "witnesses"]',
    'incremental',
    'both',
    1,
    0  -- Set to 1 after deploying to Vercel
);
```

---

## Error Handling & Reliability

### Retry Strategy

The system implements comprehensive retry logic with exponential backoff:

**API Client Configuration**:
```python
retry_attempts = 5              # Up from 3
retry_backoff_factor = 2.0      # 2s → 4s → 8s → 16s → 32s
status_forcelist = [429, 500, 502, 503, 504]
```

**Features**:
- Automatic retries on transient failures
- Exponential backoff prevents overwhelming servers
- Retry statistics tracking for monitoring
- Configurable via environment variables

### Circuit Breaker Pattern

Protects against cascading failures by monitoring error rates:

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Threshold exceeded (5 consecutive failures), requests blocked
- **HALF_OPEN**: Testing recovery after 60-second timeout

**Configuration**:
```bash
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60
```

**Behavior**:
- Opens after 5 consecutive API failures
- Prevents wasting resources on unavailable service
- Automatically tests recovery after timeout
- Closes after 2 successful requests

**Integration**:
- Health endpoint shows circuit breaker state
- Notifications sent when breaker opens
- DailyUpdater handles CircuitBreakerError gracefully

### Notification System

Automated alerts for critical issues:

**Notification Types**:
1. **Log** (default): Always enabled, writes to application log
2. **Email**: SendGrid integration for email alerts
3. **Webhook**: Discord/Slack webhook integration

**Configuration**:

```bash
# Enable notifications
NOTIFICATION_ENABLED=true
NOTIFICATION_TYPE=email  # or webhook, log

# Email notifications (SendGrid)
SENDGRID_API_KEY=your_api_key
NOTIFICATION_EMAIL=admin@example.com

# Webhook notifications (Discord/Slack)
NOTIFICATION_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**Alert Triggers**:
- Update failures (critical)
- Circuit breaker opens (critical)
- High error rate > 10 errors (warning)
- Rate limit exhausted (warning)

**Example Discord Alert**:
```
🔴 Daily Update Failed
Severity: ERROR
Timestamp: 2025-10-13 06:15:23

The daily update process failed with error: CircuitBreakerError: Circuit breaker 'congress_api' is OPEN

Additional Details:
{
  "hearings_checked": 150,
  "hearings_updated": 0,
  "error_count": 12,
  "duration_seconds": 45.2
}
```

### Error Recovery

**Automatic Recovery**:
1. **Transient API Errors**: Automatic retry with backoff
2. **Rate Limiting**: Wait and resume when limit resets
3. **Circuit Breaker Open**: Wait 60s, test recovery, resume
4. **Partial Update Failures**: Log errors, continue with remaining items

**Manual Recovery**:
```bash
# Check system health
curl https://your-app.vercel.app/api/cron/health

# Validate database integrity
python scripts/verify_updates.py

# Manually trigger update
curl -X POST -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/test-schedule/3

# Run database maintenance
python scripts/database_maintenance.py --full
```

### Error Monitoring

**Health Endpoint Enhancements**:

The `/api/cron/health` endpoint now includes:

```json
{
  "checks": {
    "circuit_breaker": {
      "name": "congress_api",
      "state": "closed",
      "failure_count": 0,
      "failure_rate_pct": 2.5,
      "total_calls": 1523,
      "times_opened": 0
    },
    "retry_stats": {
      "total_retries": 15,
      "last_retry_time": 1729238400
    }
  }
}
```

**Monitoring Script**:

Use the included health check script:

```bash
# Check health with colored output
./scripts/check_health.sh https://your-app.vercel.app/api/cron/health

# Use in cron for automated monitoring
*/30 * * * * /path/to/check_health.sh https://your-app.vercel.app/api/cron/health || /path/to/alert.sh
```

See [MONITORING_SETUP.md](MONITORING_SETUP.md) for complete monitoring configuration.

---

## Monitoring & Health Checks

### Health Check Endpoint

**Endpoint**: `GET /api/cron/health`

Returns comprehensive system health:

```json
{
  "timestamp": "2025-10-13T10:30:00",
  "status": "healthy",
  "checks": {
    "database": "connected",
    "database_size_mb": 8.75,
    "last_update": {
      "date": "2025-10-13",
      "start_time": "2025-10-13 06:00:05",
      "end_time": "2025-10-13 06:08:23",
      "duration_seconds": 498.3,
      "hearings_updated": 15,
      "hearings_added": 3,
      "error_count": 0,
      "success": true,
      "trigger_source": "vercel_cron"
    },
    "hours_since_last_update": 4.5,
    "active_tasks": 1,
    "tasks": [
      {
        "id": 3,
        "name": "Daily at 6 AM UTC",
        "schedule": "0 6 * * *",
        "deployed": true,
        "last_run": "2025-10-13 06:00:05"
      }
    ],
    "data_counts": {
      "hearings": 1340,
      "committees": 239,
      "witnesses": 2234,
      "members": 538
    },
    "error_rate_7days": {
      "total_updates": 7,
      "failed_updates": 0,
      "error_rate_pct": 0.0
    }
  },
  "warnings": [],
  "errors": []
}
```

**Status Codes**:
- `200`: Healthy or degraded (with warnings)
- `503`: Unhealthy (critical errors)

**Health Status**:
- `healthy`: All checks pass
- `degraded`: Warnings present but functional
- `unhealthy`: Critical errors detected

### Validation Script

**Script**: `scripts/verify_updates.py`

Run after each update to validate data:

```bash
# Basic validation
python scripts/verify_updates.py

# Verbose output
python scripts/verify_updates.py --verbose

# JSON output (for monitoring tools)
python scripts/verify_updates.py --json

# Attempt to fix issues
python scripts/verify_updates.py --fix
```

**Checks Performed**:
1. Data counts (reasonable table sizes)
2. Date ranges (no far-future or ancient dates)
3. Foreign key integrity
4. Duplicate records
5. Missing relationships (hearings without committees)
6. Anomalies (sudden data drops, missing videos)
7. Recent update status

**Example Output**:

```
================================================================================
UPDATE VALIDATION REPORT
================================================================================
Timestamp: 2025-10-13 10:30:15

DATABASE STATISTICS:
--------------------------------------------------------------------------------
  hearings                      :    1,340
  committees                    :      239
  witnesses                     :    2,234
  members                       :      538
  witness_appearances           :    2,650
  hearing_committees            :    1,351

  Hearing Date Range: 2025-01-14 to 2025-10-22 (1340 hearings)

✓ NO ISSUES FOUND

WARNINGS:
--------------------------------------------------------------------------------
  1. 15 hearings have no committee associations
  2. Recent video extraction rate: 78.5%

================================================================================
✓ VALIDATION PASSED
================================================================================
```

---

## Update Modes

### Incremental Mode (Default)

**When to use**: Daily updates, regular maintenance

**Configuration**:
```python
lookback_days = 7
mode = "incremental"
```

**How it works**:
1. Fetch 90-day window of hearings (covers recent activity)
2. Filter by `updateDate` (last 7 days)
3. Compare with database to identify changes
4. Update only changed fields

**Performance**:
- Duration: 5-10 minutes
- API Requests: ~1,500-2,000
- Data Coverage: Recent changes only

**Advantages**:
- Fast and efficient
- Minimal API usage
- Catches all updates (even for future hearings)

### Full Mode

**When to use**: Initial import, recovery from errors, comprehensive sync

**Configuration**:
```python
lookback_days = 90
mode = "full"
```

**How it works**:
1. Fetch ALL hearings for congress (no date filter)
2. Fetch detailed info for every hearing
3. Full comparison with database
4. Update everything

**Performance**:
- Duration: 20-30 minutes
- API Requests: ~3,000-4,000
- Data Coverage: Complete

**Advantages**:
- Comprehensive data coverage
- Recovers from any data issues
- Ensures consistency

---

## Deployment Guide

### Step 1: Verify Configuration

1. **Check scheduled_tasks table**:
```sql
SELECT * FROM scheduled_tasks WHERE task_id = 3;
```

Ensure:
- `is_active = 1`
- `schedule_cron = "0 6 * * *"`
- `lookback_days = 7`
- `mode = "incremental"`

2. **Verify environment variables in Vercel**:
- `CONGRESS_API_KEY` - Your API key
- `CRON_SECRET` - Random secure token

### Step 2: Deploy to Vercel

```bash
# Install Vercel CLI
npm install -g vercel

# Login
vercel login

# Deploy
vercel --prod

# Verify deployment
vercel ls
```

### Step 3: Mark as Deployed

```sql
UPDATE scheduled_tasks
SET is_deployed = 1
WHERE task_id = 3;
```

### Step 4: Test Cron Endpoint

```bash
# Test with curl (replace with your Vercel URL)
curl -X POST \
  -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/scheduled-update/3
```

### Step 5: Monitor First Run

1. **Check update_logs**:
```sql
SELECT * FROM update_logs
WHERE trigger_source = 'vercel_cron'
ORDER BY start_time DESC
LIMIT 1;
```

2. **Check health endpoint**:
```bash
curl https://your-app.vercel.app/api/cron/health
```

3. **Run validation**:
```bash
python scripts/verify_updates.py
```

---

## Troubleshooting

### Issue: Cron job not running

**Symptoms**:
- No new entries in `update_logs` with `trigger_source = 'vercel_cron'`
- `last_run_at` in `scheduled_tasks` is old

**Diagnosis**:
1. Check Vercel dashboard for cron logs
2. Verify `vercel.json` is deployed
3. Check `is_deployed` flag in database

**Solutions**:
- Redeploy with `vercel --prod`
- Verify cron schedule format
- Check CRON_SECRET is set correctly

### Issue: Updates failing with errors

**Symptoms**:
- `success = 0` in `update_logs`
- High `error_count`

**Diagnosis**:
1. Check `errors` column in `update_logs`
2. Review logs in Vercel dashboard
3. Run validation script

**Common Causes**:
- API rate limit exceeded
- Network timeouts
- Database foreign key violations
- Missing API key

**Solutions**:
- Increase `lookback_days` to reduce API calls
- Add retry logic with backoff
- Fix database schema issues
- Verify API key is valid

### Issue: No new hearings added

**Symptoms**:
- `hearings_checked > 0` but `hearings_added = 0`
- Hearing count not increasing

**Diagnosis**:
1. Check if Congress is in session
2. Verify updateDate filtering is working
3. Check if data is actually changing

**Solutions**:
- Increase `lookback_days` temporarily
- Switch to `full` mode for one run
- Verify API is returning data

### Issue: Foreign key violations

**Symptoms**:
- Errors mentioning foreign keys
- `FOREIGN KEY constraint failed`

**Diagnosis**:
```bash
python scripts/verify_updates.py
```

Check `PRAGMA foreign_key_check`:
```sql
PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;
```

**Solutions**:
- Ensure using `UPDATE` instead of `INSERT OR REPLACE`
- Fix orphaned records
- Re-run with `--fix` flag

---

## Best Practices

### Daily Operations

1. **Monitor health endpoint**: Check daily at `/api/cron/health`
2. **Review update logs**: Weekly review of `update_logs` table
3. **Run validation**: Weekly run of `verify_updates.py`
4. **Check error rates**: Keep error rate < 5%

### Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Health check | Daily | `curl /api/cron/health` |
| Validation | Weekly | `python scripts/verify_updates.py` |
| Database vacuum | Monthly | `sqlite3 database.db "VACUUM"` |
| Full sync | Quarterly | Switch to `full` mode for one run |
| Log cleanup | Quarterly | Delete old `update_logs` (> 90 days) |

### Performance Optimization

1. **Use incremental mode** for daily updates
2. **Optimize lookback window**: 7 days is usually sufficient
3. **Monitor API usage**: Stay well under 5,000 req/hour
4. **Database maintenance**: Regular VACUUM and ANALYZE
5. **Index optimization**: Ensure indexes on update-heavy tables

### Security

1. **Protect CRON_SECRET**: Use strong random token
2. **Verify cron auth**: Check Authorization header
3. **Rate limiting**: Implement exponential backoff
4. **Error logging**: Don't expose API keys in logs
5. **Database backups**: Regular backups before updates

---

## Metrics & KPIs

### Target Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Success Rate | > 99% | < 95% |
| Update Duration | < 10 min | > 15 min |
| API Requests | < 2,000 | > 4,000 |
| Error Rate | < 5% | > 10% |
| Data Freshness | < 24 hours | > 48 hours |
| Database Size | < 50 MB | > 100 MB |

### Monitoring Queries

**Success rate (last 30 days)**:
```sql
SELECT
    ROUND(100.0 * SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate_pct,
    COUNT(*) as total_updates
FROM update_logs
WHERE start_time >= datetime('now', '-30 days');
```

**Average update duration**:
```sql
SELECT
    ROUND(AVG(duration_seconds), 2) as avg_duration_sec,
    ROUND(MAX(duration_seconds), 2) as max_duration_sec
FROM update_logs
WHERE success = 1 AND start_time >= datetime('now', '-30 days');
```

**API usage trends**:
```sql
SELECT
    DATE(start_time) as date,
    AVG(api_requests) as avg_requests,
    MAX(api_requests) as max_requests
FROM update_logs
WHERE start_time >= datetime('now', '-7 days')
GROUP BY DATE(start_time)
ORDER BY date DESC;
```

---

## Future Enhancements

### ✅ Recently Completed (October 2025)

1. **Error Handling & Reliability** ✅
   - ✅ Enhanced retry logic with exponential backoff (5 attempts)
   - ✅ Circuit breaker pattern implementation
   - ✅ Automatic recovery from transient failures
   - ✅ Error notification system (Email/Webhook)

2. **Monitoring Enhancements** ✅
   - ✅ Circuit breaker status in health endpoint
   - ✅ Retry statistics tracking
   - ✅ Health check automation script
   - ✅ Comprehensive monitoring guide

### Short-term (Next Sprint)

1. **Smart Scheduling**
   - Detect congressional recess
   - Reduce frequency during recess
   - Increase during active periods
   - Adaptive lookback windows

2. **Advanced Notifications**
   - SMS for critical errors (Twilio)
   - PagerDuty integration
   - Notification escalation rules
   - Alert grouping and deduplication

### Medium-term (Next Quarter)

1. **Performance Optimization**
   - Caching layer (Redis)
   - Batch API requests
   - Connection pooling

2. **Advanced Monitoring**
   - Grafana dashboards
   - Prometheus metrics
   - Real-time alerting

3. **Data Enrichment**
   - Video backfill
   - Document completeness
   - Relationship inference

### Long-term (Future)

1. **PostgreSQL Migration**
   - When database > 100 MB
   - Better concurrent access
   - Advanced features

2. **Microservices Architecture**
   - Separate update service
   - Queue-based processing
   - Horizontal scaling

3. **ML/AI Integration**
   - Anomaly detection
   - Smart data validation
   - Predictive scheduling

---

## Related Documentation

- [System Architecture](SYSTEM_ARCHITECTURE.md) - Overall system design
- [Database Schema](reference/architecture/database-schema.md) - Complete schema reference
- [Admin Dashboard Guide](ADMIN_DASHBOARD.md) - Using the admin interface
- [API Reference](reference/API_REFERENCE.md) - API endpoints documentation
- [Deployment Guide](deployment/DEPLOYMENT.md) - Vercel deployment instructions

---

## Support & Contact

For issues or questions:
- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Check `/docs` directory
- **Health Check**: Monitor `/api/cron/health` endpoint
- **Validation**: Run `scripts/verify_updates.py`

---

**Document Version**: 2.0
**Last Reviewed**: October 13, 2025
**Next Review**: January 2026
