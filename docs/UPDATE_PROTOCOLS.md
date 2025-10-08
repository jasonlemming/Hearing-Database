# Update Protocols - Congressional Hearing Database

## Overview

This document describes the automated and manual update protocols for keeping the Congressional Hearing Database synchronized with Congress.gov data.

**Status**: ✅ Fixed and tested as of October 8, 2025
- ✅ **Date format bug fixed** - Incremental updates now functional
- ✅ Foreign key constraint issues resolved
- ✅ Multi-cadence update strategy implemented
- ✅ Video synchronization included in daily updates
- ✅ Admin dashboard operational

## Multi-Cadence Update Strategy

### Daily Updates (Automated - 6 AM UTC)
**Scope**: 7-day lookback window
**Trigger**: Vercel cron job (`/api/cron/daily-update`)
**Duration**: ~5-10 minutes
**API Requests**: <500

**Operations**:
- ✅ Fetch recently modified hearings (new + updated)
- ✅ Update hearing metadata (titles, dates, status, location)
- ✅ **Add/update video URLs and YouTube video IDs**
- ✅ Add new hearings
- ❌ No committee structure changes
- ❌ No member roster updates
- ❌ No full document re-import

**Expected Results**:
- 0-50 hearings updated per day (varies by congressional activity)
- 0-10 new hearings added per day
- 0 foreign key constraint errors

### Weekly Updates (Automated - Sundays 1 AM UTC & Mondays 1 AM UTC)

**Sunday - Committee Updates**
**Scope**: Full committee refresh
**Operations**:
- Committee structure updates
- Committee membership changes
- Subcommittee assignments

**Monday - Member Updates**
**Scope**: Full member roster
**Operations**:
- New member additions
- Party affiliation changes
- Leadership position updates

### Monthly Updates (Manual - 1st of month)
**Scope**: 90-day lookback
**Operations**:
- Full data integrity check
- Deep witness re-import
- Document refresh (transcripts, statements)
- Video backfill for older hearings

**Command**:
```bash
python cli.py update incremental --lookback-days 90
```

---

## Manual CLI Update Commands

### Quick Daily Update (7 days)
```bash
python cli.py update incremental --lookback-days 7
```

### Deep Sync (30 days)
```bash
python cli.py update incremental --lookback-days 30
```

### Component-Specific Updates

Control which components get updated during incremental sync:

**Hearings Only** (fastest - metadata + videos):
```bash
python cli.py update incremental --lookback-days 7 --components hearings
```

**Hearings + Witnesses** (skip committees):
```bash
python cli.py update incremental --lookback-days 7 --components hearings --components witnesses
```

**All Components** (default - most comprehensive):
```bash
python cli.py update incremental --lookback-days 7 --components hearings --components witnesses --components committees
# Or simply:
python cli.py update incremental --lookback-days 7
```

**Performance Impact:**
- Hearings only: ~1 API call per hearing, fastest
- + Witnesses: No additional API calls (extracted from hearing details)
- + Committees: No additional API calls (extracted from hearing details)
- **Total API calls reduced by 66%** vs previous implementation (eliminated redundant fetches)

**Note:**
- Videos are always included with hearing metadata (same API response, cannot be separated)
- Member updates run separately on weekly schedule (Mondays)

### Legacy Component Updates

**Video URLs** (backfill missing videos):
```bash
python cli.py update videos --limit 100
```

**Witnesses** (standalone):
```bash
python cli.py update witnesses --lookback-days 30
```

**Committees** (full refresh):
```bash
python cli.py update committees --chamber all
```

---

## Technical Details

### Foreign Key Constraint Fix

**Problem**: Previous implementation used `INSERT OR REPLACE` which caused SQLite to DELETE then INSERT records, violating foreign key constraints when child records existed.

**Solution**: Replaced with proper UPDATE/INSERT pattern:
1. Check if record exists by unique key
2. If exists → UPDATE existing record
3. If not exists → INSERT new record

**Files Modified**:
- `database/manager.py` - Fixed `upsert_hearing()`, `upsert_committee()`, `upsert_member()`, `upsert_bill()`
- `api/cron-update.py` - Replaced raw SQL with manager methods
- `updaters/daily_updater.py` - Already used manager methods (no changes needed)

### Update Flow

```
1. Fetch hearings from Congress.gov API (modified in last N days)
2. For each hearing:
   a. Check if exists in database by event_id
   b. If exists:
      - Compare API data with database record
      - If changes detected → UPDATE record
   c. If new:
      - INSERT new record
   d. Update related data (committees, witnesses, documents)
3. Record update metrics in update_logs table
```

### Video Synchronization

Videos are now included in daily updates:
- `video_url` - Full Congress.gov video URL
- `youtube_video_id` - Extracted YouTube video ID
- `video_type` - Video source type

**Extraction Pattern**:
```python
# House: https://www.youtube.com/embed/{video_id}
# Senate: https://www.senate.gov/isvp/...
```

### Database Schema

