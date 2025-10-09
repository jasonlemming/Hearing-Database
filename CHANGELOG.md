# Changelog

All notable changes to the Congressional Hearing Database project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project uses dates for versioning.

---

## [2025-10-08] - Update System Fixes & Admin Dashboard

### Fixed
- **Critical**: Fixed foreign key constraint errors affecting 783/1,338 hearings
- **Critical**: Fixed date format bug in incremental updates (was returning 0 results)
- Changed date format from `YYYY-MM-DD` to ISO 8601 (`YYYY-MM-DDTHH:MM:SSZ`)
- Replaced `INSERT OR REPLACE` with proper UPDATE/INSERT pattern in all upsert methods
- Updated Vercel cron endpoint to use fixed DatabaseManager methods

### Added
- **Admin Dashboard** with real-time update monitoring (`/admin/`)
  - Manual update controls with configurable lookback days and components
  - Live progress tracking with 2-second polling
  - Task management and cancellation
  - Changes-since-baseline comparison
  - Update history viewer
- **Task Manager** for background CLI process execution
- **Multi-cadence update strategy**:
  - Daily: 7-day lookback (automated, 6 AM UTC)
  - Weekly: Committee updates (Sunday), Member updates (Monday)
  - Monthly: 90-day comprehensive sync (manual)
- **Component-specific update commands**:
  - `cli.py update incremental --components hearings`
  - `cli.py update videos --limit 100 --force`
  - `cli.py update witnesses --lookback-days 30`
  - `cli.py update committees --chamber all`

### Changed
- Video URLs now synchronize in daily updates
- Update system properly tracks metrics in `update_logs` table
- Enhanced CLI with `--json-progress` flag for admin dashboard integration

### Documentation
- Added `docs/UPDATE_PROTOCOLS.md` - comprehensive update strategy guide
- Updated `docs/DAILY_UPDATES.md` - added fix notices
- Added `docs/ADMIN_DASHBOARD.md` - dashboard quick start guide
- Added `UPDATE_SYSTEM_FIXES_SUMMARY.md` (archived)

---

## [2025-10-07] - YouTube Video Integration

### Added
- **Video support** for congressional hearings
  - `video_url` field - Full Congress.gov video URL
  - `youtube_video_id` field - Extracted YouTube video ID
  - Database migration: `001_add_video_fields.sql`
  - Indexed `youtube_video_id` for efficient queries

### Changed
- **Enhanced data collection**:
  - `HearingFetcher.extract_videos()` - pulls video data from API
  - `HearingParser.parse_video_url()` - extracts YouTube IDs with validation
  - `ImportOrchestrator` - video extraction during import and daily updates
- **Improved web interface**:
  - Added "Video of Proceedings" player on hearing detail pages
  - Responsive video player (16:9 aspect ratio, medium-sized)
  - Fallback UI when video unavailable
  - Congress.gov link when video exists

### Documentation
- Added `YOUTUBE_VIDEO_INTEGRATION.md` (root and docs/)
- Created test suite: `test_video_extraction.py` (8 passing tests)

---

## [2025-10-05] - Document Handling Improvements

### Fixed
- **Accurate Congress.gov API parsing** for all document types
- Enhanced transcript extraction with multiple fallback mechanisms
- Comprehensive witness document extraction with full metadata
- Supporting documents now include descriptions

### Added
- **Complete document import** for all 1,168 hearings (removed 100-hearing limit)
- All three document tables now populated:
  - `hearing_transcripts`
  - `witness_documents` (properly linked via appearance_id)
  - `supporting_documents`
- **Enhanced UI organization**:
  - Witness documents clustered by witness name on hearing pages
  - Collapsible accordion interface on witness detail pages
  - Per-hearing document sections with type categorization
- **Testing infrastructure**:
  - `tests/documents/test_document_fetcher.py` (8 unit tests)
  - `tests/documents/test_document_import.py` (3 integration tests)
  - All 11 tests passing

### Changed
- `DocumentFetcher` - enhanced parsing for all document types
- `ImportOrchestrator.import_documents()` - completely rewritten
- Hearing detail template - documents grouped by witness
- Witness detail template - accordion-based design
- Enhanced error handling and mismatch detection logging

