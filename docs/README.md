# Congressional Hearing Database - Documentation

Welcome to the comprehensive documentation for the Congressional Hearing Database. This documentation hub will help you find the information you need quickly.

## 🚀 Quick Navigation

### Getting Started
- **[Quick Start Guide](getting-started/quick-start.md)** - Get running in 5 minutes
- **[Installation Guide](getting-started/installation.md)** - Detailed setup for all environments
- **[Configuration Guide](getting-started/configuration.md)** - Environment variables and settings

### User Guides
- **[User Guide](guides/user/USER_GUIDE.md)** - Browse hearings, search data, explore committees
- **[CLI Guide](guides/developer/CLI_GUIDE.md)** - Command-line tools reference
- **[Operations Guide](guides/operations/UPDATE_PROTOCOLS.md)** - Update strategies and protocols

### Features & Capabilities
- **[Admin Dashboard](features/admin-dashboard.md)** - Real-time update monitoring and control
- **[Video Integration](features/video-integration.md)** - YouTube and Senate ISVP video support
- **[Scheduling System](features/scheduling.md)** - Automated task scheduling with Vercel cron

### Technical Reference
- **[System Architecture](reference/architecture/SYSTEM_ARCHITECTURE.md)** - Complete system design
- **[Database Schema](reference/architecture/database-schema.md)** - All 20 tables documented
- **[Web Architecture](reference/architecture/WEB_ARCHITECTURE.md)** - Flask blueprints and modular design
- **[API Reference](reference/API_REFERENCE.md)** - Flask API endpoints
- **[CLI Commands Reference](reference/cli-commands.md)** - Complete command reference

### Development
- **[Development Guide](guides/developer/DEVELOPMENT.md)** - Development workflow and patterns
- **[Testing Guide](guides/developer/testing.md)** - Running tests and writing new ones

### Operations & Monitoring
- **[Daily Updates](guides/operations/DAILY_UPDATES.md)** - Automated daily synchronization
- **[Update Protocols](guides/operations/UPDATE_PROTOCOLS.md)** - Multi-cadence update strategy
- **[Monitoring Guide](guides/operations/MONITORING.md)** - Health checks and performance metrics

### Deployment
- **[Deployment Guide](deployment/DEPLOYMENT.md)** - Deployment for all environments (includes Vercel)

### Troubleshooting
- **[Common Issues](troubleshooting/common-issues.md)** - Frequently encountered problems
- **[Debugging Guide](troubleshooting/debugging.md)** - Debugging tools and techniques

---

## 📚 Documentation by Audience

### For End Users
**Goal**: Browse congressional hearings and explore data

1. Start with [Quick Start Guide](getting-started/quick-start.md)
2. Read [User Guide](guides/user/USER_GUIDE.md) to learn web interface features
3. Explore hearings, committees, witnesses, and documents

### For Developers
**Goal**: Contribute code or understand the codebase

1. Follow [Installation Guide](getting-started/installation.md) for dev environment setup
2. Read [Development Guide](guides/developer/DEVELOPMENT.md) to understand architecture
3. Review [System Architecture](reference/architecture/SYSTEM_ARCHITECTURE.md) for technical details
4. Use [CLI Guide](guides/developer/CLI_GUIDE.md) for command-line operations
5. Run tests per [Testing Guide](guides/developer/testing.md)

### For Operators/Admins
**Goal**: Deploy, monitor, and maintain the system

1. Follow [Deployment Guide](deployment/DEPLOYMENT.md) for your environment
2. Configure [Update Protocols](guides/operations/UPDATE_PROTOCOLS.md) for data synchronization
3. Use [Admin Dashboard](features/admin-dashboard.md) for real-time monitoring
4. Set up [Monitoring](guides/operations/MONITORING.md) for health checks
5. Refer to [Troubleshooting](troubleshooting/common-issues.md) when issues arise

### For Researchers
**Goal**: Access data programmatically or understand data structure

1. Review [Database Schema](reference/architecture/database-schema.md) to understand data model
2. Use [API Reference](reference/API_REFERENCE.md) for programmatic access
3. Check [CLI Commands](reference/cli-commands.md) for data export/analysis

---

## 🏗️ Architecture Overview

The Congressional Hearing Database is a modular Flask web application with a comprehensive ETL pipeline:

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│ Congress.gov    │────────▶│  ETL Pipeline    │────────▶│  SQLite DB      │
│ API             │         │  Fetchers/Parsers│         │  20 Tables      │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                                                   │
                                                                   ▼
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│ Web Interface   │◀────────│  Flask App       │◀────────│  Database       │
│ 6 Blueprints    │         │  91 lines (core) │         │  Manager        │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

