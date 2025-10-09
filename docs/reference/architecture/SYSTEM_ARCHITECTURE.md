# Congressional Hearing Database - System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface Layer                    │
├─────────────────────────────────────────────────────────────────┤
│  Flask Web Application (web/app.py)                             │
│  ├── Routes & Controllers                                       │
│  ├── Template Rendering (Jinja2)                               │
│  ├── Request/Response Handling                                 │
│  └── Static Assets (Bootstrap, FontAwesome)                    │
├─────────────────────────────────────────────────────────────────┤
│                      Business Logic Layer                       │
├─────────────────────────────────────────────────────────────────┤
│  Database Manager (database/manager.py)                        │
│  ├── Connection Management                                     │
│  ├── Transaction Handling                                      │
│  ├── Query Optimization                                        │
│  └── Data Access Abstraction                                   │
├─────────────────────────────────────────────────────────────────┤
│                        Data Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  SQLite Database (data/congressional_hearings.db)              │
│  ├── 17 Normalized Tables                                      │
│  ├── Foreign Key Constraints                                   │
│  ├── Indexes for Performance                                   │
│  └── ACID Compliance                                            │
├─────────────────────────────────────────────────────────────────┤
│                    External Integration Layer                   │
├─────────────────────────────────────────────────────────────────┤
│  Congress.gov API Client                                       │
│  ├── Rate Limiting (5000/hour)                                 │
│  ├── Authentication Management                                 │
│  ├── Error Handling & Retries                                  │
│  └── Data Fetching & Parsing                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Web Application Layer (`web/`)

#### Core Components
- **`app.py`**: Main Flask application with route definitions
- **Templates**: Jinja2 templates for HTML rendering
- **Static Assets**: CSS, JavaScript, and images

#### Route Structure
```python
@app.route('/')                          # → Redirect to /hearings
@app.route('/hearings')                  # → Main hearings listing
@app.route('/hearing/<int:hearing_id>')  # → Individual hearing details
@app.route('/committees')                # → Committee browser
@app.route('/committee/<int:id>')        # → Committee details
@app.route('/members')                   # → Member listings
@app.route('/search')                    # → Global search
@app.route('/api/stats')                 # → Database statistics API
```

#### Template Hierarchy
```
base.html                    # Base template with navigation
├── hearings.html           # Main listings page (homepage)
├── hearing_detail.html     # Individual hearing view
├── committees.html         # Committee browser with hierarchy
├── committee_detail.html   # Committee-specific view
├── members.html           # Member listings with filters
└── search.html            # Global search interface
```

### 2. Database Layer

#### Schema Overview (17 Tables)

##### Core Entities
```sql
-- Government Structure
committees              # Congressional committees and subcommittees
members                # Representatives and Senators
committee_memberships  # Member-committee relationships

-- Legislative Activities
hearings               # Committee meetings and hearings
hearing_committees     # Hearing-committee relationships
bills                  # Legislation referenced in hearings
hearing_bills          # Hearing-bill relationships

-- Hearing Participants
witnesses              # Individuals testifying
witness_appearances    # Witness-hearing relationships
documents             # Transcripts and materials
hearing_documents     # Document-hearing relationships

-- Supporting Data
policy_areas          # Subject categorization
hearing_policy_areas  # Hearing-policy relationships
locations             # Hearing venues
member_leadership     # Leadership positions

-- System Tables
sync_tracking         # Import synchronization
import_errors         # Error logging
```

##### Key Relationships
```
Committees (1) ←→ (N) Committee_Memberships (N) ←→ (1) Members
Committees (1) ←→ (N) Hearing_Committees (N) ←→ (1) Hearings
Hearings (1) ←→ (N) Witness_Appearances (N) ←→ (1) Witnesses
Hearings (1) ←→ (N) Hearing_Documents (N) ←→ (1) Documents
Hearings (1) ←→ (N) Hearing_Bills (N) ←→ (1) Bills
```

