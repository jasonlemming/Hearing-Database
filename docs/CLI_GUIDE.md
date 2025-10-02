# Congressional Hearing Database - Unified CLI Guide

The Congressional Hearing Database now features a unified command-line interface (`cli.py`) that consolidates all database management operations into a single, organized tool. This replaces the previous collection of 18+ individual scripts with a structured CLI.

## Installation and Setup

```bash
cd /path/to/Congressional-meetings-api-claude-experiment
source venv/bin/activate
python cli.py --config-check  # Verify configuration
```

## Command Structure

The CLI is organized into logical command groups:

```bash
python cli.py COMMAND SUBCOMMAND [OPTIONS]
```

### Available Command Groups

- **`import`** - Import data from Congress.gov API
- **`enhance`** - Enhance existing data with additional details
- **`update`** - Update database with latest changes
- **`database`** - Database management operations
- **`analysis`** - Analysis and audit operations
- **`witness`** - Witness-specific operations
- **`web`** - Web application operations

## Command Reference

### Import Commands

Replace the previous `run_import.py` and related scripts:

```bash
# Full import (replaces run_import.py)
python cli.py import full --congress 119 --phase all

# Import specific phase
python cli.py import full --congress 119 --phase hearings --batch-size 50

# Import hearings for specific criteria
python cli.py import hearings --congress 119 --chamber house --committee HSAG
```

**Options:**
- `--congress NUMBER`: Congress number to import (default: 119)
- `--validation`: Run in validation mode (no database writes)
- `--phase`: Specific phase (committees, members, hearings, documents, all)
- `--resume`: Resume from last checkpoint
- `--batch-size`: Batch size for processing
- `--chamber`: house, senate, or both
- `--committee`: Specific committee system name

### Enhancement Commands

Replace `enhance_hearings.py`, `enhance_missing_titles.py`, and related scripts:

```bash
# Enhance hearings with missing data (replaces enhance_hearings.py)
python cli.py enhance hearings --target all --limit 200

# Fix missing titles specifically (replaces enhance_missing_titles.py)
python cli.py enhance titles --limit 100

# Enhance specific target
python cli.py enhance hearings --target titles --chamber senate
```

**Options:**
- `--target`: What to enhance (titles, dates, committees, all)
- `--limit`: Maximum number of records to process
- `--chamber`: house, senate, or both

### Update Commands

Replace `daily_update.py`, `refresh_committees.py`:

```bash
# Daily incremental update (replaces daily_update.py)
python cli.py update incremental --lookback-days 7

# Refresh committee data (replaces refresh_committees.py)
python cli.py update committees --congress 119 --chamber all
```

**Options:**
- `--congress`: Congress number to update
- `--lookback-days`: Days to look back for changes
- `--quiet`: Reduce output for cron jobs
- `--chamber`: house, senate, joint, or all

### Database Commands

Replace `init_database.py`, `clean_committees.py`:

```bash
# Initialize database (replaces init_database.py)
python cli.py database init

# Clean obsolete data (replaces clean_committees.py)
python cli.py database clean

# Show database status
python cli.py database status
```

### Witness Commands

Replace `import_witnesses.py`, `test_witness_api.py`:

```bash
# Import witnesses (replaces import_witnesses.py)
python cli.py witness import-all --congress 119 --limit 500 --batch-size 10

# Test witness API (replaces test_witness_api.py)
python cli.py witness test
```

**Options:**
- `--congress`: Congress number for witness import
- `--limit`: Maximum number of hearings to process
- `--batch-size`: Number of hearings per batch

### Analysis Commands

Replace `comprehensive_database_audit.py`:

```bash
# Comprehensive audit (replaces comprehensive_database_audit.py)
python cli.py analysis audit

# Recent activity analysis
python cli.py analysis recent --days 7
```

**Options:**
- `--days`: Number of days to analyze for recent activity

### Web Commands

Replace manual web application startup:

```bash
# Start web application
python cli.py web serve --host 0.0.0.0 --port 5000 --debug
```

**Options:**
- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 5000)
- `--debug`: Run in debug mode

## Common Usage Patterns

### Daily Operations

```bash
# Check database status
python cli.py database status

# Run daily update
python cli.py update incremental --quiet

# Start web server
python cli.py web serve
```

### Initial Setup

```bash
# Initialize database
python cli.py database init

# Import all data for Congress 119
python cli.py import full --congress 119

# Import witnesses
python cli.py witness import-all --congress 119
```

### Data Enhancement

```bash
# Fix missing titles
python cli.py enhance titles --limit 200

# Enhance all hearing data
python cli.py enhance hearings --target all --limit 500

# Refresh committee information
python cli.py update committees
```

### Maintenance and Analysis

```bash
# Run comprehensive audit
python cli.py analysis audit

# Clean obsolete data
python cli.py database clean

# Check recent activity
python cli.py analysis recent --days 30
```

## Global Options

All commands support these global options:

- `-v, --verbose`: Enable verbose logging
- `--config-check`: Check configuration and exit

```bash
# Enable verbose logging for any command
python cli.py -v enhance hearings --limit 10

# Check configuration
python cli.py --config-check
```

## Migration from Individual Scripts

The unified CLI replaces these scripts:

| Old Script | New Command |
|------------|-------------|
| `run_import.py` | `python cli.py import full` |
| `enhance_hearings.py` | `python cli.py enhance hearings` |
| `enhance_missing_titles.py` | `python cli.py enhance titles` |
| `daily_update.py` | `python cli.py update incremental` |
| `refresh_committees.py` | `python cli.py update committees` |
| `import_witnesses.py` | `python cli.py witness import-all` |
| `test_witness_api.py` | `python cli.py witness test` |
| `init_database.py` | `python cli.py database init` |
| `clean_committees.py` | `python cli.py database clean` |
| `comprehensive_database_audit.py` | `python cli.py analysis audit` |
| Manual web startup | `python cli.py web serve` |

## Cron Integration

Update your cron jobs to use the unified CLI:

```bash
# Old cron job
0 2 * * * cd /path/to/project && python scripts/daily_update.py --quiet

# New cron job
0 2 * * * cd /path/to/project && python cli.py update incremental --quiet
```

## Error Handling and Logging

The CLI includes comprehensive error handling and logging:

- All commands use the standard logging configuration
- Use `--verbose` for detailed debugging information
- Check logs in the `logs/` directory for detailed output
- Use `--config-check` to verify setup before running operations

## Benefits of the Unified CLI

1. **Reduced Script Proliferation**: Single entry point instead of 18+ scripts
2. **Consistent Interface**: Standardized options and behavior across operations
3. **Better Organization**: Logical grouping of related functionality
4. **Improved Documentation**: Comprehensive help system with `--help`
5. **Easier Maintenance**: Centralized command handling and error management
6. **Enhanced Discoverability**: All operations visible through `python cli.py --help`

## Future Enhancements

The unified CLI provides a foundation for:

- Tab completion support
- Configuration file management
- Interactive mode for complex operations
- Batch operation scripts
- Integration with external monitoring tools

For issues or feature requests, refer to the project documentation or use the analysis commands to troubleshoot database state.