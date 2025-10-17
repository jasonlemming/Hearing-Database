# Daily Substack Ingestion - Cron Setup

## Overview

A cron job has been set up to automatically ingest new Substack articles daily.

## Schedule

**Runs daily at 6:00 AM**

## Files

### Scripts
- `brookings_ingester/scripts/daily_substack_ingest.py` - Main Python ingestion script
- `brookings_ingester/scripts/run_daily_substack.sh` - Shell wrapper that activates venv and runs Python script
- `brookings_ingester/scripts/setup_cron.sh` - Helper script to install/update the cron job

### Logs
- `logs/substack_daily.log` - Detailed ingestion logs from the Python script
- `logs/substack_cron.log` - Cron execution logs (stdout/stderr)

## How It Works

1. **Cron job triggers** at 6:00 AM daily
2. **Wrapper script** (`run_daily_substack.sh`) activates the virtual environment
3. **Python script** (`daily_substack_ingest.py`):
   - Discovers articles from Substack RSS feed (~20 most recent)
   - Fetches and parses each article
   - Stores new articles in database
   - Skips duplicates (based on URL)
   - Logs all activity

## Managing the Cron Job

### View current cron jobs
```bash
crontab -l
```

### Edit cron jobs manually
```bash
crontab -e
```

### Reinstall/update the cron job
```bash
bash brookings_ingester/scripts/setup_cron.sh
```

### Remove all cron jobs
```bash
crontab -r
```

### Test the script manually
```bash
# Full path version (works from anywhere)
bash /Users/jason/Documents/GitHub/Hearing-Database/brookings_ingester/scripts/run_daily_substack.sh

# Or from project root:
cd /Users/jason/Documents/GitHub/Hearing-Database
bash brookings_ingester/scripts/run_daily_substack.sh
```

## Cron Job Details

```
0 6 * * * /Users/jason/Documents/GitHub/Hearing-Database/brookings_ingester/scripts/run_daily_substack.sh >> /Users/jason/Documents/GitHub/Hearing-Database/logs/substack_cron.log 2>&1
```

**Schedule explained:**
- `0` - Minute (0 = on the hour)
- `6` - Hour (6 = 6 AM)
- `*` - Day of month (any)
- `*` - Month (any)
- `*` - Day of week (any)

## Monitoring

### Check recent cron execution
```bash
tail -50 logs/substack_cron.log
```

### Check detailed ingestion logs
```bash
tail -100 logs/substack_daily.log
```

### Check if cron is working
Wait for the next scheduled run (6:00 AM), then check:
```bash
# Should show recent timestamp if ran today
ls -lah logs/substack_cron.log
tail -20 logs/substack_cron.log
```

## Troubleshooting

### Cron job not running?

1. **Check if cron service is running** (macOS):
   ```bash
   sudo launchctl list | grep cron
   ```

2. **Check system logs** (macOS):
   ```bash
   log show --predicate 'process == "cron"' --last 1h
   ```

3. **Test script manually**:
   ```bash
   bash brookings_ingester/scripts/run_daily_substack.sh
   ```

4. **Check script permissions**:
   ```bash
   ls -la brookings_ingester/scripts/run_daily_substack.sh
   # Should show: -rwxr-xr-x (executable)
   ```

### Database connection issues?

- Ensure PostgreSQL is running
- Check database credentials in `brookings_ingester/config.py`
- Test database connection manually

### No new articles?

This is normal if:
- RSS feed hasn't updated since last run
- All articles in feed already exist in database (duplicates are skipped)

Check logs to confirm:
```bash
grep "Skipped (duplicates)" logs/substack_daily.log
```

## Disabling

To temporarily disable without removing:
```bash
# Edit crontab
crontab -e

# Comment out the line by adding # at the beginning:
# 0 6 * * * /Users/jason/Documents/GitHub/Hearing-Database/brookings_ingester/scripts/run_daily_substack.sh >> /Users/jason/Documents/GitHub/Hearing-Database/logs/substack_cron.log 2>&1
```

To permanently remove:
```bash
crontab -r
```

## Exit Codes

The Python script returns:
- `0` - Success (all articles processed)
- `1` - Fatal error or all articles failed
- `2` - Partial failure (some articles failed)