#### Database Manager (`database/manager.py`)
```python
class DatabaseManager:
    def __init__(self, db_path=None)
    def get_connection(self)                    # Connection factory
    def transaction(self)                       # Transaction context manager
    def execute_script(self, script_path)       # Schema management
    def backup_database(self, backup_path)      # Data protection
```

### 3. Data Import Pipeline

#### Import Architecture
```
Congress.gov API
        ↓
   API Client (api/)
        ↓
   Rate Limiter
        ↓
   Data Fetchers (fetchers/)
        ↓
   Data Parsers (parsers/)
        ↓
   Data Validators
        ↓
   Batch Processors
        ↓
   Database Writers
        ↓
   SQLite Database
```

#### Key Import Components

##### API Client (`api/client.py`)
```python
class CongressApiClient:
    def __init__(self, api_key, base_url)
    def get(self, endpoint, params=None)        # HTTP GET with retries
    def _make_request(self, url, params)        # Core request handler
    def _handle_rate_limit(self, response)      # Rate limit management
```

##### Fetchers (`fetchers/`)
- **`committee_fetcher.py`**: Committee and subcommittee data
- **`member_fetcher.py`**: Congressional member information
- **`hearing_fetcher.py`**: Hearing metadata and details
- **`bill_fetcher.py`**: Legislation referenced in hearings
- **`document_fetcher.py`**: Transcripts and supporting materials

##### Parsers (`parsers/`)
- **`committee_parser.py`**: Committee data validation
- **`member_parser.py`**: Member information parsing
- **`hearing_parser.py`**: Hearing metadata extraction
- **Data validation with strict/lenient modes**

##### Import Orchestration (`importers/`)
```python
class ImportOrchestrator:
    def run_import(self, phases=None)           # Main import controller
    def import_committees(self)                 # Committee import phase
    def import_members(self)                    # Member import phase
    def import_hearings(self)                   # Hearing import phase
    def create_checkpoint(self, phase)          # Resume capability
```

### 4. Configuration Management

#### Environment Configuration
```bash
# Core API Settings
CONGRESS_API_KEY=your_api_key_here
TARGET_CONGRESS=119
API_BASE_URL=https://api.congress.gov/v3

# Database Configuration
DATABASE_PATH=data/congressional_hearings.db
BATCH_SIZE=50
VALIDATION_MODE=false

# Import Behavior
MAX_RETRIES=3
RETRY_DELAY=5
CHECKPOINT_ENABLED=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/import.log
```

#### Runtime Configuration (`config/settings.py`)
```python
class Settings:
    API_KEY: str
    DATABASE_PATH: str
    BATCH_SIZE: int = 50
    VALIDATION_MODE: bool = False
    MAX_RETRIES: int = 3

    @classmethod
    def from_env(cls)                           # Environment loading
```

### 5. Web Interface Architecture

#### Frontend Technology Stack
- **Bootstrap 5**: Responsive CSS framework
- **Font Awesome 6**: Icon library
- **jQuery**: JavaScript utilities
- **Custom CSS**: Muted color palette, responsive design

#### UI Component Structure
```
Navigation Bar
├── Brand Link (→ hearings)
├── Primary Navigation
│   ├── Hearings (homepage)
│   ├── Committees
│   └── Members
└── Search Form

Content Area
├── Page Header
├── Filters & Search
├── Data Tables
│   ├── Sortable Headers
│   ├── Clickable Rows
│   └── Pagination Controls
└── Action Buttons
```

#### Data Flow in Web Interface
```
User Request
    ↓
Flask Route Handler
    ↓
Parameter Extraction & Validation
    ↓
Database Query Construction
    ↓
DatabaseManager.transaction()
    ↓
SQL Execution
    ↓
Result Processing
    ↓
Template Rendering
    ↓
HTML Response
```

### 6. Search and Filtering Architecture

#### Search Implementation
```python
# Multi-table search with JOIN operations
def global_search(query):
    # Search committees by name
    # Search hearings by title
    # Search members by name
    # Return categorized results

# Filtered queries with preserved parameters
def filtered_hearings(search, chamber, committee, sort, order):
    # Build dynamic WHERE clauses
    # Apply sorting with proper NULL handling
    # Implement pagination
    # Preserve filter state across pages
```