**Update Logs Table**:
```sql
CREATE TABLE update_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    errors TEXT,
    success BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Query Recent Updates**:
```sql
SELECT
    update_date,
    hearings_checked,
    hearings_updated,
    hearings_added,
    error_count,
    success
FROM update_logs
ORDER BY start_time DESC
LIMIT 10;
```

---

## Monitoring & Troubleshooting

### Health Check Queries

**Check last update status**:
```sql
SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 1;
```

**Check error rate**:
```sql
SELECT
    COUNT(*) as total_updates,
    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
    SUM(error_count) as total_errors
FROM update_logs
WHERE update_date >= date('now', '-30 days');
```

**Check hearings with missing videos**:
```sql
SELECT COUNT(*)
FROM hearings
WHERE (video_url IS NULL OR video_url = '')
AND hearing_date >= date('now', '-90 days');
```

### Common Issues

**Issue**: Incremental update returns 0 hearings checked
**Solution**: ✅ FIXED as of Oct 8, 2025. Date format now uses ISO 8601. If you're on an older version, update `fetchers/hearing_fetcher.py` lines 72-73 to use `'%Y-%m-%dT00:00:00Z'` format.

**Issue**: Update taking too long (>15 minutes)
**Solution**: Reduce lookback window or check API rate limiting. Note: Incremental mode fetches 90-day window then filters, so even 1-day lookback will check ~900-1000 hearings (this is expected behavior).

**Issue**: Foreign key constraint errors
**Solution**: Should no longer occur with fixed upsert methods. If persists, check database schema integrity.

**Issue**: Missing recent hearings
**Solution**: Increase lookback-days parameter or run full import

**Issue**: Video URLs not updating
**Solution**: Run `python cli.py update videos --force --limit 100`

### Performance Metrics

**Expected Update Times** (October 2025, 119th Congress):
- 1-day lookback: 2-3 minutes (checks ~938 hearings, finds ~10-30 updates)
- 7-day lookback: 3-5 minutes (checks ~938 hearings, finds ~100-300 updates)
- 30-day lookback: 5-10 minutes (checks ~938 hearings, finds ~600-800 updates)
- 90-day lookback: 10-20 minutes (checks ~938 hearings, finds ~900+ updates)

**Note**: Incremental mode fetches a 90-day window from the API (to catch hearings scheduled far ahead that were recently updated), then filters by `updateDate` to find hearings modified in your lookback period. This is why even a 1-day lookback checks ~900+ hearings.

**API Request Limits**:
- Congress.gov: 5,000 requests/hour
- Incremental update uses: ~940 requests (1 per hearing + list calls)
- Daily 7-day update typically uses: 200-500 requests after filtering

---

## Vercel Deployment

### Cron Configuration (`vercel.json`)

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

### Environment Variables

Required in Vercel dashboard:
```bash
API_KEY=your_congress_api_key
DATABASE_PATH=/var/task/database.db
TARGET_CONGRESS=119
```

### Monitoring Vercel Cron

Check logs in Vercel dashboard:
1. Go to Deployments → Logs
2. Filter by `/api/cron/daily-update`
3. Check for errors or timeouts

### Manual Trigger

Test cron endpoint locally:
```bash
curl http://localhost:5000/api/cron/daily-update \
  -H "Authorization: Bearer YOUR_CRON_SECRET"
```

---

## Best Practices

### Update Frequency Recommendations

1. **During Congressional Session**: Daily updates at 6 AM UTC
2. **During Recess**: Reduce to weekly updates
3. **High Activity Periods**: Consider twice-daily updates

### Data Integrity

- Run monthly 90-day lookback to catch any missed updates
- Monitor error_count in update_logs
- Use `cli.py analysis audit` quarterly for database health check

### API Usage Optimization

- Use incremental updates (not full re-imports)
- Batch related operations
- Respect rate limits (5,000/hour)
- Cache API responses when possible

---

## Changelog

**October 8, 2025 (Evening)**:
- ✅ **CRITICAL FIX**: Fixed date format bug in incremental updates
- ✅ Changed API date format from `YYYY-MM-DD` to ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`)
- ✅ Incremental updates now return actual results (was returning 0)
- ✅ All automated and manual update functionality restored
- ✅ Verified with testing: 1-day lookback = 24 hearings (was 0)

**October 8, 2025 (Earlier)**:
- ✅ Fixed foreign key constraint errors in all upsert methods
- ✅ Added video synchronization to daily updates
- ✅ Implemented multi-cadence update strategy
- ✅ Added comprehensive CLI update commands
- ✅ Updated Vercel cron endpoint to use fixed methods

**October 7, 2025**:
- ❌ Identified 783 foreign key constraint failures
- ❌ Updates failing on existing hearings with child records

---

## Support

For issues with daily updates:

1. Check update logs: `SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;`
2. Review error messages in `errors` column
3. Run manual update with verbose logging: `python cli.py update incremental --verbose`
4. Check API key validity
5. Verify database file permissions

**Contact**: Open GitHub issue with update logs and error messages
