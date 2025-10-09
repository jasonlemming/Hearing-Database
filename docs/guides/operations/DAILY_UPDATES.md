# Daily Update Automation System

The Congressional Hearing Database includes an automated daily update system that keeps the database synchronized with the latest data from the Congress.gov API.

> **🔧 FIXED**: As of October 8, 2025 (evening):
> - ✅ **Date format bug fixed** - Incremental updates now return actual results
> - ✅ All foreign key constraint errors resolved
> - ✅ Update system fully operational
> - ✅ Admin dashboard functional
>
> **📖 NEW DOCUMENTATION**: See [UPDATE_PROTOCOLS.md](UPDATE_PROTOCOLS.md) for comprehensive update strategy, CLI commands, and troubleshooting.

## Overview

The daily update system implements **incremental updates** to efficiently synchronize new and modified hearings without requiring full data re-imports. This ensures the database stays current with minimal API usage and processing time.

**Key Improvements**:
- ✅ Zero foreign key constraint errors
- ✅ Video URL synchronization included in daily updates
- ✅ Multi-cadence strategy (daily/weekly/monthly)
- ✅ Enhanced CLI commands for manual updates

## Features

- ✅ **Incremental Updates**: Only processes hearings modified in the last N days
- ✅ **Change Detection**: Compares API data with database records to identify updates
- ✅ **Comprehensive Logging**: Detailed logs of all update operations and metrics
- ✅ **Error Handling**: Graceful error handling with retry mechanisms
- ✅ **Rate Limiting**: Respects Congress.gov API rate limits (5,000 requests/hour)
- ✅ **Vercel Cron Integration**: Automated scheduling via Vercel cron jobs
- ✅ **Update History**: Tracks update metrics in database

## Quick Start

### 1. Manual Update (Local)

Run a manual update to test the system:

```bash
cd /path/to/Hearing-Database
source venv/bin/activate
python cli.py update incremental --lookback-days 7
```

### 2. Vercel Automated Updates

The system is configured for automatic daily updates on Vercel:

- **Schedule**: Daily at 6:00 AM UTC
- **Endpoint**: `/api/cron/daily-update`
- **Configuration**: `vercel.json` cron configuration

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-update",
      "schedule": "0 6 * * *"
    }
  ]
}
```

### 3. Local Cron Setup (Alternative)

For self-hosted deployments, schedule via cron:

```bash
# Edit your crontab
crontab -e

# Add daily update at 2 AM
0 2 * * * cd /path/to/Hearing-Database && /path/to/venv/bin/python cli.py update incremental --quiet >> logs/cron.log 2>&1
```

### 4. Monitor Updates

View update history and status:

- **API Endpoint**: `GET /api/update-status`
- **Admin Interface**: `/admin/updates` (if admin blueprint is enabled)
- **Log Files**: `logs/import.log`
- **Database Table**: `update_logs`

## How It Works

### Update Process

1. **Fetch Recent Data**: Retrieves hearings modified in the last N days from Congress.gov API
2. **Compare Records**: Compares API data with existing database records
3. **Identify Changes**: Determines which hearings need updates or are new
4. **Apply Updates**: Updates database records and adds new hearings
5. **Update Related Data**: Synchronizes witnesses, committees, and documents
6. **Record Metrics**: Logs update statistics to `update_logs` table

### Change Detection

The system compares these key fields to detect changes:

- Hearing title
- Date and time
- Status
- Hearing type
- Committee associations
- Witness information

### Incremental Processing Strategy

- **Daily Updates**: 7-day lookback (default)
- **Weekly Deep Sync**: 30-day lookback recommended
- **Monthly Comprehensive**: 60-90 day lookback for thoroughness

## Configuration

### Environment Variables

Set in `.env` or Vercel environment:

```bash
CONGRESS_API_KEY=your_api_key_here    # Required
UPDATE_WINDOW_DAYS=30                  # Lookback window (default: 30)
TARGET_CONGRESS=119                    # Congress to update
LOG_LEVEL=INFO                         # Logging level
```

### Command Line Options

```bash
python cli.py update incremental --help

Options:
  --congress INTEGER      Congress number to update (default: from env)
  --lookback-days INTEGER Days to look back for changes (default: 30)
  --quiet                 Reduce output for cron jobs
  --help                  Show this help message
```

## Update Metrics

The system tracks comprehensive metrics in the `update_logs` table:

```sql
CREATE TABLE update_logs (
    log_id INTEGER PRIMARY KEY,
    update_date DATE,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    duration_seconds REAL,
    hearings_checked INTEGER,
    hearings_updated INTEGER,
    hearings_added INTEGER,
    committees_updated INTEGER,
    witnesses_updated INTEGER,
    documents_cleaned INTEGER,
    documents_imported INTEGER,
    api_requests INTEGER,
    error_count INTEGER,
    success BOOLEAN
);
```

### Example Metrics Query

```sql
-- Recent update history
SELECT
    update_date,
    duration_seconds,
    hearings_checked,
    hearings_updated,
    hearings_added,
    success