#### Sorting System
```python
sort_columns = {
    'title': 'h.title',
    'committee': 'COALESCE(parent.name, c.name)',
    'date': 'h.hearing_date_only',
    'chamber': 'h.chamber',
    'status': 'h.status'
}

# Dynamic ORDER BY with NULL handling
# Bi-directional sorting (ASC/DESC)
# Visual indicators in templates
```

### 7. Performance Considerations

#### Database Optimization
```sql
-- Key indexes for query performance
CREATE INDEX idx_hearings_date ON hearings(hearing_date_only);
CREATE INDEX idx_hearings_chamber ON hearings(chamber);
CREATE INDEX idx_committee_memberships_active ON committee_memberships(is_active);
CREATE INDEX idx_hearing_committees_primary ON hearing_committees(is_primary);

-- Query optimization techniques
-- Use of COALESCE for hierarchy queries
-- DISTINCT handling for aggregate functions
-- Proper JOIN order for performance
```

#### Caching Strategy
- **Template caching**: Jinja2 template compilation
- **Database connections**: Connection reuse within requests
- **Static assets**: Browser caching headers
- **Query result caching**: Future enhancement opportunity

### 8. Security Architecture

#### Current Security Measures
- **SQL Injection Protection**: Parameterized queries throughout
- **Input Validation**: Form data sanitization
- **Error Handling**: No sensitive data in error messages
- **Access Control**: Public data model (appropriate for congressional data)

#### Future Security Enhancements
- **CSRF Protection**: Flask-WTF integration
- **Rate Limiting**: Request throttling
- **Input Sanitization**: Enhanced XSS protection
- **Authentication**: User management system

### 9. Error Handling and Logging

#### Error Management Strategy
```python
# Three-tier error handling
try:
    # Primary operation
    result = perform_operation()
except SpecificException as e:
    # Handle known issues
    log_error(e, context)
    return fallback_response()
except Exception as e:
    # Handle unexpected issues
    log_critical_error(e, context)
    return error_response()
```

#### Logging Architecture
```
Application Logs
├── Database Operations
├── API Interactions
├── Import Progress
├── Error Details
└── Performance Metrics

Database Error Log
├── Import Errors Table
├── Validation Failures
├── Data Quality Issues
└── Resolution Tracking
```

### 10. Deployment Architecture

#### Current Deployment Model
- **Development Environment**: Local SQLite database
- **Single-user Focus**: Research and analysis use case
- **Manual Deployment**: Direct file system access

#### Production Deployment Considerations
```
Load Balancer
    ↓
Web Server (Nginx/Apache)
    ↓
WSGI Server (Gunicorn/uWSGI)
    ↓
Flask Application
    ↓
Database Server (PostgreSQL/MySQL)
    ↓
Redis Cache
```

### 11. Data Pipeline Architecture

#### ETL Process Flow
```
Extract (E)
├── Congress.gov API Calls
├── Rate-limited Requests
├── JSON Response Handling
└── Error Recovery

Transform (T)
├── Data Validation
├── Field Mapping
├── Relationship Resolution
└── Data Enrichment

Load (L)
├── Batch Processing
├── Transaction Management
├── Constraint Checking
└── Index Updates
```

#### Import Phases
1. **Infrastructure**: Database schema and indexes
2. **Reference Data**: Committees and members
3. **Core Data**: Hearings and relationships
4. **Extended Data**: Bills, witnesses, documents
5. **Enrichment**: Policy areas and metadata

This architecture supports the current research-focused use case while providing a foundation for scaling to production deployment with multiple users and real-time updates.

---

**Last Updated**: October 9, 2025
**Architecture Version**: 2.0
**Components**: API Client, Fetchers, Parsers, Database, Web Interface

[← Back: Documentation Hub](../../README.md) | [Up: Reference](../) | [Next: Database Schema →](database-schema.md)