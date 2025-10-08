# Admin Dashboard - Quick Start Guide

## Overview

The Admin Dashboard provides a comprehensive interface for managing and monitoring database updates for the Congressional Hearing Database. It enables manual update triggering, real-time progress tracking, and visual verification of data changes.

**⚠️ IMPORTANT**: This dashboard has NO AUTHENTICATION and is designed for localhost use only. Never deploy the `/admin` route to production without adding proper authentication.

## Accessing the Dashboard

1. **Start the Flask application**:
   ```bash
   python3 -m web.app
   ```

2. **Open your browser** to:
   ```
   http://localhost:5001/admin/
   ```

## Features

### 1. Dashboard Overview

The main dashboard displays:

- **Total Hearings**: Current count in local database
- **Ahead of Production**: Number of hearings not yet on production
- **Updated Since Baseline**: Hearings modified since October 1, 2025
- **Last Update**: Date and time of most recent update

### 2. Manual Update Controls

Trigger updates with customizable parameters:

**Lookback Days** (1-90)
- Slider to control how many days back to check for changes
- Default: 7 days

**Components**
- ☑ **Hearing Metadata** (REQUIRED)
  - Title, date, status, location, type
  - Video URLs and YouTube IDs
  - Cannot be disabled (videos come in same API response)

- ☑ **Witnesses & Documents** (OPTIONAL)
  - Witness information and testimonies
  - Witness-submitted documents
  - Uncheck to skip witness processing (~30% faster)

- ☑ **Committee Associations** (OPTIONAL)
  - Committee memberships for hearings
  - Primary committee designation
  - Uncheck to skip committee processing (~20% faster)

**Note:** Member roster updates run separately on weekly schedule (Mondays).

**Chamber Filter**
- Both Chambers (default)
- House Only
- Senate Only

**Dry Run Mode**
- Preview changes without modifying database
- Useful for testing

**Start Update Button**
- Click to begin update process
- Only one update can run at a time

### 3. Live Progress Tracking

When an update is running, you'll see:

**Progress Bar**
- Visual percentage complete
- Updates every 2 seconds

**Current Status**
- Operation status message
- Duration counter

**Live Stats**
- Checked: Total hearings processed
- Updated: Hearings modified
- Added: New hearings created
- Errors: Count of any errors

**Recent Changes List**
- Shows last 10 operations in real-time
- Color-coded (green=added, blue=updated, red=error)

**Detailed Logs** (Expandable)
- Click "Show Detailed Logs" to view full output
- Terminal-style log viewer with auto-scroll
- Shows stdout from update process

**Cancel Button**
- Stops the running update immediately
- Safe - won't corrupt database

### 4. Changes Since Baseline

View hearings added or modified since production:

**Date Filter**
- Select baseline date (default: October 1, 2025)
- Click "Refresh" to reload table

**Change Table Columns**
- Event ID
- Title (truncated to 60 chars)
- Chamber
- Hearing Date
- Change Type (ADDED or UPDATED)
- Updated At timestamp

### 5. Update History

**Last Update Summary**
- Quick view of most recent update
- Shows updated and added counts

**View Full History Link**
- Access complete 30-day update history
- Detailed error logs and metrics
- Located at `/admin/history`

## API Endpoints

All endpoints require the Flask server to be running on localhost.

### GET `/admin/api/production-diff`

Compare local database with production baseline.

**Response**:
```json
{
  "local_count": 1338,
  "production_count": 1168,
  "difference": 170,
  "new_hearings": 1338,
  "updated_hearings": 1314,
  "baseline_date": "2025-10-01 20:06:25",
  "last_update": "2025-10-08 13:27:30"
}
```

### GET `/admin/api/recent-changes?since=YYYY-MM-DD&limit=N`

Get hearings modified since a date.

**Query Parameters**:
- `since`: Date in YYYY-MM-DD format (default: 2025-10-01)
- `limit`: Max records (default: 50)

**Response**:
```json
{
  "since_date": "2025-10-01",
  "count": 1314,
  "changes": [
    {
      "event_id": "118296",
      "title": "Hearing title...",
      "chamber": "House",
      "hearing_date": "2025-10-09",
      "change_type": "updated",
      "created_at": "2025-10-01 20:06:25",
      "updated_at": "2025-10-08 13:27:30"
    }
  ]
}
```

### POST `/admin/api/start-update`

Start a manual update task.

**Request Body**:
```json
{
  "lookback_days": 7,
  "components": ["hearings", "witnesses", "committees"],
  "chamber": "both",
  "dry_run": false
}
```

**Response**:
```json
{
  "task_id": "uuid-string",
  "status": "started",
  "command": "python3 cli.py update incremental..."
}
```

### GET `/admin/api/task-status/<task_id>`

Poll for task progress (called automatically by UI every 2 seconds).

**Response**:
```json
{
  "status": "running",
  "progress": {
    "hearings_checked": 127,
    "hearings_updated": 5,
    "hearings_added": 2,
    "errors": 0,
    "percent": 45
  },
  "duration_seconds": 23.5,
  "recent_logs": ["...", "..."],
  "error_count": 0
}
```

### GET `/admin/api/task-logs/<task_id>?since_line=N`

Get full log output for a task.

**Response**:
```json
{
  "stdout": ["line1", "line2", "..."],
  "stderr": [],
  "total_stdout_lines": 156,
  "total_stderr_lines": 0
}
```

### POST `/admin/api/cancel-update/<task_id>`

Cancel a running update task.

**Response**:
```json
{
  "status": "cancelled"
}
```

## Common Workflows

### Quick 7-Day Update