**Key Components**:
- **Data Collection**: Fetchers extract data from Congress.gov API
- **Data Validation**: Pydantic-based parsers ensure data quality
- **Data Storage**: DatabaseManager with transaction support
- **Web Interface**: Modular Flask app with 6 specialized blueprints
- **CLI Tool**: Unified command-line interface (865 lines)
- **Update System**: Automated daily synchronization with multi-cadence strategy
- **Admin Dashboard**: Real-time monitoring and task management

---

## 📊 Database Structure

The database contains **20 tables** organized into several domains:

### Core Entities
- `committees` (213) - Congressional committees and subcommittees
- `members` - Representatives and senators
- `hearings` (1,168+) - Committee hearings and meetings
- `bills` - Legislation referenced in hearings
- `witnesses` - Individuals testifying at hearings

### Relationships
- `committee_memberships` - Member assignments to committees
- `hearing_committees` - Committee-hearing associations
- `hearing_bills` - Bill-hearing relationships
- `witness_appearances` - Witness-hearing appearances

### Documents
- `hearing_transcripts` - Official hearing transcripts
- `witness_documents` - Witness-submitted documents
- `supporting_documents` - Additional hearing materials

### System Tables
- `sync_tracking` - Synchronization status
- `import_errors` - Error logging
- `scheduled_tasks` - Automated task definitions
- `update_logs` - Update operation history

See [Database Schema](reference/architecture/database-schema.md) for complete details.

---

## 🔄 Update Strategy

The database uses a **multi-cadence update strategy** to stay current:

### Daily Updates (Automated - 6 AM UTC)
- 7-day lookback window
- Updates hearing metadata (titles, dates, status, videos)
- Adds new hearings
- ~5-10 minutes, <500 API requests

### Weekly Updates (Automated)
- **Sunday 1 AM UTC**: Committee structure refresh
- **Monday 1 AM UTC**: Member roster updates

### Monthly Updates (Manual)
- 90-day lookback for comprehensive sync
- Full data integrity check
- Document refresh

See [Update Protocols](guides/operations/UPDATE_PROTOCOLS.md) for details.

---

## 🛠️ Common Tasks

### Running the Application
```bash
# Start web server
python cli.py web serve --host 0.0.0.0 --port 5001 --debug

# Or directly
python web/app.py
```

### Updating Data
```bash
# Quick daily sync (7 days)
python cli.py update incremental --lookback-days 7

# Comprehensive sync (30 days)
python cli.py update incremental --lookback-days 30

# Update specific components only
python cli.py update incremental --components hearings --lookback-days 7
```

### Database Operations
```bash
# Initialize database
python cli.py database init

# Check database status
python cli.py database status

# Run data quality audit
python cli.py analysis audit
```

### Importing Data
```bash
# Full import for Congress 119
python cli.py import full --congress 119

# Import specific phase
python cli.py import full --phase hearings --congress 119
```

---

## 📖 Additional Resources

### External Links
- [Congress.gov API Documentation](https://api.congress.gov/)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### Project Resources
- [Main README](../README.md) - Project overview
- [CHANGELOG](../CHANGELOG.md) - Version history and changes
- [GitHub Repository](https://github.com/your-org/Hearing-Database) (update with actual URL)

### Support
- Check [Troubleshooting Guide](troubleshooting/common-issues.md) for solutions
- Review [GitHub Issues](https://github.com/your-org/Hearing-Database/issues) for known problems
- Open a new issue for bugs or feature requests

---

## 🗂️ Document History

Historical documents and detailed implementation reports are archived in the `archive/` directory:

- `archive/2025-10-08_UPDATE_SYSTEM_FIXES.md` - Update system fixes
- `archive/2025-10-05_DOCUMENT_IMPROVEMENTS.md` - Document handling improvements
- `archive/2025-10-03_COMPREHENSIVE_DATABASE_REPORT.md` - Database enhancement
- `archive/2025-10-03_AUDIT_EXECUTIVE_SUMMARY.md` - Initial audit
- `archive/2025-10-01_PROJECT_STATUS.md` - Project status at launch

---

## 📝 Contributing to Documentation

Found an error or want to improve the documentation?

1. Documentation source files are in `docs/`
2. Follow the existing structure and formatting
3. Update internal links when moving files
4. Test all links before submitting changes
5. Submit a pull request with your improvements

---

**Last Updated**: October 9, 2025
**Documentation Version**: 2.0
**Project Version**: 119th Congress (1,168+ hearings)
