# Automated Update Scheduling

## Overview

The admin dashboard includes a scheduling interface for managing automated data ingestion tasks that run on Vercel cron jobs.

## Features

### Schedule Management
- **Create schedules**: Define recurring update tasks with custom configurations
- **Edit schedules**: Modify existing schedules including name, cron expression, lookback days, components, chamber filter, and mode
- **Enable/Disable**: Toggle schedules active/inactive without deletion
- **Delete schedules**: Remove schedules that are no longer needed
- **Deployment tracking**: Track which schedules are deployed to Vercel

### Configuration Options

Each schedule can be configured with:

- **Name**: Descriptive name for the schedule (e.g., "Daily Hearings Update")
- **Description**: Optional detailed description
- **Schedule (Cron)**: Cron expression defining when the task runs
  - Examples:
    - `0 6 * * *` - Daily at 6:00 AM UTC
    - `0 */4 * * *` - Every 4 hours
    - `0 0 * * 0` - Weekly on Sundays at midnight
- **Lookback Days**: Number of days to look back for updates (1-90)
- **Components**: Which data to update
  - Hearings (required)
  - Committees (optional)
  - Witnesses (optional)
- **Chamber**: Filter by chamber
  - Both chambers (default)
  - House only
  - Senate only
- **Mode**: Update mode
  - Incremental (default) - Only update changed records
  - Full - Complete refresh
- **Active Status**: Whether the schedule is enabled

## Using the Interface

### Accessing the Scheduler

1. Navigate to the admin dashboard at `/admin/`
2. Scroll to the "Scheduled Updates" section
3. View all configured schedules in the table

### Creating a Schedule

1. Click the "New Schedule" button
2. Fill in the schedule configuration form
3. Click "Save" to create the schedule
4. The schedule is saved but not yet deployed to Vercel

### Deploying to Vercel

After creating or modifying schedules:

1. Click the "Export Vercel Config" button
2. Review the generated `vercel.json` configuration
3. Click "Copy to Clipboard"
4. Update your `vercel.json` file in the repository root
5. Commit and push to deploy:
   ```bash
   git add vercel.json
   git commit -m "Update scheduled tasks configuration"
   git push
   ```
6. Vercel will automatically redeploy with the new cron schedules

### Vercel Configuration Structure

The export generates a complete `vercel.json` configuration with:

```json
{
  "version": 2,
  "builds": [...],
  "routes": [...],
  "crons": [
    {
      "path": "/api/cron/scheduled-update/1",
      "schedule": "0 6 * * *"
    }
  ]
}
```

Each cron entry:
- **path**: Points to the schedule by task_id
- **schedule**: Cron expression from the schedule configuration

## Database Schema

Schedules are stored in the `scheduled_tasks` table with the following fields:

- `task_id`: Unique identifier
- `name`: Schedule name
- `description`: Optional description
- `schedule_cron`: Cron expression
- `lookback_days`: Days to look back (1-90)
- `components`: JSON array of components to update
- `chamber`: Chamber filter (both/house/senate)
- `mode`: Update mode (incremental/full)
- `is_active`: Active status (boolean)
- `is_deployed`: Deployment tracking (boolean)
- `last_run_at`: Last execution timestamp
- `next_run_at`: Calculated next run time
- `created_at`: Creation timestamp
- `updated_at`: Last modification timestamp
- `created_by`: Creator identifier

## API Endpoints

The scheduling system provides REST API endpoints:

- `GET /admin/api/schedules` - List all schedules
- `GET /admin/api/schedules/<id>` - Get single schedule
- `POST /admin/api/schedules` - Create new schedule
- `PUT /admin/api/schedules/<id>` - Update schedule
- `DELETE /admin/api/schedules/<id>` - Delete schedule
- `POST /admin/api/schedules/<id>/toggle` - Toggle active status
- `GET /admin/api/schedules/export-vercel` - Export Vercel configuration

## Best Practices

1. **Start with conservative lookback days**: Begin with 7 days and adjust based on data volatility
2. **Use incremental mode**: Unless you need a full refresh, incremental mode is faster and more efficient
3. **Coordinate schedules**: Avoid scheduling multiple heavy updates at the same time
4. **Monitor execution**: Check logs after deploying new schedules to ensure they run successfully
5. **Test before deploying**: Use the manual update feature to test your configuration before scheduling
6. **Keep schedules active**: Only create schedules you intend to deploy and keep active
7. **Update deployment status**: After deploying, manually update the `is_deployed` flag for tracking

## Troubleshooting

### Schedule not running on Vercel
- Verify the schedule is marked as active
- Check that you exported and deployed the latest `vercel.json`
- Review Vercel deployment logs for errors
- Ensure the cron endpoint (`/api/cron/scheduled-update/<id>`) exists

### Updates not processing data
- Check the schedule configuration (components, chamber, lookback days)
- Review application logs for errors
- Verify API key is configured in Vercel environment variables
- Test manually using the admin dashboard's manual update feature

## Future Enhancements

Potential improvements to consider:

- Email/webhook notifications on completion or errors
- Execution history and logs per schedule
- Schedule templates for common patterns
- Estimated next run time display
- Automatic deployment to Vercel via API
- Schedule conflict detection
- Performance metrics per schedule

---

**Last Updated**: October 9, 2025
**Status**: Feature Documentation

[← Back: Admin Dashboard](admin-dashboard.md) | [Up: Documentation Hub](../README.md) | [Next: Video Integration →](video-integration.md)
