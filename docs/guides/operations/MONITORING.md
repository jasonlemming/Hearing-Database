# Monitoring Guide

Complete guide to monitoring the Congressional Hearing Database for health, performance, and data quality.

## Table of Contents

1. [Overview](#overview)
2. [Admin Dashboard](#admin-dashboard)
3. [Health Check Endpoints](#health-check-endpoints)
4. [Performance Metrics](#performance-metrics)
5. [Database Monitoring](#database-monitoring)
6. [Update Monitoring](#update-monitoring)
7. [Alert Thresholds](#alert-thresholds)
8. [Log Analysis](#log-analysis)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The Congressional Hearing Database provides comprehensive monitoring capabilities through:

- **Admin Dashboard** (`/admin`) - Real-time monitoring interface
- **API Endpoints** - Programmatic access to metrics
- **Database Tables** - Historical tracking (`update_logs`, `sync_tracking`, `import_errors`)
- **CLI Commands** - Command-line monitoring tools

**Monitoring Architecture**:

```
┌─────────────────────────────────────────────────────────┐
│                   Admin Dashboard                       │
│   http://localhost:5001/admin                          │
│   - Real-time update monitoring                         │
│   - Task management                                     │
│   - History viewer                                      │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│                   API Endpoints                         │
│   /admin/api/*                                          │
│   - Start/cancel updates                                │
│   - Task status                                         │
│   - Metrics retrieval                                   │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│                Database Tracking Tables                 │
│   - update_logs (all updates with metrics)             │
│   - sync_tracking (last sync per entity)               │
│   - import_errors (error log)                          │
│   - scheduled_tasks (automation config)                │
│   - schedule_execution_logs (execution history)        │
└─────────────────────────────────────────────────────────┘
```

**⚠️ Security Warning**: The admin dashboard has NO AUTHENTICATION. Only use on localhost for development/testing. DO NOT deploy `/admin` routes to production without adding authentication.

---

## Admin Dashboard

### Accessing the Dashboard

```bash
# Start the web server
python cli.py web serve --host 127.0.0.1 --port 5001

# Open in browser
open http://localhost:5001/admin
```

### Dashboard Features

#### 1. Main Dashboard (`/admin`)

**Shows**:
- Total hearings in database
- Hearings updated since baseline
- Last update timestamp
- Changes since production baseline
- Quick action buttons

**Key Metrics**:
```
Total Hearings: 1,168
Updated Since Baseline: 783
New Since Baseline: 125
Last Update: 2025-10-09 06:00:15 UTC
```

#### 2. Update History (`/admin/updates`)

**Shows**:
- Last 50 updates (30-day window)
- Update metrics (checked, updated, added)
- Duration and API request counts
- Error counts and messages
- Success/failure status

**Example Update Log**:
```
Update Date: 2025-10-09
Duration: 147.3 seconds
Hearings Checked: 235
Hearings Updated: 12
Hearings Added: 3
API Requests: 248
Errors: 0
Status: ✓ Success
```

#### 3. Manual Update Controls

**Features**:
- Run update with custom parameters
- Component selection (hearings, witnesses, committees)
- Lookback days (1-90)
- Chamber filter (both, house, senate)
- Mode selection (incremental, full)
- Dry-run option
- Real-time progress tracking

**UI Controls**:
```javascript
// Update configuration
{
  "lookback_days": 7,
  "components": ["hearings", "videos"],
  "chamber": "both",
  "mode": "incremental",
  "dry_run": false
}
```

#### 4. Real-Time Progress Monitoring

**Features**:
- 2-second polling interval
- Live log streaming
- Progress percentage
- Metric updates
- Task cancellation

**Progress Display**:
```
Status: Running
Progress: 35% (82/235 hearings processed)
Duration: 52 seconds
Hearings Updated: 4
Hearings Added: 1
Errors: 0
```

---

## Health Check Endpoints

### API Endpoint Reference

All endpoints return JSON. Base path: `/admin/api`

#### 1. Database Status

**Endpoint**: `GET /admin/api/production-diff`

**Returns**:
```json
{
  "local_count": 1293,
  "production_count": 1168,
  "difference": +125,
  "new_hearings": 125,
  "updated_hearings": 783,
  "baseline_date": "2025-10-01",
  "last_update": "2025-10-09 06:00:15"
}
```

**Health Criteria**:
- ✓ Good: `difference >= 0` (local ahead of or equal to production)
- ⚠️ Warning: `difference < 0` (local behind production)
- ✓ Good: `last_update` within last 24 hours (for automated updates)

#### 2. Recent Changes

**Endpoint**: `GET /admin/api/recent-changes?since=2025-10-01&limit=50`

**Returns**:
```json
{
  "since_date": "2025-10-01",
  "count": 125,
  "changes": [
    {
      "event_id": "LC12345",
      "title": "Hearing on Budget",
      "chamber": "House",
      "hearing_date": "2025-10-15",
      "change_type": "updated",
      "created_at": "2025-10-01 10:00:00",
      "updated_at": "2025-10-09 06:05:22"
    }
  ]
}
```

**Monitoring**:
- Track `change_type` distribution (added vs updated)
- Monitor `count` for unusual spikes
- Verify `updated_at` timestamps are recent

#### 3. Update Logs

**Endpoint**: Direct database query or dashboard UI

**Query**:
```sql
SELECT
    update_date,
    start_time,
    end_time,
    duration_seconds,
    hearings_checked,
    hearings_updated,
    hearings_added,
    api_requests,
    error_count,
    success
FROM update_logs
WHERE update_date >= date('now', '-7 days')
ORDER BY start_time DESC;
```

**Health Criteria**:
- ✓ Good: `success = 1` for all recent updates
- ✓ Good: `duration_seconds < 300` (under 5 minutes for 7-day update)
- ⚠️ Warning: `error_count > 0` (investigate errors)
- ⚠️ Warning: `api_requests > 4500` (approaching rate limit)

#### 4. Task Status

**Endpoint**: `GET /admin/api/task-status/<task_id>`

**Returns**:
```json
{
  "status": "running",
  "progress": {
    "hearings_checked": 82,
    "hearings_updated": 4,
    "hearings_added": 1,
    "errors": 0
  },
  "duration_seconds": 52,
  "recent_logs": [
    "Processing hearing LC12345...",
    "Updated: Budget Hearing (video added)",
    "Processed 82/235 hearings (35%)"
  ],
  "error_count": 0
}
```

**Status Values**:
- `running` - Task in progress
- `completed` - Task finished successfully
- `failed` - Task encountered fatal error
- `cancelled` - Task manually cancelled

---

## Performance Metrics

### Update Performance

**Key Metrics**:

| Metric | Target | Warning Threshold | Description |
|--------|--------|-------------------|-------------|
| Duration (7-day) | < 3 minutes | > 5 minutes | Time to complete 7-day update |
| Duration (30-day) | < 15 minutes | > 20 minutes | Time to complete 30-day update |
| API requests | < 500 (7-day) | > 4500 (hourly) | Number of API calls made |
| Hearings/second | > 5 | < 2 | Processing throughput |
| Error rate | 0% | > 1% | Percentage of failed operations |

**Measuring Performance**:

```sql
-- Calculate average update duration by lookback period
SELECT
    CASE
        WHEN hearings_checked < 100 THEN '7-day'
        WHEN hearings_checked < 500 THEN '30-day'
        ELSE '90-day'
    END as period,
    COUNT(*) as update_count,
    AVG(duration_seconds) as avg_duration,
    MIN(duration_seconds) as min_duration,
    MAX(duration_seconds) as max_duration,
    AVG(hearings_checked) as avg_hearings_checked,
    AVG(CAST(hearings_checked AS FLOAT) / duration_seconds) as hearings_per_second
FROM update_logs
WHERE update_date >= date('now', '-30 days')
  AND success = 1
GROUP BY CASE
    WHEN hearings_checked < 100 THEN '7-day'
    WHEN hearings_checked < 500 THEN '30-day'
    ELSE '90-day'
END
ORDER BY avg_duration;
```

**Expected Results**:
```
period   | update_count | avg_duration | hearings_per_second
---------|--------------|--------------|--------------------
7-day    |     30       |    147.3     |        5.8
30-day   |      4       |    852.1     |        4.2
90-day   |      1       |   2401.5     |        3.1
```

### API Rate Limiting

**Congress.gov API Limits**:
- **Rate Limit**: 5,000 requests per hour
- **Request Tracking**: Logged in `update_logs.api_requests`
- **Safety Margin**: Keep under 4,500 requests/hour

**Monitoring API Usage**:

```sql
-- API requests per update
SELECT
    update_date,
    start_time,
    api_requests,
    hearings_checked,
    CAST(api_requests AS FLOAT) / hearings_checked as requests_per_hearing
FROM update_logs
WHERE update_date >= date('now', '-7 days')
ORDER BY start_time DESC;
```

**Typical Ratios**:
- **Hearings only**: ~1.0 requests per hearing (just metadata)
- **With videos**: ~1.0 requests per hearing (video data in same response)
- **With witnesses**: ~1.5-2.0 requests per hearing (additional witness fetches)
- **Full import**: ~3-5 requests per hearing (committees, members, documents)

### Database Performance

**Key Metrics**:

| Metric | Target | Command |
|--------|--------|---------|
| Database size | < 100 MB | `ls -lh database.db` |
| Query response | < 100 ms | Monitor via logs |
| Index efficiency | > 95% | `EXPLAIN QUERY PLAN` |
| Table counts | Consistent | `python cli.py database status` |

**Monitoring Database Size**:

```bash
# Check database size
ls -lh database.db

# Expected: ~50-60 MB for 1,200 hearings
# Warning if > 100 MB (may need VACUUM)
```

**Database Maintenance**:

```bash
# Optimize database (reclaim space, update statistics)
sqlite3 database.db "VACUUM; ANALYZE;"

# Check integrity
sqlite3 database.db "PRAGMA integrity_check;"

# Check foreign keys
sqlite3 database.db "PRAGMA foreign_key_check;"
```

---

## Database Monitoring

### Table Counts

**Check Record Counts**:

```bash
# Via CLI
python cli.py database status

# Output:
Database Status:
==================================================
hearings            :      1,168
committees          :        213
members             :      [count]
witnesses           :      [count]
committee_memberships:     [count]
hearing_committees  :      [count]
witness_appearances :      [count]
```

**Via SQL**:

```sql
-- Get all table counts
SELECT
    'hearings' as table_name, COUNT(*) as count FROM hearings
UNION ALL
SELECT 'committees', COUNT(*) FROM committees
UNION ALL
SELECT 'members', COUNT(*) FROM members
UNION ALL
SELECT 'witnesses', COUNT(*) FROM witnesses
UNION ALL
SELECT 'hearing_committees', COUNT(*) FROM hearing_committees
UNION ALL
SELECT 'witness_appearances', COUNT(*) FROM witness_appearances;
```

### Data Quality Metrics

**Hearing Completeness**:

```sql
-- Completeness report
SELECT
    COUNT(*) as total_hearings,
    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_title,
    COUNT(CASE WHEN hearing_date IS NOT NULL THEN 1 END) as with_date,
    COUNT(CASE WHEN youtube_video_id IS NOT NULL THEN 1 END) as with_video,
    ROUND(100.0 * COUNT(CASE WHEN title IS NOT NULL THEN 1 END) / COUNT(*), 2) as title_pct,
    ROUND(100.0 * COUNT(CASE WHEN hearing_date IS NOT NULL THEN 1 END) / COUNT(*), 2) as date_pct,
    ROUND(100.0 * COUNT(CASE WHEN youtube_video_id IS NOT NULL THEN 1 END) / COUNT(*), 2) as video_pct
FROM hearings
WHERE congress = 119;
```

**Expected Completeness**:
- **Titles**: > 95% (some hearings lack titles)
- **Dates**: > 90% (scheduled hearings may not have dates yet)
- **Videos**: > 30% (not all hearings recorded)
- **Committee assignments**: > 99% (should be nearly complete)

**Relationship Integrity**:

```sql
-- Check for orphaned records
SELECT
    'hearing_committees' as table_name,
    COUNT(*) as orphan_count
FROM hearing_committees hc
LEFT JOIN hearings h ON hc.hearing_id = h.hearing_id
WHERE h.hearing_id IS NULL

UNION ALL

SELECT
    'witness_appearances',
    COUNT(*)
FROM witness_appearances wa
LEFT JOIN hearings h ON wa.hearing_id = h.hearing_id
WHERE h.hearing_id IS NULL

UNION ALL

SELECT
    'hearing_transcripts',
    COUNT(*)
FROM hearing_transcripts ht
LEFT JOIN hearings h ON ht.hearing_id = h.hearing_id
WHERE h.hearing_id IS NULL;
```

**Health Criteria**:
- ✓ Good: `orphan_count = 0` for all tables
- ❌ Critical: `orphan_count > 0` (data integrity violation)

### Sync Tracking

**Last Successful Sync**:

```sql
-- Get last sync for each entity type
SELECT
    entity_type,
    last_sync_timestamp,
    records_processed,
    errors_count,
    status
FROM sync_tracking
WHERE status = 'success'
  AND sync_id IN (
    SELECT MAX(sync_id)
    FROM sync_tracking
    WHERE status = 'success'
    GROUP BY entity_type
  )
ORDER BY last_sync_timestamp DESC;
```

**Expected Sync Frequency**:
- **Hearings**: Daily (last sync < 24 hours old)
- **Committees**: Weekly (last sync < 7 days old)
- **Members**: Weekly (last sync < 7 days old)
- **Bills**: As needed (tracked via hearing relationships)
- **Documents**: Monthly (last sync < 30 days old)

---

## Update Monitoring

### Automated Update Monitoring

**Scheduled Tasks**:

```sql
-- Check active scheduled tasks
SELECT
    name,
    schedule_cron,
    lookback_days,
    is_active,
    is_deployed,
    last_run_at,
    next_run_at
FROM scheduled_tasks
WHERE is_active = 1
ORDER BY next_run_at;
```

**Expected Schedule** (default configuration):
```
name                      | schedule_cron | last_run_at           | next_run_at
--------------------------|---------------|-----------------------|------------------------
Daily Hearing Update      | 0 6 * * *     | 2025-10-09 06:00:15  | 2025-10-10 06:00:00
Weekly Committee Refresh  | 0 1 * * 0     | 2025-10-06 01:00:00  | 2025-10-13 01:00:00
Weekly Member Refresh     | 0 1 * * 1     | 2025-10-07 01:00:00  | 2025-10-14 01:00:00
```

**Health Checks**:
- ✓ Good: `last_run_at` within expected interval
- ⚠️ Warning: `last_run_at` > 2x expected interval (may be stuck)
- ❌ Critical: `is_deployed = 0` but `is_active = 1` (not deployed to Vercel)

### Execution History

**Scheduled Task Performance**:

```sql
-- Success rate per scheduled task (last 30 days)
SELECT
    st.name,
    COUNT(*) as total_executions,
    SUM(CASE WHEN sel.success = 1 THEN 1 ELSE 0 END) as successful,
    ROUND(100.0 * SUM(CASE WHEN sel.success = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
    AVG(ul.duration_seconds) as avg_duration_seconds
FROM schedule_execution_logs sel
JOIN scheduled_tasks st ON sel.schedule_id = st.task_id
JOIN update_logs ul ON sel.log_id = ul.log_id
WHERE sel.execution_time >= datetime('now', '-30 days')
GROUP BY st.task_id, st.name
ORDER BY success_rate DESC;
```

**Target Success Rate**: > 95%

**Action Items**:
- **Success rate < 95%**: Investigate error patterns
- **Success rate < 80%**: Review schedule configuration
- **Success rate = 0%**: Check Vercel deployment or API connectivity

### Manual Update Tracking

**Recent Manual Updates**:

```sql
-- Recent manual updates
SELECT
    update_date,
    start_time,
    duration_seconds,
    hearings_checked,
    hearings_updated,
    hearings_added,
    trigger_source,
    success
FROM update_logs
WHERE trigger_source = 'manual'
ORDER BY start_time DESC
LIMIT 10;
```

**Monitor For**:
- Frequent manual updates (may indicate automation issues)
- Long-running manual updates (> 10 minutes)
- Failed manual updates (investigate immediately)

---

## Alert Thresholds

### Critical Alerts

**Immediate Action Required**:

| Alert | Threshold | Query | Action |
|-------|-----------|-------|--------|
| Update failure | Any update with `success = 0` | Check `update_logs` WHERE `success = 0` | Review error logs, retry update |
| API rate limit | `api_requests > 4500` in 1 hour | Check recent `update_logs.api_requests` | Reduce update frequency or batch size |
| Data integrity | `orphan_count > 0` | Foreign key check queries | Run database repair |
| Database corruption | Integrity check fails | `PRAGMA integrity_check` | Restore from backup |
| No updates in 48 hours | `last_update > 48 hours ago` | Check `update_logs.start_time` | Investigate automation |

**Query for Critical Alerts**:

```sql
-- Critical alert summary
SELECT
    'Recent failures' as alert_type,
    COUNT(*) as count
FROM update_logs
WHERE update_date >= date('now', '-7 days')
  AND success = 0

UNION ALL

SELECT
    'High API usage',
    COUNT(*)
FROM update_logs
WHERE update_date >= date('now', '-1 day')
  AND api_requests > 4500

UNION ALL

SELECT
    'Stale data (>48 hours)',
    CASE
        WHEN MAX(start_time) < datetime('now', '-48 hours') THEN 1
        ELSE 0
    END
FROM update_logs;
```

### Warning Alerts

**Investigate Soon**:

| Alert | Threshold | Query | Action |
|-------|-----------|-------|--------|
| Slow updates | `duration_seconds > 300` for 7-day | Check `update_logs.duration_seconds` | Review performance logs |
| High error count | `error_count > 5` | Check `update_logs.error_count` | Review error messages |
| Missing committee assignments | `> 5 hearings` without committees | Check `hearing_committees` | Run relationship inference |
| Low video coverage | `< 25%` hearings with videos | Check completeness query | Verify video extraction working |
| Declining success rate | `< 90%` for scheduled tasks | Check execution logs | Review schedule configuration |

### Informational Monitoring

**Track Trends**:

| Metric | Description | Frequency |
|--------|-------------|-----------|
| Daily hearing count | New hearings per day | Daily |
| Update duration trend | Average duration over time | Weekly |
| Video availability trend | Percentage with videos | Weekly |
| Committee activity | Hearings per committee | Monthly |
| Witness testimony frequency | Top witnesses by appearances | Monthly |

**Trending Query**:

```sql
-- Daily update metrics (last 30 days)
SELECT
    update_date,
    COUNT(*) as updates_run,
    AVG(duration_seconds) as avg_duration,
    SUM(hearings_added) as total_hearings_added,
    SUM(hearings_updated) as total_hearings_updated,
    AVG(error_count) as avg_errors
FROM update_logs
WHERE update_date >= date('now', '-30 days')
GROUP BY update_date
ORDER BY update_date DESC;
```

---

## Log Analysis

### Update Logs

**Location**: Database table `update_logs`

**Key Fields**:
- `start_time`, `end_time`, `duration_seconds` - Timing
- `hearings_checked`, `hearings_updated`, `hearings_added` - Metrics
- `api_requests` - Rate limiting tracking
- `error_count`, `errors` - Error tracking
- `success` - Overall status
- `trigger_source` - manual, vercel_cron, test

**Analyzing Errors**:

```sql
-- Error patterns
SELECT
    json_extract(value, '$') as error_message,
    COUNT(*) as occurrence_count,
    MAX(update_date) as last_occurrence
FROM update_logs,
     json_each(update_logs.errors)
WHERE errors IS NOT NULL
  AND errors != '[]'
  AND update_date >= date('now', '-30 days')
GROUP BY json_extract(value, '$')
ORDER BY occurrence_count DESC
LIMIT 20;
```

**Common Error Patterns**:
- **API timeout**: `Request timeout after 30 seconds` - Increase timeout or retry
- **Rate limit**: `429 Too Many Requests` - Reduce update frequency
- **Parse error**: `Failed to parse hearing data` - Data format changed (API update)
- **Foreign key error**: `FOREIGN KEY constraint failed` - Upsert logic issue

### Import Errors

**Location**: Database table `import_errors`

**Query Unresolved Errors**:

```sql
-- Unresolved critical errors
SELECT
    entity_type,
    entity_identifier,
    error_type,
    error_message,
    created_at
FROM import_errors
WHERE severity = 'critical'
  AND is_resolved = 0
ORDER BY created_at DESC
LIMIT 50;
```

**Error Categories**:

| Error Type | Severity | Typical Causes | Resolution |
|------------|----------|----------------|------------|
| `validation` | Warning | Invalid data format | Update parser validators |
| `api_error` | Critical | API unavailable or changed | Check API status, update client |
| `parse_error` | Warning | Unexpected data structure | Update parser logic |
| `network_error` | Critical | Connection timeout | Check network, retry |

**Marking Errors Resolved**:

```sql
-- Mark specific errors as resolved after fix
UPDATE import_errors
SET is_resolved = 1
WHERE error_id IN (123, 124, 125);
```

### Application Logs

**Location**: `logs/import.log` (configurable via `LOG_FILE`)

**Log Levels**:
- **DEBUG**: Detailed diagnostic information
- **INFO**: General informational messages
- **WARNING**: Non-critical issues
- **ERROR**: Errors that don't stop execution
- **CRITICAL**: Critical errors requiring immediate attention

**Analyzing Application Logs**:

```bash
# Recent errors
grep ERROR logs/import.log | tail -20

# Critical issues
grep CRITICAL logs/import.log

# Failed updates
grep "Update failed" logs/import.log | tail -10

# API rate limit warnings
grep "rate limit" logs/import.log -i

# Parse errors
grep "Failed to parse" logs/import.log | tail -20
```

**Log Rotation**:

```bash
# Manual log rotation (if logs grow large)
mv logs/import.log logs/import.log.$(date +%Y%m%d)
touch logs/import.log

# Keep last 30 days
find logs/ -name "import.log.*" -mtime +30 -delete
```

---

## Troubleshooting

### Update Not Running

**Symptoms**: Updates not occurring on schedule

**Diagnosis**:

```sql
-- Check scheduled tasks
SELECT * FROM scheduled_tasks WHERE is_active = 1;

-- Check recent executions
SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;
```

**Possible Causes**:
1. **Schedule not deployed**: `is_deployed = 0` but `is_active = 1`
   - **Fix**: Deploy schedule to Vercel, or set `is_deployed = 1` after deployment
2. **Vercel cron not configured**: Missing `vercel.json` cron entry
   - **Fix**: Export Vercel config via `/admin/api/schedules/export-vercel`
3. **API key missing**: `CONGRESS_API_KEY` not set in Vercel environment
   - **Fix**: Add environment variable in Vercel dashboard
4. **Rate limit reached**: Previous update hit rate limit
   - **Fix**: Wait for rate limit reset, reduce lookback_days

### Slow Updates

**Symptoms**: Updates taking > 5 minutes for 7-day lookback

**Diagnosis**:

```sql
-- Recent update durations
SELECT
    update_date,
    start_time,
    duration_seconds,
    hearings_checked,
    CAST(hearings_checked AS FLOAT) / duration_seconds as hearings_per_second
FROM update_logs
WHERE update_date >= date('now', '-7 days')
ORDER BY duration_seconds DESC;
```

**Possible Causes**:
1. **High hearing count**: More hearings to check than usual
   - **Solution**: Normal, not an issue
2. **Witness fetching enabled**: Additional API calls per hearing
   - **Solution**: Disable witnesses component for faster updates
3. **Network latency**: Slow API responses
   - **Solution**: Increase `REQUEST_TIMEOUT`, check network
4. **Database locks**: Concurrent operations blocking
   - **Solution**: Avoid running manual updates during automated ones

### Missing Data

**Symptoms**: Expected hearings or data not appearing

**Diagnosis**:

```sql
-- Check hearing counts by date
SELECT
    hearing_date,
    COUNT(*) as count,
    COUNT(CASE WHEN updated_at > created_at THEN 1 END) as updated_count
FROM hearings
WHERE hearing_date >= date('now', '-30 days')
GROUP BY hearing_date
ORDER BY hearing_date DESC;

-- Check for gaps in hearing_committees
SELECT
    COUNT(*) as hearings_without_committee
FROM hearings h
LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
WHERE hc.hearing_id IS NULL
  AND h.congress = 119;
```

**Possible Causes**:
1. **Not yet in API**: Congress.gov hasn't published yet
   - **Solution**: Wait for API update
2. **Update skipped**: Hearing outside lookback window
   - **Solution**: Run update with longer lookback (e.g., 30 days)
3. **Import error**: Parsing or validation failed
   - **Solution**: Check `import_errors` table for specific hearing
4. **Relationship missing**: Committee assignment not inferred
   - **Solution**: Run `python cli.py enhance hearings --target committees`

### High Error Count

**Symptoms**: `error_count > 0` in update logs

**Diagnosis**:

```sql
-- View recent errors
SELECT
    update_date,
    start_time,
    error_count,
    errors
FROM update_logs
WHERE error_count > 0
ORDER BY start_time DESC
LIMIT 10;
```

**Possible Causes**:
1. **API format change**: Congress.gov updated data structure
   - **Solution**: Update parsers to handle new format
2. **Network issues**: Transient API timeouts
   - **Solution**: Retry update
3. **Data validation failures**: Invalid data from API
   - **Solution**: Relax validators or report to Congress.gov
4. **Foreign key violations**: Upsert logic issue
   - **Solution**: Ensure proper upsert methods used (not INSERT OR REPLACE)

### Database Integrity Issues

**Symptoms**: Foreign key check fails or orphaned records

**Diagnosis**:

```bash
# Check foreign keys
sqlite3 database.db "PRAGMA foreign_key_check;"

# Check integrity
sqlite3 database.db "PRAGMA integrity_check;"
```

**Possible Causes**:
1. **Improper upsert**: Used INSERT OR REPLACE (breaks FK)
   - **Solution**: Always use DatabaseManager upsert methods
2. **Concurrent modifications**: Multiple processes writing simultaneously
   - **Solution**: Ensure only one update process runs at a time
3. **Database corruption**: File corruption from crash or power loss
   - **Solution**: Restore from backup

**Recovery**:

```bash
# Backup first
cp database.db database.db.backup

# Try repair
sqlite3 database.db ".recover" | sqlite3 database_recovered.db

# If recovery fails, restore from backup
cp backups/database_YYYYMMDD_HHMMSS.db database.db
```

---

## Additional Resources

### Related Documentation

- **[Update Protocols](UPDATE_PROTOCOLS.md)** - Update strategies and scheduling
- **[Daily Updates](DAILY_UPDATES.md)** - Automated daily synchronization
- **[Admin Dashboard](../../features/admin-dashboard.md)** - Dashboard quick start
- **[Troubleshooting Guide](../../troubleshooting/common-issues.md)** - Common problems

### External Resources

- **[Congress.gov API Status](https://api.congress.gov/)** - Check API availability
- **[Vercel Status](https://www.vercel-status.com/)** - Vercel service status
- **[SQLite PRAGMA Commands](https://www.sqlite.org/pragma.html)** - Database commands

---

## Monitoring Checklist

### Daily Checks

- [ ] Automated update ran successfully (check `/admin/updates`)
- [ ] Error count = 0 in last update
- [ ] API requests < 4500 per hour
- [ ] No critical errors in `import_errors` table

### Weekly Checks

- [ ] Committee and member updates ran successfully
- [ ] Update duration trends stable (not increasing)
- [ ] Success rate > 95% for scheduled tasks
- [ ] Database size reasonable (< 100 MB)

### Monthly Checks

- [ ] Run comprehensive 90-day update
- [ ] Run database integrity check (`PRAGMA integrity_check`)
- [ ] Check data quality metrics (completeness, relationships)
- [ ] Review and resolve non-critical import errors
- [ ] Analyze performance trends
- [ ] Rotate/archive old logs if needed

---

**Last Updated**: October 9, 2025
**Version**: 2.0
**System**: Congressional Hearing Database

[← Back: Update Protocols](UPDATE_PROTOCOLS.md) | [Up: Documentation Hub](../../README.md) | [Next: Troubleshooting →](../../troubleshooting/common-issues.md)
