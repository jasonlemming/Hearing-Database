# Congressional Hearing Database

A public-facing tool for exploring congressional committee hearings, witness testimony, and legislative activity. Track what's happening in Congress through an accessible web interface and powerful data management tools.

**Live Demo**: [Deployed on Vercel](https://hearing-database.vercel.app) (if applicable)

## What Can You Do With This?

- 📅 **Track Committee Activity** - Monitor specific committees and subject areas
- 👥 **Follow Members** - See what congressional members are working on
- 🎤 **Analyze Witness Testimony** - Identify who testifies and organizational representation patterns
- 🔍 **Search & Filter** - Find hearings by chamber, committee, date, or keyword
- 📄 **Access Documents** - Direct links to official transcripts and supporting materials

## Current Data

- **Congress**: 119th (2025-2027)
- **Hearings**: 1,168 (613 House, 555 Senate)
- **Witnesses**: 1,545 unique individuals with 1,620 appearances
- **Committees**: 53 parent committees + 161 subcommittees
- **Members**: 538 congressional members tracked
- **Updates**: Daily automated sync at 6am UTC

## Quick Start

### For Casual Users

**Just want to browse hearings?** Visit the web interface:

```bash
# Clone and run locally
git clone <repository-url>
cd Hearing-Database
pip install -r requirements.txt
python cli.py web serve
```

Then open http://localhost:5000 in your browser.

👉 **See the [User Guide](docs/guides/user/USER_GUIDE.md) for web interface tutorials**

### For Technical Users

**Want to import your own data or run custom queries?**

1. **Get a Congress.gov API Key** (free): https://api.congress.gov/sign-up/
2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API key
   ```
3. **Initialize database**:
   ```bash
   python cli.py database init
   ```
4. **Import data**:
   ```bash
   python cli.py import full --congress 119
   ```

👉 **See the [CLI Commands Reference](docs/reference/cli-commands.md) for detailed command documentation**

### For Developers

**Want to contribute or integrate with the API?**

📚 **[Complete Documentation Hub](docs/README.md)** - Explore all guides organized by audience

**Essential Guides**:
- **Development**: [Developer Guide](docs/guides/developer/DEVELOPMENT.md) - Architecture, patterns, and how to contribute
- **Database**: [Database Schema Reference](docs/reference/architecture/database-schema.md) - Complete schema documentation
- **Testing**: [Testing Guide](docs/guides/developer/testing.md) - Writing and running tests
- **API**: [API Reference](docs/reference/API_REFERENCE.md) - Programmatic access documentation
- **Deployment**: [Deployment Guide](docs/deployment/DEPLOYMENT.md) - Vercel and production setup
- **Monitoring**: [Operations & Monitoring](docs/guides/operations/MONITORING.md) - Health checks and performance tracking

## Features

### Web Interface
- Browse hearings with advanced filtering (chamber, committee, date range, search)
- View detailed hearing information with witness lists and documents
- Explore committee structures and membership
- Track witness testimony across multiple hearings
- Member detail pages with committee assignments

### Data Management CLI
- **Import**: Full data import from Congress.gov API
- **Update**: Incremental daily updates (fetches only changed data)
- **Enhance**: Enrich existing data with additional details
- **Database**: Schema management and maintenance
- **Analysis**: Audit tools and data quality checks

### Automated Updates
- Daily cron job (Vercel deployment) syncs new hearings and updates
- Incremental update strategy minimizes API usage
- Error tracking and logging for monitoring

## Project Structure

```
Hearing-Database/
├── api/                    # Congress.gov API client and rate limiting
├── config/                 # Configuration and logging
├── database/              # Database schema and operations (SQLite)
├── fetchers/              # API data fetchers (hearings, committees, witnesses, etc.)
├── parsers/               # Data validation and parsing
├── importers/             # Import orchestration
├── updaters/              # Daily update automation
├── web/                   # Flask web application
│   ├── blueprints/        # Modular route handlers
│   ├── templates/         # HTML templates
│   └── static/            # CSS, JavaScript, images
├── scripts/               # Legacy standalone scripts
├── docs/                  # Documentation
├── tests/                 # Test suite
└── cli.py                 # Unified command-line interface
```

## Database Schema

The SQLite database tracks comprehensive congressional hearing data:

**Core Tables**:
- `hearings` - Hearing metadata (title, date, chamber, status, type)
- `committees` - Committee and subcommittee information
- `members` - Congressional members with party and state
- `witnesses` - Witness information (name, title, organization)

**Relationship Tables**:
- `hearing_committees` - Links hearings to committees
- `hearing_transcripts` - Transcript URLs and metadata
- `witness_appearances` - Witness testimony records
- `witness_documents` - Witness written statements
- `supporting_documents` - Additional hearing materials
- `committee_memberships` - Member committee assignments

**Tracking Tables**:
- `sync_tracking` - Import/update history
- `update_logs` - Daily update metrics
- `import_errors` - Error tracking

## Technology Stack

- **Backend**: Python 3.8+ with Flask web framework
- **Database**: SQLite (portable, serverless-friendly)
- **API**: Congress.gov API v3 (5,000 requests/hour limit)
- **Frontend**: Bootstrap 5 with vanilla JavaScript
- **Deployment**: Vercel with automated daily cron jobs
- **CLI**: Click framework for command-line interface

## Data Scope & Philosophy

### Current Focus
- **119th Congress** (2025-2027) - Currently active congress
- **Historical Archive** - Data accumulates over time (will retain 119th when 120th starts)
- **Metadata Focus** - Stores links to documents rather than full text (lightweight approach)
- **Public Data** - All data sourced from official Congress.gov API

### Out of Scope (Current)
- Bill tracking (schema exists but low priority)
- Full-text document storage/search
- Historical backfill to prior congresses (possible future enhancement)

## Use Cases

### Civic Engagement
- Monitor hearings on topics you care about
- See which organizations testify before Congress
- Track your representatives' committee activities
- Access official hearing documents and transcripts

### Research & Analysis
- Study witness testimony patterns and organizational representation
- Analyze committee hearing frequency and topics
- Track legislative oversight activities
- Export data for custom analysis

### Journalism & Transparency
- Quick lookup of hearing information
- Verify witness testimony claims
- Monitor congressional activity timelines
- Access primary source documents

## API Endpoints

Public JSON API for programmatic access:

- `GET /api/stats` - Database statistics
- `GET /api/update-status` - Daily update status and history
- `GET /api/debug` - System diagnostic information

See [API Reference](docs/reference/API_REFERENCE.md) for complete documentation.

## Configuration

Key environment variables (`.env` file):

```bash
# Required
CONGRESS_API_KEY=your_api_key_here

# Optional
DATABASE_PATH=database.db          # Database file location
TARGET_CONGRESS=119                # Congress to import
BATCH_SIZE=50                      # Import batch size
UPDATE_WINDOW_DAYS=30              # Daily update lookback window
LOG_LEVEL=INFO                     # Logging verbosity
```

## Development

### Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black .
```

### Running Locally
```bash
# Start web server
python cli.py web serve --host 127.0.0.1 --port 5000

# Or run Flask app directly
python web/app.py  # Runs on port 8000
```

## Deployment

The system is designed for Vercel serverless deployment with automated daily updates:

- Vercel handles web hosting and serverless functions
- Cron job triggers daily data sync at 6am UTC
- SQLite database deployed with the application
- Read-mostly workload optimized for Vercel's serverless environment

See [Deployment Guide](docs/deployment/DEPLOYMENT.md) for detailed instructions.

## Performance & Limitations

### Current Scale
- **Database Size**: ~4.5 MB (1,168 hearings with full metadata)
- **API Rate Limit**: 5,000 requests/hour (Congress.gov)
- **Update Time**: ~5-10 minutes for daily incremental updates
- **Full Import**: ~30-60 minutes for complete 119th Congress import

### SQLite Considerations
- Excellent for read-heavy workloads (web browsing)
- Single-writer limitation (appropriate for daily batch updates)
- Portable and serverless-friendly
- May need migration to PostgreSQL if scale significantly increases

## Contributing

Contributions welcome! Areas of interest:

- Additional data visualizations
- Enhanced search capabilities
- Alternative transcript data source integration
- Historical congress backfill
- Performance optimizations
- Documentation improvements

Please open an issue to discuss major changes before submitting PRs.

## Roadmap

### Potential Future Enhancements
- **Full-text search** of transcript content (if alternative data source identified)
- **Historical backfill** to prior congresses (118th, 117th, etc.)
- **Advanced analytics** dashboard with charts and trends
- **Export capabilities** (CSV, JSON) for custom analysis
- **Email notifications** for committee/member activity
- **Mobile-responsive** improvements

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Data provided by the [Congress.gov API](https://api.congress.gov)
- Built for civic engagement and government transparency
- Inspired by the need for accessible congressional oversight data

## Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Documentation**: See `docs/` directory for detailed guides
- **Questions**: Open a discussion for usage questions

---

**Disclaimer**: This is an independent project and is not affiliated with or endorsed by Congress.gov, the Library of Congress, or any government entity. All data is sourced from publicly available official sources.
# CRS/Policy Library migrated to PostgreSQL with products/product_versions views