FROM update_logs
ORDER BY start_time DESC
LIMIT 10;
```

## API Integration

### Check Update Status

```bash
curl http://localhost:5000/api/update-status
```

**Response:**
```json
{
  "status": "updated_today",
  "last_update": {
    "date": "2025-10-04",
    "start_time": "2025-10-04T06:00:15",
    "end_time": "2025-10-04T06:08:42",
    "duration_seconds": 507,
    "hearings_checked": 245,
    "hearings_updated": 12,
    "hearings_added": 3,
    "success": true
  },
  "recent_updates": [...],
  "total_recent_updates": 7
}
```

## Performance Optimization

### API Rate Limiting

- **Limit**: 5,000 requests/hour (Congress.gov)
- **Strategy**: Batch requests, respect rate limits
- **Monitoring**: Track `api_requests` in update logs

### Update Timing

Typical update times (October 2025, 119th Congress):

- **1-day lookback**: 2-3 minutes (checks ~938 hearings, finds ~10-30 updates)
- **7-day lookback**: 3-5 minutes (checks ~938 hearings, finds ~100-300 updates)
- **30-day lookback**: 5-10 minutes (checks ~938 hearings, finds ~600-800 updates)
- **60-day lookback**: 10-15 minutes (checks ~938 hearings, finds ~800+ updates)

**Note**: Times include fetching 90-day window and filtering by updateDate.

### Efficiency Strategies

1. **Incremental Processing**: Only fetch changed hearings
2. **Batch Operations**: Process hearings in batches
3. **Selective Updates**: Update only modified fields
4. **Connection Pooling**: Reuse database connections

## Error Handling

### Automatic Retry Logic

- Network errors: 3 retries with exponential backoff
- Rate limit exceeded: Wait for reset window
- Partial failures: Continue processing remaining items

### Error Tracking

All errors logged to:

- **Database**: `import_errors` table
- **Log Files**: `logs/import.log`
- **Update Metrics**: `error_count` field in `update_logs`

### Recovery Procedures

```bash
# Check recent errors
python cli.py analysis audit

# Re-run update with increased lookback
python cli.py update incremental --lookback-days 14

# Full re-import if needed
python cli.py import full --congress 119
```

## Monitoring & Alerts

### Health Checks

Monitor update health:

```bash
# Check recent update success
sqlite3 database.db "SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 1;"

# Check error counts
sqlite3 database.db "SELECT COUNT(*) FROM import_errors WHERE created_at > date('now', '-7 days');"
```

### Recommended Monitoring

1. **Daily Success Rate**: Should be >95%
2. **Update Duration**: Should be <15 minutes for 30-day lookback
3. **Error Count**: Should be <5 per update
4. **API Requests**: Should be <1000 per update

### Alert Thresholds

- ⚠️ **Warning**: Update duration >15 minutes
- ⚠️ **Warning**: Error count >5
- 🚨 **Critical**: Update failed
- 🚨 **Critical**: No successful update in 48 hours

## Vercel Deployment

### Cron Job Setup

The `vercel.json` configuration handles automated scheduling:

```json
{
  "crons": [
    {
      "path": "/api/cron/daily-update",
      "schedule": "0 6 * * *"
    }
  ]
}
```

### Cron Endpoint

Located at `api/cron-update.py`:

```python
@app.route('/api/cron/daily-update')
def daily_update():
    """Vercel cron endpoint for daily updates"""
    # Runs DailyUpdater with 30-day lookback
    # Returns JSON status
```

### Vercel Environment Variables

Set in Vercel dashboard:

- `CONGRESS_API_KEY` (or `API_KEY`)
- `DATABASE_PATH` (auto-configured for Vercel)
- `TARGET_CONGRESS`
- `UPDATE_WINDOW_DAYS`

## Best Practices

### Update Scheduling

1. **Daily Updates**: 7-day lookback during weekdays
2. **Weekend Deep Sync**: 30-day lookback on Sundays
3. **Monthly Verification**: 90-day lookback on 1st of month

### Maintenance

- **Weekly**: Review update logs for errors
- **Monthly**: Audit database integrity with `cli.py analysis audit`
- **Quarterly**: Consider full re-import to catch any missed data

### Troubleshooting

**Issue**: Updates taking too long
- **Solution**: Reduce lookback window or increase batch size

**Issue**: High error counts
- **Solution**: Check API key validity and rate limits

**Issue**: Missing recent hearings
- **Solution**: Increase lookback-days or run full import

## Database Cleanup

The update system includes automatic cleanup:

- **Document Deduplication**: Removes duplicate document entries
- **Orphan Removal**: Cleans up relationships with deleted hearings
- **Metadata Refresh**: Updates timestamps and sync tracking

## Future Enhancements

Planned improvements:

- **Webhook Notifications**: Alert on update failures
- **Selective Updates**: Update only specific committees/chambers
- **Historical Backfill**: Automated backfill of older congresses
- **Smart Scheduling**: Adjust update frequency based on congressional activity
- **Diff Reporting**: Detailed change reports in update logs

## Support

For issues with daily updates:

1. Check `/api/update-status` endpoint
2. Review `logs/import.log`
3. Query `update_logs` table for history
4. Run `python cli.py analysis audit` for database health
5. Open GitHub issue with update logs

---

**Note**: The daily update system is designed for hands-off operation. Once configured, it maintains database freshness with minimal intervention.

---

**Last Updated**: October 9, 2025
**Update Schedule**: Daily at 6:00 AM UTC
**Target Audience**: Operations and DevOps

[← Back: Monitoring](MONITORING.md) | [Up: Documentation Hub](../../README.md) | [Next: Update Protocols →](UPDATE_PROTOCOLS.md)
