# CLI Commands Reference

Complete reference for the Congressional Hearing Database unified CLI tool.

## Table of Contents

1. [Overview](#overview)
2. [Global Options](#global-options)
3. [Import Commands](#import-commands)
4. [Enhance Commands](#enhance-commands)
5. [Update Commands](#update-commands)
6. [Database Commands](#database-commands)
7. [Analysis Commands](#analysis-commands)
8. [Witness Commands](#witness-commands)
9. [Web Commands](#web-commands)
10. [Common Usage Patterns](#common-usage-patterns)

---

## Overview

The unified CLI tool (`cli.py`) consolidates all database management scripts into a single, organized command-line interface with 865 lines replacing 18+ individual scripts.

**Command Structure**:
```
python cli.py [GLOBAL_OPTIONS] <COMMAND_GROUP> <COMMAND> [OPTIONS]
```

**Example**:
```bash
python cli.py --verbose update incremental --lookback-days 7
│              │         │      │           └─ Command options
│              │         │      └─ Specific command
│              │         └─ Command group
│              └─ Global options
```

**Command Groups**:
- `import` - Import data from Congress.gov API
- `enhance` - Enhance existing data with additional details
- `update` - Update database with latest changes
- `database` - Database management operations
- `analysis` - Analysis and audit operations
- `witness` - Witness-specific operations
- `web` - Web application operations

---

## Global Options

Apply to all commands, specified before the command group.

### `--verbose, -v`

Enable verbose (DEBUG level) logging.

**Usage**:
```bash
python cli.py --verbose update incremental --lookback-days 7
```

**Output**:
- Additional diagnostic information
- API request details
- Data processing steps
- Database operations

### `--config-check`

Check configuration and exit. Tests API connectivity and database path.

**Usage**:
```bash
python cli.py --config-check
```

**Output**:
```
Checking configuration...
✓ API key configured
✓ API connectivity: OK
✓ Database path: /path/to/database.db
Configuration check passed
```

**Exit Codes**:
- `0`: Configuration valid
- `1`: Configuration error

---

## Import Commands

Import data from Congress.gov API. Base command: `python cli.py import`

### `import full`

Run full data import for a specified Congress.

**Usage**:
```bash
python cli.py import full [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number to import |
| `--validation` | Flag | False | Run in validation mode (no database writes) |
| `--phase` | Choice | all | Specific phase to run: committees, members, hearings, documents, all |
| `--resume` | Flag | False | Resume from last checkpoint |
| `--batch-size` | Integer | 50 | Batch size for processing |

**Examples**:

```bash
# Full import for 119th Congress
python cli.py import full --congress 119

# Import only hearings
python cli.py import full --phase hearings --congress 119

# Validation mode (test without writing to database)
python cli.py import full --validation --congress 119

# Resume interrupted import
python cli.py import full --resume --congress 119

# Custom batch size for slower systems
python cli.py import full --batch-size 25 --congress 119
```

**Phases Explained**:
- `committees` - Import committees and subcommittees
- `members` - Import congressional members
- `hearings` - Import hearing metadata (titles, dates, status)
- `documents` - Import transcripts and witness documents
- `all` - Run all phases in sequence

**Duration**:
- **Full import**: 20-30 minutes for ~1,200 hearings
- **Hearings only**: 10-15 minutes
- **Documents only**: 15-20 minutes

**API Requests**:
- **Full import**: ~3,000-5,000 requests
- **Hearings only**: ~1,200 requests
- **Rate Limit**: 5,000 requests/hour

### `import hearings`

Import hearings for specific criteria (faster than full import).

**Usage**:
```bash
python cli.py import hearings [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number |
| `--chamber` | Choice | both | Chamber: house, senate, both |
| `--committee` | String | None | Specific committee system code |

**Examples**:

```bash
# Import all hearings for 119th Congress
python cli.py import hearings --congress 119

# House hearings only
python cli.py import hearings --congress 119 --chamber house

# Specific committee (House Oversight)
python cli.py import hearings --congress 119 --committee hsgo00
```

---

## Enhance Commands

Enhance existing data with additional details. Base command: `python cli.py enhance`

### `enhance hearings`

Enhance hearing data (titles, dates, committees).

**Usage**:
```bash
python cli.py enhance hearings [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--target` | Choice | all | What to enhance: titles, dates, committees, all |
| `--limit` | Integer | 200 | Maximum number of records to process |
| `--chamber` | Choice | both | Chamber filter: both, house, senate |

**Examples**:

```bash
# Enhance all missing data (up to 200 hearings)
python cli.py enhance hearings --target all --limit 200

# Fix only missing titles
python cli.py enhance hearings --target titles --limit 100

# Fix dates for House hearings only
python cli.py enhance hearings --target dates --chamber house --limit 50

# Add committee assignments to unassigned hearings
python cli.py enhance hearings --target committees --limit 500
```

**What Gets Enhanced**:
- **titles**: Fetches missing or generic titles ("Event #12345")
- **dates**: Adds missing hearing dates
- **committees**: Infers committee assignments for unassigned hearings
- **all**: Runs all enhancement types

**Duration**: ~1-2 minutes per 100 hearings

### `enhance titles`

Fix missing titles specifically.

**Usage**:
```bash
python cli.py enhance titles [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--limit` | Integer | 100 | Maximum number of missing titles to fix |

**Examples**:

```bash
# Fix up to 100 missing titles
python cli.py enhance titles --limit 100

# Fix all missing titles
python cli.py enhance titles --limit 10000
```

**Targets**: Hearings with `title IS NULL`, `title = ''`, or `title LIKE 'Event #%'`

---

## Update Commands

Update database with latest changes. Base command: `python cli.py update`

### `update incremental`

Run incremental daily update (equivalent to `daily_update.py`).

**Usage**:
```bash
python cli.py update incremental [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number to update |
| `--lookback-days` | Integer | 7 | Days to look back for changes |
| `--mode` | Choice | incremental | Update mode: incremental, full |
| `--components` `-c` | Multiple | hearings,witnesses,committees | Components to update (can specify multiple) |
| `--dry-run` | Flag | False | Preview changes without modifying database |
| `--quiet` | Flag | False | Reduce output for cron jobs |
| `--json-progress` | Flag | False | Output progress as JSON for admin dashboard |

**Examples**:

```bash
# Standard 7-day update (recommended for daily automation)
python cli.py update incremental --lookback-days 7

# 30-day comprehensive sync
python cli.py update incremental --lookback-days 30

# Update only hearings (faster, excludes witnesses and committees)
python cli.py update incremental --components hearings --lookback-days 7

# Multiple components
python cli.py update incremental --components hearings --components videos --lookback-days 7

# Dry-run to preview changes
python cli.py update incremental --lookback-days 7 --dry-run

# Quiet mode for cron jobs
python cli.py update incremental --lookback-days 7 --quiet

# JSON progress for admin dashboard integration
python cli.py update incremental --lookback-days 7 --json-progress
```

**Components Explained**:
- `hearings` - Updates hearing metadata (titles, dates, status, videos)
- `witnesses` - Updates witness information for recent hearings
- `committees` - Updates committee rosters and assignments

**Recommended Lookback**:
- **Daily automation**: 7 days
- **Weekly manual**: 14-30 days
- **Monthly comprehensive**: 90 days

**Duration**:
- **7-day**: 2-5 minutes
- **30-day**: 10-15 minutes
- **90-day**: 30-45 minutes

### `update committees`

Refresh committee data.

**Usage**:
```bash
python cli.py update committees [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number |
| `--chamber` | Choice | all | Chamber: house, senate, joint, all |

**Examples**:

```bash
# Refresh all committees
python cli.py update committees --congress 119

# House committees only
python cli.py update committees --congress 119 --chamber house

# Senate committees only
python cli.py update committees --congress 119 --chamber senate
```

**Frequency**: Weekly recommended

### `update hearings`

Update hearing data (titles, dates, status, optionally videos).

**Usage**:
```bash
python cli.py update hearings [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number |
| `--chamber` | Choice | all | Chamber: house, senate, all |
| `--lookback-days` | Integer | 30 | Days to look back |
| `--include-videos` | Flag | False | Fetch and update video URLs |

**Examples**:

```bash
# Update hearings from last 30 days
python cli.py update hearings --congress 119 --lookback-days 30

# Update with video URLs
python cli.py update hearings --congress 119 --lookback-days 30 --include-videos

# House hearings only
python cli.py update hearings --congress 119 --chamber house --lookback-days 14
```

### `update videos`

Update video URLs and YouTube video IDs for hearings.

**Usage**:
```bash
python cli.py update videos [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number |
| `--limit` | Integer | 100 | Maximum number of hearings to update |
| `--force` | Flag | False | Update all hearings, even those with existing videos |

**Examples**:

```bash
# Update videos for hearings without them (up to 100)
python cli.py update videos --congress 119 --limit 100

# Force re-check all videos
python cli.py update videos --congress 119 --limit 1000 --force

# Update more hearings
python cli.py update videos --congress 119 --limit 500
```

**Notes**:
- By default, only updates hearings without `video_url`
- Use `--force` to re-fetch all videos (e.g., after API changes)
- Ordered by `hearing_date DESC` (recent first)

### `update witnesses`

Update witness information for recent hearings.

**Usage**:
```bash
python cli.py update witnesses [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number |
| `--lookback-days` | Integer | 30 | Update witnesses for hearings in last N days |

**Examples**:

```bash
# Update witnesses for hearings in last 30 days
python cli.py update witnesses --congress 119 --lookback-days 30

# Update witnesses for last 7 days only
python cli.py update witnesses --congress 119 --lookback-days 7
```

---

## Database Commands

Database management operations. Base command: `python cli.py database`

### `database init`

Initialize database schema (equivalent to `init_database.py`).

**Usage**:
```bash
python cli.py database init
```

**What It Does**:
- Creates all 20 tables
- Sets up indexes
- Creates foreign key constraints
- Initializes triggers (if any)

**Output**:
```
Database initialization completed
Schema loaded from: database/schema.sql
Tables created: 20
```

**⚠️ Warning**: This will drop existing tables if they exist. Use with caution.

**Safe Alternative**:
```bash
# Backup first
cp database.db database.db.backup

# Then initialize
python cli.py database init
```

### `database status`

Show database status and record counts.

**Usage**:
```bash
python cli.py database status
```

**Output**:
```
Database Status:
==================================================
hearings            :      1,168
committees          :        213
members             :        535
witnesses           :      2,341
committee_memberships:       847
hearing_committees  :      1,654
hearing_bills       :        234
witness_appearances :      3,125
bills               :        189
```

**Use Cases**:
- Quick health check
- Verify import completed
- Monitor data growth
- Debugging relationship counts

### `database clean`

Clean obsolete committees and data.

**Usage**:
```bash
python cli.py database clean
```

**What It Removes**:
- Committees marked as obsolete (e.g., "Historical")
- Archive committees
- Committees with "HIST" in system code

**Output**:
```
Cleaned 3 obsolete committee records
```

**Safety**: Does not remove committees with hearing relationships.

---

## Analysis Commands

Analysis and audit operations. Base command: `python cli.py analysis`

### `analysis audit`

Comprehensive database audit (equivalent to `comprehensive_database_audit.py`).

**Usage**:
```bash
python cli.py analysis audit
```

**What It Checks**:
- Data completeness (titles, dates, committees)
- Relationship integrity
- Document availability
- Video coverage
- Witness assignments
- Data quality metrics

**Output**:
```
=== Congressional Hearing Database Audit ===
Generated: 2025-10-09 10:30:15

DATABASE STATISTICS
-------------------
Total Hearings: 1,168
  - House: 687 (58.8%)
  - Senate: 481 (41.2%)

DATA COMPLETENESS
-----------------
Hearings with titles: 1,145 (98.0%)
Hearings with dates: 1,089 (93.2%)
Hearings with videos: 389 (33.3%)
Hearings with committees: 1,167 (99.9%)

WARNINGS
--------
- 23 hearings missing titles
- 79 hearings missing dates
- 1 hearing without committee assignment
```

**Duration**: ~30 seconds

**Output File**: Results saved to console (redirect to file if needed)

### `analysis recent`

Analyze recent hearing activity.

**Usage**:
```bash
python cli.py analysis recent [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--days` | Integer | 7 | Number of days to analyze |

**Examples**:

```bash
# Last 7 days
python cli.py analysis recent --days 7

# Last 30 days
python cli.py analysis recent --days 30
```

**Output**:
```
Recent Activity (7 days):
========================================
Total hearings: 23
House hearings: 14
Senate hearings: 9
With titles: 22
```

---

## Witness Commands

Witness-specific operations. Base command: `python cli.py witness`

### `witness import-all`

Import witnesses for all hearings.

**Usage**:
```bash
python cli.py witness import-all [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--congress` | Integer | 119 | Congress number to import witnesses for |
| `--limit` | Integer | None | Maximum number of hearings to process |
| `--batch-size` | Integer | 10 | Number of hearings to process per batch |

**Examples**:

```bash
# Import all witnesses for 119th Congress
python cli.py witness import-all --congress 119

# Import first 100 hearings
python cli.py witness import-all --congress 119 --limit 100

# Smaller batch size for slower systems
python cli.py witness import-all --congress 119 --batch-size 5
```

**Duration**: ~30-45 minutes for 1,200 hearings

### `witness test`

Test witness API connectivity.

**Usage**:
```bash
python cli.py witness test
```

**What It Does**:
- Tests API connection
- Fetches sample witness data
- Validates parsing logic
- Reports any errors

**Output**:
```
Testing witness API connectivity...
✓ API connection successful
✓ Sample data fetched
✓ Parsing successful
Test completed
```

---

## Web Commands

Web application operations. Base command: `python cli.py web`

### `web serve`

Start the web application.

**Usage**:
```bash
python cli.py web serve [OPTIONS]
```

**Options**:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | String | 127.0.0.1 | Host to bind to |
| `--port` | Integer | 5000 | Port to bind to |
| `--debug` | Flag | False | Run in debug mode |

**Examples**:

```bash
# Start on default port (5000)
python cli.py web serve

# Start on custom port
python cli.py web serve --port 5001

# Start on all interfaces (accessible from network)
python cli.py web serve --host 0.0.0.0 --port 5001

# Debug mode (auto-reload on code changes)
python cli.py web serve --debug --port 5001

# Production-like (no debug)
python cli.py web serve --host 0.0.0.0 --port 8080
```

**Debug Mode Features**:
- Auto-reloads on code changes
- Detailed error pages
- Interactive debugger in browser

**⚠️ Warning**: Never use `--debug` in production.

**Stopping the Server**:
Press `Ctrl+C` in the terminal.

---

## Common Usage Patterns

### Daily Maintenance

```bash
#!/bin/bash
# daily_maintenance.sh - Run daily at 6 AM

# 1. Run incremental update (7-day lookback)
python cli.py update incremental --lookback-days 7 --quiet

# 2. Check database status
python cli.py database status

# 3. Analyze recent activity
python cli.py analysis recent --days 7
```

### Weekly Maintenance

```bash
#!/bin/bash
# weekly_maintenance.sh - Run weekly on Sunday

# 1. Refresh committee data
python cli.py update committees --congress 119

# 2. Comprehensive update (30-day lookback)
python cli.py update incremental --lookback-days 30

# 3. Run audit
python cli.py analysis audit > audit_$(date +%Y%m%d).txt

# 4. Clean obsolete data
python cli.py database clean
```

### Monthly Maintenance

```bash
#!/bin/bash
# monthly_maintenance.sh - Run monthly on 1st

# 1. Comprehensive 90-day sync
python cli.py update incremental --lookback-days 90

# 2. Update all videos
python cli.py update videos --limit 1500 --force

# 3. Run full audit
python cli.py analysis audit > audit_monthly_$(date +%Y%m%d).txt

# 4. Database maintenance
sqlite3 database.db "VACUUM; ANALYZE;"

# 5. Backup
cp database.db backups/database_$(date +%Y%m%d).db
```

### Initial Setup

```bash
# 1. Initialize database
python cli.py database init

# 2. Full import for 119th Congress
python cli.py import full --congress 119

# 3. Import witnesses
python cli.py witness import-all --congress 119

# 4. Enhance any missing data
python cli.py enhance hearings --target all --limit 500

# 5. Verify
python cli.py database status
python cli.py analysis audit
```

### Troubleshooting Workflow

```bash
# 1. Check configuration
python cli.py --config-check

# 2. Database status
python cli.py database status

# 3. Recent activity
python cli.py analysis recent --days 7

# 4. Run audit
python cli.py analysis audit

# 5. Check update history
sqlite3 database.db "SELECT * FROM update_logs ORDER BY start_time DESC LIMIT 5;"

# 6. Check errors
sqlite3 database.db "SELECT * FROM import_errors WHERE is_resolved = 0 LIMIT 10;"
```

### Development Workflow

```bash
# 1. Test with validation mode (no database writes)
python cli.py import full --validation --congress 119

# 2. Dry-run update to preview changes
python cli.py update incremental --lookback-days 1 --dry-run

# 3. Run with verbose logging
python cli.py --verbose update incremental --lookback-days 1

# 4. Start dev server with debug mode
python cli.py web serve --debug --port 5001
```

### Automation with Cron

```cron
# /etc/crontab or crontab -e

# Daily update at 6 AM UTC
0 6 * * * cd /path/to/Hearing-Database && /path/to/venv/bin/python cli.py update incremental --lookback-days 7 --quiet >> logs/cron.log 2>&1

# Weekly committee refresh (Sunday 1 AM)
0 1 * * 0 cd /path/to/Hearing-Database && /path/to/venv/bin/python cli.py update committees --congress 119 >> logs/cron.log 2>&1

# Monthly comprehensive sync (1st of month, 2 AM)
0 2 1 * * cd /path/to/Hearing-Database && /path/to/venv/bin/python cli.py update incremental --lookback-days 90 >> logs/cron.log 2>&1

# Database status check (daily at 7 AM)
0 7 * * * cd /path/to/Hearing-Database && /path/to/venv/bin/python cli.py database status >> logs/status.log 2>&1
```

---

## Environment Variables

Recognized environment variables (alternatively set in `.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `CONGRESS_API_KEY` | Congress.gov API key | None (required) |
| `DATABASE_PATH` | Path to SQLite database | database.db |
| `TARGET_CONGRESS` | Default Congress number | 119 |
| `LOG_LEVEL` | Logging level | INFO |
| `LOG_FILE` | Log file path | logs/import.log |
| `BATCH_SIZE` | Default batch size | 50 |
| `UPDATE_WINDOW_DAYS` | Default lookback days | 30 |
| `RATE_LIMIT` | API requests per hour | 5000 |

**Setting Environment Variables**:

```bash
# Temporary (current session)
export CONGRESS_API_KEY=your_key_here
python cli.py update incremental --lookback-days 7

# Permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export CONGRESS_API_KEY=your_key_here' >> ~/.bashrc
source ~/.bashrc

# Via .env file (recommended)
echo "CONGRESS_API_KEY=your_key_here" >> .env
python cli.py update incremental --lookback-days 7
```

---

## Exit Codes

All commands use standard Unix exit codes:

| Code | Meaning | Example |
|------|---------|---------|
| `0` | Success | Update completed successfully |
| `1` | General error | API error, parse error, database error |
| `2` | Misuse of command | Invalid option, missing argument |

**Checking Exit Code**:

```bash
# Run command
python cli.py update incremental --lookback-days 7

# Check exit code
echo $?  # 0 = success, 1 = error

# Conditional execution
python cli.py update incremental --lookback-days 7 && echo "Success" || echo "Failed"
```

---

## Additional Resources

### Related Documentation

- **[Development Guide](../guides/developer/DEVELOPMENT.md)** - Development patterns and workflows
- **[Update Protocols](../guides/operations/UPDATE_PROTOCOLS.md)** - Update strategies
- **[Monitoring Guide](../guides/operations/MONITORING.md)** - Monitoring and alerts

### External Resources

- **[Click Documentation](https://click.palletsprojects.com/)** - CLI framework reference
- **[Congress.gov API](https://api.congress.gov/)** - API documentation
- **[Cron Syntax](https://crontab.guru/)** - Cron expression builder

---

**Last Updated**: October 9, 2025
**CLI Version**: 865 lines
**Command Groups**: 7
**Total Commands**: 23

[← Back: Development Guide](../guides/developer/DEVELOPMENT.md) | [Up: Documentation Hub](../README.md) | [Next: API Reference →](API_REFERENCE.md)