### Documentation
- Added `DOCUMENT_IMPROVEMENTS_SUMMARY.md`

---

## [2025-10-03] - Comprehensive Database Enhancement

### Added
- **Senate data recovery**: 500 Senate hearing titles (0% → 90.1% coverage)
- **Committee relationships**: 554 new relationships (+83.3%)
- Multi-layered inference algorithms:
  - API-based committee data extraction
  - Event ID proximity analysis
  - Keyword-based committee matching

### Changed
- **Dramatic improvements across all metrics**:
  - Hearings with titles: 448 → 948 (+500, +42.8%)
  - Committee coverage: 52.5% → 99.9% (only 1 unassigned hearing)
  - Senate committee coverage: 0% → 89.7%
- **Enhanced parsing**:
  - Improved error-resilient processing
  - Better API limitation handling
  - Enhanced relationship building

### Documentation
- Added `COMPREHENSIVE_DATABASE_REPORT.md`
- Added `AUDIT_EXECUTIVE_SUMMARY.md`

---

## [2025-10-01] - Initial Production Deployment

### Added
- **Production database** with 1,168 hearings (119th Congress)
- **Modular Flask web application**:
  - 6 blueprints: committees, hearings, main_pages, api, admin, crs
  - Main app reduced from 841 → 91 lines (89% reduction)
  - Clean separation of concerns
- **Unified CLI tool** (`cli.py` - 865 lines):
  - Replaces 18+ individual scripts
  - Commands: import, enhance, update, database, analysis, witness, web
  - Organized command groups with comprehensive options
- **Complete database schema** (20 tables):
  - Committees, members, hearings, bills, witnesses
  - Committee memberships, hearing relationships
  - Document tables (3 types)
  - Sync tracking, error logging, scheduled tasks
- **ETL pipeline architecture**:
  - Fetchers → Parsers → Database Manager pattern
  - 7 specialized fetchers
  - Pydantic-based data models
- **Testing infrastructure**:
  - Pytest-based test suite
  - Tests for documents, security, integration
- **Audit tools**:
  - Database validation
  - Template style analysis
  - HTTP testing
  - Comprehensive audit reports

### Documentation
- Main `README.md` - comprehensive project overview
- `SYSTEM_ARCHITECTURE.md` - detailed architecture documentation
- `docs/WEB_ARCHITECTURE.md` - blueprint-based modular design
- `docs/CLI_GUIDE.md` - CLI command reference
- `docs/USER_GUIDE.md` - end-user guide for web interface
- `docs/API_REFERENCE.md` - Flask API documentation
- `audit_tools/README.md` - audit tool usage guide
- `PROJECT_STATUS.md` - initial project status report

---

## Future Enhancements

### Planned
- Email/webhook notifications for update failures
- Schedule templates for common update patterns
- Automatic Vercel deployment via API
- Performance metrics per scheduled task
- Diff reporting for update logs
- Real-time WebSocket updates (vs. polling)
- Authentication and user management for admin dashboard
- Video thumbnails on hearing list pages
- Multiple video support per hearing

### Under Consideration
- Selective updates by committee/chamber
- Historical backfill of older congresses
- Smart scheduling based on congressional activity
- Plugin system for dynamic blueprint loading
- API versioning (`/api/v1`, `/api/v2`)
- Microservices architecture option

---

## Archive

Historical documents and detailed reports are available in the `archive/` directory:

- `archive/2025-10-08_UPDATE_SYSTEM_FIXES.md` - Update system fixes detailed report
- `archive/2025-10-05_DOCUMENT_IMPROVEMENTS.md` - Document handling improvements
- `archive/2025-10-03_COMPREHENSIVE_DATABASE_REPORT.md` - Database enhancement report
- `archive/2025-10-03_AUDIT_EXECUTIVE_SUMMARY.md` - Initial audit findings
- `archive/2025-10-01_PROJECT_STATUS.md` - Project status at launch
- `archive/audit_reports/` - Automated audit tool reports
