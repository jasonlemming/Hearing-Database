# Development Guide

Complete guide for developers working on the Congressional Hearing Database.

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Project Structure](#project-structure)
3. [Architecture Overview](#architecture-overview)
4. [Development Workflow](#development-workflow)
5. [Key Design Patterns](#key-design-patterns)
6. [Creating New Features](#creating-new-features)
7. [Database Development](#database-development)
8. [Testing](#testing)
9. [Code Style & Conventions](#code-style--conventions)
10. [Common Development Tasks](#common-development-tasks)

---

## Development Environment Setup

### Prerequisites

- **Python 3.9+** (tested with 3.9, 3.10, 3.11)
- **Git** for version control
- **SQLite 3.8+** (usually included with Python)
- **Congress.gov API Key** ([Get one here](https://api.congress.gov/sign-up/))

### Initial Setup

```bash
# Clone repository
git clone https://github.com/your-org/Hearing-Database.git
cd Hearing-Database

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install development tools (optional but recommended)
pip install pytest pytest-cov black flake8 ipython

# Configure environment
cp .env.example .env
nano .env  # Add your API key and configuration

# Initialize database (if needed)
python cli.py database init

# Start development server
python cli.py web serve --debug --port 5001
```

### Recommended Development Tools

- **VSCode** or **PyCharm** - Python IDEs with excellent debugging
- **DB Browser for SQLite** - Database inspection and querying
- **Postman** or **curl** - API endpoint testing
- **pytest** - Running and writing tests
- **black** - Code formatting
- **flake8** - Linting and style checking

---

## Project Structure

```
Hearing-Database/
├── api/                      # Congress.gov API client
│   ├── client.py            # HTTP client with rate limiting
│   └── __init__.py
│
├── config/                   # Configuration management
│   ├── settings.py          # Pydantic settings model
│   ├── logging_config.py    # Logging configuration
│   └── __init__.py
│
├── database/                 # Database layer
│   ├── manager.py           # DatabaseManager (core CRUD operations)
│   ├── schema.sql           # Database schema definition (20 tables)
│   └── __init__.py
│
├── fetchers/                 # API data fetchers
│   ├── base_fetcher.py      # Abstract base class
│   ├── hearing_fetcher.py   # Hearing data fetching
│   ├── committee_fetcher.py # Committee data fetching
│   ├── member_fetcher.py    # Member data fetching
│   ├── witness_fetcher.py   # Witness data fetching
│   ├── document_fetcher.py  # Document data fetching
│   ├── bill_fetcher.py      # Bill data fetching
│   └── __init__.py
│
├── parsers/                  # Data validation and transformation
│   ├── base_parser.py       # Abstract base parser
│   ├── models.py            # Pydantic data models with validators
│   ├── hearing_parser.py    # Hearing parsing and validation
│   ├── committee_parser.py  # Committee parsing
│   ├── member_parser.py     # Member parsing
│   ├── witness_parser.py    # Witness parsing
│   └── __init__.py
│
├── importers/                # Data import orchestration
│   ├── orchestrator.py      # ImportOrchestrator (coordinates full imports)
│   └── __init__.py
│
├── updaters/                 # Incremental update logic
│   ├── daily_updater.py     # DailyUpdater (incremental updates)
│   └── __init__.py
│
├── web/                      # Flask web application
│   ├── app.py               # Main Flask app (91 lines, modular)
│   ├── blueprints/          # Route blueprints
│   │   ├── hearings.py      # Hearing browsing and details
│   │   ├── committees.py    # Committee pages
│   │   ├── main_pages.py    # Members, witnesses, search
│   │   ├── api.py           # JSON API endpoints
│   │   ├── admin.py         # Admin dashboard
│   │   ├── crs.py           # CRS search integration
│   │   └── __init__.py
│   ├── templates/           # Jinja2 HTML templates
│   └── static/              # CSS, JS, images
│
├── utils/                    # Shared utility functions
│   └── __init__.py
│
├── tests/                    # Test suite
│   ├── documents/           # Document-related tests
│   ├── security/            # Security tests
│   └── __init__.py
│
├── scripts/                  # Standalone utility scripts
│   └── init_database.py     # Database initialization
│
├── docs/                     # Documentation
│   ├── README.md            # Documentation hub
│   ├── getting-started/     # Setup guides
│   ├── guides/              # User, developer, operations guides
│   ├── reference/           # Technical reference
│   └── features/            # Feature documentation
│
├── cli.py                    # Unified CLI tool (865 lines)
├── requirements.txt          # Python dependencies
├── .env.example              # Example environment variables
└── database.db               # SQLite database (1,168+ hearings)
```

---

## Architecture Overview

The Congressional Hearing Database follows a **modular, layered architecture** with clear separation of concerns.

### High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         User Interfaces                          │
├──────────────────────────┬───────────────────────────────────────┤
│   Web Interface (Flask)  │   CLI Tool (Click)                    │
│   - 6 Blueprints         │   - 7 Command Groups                  │
│   - Jinja2 Templates     │   - 865 lines                         │
└──────────────┬───────────┴─────────────────┬─────────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                         │
├──────────────────────────┬───────────────────────────────────────┤
│   ImportOrchestrator     │   DailyUpdater                        │
│   - Full imports         │   - Incremental updates               │
│   - Multi-phase          │   - Component-specific                │
└──────────────┬───────────┴─────────────────┬─────────────────────┘
               │                             │
               ▼                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      ETL Pipeline                                 │
├──────────────────────┬──────────────────┬───────────────────────┤
│   Fetchers           │   Parsers        │   DatabaseManager     │
│   - BaseFetcher      │   - BaseParser   │   - Transactions      │
│   - 7 specialized    │   - Pydantic     │   - Upsert methods    │
│   - API pagination   │   - Validators   │   - Foreign keys      │
└──────────┬───────────┴──────────┬───────┴───────────┬───────────┘
           │                      │                   │
           ▼                      ▼                   ▼
    ┌──────────────┐      ┌─────────────┐     ┌─────────────┐
    │ Congress.gov │      │   Pydantic  │     │   SQLite    │
    │     API      │      │   Models    │     │   Database  │
    └──────────────┘      └─────────────┘     └─────────────┘
```

### Key Components

#### 1. **Web Layer** (Flask Blueprints)

**Purpose**: User interface for browsing and exploring data

- `hearings.py` - Hearing list, detail pages, filtering
- `committees.py` - Committee pages and hearing lists
- `main_pages.py` - Members, witnesses, search, landing page
- `api.py` - JSON API endpoints for programmatic access
- `admin.py` - Admin dashboard for updates and monitoring
- `crs.py` - Congressional Research Service search integration

**Pattern**: Each blueprint is self-contained with its own routes and logic.

#### 2. **CLI Layer** (Click Commands)

**Purpose**: Command-line interface for operations and automation

- `import` - Data import commands (full, incremental, specific phases)
- `enhance` - Data enhancement (titles, dates, committees)
- `update` - Update commands (incremental, committees, videos, witnesses)
- `database` - Database operations (init, status, clean)
- `analysis` - Audit and analysis commands
- `witness` - Witness-specific operations
- `web` - Web server control

**Pattern**: Organized command groups with options and flags.

#### 3. **Data Pipeline** (ETL)

**Purpose**: Extract, Transform, Load data from Congress.gov API

##### Fetchers (Extract)
- Inherit from `BaseFetcher`
- Handle API pagination and rate limiting
- Return raw API response data
- Example: `HearingFetcher.fetch_hearings_by_congress(congress, chamber)`

##### Parsers (Transform)
- Use Pydantic models for validation
- Transform API data into database format
- Handle data cleaning and normalization
- Example: `HearingParser.parse(api_data) -> HearingModel`

##### DatabaseManager (Load)
- Context manager for transactions
- Upsert methods (check-then-update or insert)
- Foreign key constraint handling
- Example: `db.upsert_hearing(hearing_data) -> hearing_id`

#### 4. **Data Models** (Pydantic)

**Purpose**: Type-safe data validation with automatic error reporting

```python
class HearingModel(BaseModel):
    event_id: str
    congress: int
    chamber: str
    title: str
    hearing_date: Optional[date] = None

    @validator('chamber')
    def validate_chamber(cls, v):
        valid_chambers = ['House', 'Senate', 'NoChamber']
        if v not in valid_chambers:
            raise ValueError(f'Chamber must be one of {valid_chambers}')
        return v
```

Models include validators for:
- Chamber (House, Senate, NoChamber)
- Party (D, R, I, ID, L)
- Bill types (HR, S, HJRES, etc.)
- Document types
- Status values

---

## Development Workflow

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-new-feature

# Make changes
# ... edit files ...

# Run tests
pytest

# Format code
black .

# Check style
flake8 .

# Commit changes
git add .
git commit -m "Add my new feature"

# Push to remote
git push origin feature/my-new-feature

# Create pull request on GitHub
```

### Testing Workflow

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/documents/test_document_fetcher.py

# Run with coverage
pytest --cov=. --cov-report=html

# Run single test
pytest tests/documents/test_document_fetcher.py::TestDocumentFetcher::test_extract_transcripts -v

# Run tests with output
pytest -v -s
```

### Development Server Workflow

```bash
# Start development server with debug mode
python cli.py web serve --debug --port 5001

# Or run directly (auto-reloads on changes)
python web/app.py

# In another terminal, run updates
python cli.py update incremental --lookback-days 1

# Check database status
python cli.py database status

# Run audit
python cli.py analysis audit
```

---

## Key Design Patterns

### 1. **Repository Pattern** (DatabaseManager)

**Purpose**: Centralize database access logic

```python
class DatabaseManager:
    """Manages database operations with transaction support"""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.database_path

    @contextmanager
    def transaction(self):
        """Context manager for database transactions"""
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def upsert_hearing(self, hearing_data: Dict[str, Any]) -> int:
        """Insert or update hearing (avoids foreign key violations)"""
        existing = self.get_hearing_by_event_id(hearing_data['event_id'])
        if existing:
            # UPDATE existing record
            self.execute(update_query, params)
            return existing['hearing_id']
        else:
            # INSERT new record
            cursor = self.execute(insert_query, params)
            return cursor.lastrowid
```

**Benefits**:
- Single point of database access
- Transaction management
- Proper error handling
- Foreign key constraint handling

### 2. **Strategy Pattern** (Fetchers)

**Purpose**: Interchangeable data fetching strategies

```python
class BaseFetcher(ABC):
    """Base class for API data fetchers"""

    def __init__(self, api_client: CongressAPIClient):
        self.api_client = api_client

    @abstractmethod
    def fetch_all(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetch all records from API endpoint"""
        pass

class HearingFetcher(BaseFetcher):
    """Fetch hearing data from Congress.gov API"""

    def fetch_all(self, congress: int, chamber: str) -> List[Dict[str, Any]]:
        """Fetch all hearings for congress and chamber"""
        # Implementation specific to hearings
        pass
```

**Benefits**:
- Consistent interface
- Easy to add new data sources
- Testable in isolation

### 3. **Builder Pattern** (Parsers)

**Purpose**: Complex object construction with validation

```python
class HearingParser(BaseParser):
    """Parse and validate hearing data"""

    def parse(self, api_data: Dict[str, Any]) -> HearingModel:
        """Parse API data into validated HearingModel"""
        return HearingModel(
            event_id=api_data['eventId'],
            congress=api_data['congress'],
            chamber=self._parse_chamber(api_data),
            title=api_data.get('title', ''),
            hearing_date=self._parse_date(api_data),
            video_url=self._extract_video_url(api_data)
        )

    def _parse_chamber(self, data: Dict) -> str:
        """Extract and normalize chamber"""
        # Custom parsing logic
        pass
```

**Benefits**:
- Separation of parsing logic
- Reusable transformation methods
- Type safety through Pydantic

### 4. **Blueprint Pattern** (Flask Modular Design)

**Purpose**: Organize routes into logical modules

```python
# web/blueprints/hearings.py
from flask import Blueprint, render_template

hearings_bp = Blueprint('hearings', __name__)

@hearings_bp.route('/hearings')
def hearings():
    """Browse hearings"""
    # Route implementation
    pass

# web/app.py
from web.blueprints.hearings import hearings_bp

app = Flask(__name__)
app.register_blueprint(hearings_bp)
```

**Benefits**:
- Modular code organization
- Easy to add/remove features
- Improved maintainability
- Main app reduced from 841 → 91 lines (89% reduction)

### 5. **Command Pattern** (CLI)

**Purpose**: Encapsulate operations as objects

```python
@cli.group()
def update():
    """Update database with latest changes"""
    pass

@update.command()
@click.option('--lookback-days', default=7)
def incremental(lookback_days):
    """Run incremental daily update"""
    updater = DailyUpdater(lookback_days=lookback_days)
    result = updater.run_daily_update()
    # Handle result
```

**Benefits**:
- Self-documenting commands
- Consistent interface
- Easy to extend

---

## Creating New Features

### Adding a New Blueprint

**Example**: Add a `bills` blueprint for browsing legislation

1. **Create blueprint file**: `web/blueprints/bills.py`

```python
"""
Bill-related routes blueprint
"""
from flask import Blueprint, render_template, request
from database.manager import DatabaseManager

bills_bp = Blueprint('bills', __name__)
db = DatabaseManager()

@bills_bp.route('/bills')
def bills_list():
    """Browse bills"""
    with db.transaction() as conn:
        cursor = conn.execute('SELECT * FROM bills ORDER BY congress DESC LIMIT 100')
        bills = cursor.fetchall()

    return render_template('bills.html', bills=bills)

@bills_bp.route('/bill/<int:bill_id>')
def bill_detail(bill_id):
    """Bill detail page"""
    with db.transaction() as conn:
        cursor = conn.execute('SELECT * FROM bills WHERE bill_id = ?', (bill_id,))
        bill = cursor.fetchone()

        if not bill:
            return "Bill not found", 404

        # Get hearings mentioning this bill
        cursor = conn.execute('''
            SELECT h.* FROM hearings h
            JOIN hearing_bills hb ON h.hearing_id = hb.hearing_id
            WHERE hb.bill_id = ?
        ''', (bill_id,))
        hearings = cursor.fetchall()

    return render_template('bill_detail.html', bill=bill, hearings=hearings)
```

2. **Register blueprint**: Edit `web/app.py`

```python
from web.blueprints.bills import bills_bp

app.register_blueprint(bills_bp)
```

3. **Create templates**: `web/templates/bills.html` and `web/templates/bill_detail.html`

4. **Test**: Visit `http://localhost:5001/bills`

### Adding a New CLI Command

**Example**: Add a `validate` command to check data integrity

1. **Add command group** in `cli.py`:

```python
@cli.group()
def validate():
    """Data validation commands"""
    pass

@validate.command()
@click.option('--fix', is_flag=True, help='Automatically fix issues')
def integrity(fix):
    """Check database integrity"""
    logger = get_logger(__name__)

    db = DatabaseManager()
    issues = []

    # Check for orphaned hearing_committees
    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT hc.hearing_id, hc.committee_id
            FROM hearing_committees hc
            LEFT JOIN hearings h ON hc.hearing_id = h.hearing_id
            LEFT JOIN committees c ON hc.committee_id = c.committee_id
            WHERE h.hearing_id IS NULL OR c.committee_id IS NULL
        ''')
        orphans = cursor.fetchall()

    if orphans:
        issues.append(f"Found {len(orphans)} orphaned hearing_committees")
        if fix:
            # Delete orphaned records
            pass

    # Report results
    if issues:
        logger.warning(f"Found {len(issues)} integrity issues")
        for issue in issues:
            logger.warning(f"  - {issue}")
    else:
        logger.info("No integrity issues found")

@validate.command()
def schema():
    """Validate database schema matches expected structure"""
    # Implementation
    pass
```

2. **Test**:

```bash
python cli.py validate integrity
python cli.py validate integrity --fix
python cli.py validate schema
```

### Adding a New Fetcher

**Example**: Create `CRSReportFetcher` for Congressional Research Service reports

1. **Create fetcher**: `fetchers/crs_report_fetcher.py`

```python
"""
CRS Report fetcher for Congressional Research Service reports
"""
from typing import List, Dict, Any
from fetchers.base_fetcher import BaseFetcher

class CRSReportFetcher(BaseFetcher):
    """Fetch CRS report data"""

    def fetch_all(self, topic: str = None) -> List[Dict[str, Any]]:
        """
        Fetch all CRS reports, optionally filtered by topic

        Args:
            topic: Filter by topic (optional)

        Returns:
            List of CRS report records
        """
        params = {'limit': 250}
        if topic:
            params['topic'] = topic

        response = self.api_client.get('crs-reports', params)
        return response.get('reports', [])

    def fetch_by_number(self, report_number: str) -> Dict[str, Any]:
        """Fetch single CRS report by number"""
        response = self.api_client.get(f'crs-reports/{report_number}')
        return response.get('report', {})
```

2. **Create parser**: `parsers/crs_report_parser.py`

```python
"""
CRS Report parser
"""
from parsers.base_parser import BaseParser
from parsers.models import CRSReportModel  # Add to models.py

class CRSReportParser(BaseParser):
    """Parse CRS report data"""

    def parse(self, api_data: Dict[str, Any]) -> CRSReportModel:
        """Parse API data into CRSReportModel"""
        return CRSReportModel(
            report_number=api_data['reportNumber'],
            title=api_data['title'],
            summary=api_data.get('summary'),
            publish_date=self._parse_date(api_data.get('publishDate')),
            topics=api_data.get('topics', []),
            url=api_data.get('url')
        )
```

3. **Add to ImportOrchestrator**: Edit `importers/orchestrator.py`

```python
def import_crs_reports(self, validation_mode: bool = False):
    """Import CRS reports"""
    from fetchers.crs_report_fetcher import CRSReportFetcher
    from parsers.crs_report_parser import CRSReportParser

    fetcher = CRSReportFetcher(self.api_client)
    parser = CRSReportParser()

    reports = fetcher.fetch_all()

    for report_data in reports:
        try:
            parsed = parser.parse(report_data)
            if not validation_mode:
                self.db_manager.upsert_crs_report(parsed.dict())
        except Exception as e:
            logger.error(f"Error importing CRS report: {e}")
```

4. **Add CLI command**:

```python
@import_cmd.command()
def crs_reports():
    """Import CRS reports"""
    # Implementation
    pass
```

### Adding a New Pydantic Model

**Example**: Create model for CRS reports

Edit `parsers/models.py`:

```python
class CRSReportModel(BaseModel):
    """CRS Report data model"""
    report_number: str
    title: str
    summary: Optional[str] = None
    publish_date: Optional[date] = None
    topics: List[str] = []
    url: Optional[str] = None

    @validator('report_number')
    def validate_report_number(cls, v):
        if not v or not v.strip():
            raise ValueError('Report number is required')
        # Format: R46234, RL12345
        if not v.startswith(('R', 'RL')):
            raise ValueError('Invalid report number format')
        return v

    @validator('topics')
    def validate_topics(cls, v):
        # Ensure unique topics
        return list(set(v))

    class Config:
        str_strip_whitespace = True
```

---

## Database Development

### Working with DatabaseManager

**Transaction pattern** (always use for data modifications):

```python
from database.manager import DatabaseManager

db = DatabaseManager()

# Read operations (single query)
hearing = db.fetch_one("SELECT * FROM hearings WHERE hearing_id = ?", (123,))

# Read operations (multiple rows)
hearings = db.fetch_all("SELECT * FROM hearings WHERE chamber = ?", ("House",))

# Write operations (use transaction)
with db.transaction() as conn:
    cursor = conn.execute(
        "INSERT INTO hearings (event_id, congress, chamber) VALUES (?, ?, ?)",
        ("LC12345", 119, "House")
    )
    hearing_id = cursor.lastrowid

    # Multiple operations in same transaction
    conn.execute(
        "INSERT INTO hearing_committees (hearing_id, committee_id) VALUES (?, ?)",
        (hearing_id, 456)
    )
    # Commit happens automatically at end of context manager
```

### Upsert Pattern

**Problem**: `INSERT OR REPLACE` causes foreign key violations

**Solution**: Check existence first, then UPDATE or INSERT

```python
def upsert_hearing(self, hearing_data: Dict[str, Any]) -> int:
    """Insert or update hearing (avoids FK violations)"""
    event_id = hearing_data.get('event_id')

    # Check if exists
    existing = self.get_hearing_by_event_id(event_id)

    if existing:
        # UPDATE existing record (preserves primary key)
        update_query = """
        UPDATE hearings SET
            congress = ?, chamber = ?, title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE event_id = ?
        """
        params = (
            hearing_data.get('congress'),
            hearing_data.get('chamber'),
            hearing_data.get('title'),
            event_id
        )
        self.execute(update_query, params)
        return existing['hearing_id']
    else:
        # INSERT new record
        insert_query = """
        INSERT INTO hearings (event_id, congress, chamber, title, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        params = (
            event_id,
            hearing_data.get('congress'),
            hearing_data.get('chamber'),
            hearing_data.get('title')
        )
        cursor = self.execute(insert_query, params)
        return cursor.lastrowid
```

### Creating Database Migrations

**Pattern**: Use numbered SQL files in `database/migrations/`

1. **Create migration**: `database/migrations/002_add_crs_reports.sql`

```sql
-- Migration 002: Add CRS reports table

CREATE TABLE IF NOT EXISTS crs_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_number TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    publish_date DATE,
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_crs_reports_number ON crs_reports(report_number);
CREATE INDEX idx_crs_reports_date ON crs_reports(publish_date);

-- Junction table for topics
CREATE TABLE IF NOT EXISTS crs_report_topics (
    report_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    PRIMARY KEY (report_id, topic),
    FOREIGN KEY (report_id) REFERENCES crs_reports(report_id) ON DELETE CASCADE
);
```

2. **Apply migration**:

```bash
sqlite3 database.db < database/migrations/002_add_crs_reports.sql
```

3. **Track in version control**: Commit migration file

---

## Testing

### Test Structure

```
tests/
├── __init__.py
├── conftest.py                      # Pytest fixtures
├── documents/                       # Document-related tests
│   ├── test_document_fetcher.py    # Unit tests
│   └── test_document_import.py     # Integration tests
├── security/                        # Security tests
│   └── test_input_validation.py
└── integration/                     # End-to-end tests
    └── test_full_import.py
```

### Writing Unit Tests

**Example**: Test HearingParser

Create `tests/parsers/test_hearing_parser.py`:

```python
import pytest
from parsers.hearing_parser import HearingParser
from parsers.models import HearingModel
from pydantic import ValidationError

class TestHearingParser:
    """Test HearingParser"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return HearingParser()

    @pytest.fixture
    def valid_api_data(self):
        """Sample valid API data"""
        return {
            'eventId': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Test Hearing on Important Topic',
            'date': '2025-10-15T10:00:00Z'
        }

    def test_parse_valid_data(self, parser, valid_api_data):
        """Test parsing valid API data"""
        result = parser.parse(valid_api_data)

        assert isinstance(result, HearingModel)
        assert result.event_id == 'LC12345'
        assert result.congress == 119
        assert result.chamber == 'House'
        assert result.title == 'Test Hearing on Important Topic'

    def test_parse_missing_required_field(self, parser):
        """Test parsing with missing required field"""
        invalid_data = {
            'eventId': 'LC12345',
            # Missing congress
            'chamber': 'House'
        }

        with pytest.raises(ValidationError):
            parser.parse(invalid_data)

    def test_parse_invalid_chamber(self, parser, valid_api_data):
        """Test parsing with invalid chamber"""
        valid_api_data['chamber'] = 'InvalidChamber'

        with pytest.raises(ValidationError):
            parser.parse(valid_api_data)
```

### Writing Integration Tests

**Example**: Test full document import flow

Create `tests/integration/test_document_import.py`:

```python
import pytest
from database.manager import DatabaseManager
from importers.orchestrator import ImportOrchestrator
from api.client import CongressAPIClient

class TestDocumentImport:
    """Test document import integration"""

    @pytest.fixture
    def db_manager(self, tmp_path):
        """Create temporary database"""
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        db.initialize_schema()
        return db

    @pytest.fixture
    def orchestrator(self, db_manager):
        """Create import orchestrator"""
        api_client = CongressAPIClient()
        return ImportOrchestrator(db_manager, api_client)

    def test_import_documents_for_hearing(self, orchestrator, db_manager):
        """Test importing documents for a hearing"""
        # Setup: Create test hearing
        hearing_data = {
            'event_id': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Test Hearing'
        }
        hearing_id = db_manager.upsert_hearing(hearing_data)

        # Execute: Import documents
        result = orchestrator.import_documents([hearing_id])

        # Verify: Check documents were imported
        transcripts = db_manager.fetch_all(
            "SELECT * FROM hearing_transcripts WHERE hearing_id = ?",
            (hearing_id,)
        )

        assert len(transcripts) > 0
        assert result['success'] is True
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/parsers/test_hearing_parser.py

# Run specific test method
pytest tests/parsers/test_hearing_parser.py::TestHearingParser::test_parse_valid_data

# Run with coverage
pytest --cov=. --cov-report=html

# Run with verbose output
pytest -v -s

# Run only integration tests
pytest -m integration

# Run only unit tests
pytest -m unit
```

---

## Code Style & Conventions

### Python Style Guide

Follow **PEP 8** with these specifics:

- **Line length**: 100 characters (not 79)
- **Indentation**: 4 spaces
- **Imports**: Organized (standard library, third-party, local)
- **Docstrings**: Google style
- **Type hints**: Use when helpful (not mandatory)

### Formatting with Black

```bash
# Format all Python files
black .

# Check what would be formatted
black --check .

# Format specific file
black cli.py
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `HearingFetcher`, `DatabaseManager` |
| Functions | snake_case | `fetch_hearings()`, `upsert_hearing()` |
| Variables | snake_case | `hearing_id`, `committee_name` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRIES`, `API_BASE_URL` |
| Private methods | _leading_underscore | `_parse_date()`, `_validate_data()` |
| Blueprints | snake_case with _bp | `hearings_bp`, `committees_bp` |

### Docstring Style

```python
def upsert_hearing(self, hearing_data: Dict[str, Any]) -> int:
    """
    Insert or update hearing record using proper UPDATE to avoid foreign key violations

    Args:
        hearing_data: Dictionary containing hearing fields
            - event_id (str): Congress.gov event ID (required)
            - congress (int): Congress number (required)
            - chamber (str): Chamber name (required)
            - title (str): Hearing title (optional)

    Returns:
        int: Hearing ID (primary key)

    Raises:
        ValueError: If required fields missing
        sqlite3.IntegrityError: If foreign key constraint fails

    Example:
        >>> db = DatabaseManager()
        >>> hearing_data = {
        ...     'event_id': 'LC12345',
        ...     'congress': 119,
        ...     'chamber': 'House',
        ...     'title': 'Test Hearing'
        ... }
        >>> hearing_id = db.upsert_hearing(hearing_data)
    """
    # Implementation
```

### Logging

Use structured logging with appropriate levels:

```python
from config.logging_config import get_logger

logger = get_logger(__name__)

# DEBUG: Detailed diagnostic information
logger.debug(f"Processing hearing {hearing_id} with {len(witnesses)} witnesses")

# INFO: General informational messages
logger.info(f"Imported {count} hearings successfully")

# WARNING: Non-critical issues
logger.warning(f"Missing title for hearing {hearing_id}, using default")

# ERROR: Errors that don't stop execution
logger.error(f"Failed to fetch hearing {event_id}: {e}")

# CRITICAL: Critical errors requiring immediate attention
logger.critical(f"Database connection lost: {e}")
```

---

## Common Development Tasks

### Task 1: Add a New API Endpoint

**Goal**: Create JSON API endpoint for witness search

1. **Edit** `web/blueprints/api.py`:

```python
@api_bp.route('/api/witnesses/search')
def search_witnesses():
    """Search witnesses by name or organization"""
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 50))

    if not query:
        return jsonify({'error': 'Query parameter required'}), 400

    with db.transaction() as conn:
        cursor = conn.execute('''
            SELECT w.witness_id, w.full_name, w.organization,
                   COUNT(wa.appearance_id) as appearance_count
            FROM witnesses w
            LEFT JOIN witness_appearances wa ON w.witness_id = wa.witness_id
            WHERE w.full_name LIKE ? OR w.organization LIKE ?
            GROUP BY w.witness_id
            ORDER BY appearance_count DESC
            LIMIT ?
        ''', (f'%{query}%', f'%{query}%', limit))

        results = [dict(row) for row in cursor.fetchall()]

    return jsonify({
        'query': query,
        'count': len(results),
        'witnesses': results
    })
```

2. **Test**:

```bash
curl "http://localhost:5001/api/witnesses/search?q=smith&limit=10"
```

### Task 2: Add Database Indexes for Performance

**Goal**: Speed up hearing searches by committee

1. **Create migration**: `database/migrations/003_add_committee_indexes.sql`

```sql
-- Add indexes for committee searches
CREATE INDEX IF NOT EXISTS idx_hearing_committees_committee
ON hearing_committees(committee_id);

CREATE INDEX IF NOT EXISTS idx_hearings_date_chamber
ON hearings(hearing_date_only, chamber);

CREATE INDEX IF NOT EXISTS idx_hearings_title
ON hearings(title);
```

2. **Apply migration**:

```bash
sqlite3 database.db < database/migrations/003_add_committee_indexes.sql
```

3. **Verify**:

```bash
sqlite3 database.db "EXPLAIN QUERY PLAN SELECT * FROM hearings WHERE title LIKE '%budget%'"
```

### Task 3: Add Custom Jinja Filter

**Goal**: Format hearing types nicely in templates

1. **Edit** `web/app.py`:

```python
@app.template_filter('format_hearing_type')
def format_hearing_type_filter(hearing_type):
    """Format hearing type for display"""
    type_mapping = {
        'Hearing': 'Public Hearing',
        'Meeting': 'Committee Meeting',
        'Markup': 'Bill Markup Session'
    }
    return type_mapping.get(hearing_type, hearing_type)
```

2. **Use in template**:

```html
<span class="hearing-type">{{ hearing.hearing_type | format_hearing_type }}</span>
```

### Task 4: Add Background Task Processing

**Goal**: Run long-running updates in background

1. **Install Redis** (for task queue):

```bash
brew install redis  # macOS
pip install celery redis
```

2. **Create Celery app**: `tasks/celery_app.py`

```python
from celery import Celery

app = Celery('hearing_database', broker='redis://localhost:6379/0')

@app.task
def run_incremental_update(lookback_days=7):
    """Background task for incremental update"""
    from updaters.daily_updater import DailyUpdater

    updater = DailyUpdater(lookback_days=lookback_days)
    result = updater.run_daily_update()
    return result
```

3. **Start worker**:

```bash
celery -A tasks.celery_app worker --loglevel=info
```

4. **Trigger task**:

```python
from tasks.celery_app import run_incremental_update

# Non-blocking
task = run_incremental_update.delay(lookback_days=7)

# Check status
task.ready()  # True if complete
task.result  # Get result
```

### Task 5: Add Database Backup Automation

**Goal**: Automatically backup database daily

1. **Create script**: `scripts/backup_database.py`

```python
#!/usr/bin/env python3
"""Backup database with timestamp"""
import shutil
from datetime import datetime
from pathlib import Path
from config.settings import settings

def backup_database():
    """Create timestamped database backup"""
    db_path = Path(settings.database_path)
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = backup_dir / f"database_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    print(f"Backup created: {backup_path}")

    # Clean up old backups (keep last 30)
    backups = sorted(backup_dir.glob('database_*.db'))
    for old_backup in backups[:-30]:
        old_backup.unlink()
        print(f"Deleted old backup: {old_backup}")

if __name__ == '__main__':
    backup_database()
```

2. **Schedule with cron**:

```bash
# Edit crontab
crontab -e

# Add daily backup at 3 AM
0 3 * * * cd /path/to/Hearing-Database && /path/to/venv/bin/python scripts/backup_database.py
```

---

## Debugging Tips

### Enable Debug Mode

```bash
# Flask debug mode (auto-reload, detailed errors)
python cli.py web serve --debug

# Verbose logging
LOG_LEVEL=DEBUG python cli.py update incremental --lookback-days 1
```

### Database Debugging

```bash
# Check database status
python cli.py database status

# Run integrity check
sqlite3 database.db "PRAGMA integrity_check;"

# Check foreign key violations
sqlite3 database.db "PRAGMA foreign_key_check;"

# Analyze query performance
sqlite3 database.db "EXPLAIN QUERY PLAN SELECT * FROM hearings WHERE chamber = 'House';"
```

### API Debugging

```bash
# Test API connectivity
python cli.py --config-check

# Test specific endpoint
curl -H "X-API-Key: YOUR_KEY" "https://api.congress.gov/v3/committee/119/house?limit=1"

# Check rate limit
curl -I -H "X-API-Key: YOUR_KEY" "https://api.congress.gov/v3/committee/119/house"
```

### Python Debugging

```python
# Use ipdb for interactive debugging
import ipdb; ipdb.set_trace()

# Or use pdb (built-in)
import pdb; pdb.set_trace()

# Print debugging
import pprint
pprint.pprint(hearing_data)
```

---

## Additional Resources

### Internal Documentation

- **[CLI Guide](CLI_GUIDE.md)** - Complete CLI command reference
- **[System Architecture](../../reference/architecture/SYSTEM_ARCHITECTURE.md)** - Detailed architecture
- **[Database Schema](../../reference/architecture/database-schema.md)** - Database structure
- **[Testing Guide](testing.md)** - Testing strategies and patterns

### External Resources

- **[Congress.gov API Docs](https://api.congress.gov/)** - API reference
- **[Flask Documentation](https://flask.palletsprojects.com/)** - Flask framework
- **[Pydantic Documentation](https://docs.pydantic.dev/)** - Data validation
- **[SQLite Documentation](https://www.sqlite.org/docs.html)** - Database reference
- **[Click Documentation](https://click.palletsprojects.com/)** - CLI framework
- **[Pytest Documentation](https://docs.pytest.org/)** - Testing framework

---

## Getting Help

### Troubleshooting

- **[Common Issues](../../troubleshooting/common-issues.md)** - Frequently encountered problems
- **[Debugging Guide](../../troubleshooting/debugging.md)** - Debugging techniques

### Contributing

1. Read this development guide
2. Set up development environment
3. Create feature branch
4. Write tests
5. Submit pull request

### Questions

- **GitHub Issues** - [Report bugs or ask questions](https://github.com/your-org/Hearing-Database/issues)
- **Documentation** - Check [docs/README.md](../../README.md) for complete documentation

---

**Last Updated**: October 9, 2025
**Version**: 2.0
**Maintainer**: Development Team

[← Back: CLI Guide](CLI_GUIDE.md) | [Up: Documentation Hub](../../README.md) | [Next: Testing Guide →](testing.md)
