# Congressional Committee Hearing Database

A comprehensive system for importing, storing, and querying congressional committee hearings data from the Congress.gov API. This project creates a searchable database of hearings, witnesses, documents, and their relationships for research purposes.

## Features

- **Complete Data Import**: Fetch committees, members, hearings, bills, witnesses, and documents
- **Rate-Limited API Client**: Respects Congress.gov API limits (5,000 requests/hour)
- **Incremental Updates**: Daily sync to capture new and changed data
- **Data Validation**: Configurable strict/lenient parsing with error handling
- **Resumable Imports**: Checkpoint system allows resuming interrupted imports
- **Rich Relationships**: Links between hearings, committees, bills, witnesses, and documents

## Project Structure

```
Congressional-meetings-api-claude-experiment/
├── api/                    # API client and rate limiting
├── config/                 # Configuration and logging
├── database/              # Database schema and operations
├── fetchers/              # API data fetchers
├── parsers/               # Data validation and parsing
├── importers/             # Import orchestration
├── scripts/               # CLI scripts
├── data/                  # Database file (created on init)
└── logs/                  # Log files (created on run)
```

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your Congress.gov API key
   ```

3. **Initialize Database**
   ```bash
   python cli.py database init
   ```

4. **Run Import**
   ```bash
   # Validation run first (recommended)
   python cli.py import full --validation --congress 119

   # Full import
   python cli.py import full --congress 119
   ```

## Unified CLI

The project includes a comprehensive unified CLI (`cli.py`) that consolidates all database operations:

```bash
# Check database status
python cli.py database status

# Import data
python cli.py import full --congress 119

# Update with latest changes
python cli.py update incremental --lookback-days 7

# Enhance existing data
python cli.py enhance hearings --target titles

# Import witnesses
python cli.py witness import-all --congress 119

# Start web interface
python cli.py web serve
```

See [docs/CLI_GUIDE.md](docs/CLI_GUIDE.md) for comprehensive CLI documentation.

## Modular Web Architecture

The web application uses a modular Flask blueprint architecture for improved maintainability:

- **Main App**: 91 lines (down from 841 lines - 89% reduction)
- **Blueprints**: 6 organized modules (committees, hearings, members/witnesses/search, API, admin)
- **Benefits**: Better organization, parallel development, easier testing and maintenance

See [docs/WEB_ARCHITECTURE.md](docs/WEB_ARCHITECTURE.md) for detailed architecture documentation.

## Configuration

Key environment variables in `.env`:

- `CONGRESS_API_KEY`: Your Congress.gov API key (required)
- `TARGET_CONGRESS`: Congress number to import (default: 119)
- `DATABASE_PATH`: SQLite database file path
- `BATCH_SIZE`: Import batch size (default: 50)
- `VALIDATION_MODE`: Enable strict validation (default: False)

## Database Schema

The database includes 17 tables covering:

- **Committees**: All congressional committees and subcommittees
- **Members**: Representatives and Senators with leadership positions
- **Hearings**: Committee meetings, hearings, and markups
- **Bills**: Legislation referenced in hearings
- **Witnesses**: Individuals testifying at hearings
- **Documents**: Transcripts, witness statements, supporting materials
- **Relationships**: Links between all entities

Key relationships:
- Committees ↔ Members (committee memberships)
- Committees ↔ Hearings (hearing committees)
- Hearings ↔ Bills (hearing bills)
- Hearings ↔ Witnesses (witness appearances)
- Hearings ↔ Documents (transcripts, materials)

## Usage Examples

### Import Commands

```bash
# Check configuration
python scripts/run_import.py --check-config

# Import specific phase
python scripts/run_import.py --phase committees --congress 119
python scripts/run_import.py --phase members --congress 119
python scripts/run_import.py --phase hearings --congress 119

# Resume interrupted import
python scripts/run_import.py --resume

# Custom batch size
python scripts/run_import.py --batch-size 25 --congress 119
```

### Database Queries

```sql
-- All hearings by committee
SELECT h.* FROM hearings h
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE c.system_code = 'hsif00'
ORDER BY h.hearing_date DESC;

