# Daily Update Automation System

The Congressional Hearing Database now includes an automated daily update system that keeps the database synchronized with the latest data from the Congress.gov API.

## Overview

The daily update system implements **incremental updates** to efficiently synchronize new and modified hearings without requiring full data re-imports. This ensures the database stays current with minimal API usage and processing time.

## Features

- ✅ **Incremental Updates**: Only processes hearings modified in the last N days
- ✅ **Change Detection**: Compares API data with database records to identify updates
- ✅ **Comprehensive Logging**: Detailed logs of all update operations and metrics
- ✅ **Error Handling**: Graceful error handling with retry mechanisms
- ✅ **Rate Limiting**: Respects Congress.gov API rate limits (5,000 requests/hour)
- ✅ **Monitoring Dashboard**: Web interface to view update history and status
- ✅ **Cron Integration**: Easy setup for automated scheduling

## Quick Start

### 1. Manual Update

Run a manual update to test the system:

```bash
cd /path/to/Congressional-meetings-api-claude-experiment
source venv/bin/activate
python scripts/daily_update.py --congress 119 --lookback-days 7
```

### 2. Schedule Automated Updates

Copy the cron configuration:

```bash
# Edit your crontab
crontab -e

# Add this line for daily updates at 2 AM:
0 2 * * * cd /path/to/Congressional-meetings-api-claude-experiment && source venv/bin/activate && python scripts/daily_update.py --quiet >> logs/cron.log 2>&1
```

See `config/cron.conf` for more scheduling options.

### 3. Monitor Updates

View update history and status:
- Web interface: http://localhost:3000/admin/updates
- API endpoint: http://localhost:3000/api/update-status
- Log files: `logs/daily_update_YYYYMMDD.log`

## How It Works

### Update Process

1. **Fetch Recent Data**: Retrieves hearings modified in the last N days from Congress.gov API
2. **Compare Records**: Compares API data with existing database records
3. **Identify Changes**: Determines which hearings need updates or are new
4. **Apply Updates**: Updates database records and adds new hearings
5. **Update Related Data**: Synchronizes committee associations and witnesses
6. **Record Metrics**: Logs update statistics and performance metrics

### Change Detection

The system compares these key fields to detect changes:
- Hearing title
- Date and time
- Status
- Location
- Committee associations

### Incremental Processing

- **Default Lookback**: 7 days (configurable with `--lookback-days`)
- **Weekly Full Check**: Recommended 30-day lookback on Sundays
- **Monthly Comprehensive**: 90-day lookback on first of month

## Configuration

### Environment Variables

Ensure these are set in your environment:

```bash
CONGRESS_API_KEY=your_api_key_here
RATE_LIMIT_PER_HOUR=5000
UPDATE_SCHEDULE_HOUR=2
UPDATE_WINDOW_DAYS=7
```

### Command Line Options

```bash
python scripts/daily_update.py --help

Options:
  --congress INTEGER         Congress number to update (default: 119)
  --lookback-days INTEGER    Days to look back for changes (default: 7)
  --quiet                    Reduce output for cron jobs
```

## Monitoring and Logs

### Update Metrics

Each update records comprehensive metrics:
- Number of hearings checked
- Number of hearings updated
- Number of new hearings added
- Committee and witness updates
- API requests made
- Errors encountered
- Processing duration

### Log Files

- **Daily logs**: `logs/daily_update_YYYYMMDD.log`
- **Cron logs**: `logs/cron.log`
- **Application logs**: Database update_logs table

### Web Dashboard

Access the monitoring dashboard at `/admin/updates` to view:
- Update status summary
- Recent update history (30 days)
- Success/failure statistics
- Error details and troubleshooting
- Manual update instructions

## Recommended Schedules

### Basic Setup (Daily)
```bash
# Daily at 2 AM with 7-day lookback
0 2 * * * cd /path/to/project && source venv/bin/activate && python scripts/daily_update.py --quiet >> logs/cron.log 2>&1
```

### Comprehensive Setup (Daily + Weekly + Monthly)
```bash
# Daily incremental updates
0 2 * * * cd /path/to/project && source venv/bin/activate && python scripts/daily_update.py --lookback-days 7 --quiet >> logs/cron.log 2>&1

# Weekly comprehensive check (Sundays at 1 AM)
0 1 * * 0 cd /path/to/project && source venv/bin/activate && python scripts/daily_update.py --lookback-days 30 >> logs/weekly.log 2>&1

# Monthly full check (1st of month at midnight)
0 0 1 * * cd /path/to/project && source venv/bin/activate && python scripts/daily_update.py --lookback-days 90 >> logs/monthly.log 2>&1
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure virtual environment is activated and all dependencies installed
2. **API Key Missing**: Set CONGRESS_API_KEY environment variable
3. **Database Locked**: Check for concurrent processes accessing the database
4. **Rate Limiting**: Reduce batch size or increase lookback period

### Debugging

Test the update system:
```bash
# Check configuration
python scripts/daily_update.py --help

# Run with verbose logging
python scripts/daily_update.py --congress 119 --lookback-days 1

# Check update history
curl http://localhost:3000/api/update-status
```

### Log Analysis

View recent update activity:
```bash
# Today's update log
tail -f logs/daily_update_$(date +%Y%m%d).log

# Cron job output
tail -f logs/cron.log

# Database update history
sqlite3 data/congressional_hearings.db "SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;"
```

## API Integration

The daily update system integrates with existing components:

- **API Client**: Uses `api.client.CongressGovAPIClient` with rate limiting
- **Fetchers**: Leverages `HearingFetcher`, `CommitteeFetcher`, `WitnessFetcher`
- **Database**: Works with existing `DatabaseManager` and schema
- **Parsers**: Utilizes existing data validation and transformation logic

## Performance Considerations

### API Usage

- **Rate Limits**: Respects 5,000 requests/hour limit
- **Incremental Updates**: Reduces API calls compared to full imports
- **Batch Processing**: Configurable batch sizes for memory efficiency

### Database Impact

- **Transaction Management**: Uses database transactions for consistency
- **Minimal Locking**: SQLite operations are optimized for concurrent access
- **Index Usage**: Leverages existing database indexes for performance

### Scalability

- **Horizontal Scaling**: Multiple congress numbers can be updated independently
- **Parallel Processing**: Future enhancement for concurrent committee/witness updates
- **Caching**: Future enhancement for API response caching

## Future Enhancements

- **Real-time Updates**: WebSocket integration for live status updates
- **Email Notifications**: Alert system for failed updates or significant changes
- **Advanced Scheduling**: APScheduler integration for more complex scheduling
- **Data Validation**: Enhanced change detection and data quality checks
- **Performance Optimization**: Parallel processing and caching improvements

## Support

For issues with the daily update system:

1. Check the monitoring dashboard: `/admin/updates`
2. Review log files in the `logs/` directory
3. Test manual updates to isolate issues
4. Verify environment configuration and API access

The daily update system ensures your Congressional Hearing Database stays current with minimal maintenance overhead.