1. Open dashboard at `http://localhost:5001/admin/`
2. Verify settings (7-day lookback, both components checked)
3. Click "Start Update"
4. Monitor progress in real-time
5. Wait for completion message
6. Page auto-refreshes to show new stats

### Test Update with Dry Run

1. Set lookback to 1-3 days (faster)
2. Enable "Dry Run" checkbox
3. Click "Start Update"
4. Watch logs to see what *would* change
5. No database modifications will occur

### Verify New Data Since Production

1. Go to "Changes Since Baseline" section
2. Keep date at October 1, 2025 (production baseline)
3. Click "Refresh"
4. Review table of all 1,314 changed hearings
5. Verify new hearings vs updated hearings

### Monitor Long-Running Update

1. Start update with 30 or 90-day lookback
2. Expand "Show Detailed Logs" section
3. Watch real-time log stream
4. Monitor stats for progress
5. Use "Cancel" button if needed

### Review Update History

1. Click "View Full History" link
2. See last 30 days of updates
3. Review error counts and durations
4. Click "View Errors" for failed updates
5. Check completion status

## Troubleshooting

### "Another update task is already running"

Only one update can run at a time. Wait for the current update to complete or cancel it.

### Update Fails with API Key Error

Ensure your `.env` file contains a valid `CONGRESS_API_KEY`:
```bash
CONGRESS_API_KEY=your_api_key_here
```

### Progress Bar Stuck at 0%

✅ **FIXED** as of October 8, 2025: Incremental updates now process hearings correctly. The progress may not update smoothly during processing, but the task will complete successfully. Check the detailed logs section to see real-time progress ("Checked X/938 hearings").

### Logs Not Appearing

Check the "Show Detailed Logs" section is expanded. Logs stream in real-time during update.

### Page Shows Old Stats

The page auto-refreshes after successful updates. If it doesn't, manually refresh your browser.

### Can't Access `/admin` Route

Ensure Flask is running:
```bash
python3 -m web.app
```

Check the correct port (default: 5001):
```bash
http://localhost:5001/admin/
```

### Production Diff Shows Wrong Numbers

The production count (1,168) is hardcoded from the README. If production has been updated, edit `web/blueprints/admin.py` line 124:
```python
production_count=1168,  # Update this value
```

## Technical Notes

### Background Task Management

- Tasks run as subprocesses calling `cli.py update incremental`
- Task state stored in-memory (lost on server restart)
- Tasks auto-cleanup after 1 hour
- Only one concurrent task allowed

### JSON Progress Format

The CLI outputs structured JSON when called with `--json-progress`:
```json
{"type": "start", "timestamp": "..."}
{"type": "log", "level": "info", "message": "..."}
{"type": "complete", "success": true, "metrics": {...}}
```

### AJAX Polling

- Frontend polls `/admin/api/task-status/<id>` every 2 seconds
- Stops polling when task completes/fails/cancels
- Logs are streamed incrementally to avoid memory issues

### Security Considerations

⚠️ **NO AUTHENTICATION**

This interface has zero authentication. It should **NEVER** be deployed to production. For production use:

1. Add authentication middleware (Flask-Login, OAuth, etc.)
2. Require admin role/permissions
3. Use HTTPS
4. Add CSRF protection
5. Rate limit API endpoints

The code includes warnings:
```python
# web/blueprints/admin.py
"""
WARNING: This admin interface has NO AUTHENTICATION.
Only use on localhost for development/testing.
DO NOT deploy /admin routes to production.
"""
```

### Performance

Update speed depends on Congress.gov API rate limits and number of hearings to check.

**Expected times (October 2025, 119th Congress)**:
- 1-day lookback: ~2-3 minutes (finds ~10-30 updated hearings)
- 7-day lookback: ~3-5 minutes (finds ~100-300 updated hearings)
- 30-day lookback: ~5-10 minutes (finds ~600-800 updated hearings)
- 90-day lookback: ~10-20 minutes (finds ~900+ updated hearings)

**Note**: All lookback periods check ~938 hearings (90-day window) then filter by updateDate. This is expected behavior to catch hearings scheduled far ahead that were recently updated.

### Database Impact

- Updates use proper UPDATE statements (not INSERT OR REPLACE)
- Zero foreign key constraint errors
- Safe to run multiple times (idempotent)
- Dry run mode makes NO database changes

## Files Created

```
config/
└── task_manager.py           (NEW - 350 lines)

web/
├── blueprints/
│   └── admin.py              (MODIFIED - added 350 lines)
├── templates/
│   └── admin_dashboard.html  (NEW - 400 lines)
└── static/
    └── admin/
        ├── admin.js          (NEW - 450 lines)
        └── admin.css         (NEW - 250 lines)

cli.py                        (MODIFIED - added --json-progress flag)
web/templates/base.html       (MODIFIED - added {% block head %})
```

## Support

For issues or questions:

1. Check Flask logs: `cat /tmp/flask.log`
2. Check update_logs table: `sqlite3 database.db "SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;"`
3. Review error messages in dashboard
4. Check browser console for JavaScript errors
5. Open GitHub issue with details

## Future Enhancements

Potential improvements for future versions:

- [ ] Real-time progress updates (requires DailyUpdater callbacks)
- [ ] Schedule future updates
- [ ] Email notifications on completion
- [ ] Export update logs to CSV
- [ ] Compare two update runs side-by-side
- [ ] Rollback failed updates
- [ ] Authentication and user management
- [ ] Multi-user task queue
- [ ] WebSocket for instant updates (vs. polling)

---

**Built**: October 8, 2025
**Version**: 1.0
**Status**: Production Ready (localhost only)