-- All testimony by witness
SELECT w.full_name, h.title, h.hearing_date, c.name
FROM witnesses w
JOIN witness_appearances wa ON w.witness_id = wa.witness_id
JOIN hearings h ON wa.hearing_id = h.hearing_id
JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
JOIN committees c ON hc.committee_id = c.committee_id
WHERE w.full_name LIKE '%Smith%'
ORDER BY h.hearing_date DESC;

-- Committee roster
SELECT m.full_name, m.party, m.state, cm.role
FROM committees c
JOIN committee_memberships cm ON c.committee_id = cm.committee_id
JOIN members m ON cm.member_id = m.member_id
WHERE c.system_code = 'ssfi00' AND cm.is_active = 1
ORDER BY cm.role, m.last_name;
```

## API Integration

The system integrates with Congress.gov API v3:

- **Base URL**: https://api.congress.gov/v3
- **Authentication**: API key required
- **Rate Limits**: 5,000 requests/hour (automatically managed)
- **Response Format**: JSON

Key endpoints used:
- `/committee/{congress}/{chamber}` - Committee listings
- `/member/congress/{congress}` - Member listings
- `/committee-meeting/{congress}/{chamber}` - Hearing listings
- `/bill/{congress}/{type}/{number}` - Bill details
- `/hearing/{congress}/{chamber}/{jacket}` - Transcript details

## Data Validation

The system supports two validation modes:

**Strict Mode** (`VALIDATION_MODE=True`):
- Critical field failures halt processing
- Ensures data quality at cost of completeness

**Lenient Mode** (`VALIDATION_MODE=False`):
- Logs errors, uses defaults, continues processing
- Maximizes data capture with quality warnings

## Error Handling

- **Automatic Retries**: Network failures and rate limits
- **Error Logging**: Detailed logs in database and files
- **Graceful Degradation**: Continue processing on non-critical errors
- **Resume Capability**: Checkpoint system for interrupted imports

## Performance

- **Batch Processing**: Configurable batch sizes for memory efficiency
- **Database Indexes**: Optimized for common query patterns
- **Connection Pooling**: Efficient database operations
- **Rate Limiting**: Automatic API throttling

Expected import times (119th Congress):
- Committees: ~5 minutes
- Members: ~10 minutes
- Hearings: ~30-60 minutes
- Documents: ~2-4 hours (varies by hearing count)

## Monitoring

Check import progress:

```bash
# View logs
tail -f logs/import.log

# Check database counts
sqlite3 data/congressional_hearings.db "
SELECT 'committees' as table_name, COUNT(*) as count FROM committees
UNION ALL SELECT 'members', COUNT(*) FROM members
UNION ALL SELECT 'hearings', COUNT(*) FROM hearings
UNION ALL SELECT 'witnesses', COUNT(*) FROM witnesses;"

# Check sync status
sqlite3 data/congressional_hearings.db "
SELECT * FROM sync_tracking ORDER BY last_sync_timestamp DESC LIMIT 10;"

# Check errors
sqlite3 data/congressional_hearings.db "
SELECT * FROM import_errors WHERE is_resolved = 0 ORDER BY created_at DESC;"
```

## Future Enhancements

Planned features:
- Full-text search of hearing transcripts (SQLite FTS5)
- Web dashboard for browsing and searching
- PDF text extraction for documents
- Analytics and reporting features
- Historical congress coverage (118th, 117th, etc.)
- Integration with transcription tools

## Troubleshooting

**Common Issues:**

1. **Rate Limit Exceeded**
   - System automatically waits for reset
   - Reduce batch size if persistent

2. **Missing Data**
   - Check API response structure in logs
   - Some fields may be optional/missing

3. **Database Errors**
   - Check disk space and permissions
   - Restore from backup if needed

4. **Network Issues**
   - System retries automatically
   - Check internet connectivity

**Getting Help:**

1. Check logs in `logs/import.log`
2. Review error records in `import_errors` table
3. Validate configuration with `--check-config`
4. Run in validation mode first to identify issues

## License

This project is for research and educational purposes. Please review Congress.gov API terms of service for usage guidelines.

## Contributing

This system is designed as scaffolding for congressional hearing research. Feel free to extend for your specific use cases:

- Add new data sources
- Implement additional parsers
- Create analysis tools
- Build web interfaces
- Integrate with other systems