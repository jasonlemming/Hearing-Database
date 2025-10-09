# Congressional Hearing Database - API Reference

Complete reference for the JSON API endpoints and programmatic database access.

## Base URL

**Local Development**: `http://localhost:5000`
**Production**: Your Vercel deployment URL

## Authentication

Currently no authentication required - all endpoints are public read-only.

## API Endpoints

### Database Statistics

Get current database statistics and counts.

```http
GET /api/stats
```

**Response**:
```json
{
  "committees": 214,
  "members": 538,
  "hearings": 1168,
  "hearing_committees": 1245,
  "policy_areas": 156
}
```

**Status Codes**:
- `200 OK` - Success
- `500 Internal Server Error` - Database error

**Example**:
```bash
curl http://localhost:5000/api/stats
```

**Use Cases**:
- Dashboard metrics
- Data completeness monitoring
- System health checks

---

### Update Status

Get daily update status and recent update history.

```http
GET /api/update-status
```

**Response**:
```json
{
  "status": "updated_today",
  "last_update": {
    "date": "2025-10-04",
    "start_time": "2025-10-04T06:00:15",
    "end_time": "2025-10-04T06:08:42",
    "duration_seconds": 507,
    "hearings_checked": 245,
    "hearings_updated": 12,
    "hearings_added": 3,
    "success": true
  },
  "recent_updates": [
    {
      "date": "2025-10-04",
      "start_time": "2025-10-04T06:00:15",
      "end_time": "2025-10-04T06:08:42",
      "duration_seconds": 507,
      "hearings_checked": 245,
      "hearings_updated": 12,
      "hearings_added": 3,
      "committees_updated": 2,
      "witnesses_updated": 8,
      "api_requests": 287,
      "error_count": 1,
      "success": true
    }
  ],
  "total_recent_updates": 7
}
```

**Status Values**:
- `updated_today` - Update completed today
- `last_update_successful` - Last update succeeded (not today)
- `last_update_failed` - Last update failed
- `no_logs` - No update logs found
- `unknown` - Status cannot be determined

**Status Codes**:
- `200 OK` - Success
- `500 Internal Server Error` - Database error

**Example**:
```bash
curl http://localhost:5000/api/update-status
```

**Use Cases**:
- Monitor daily update health
- Display last update time on dashboards
- Alert on update failures
- Track update performance trends

---

### System Debug

Get system diagnostic information (useful for troubleshooting).

```http
GET /api/debug
```

**Response**:
```json
{
  "cwd": "/Users/username/Hearing-Database",
  "path": ["/Users/username/Hearing-Database", "/usr/local/lib/python3.9/site-packages", "..."],
  "db_path": "database.db",
  "db_exists": true,
  "files_in_root": ["api", "config", "database", "web", "..."],
  "python_version": "3.9.7 (default, Sep 16 2021, 13:09:58)...",
  "tables": ["hearings", "committees", "witnesses", "..."]
}
```

**Status Codes**:
- `200 OK` - Success

**Example**:
```bash
curl http://localhost:5000/api/debug
```

**Use Cases**:
- Troubleshoot deployment issues
- Verify database connectivity
- Check file structure
- Diagnose path problems

---

## Direct Database Access

For advanced queries, access the SQLite database directly.

### Connection

```python
import sqlite3

conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row  # Access columns by name
cursor = conn.cursor()
```

### Example Queries

#### Get Recent Hearings

```sql
SELECT
    h.hearing_id,
    h.title,
    h.hearing_date_only,
    h.chamber,
    c.name as committee_name
FROM hearings h
LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
LEFT JOIN committees c ON hc.committee_id = c.committee_id
WHERE h.hearing_date_only >= date('now', '-30 days')
ORDER BY h.hearing_date_only DESC
LIMIT 20;
```

#### Find Hearings by Topic

```sql
SELECT
    h.hearing_id,
    h.title,
    h.hearing_date_only,
    c.name as committee_name
FROM hearings h
LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
LEFT JOIN committees c ON hc.committee_id = c.committee_id
WHERE h.title LIKE '%climate%'
ORDER BY h.hearing_date_only DESC;
```

#### Get Witness Testimony History

```sql
SELECT
    w.full_name,
    w.organization,
    w.witness_type,
    h.title as hearing_title,
    h.hearing_date_only,
    c.name as committee_name
FROM witnesses w
JOIN witness_appearances wa ON w.witness_id = wa.witness_id
JOIN hearings h ON wa.hearing_id = h.hearing_id
LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
LEFT JOIN committees c ON hc.committee_id = c.committee_id
WHERE w.full_name LIKE '%Smith%'
ORDER BY h.hearing_date_only DESC;
```

#### Count Hearings by Committee

```sql
SELECT
    c.name,
    c.chamber,
    COUNT(hc.hearing_id) as hearing_count
FROM committees c
LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
WHERE c.parent_committee_id IS NULL  -- Parent committees only
GROUP BY c.committee_id, c.name, c.chamber
HAVING hearing_count > 0
ORDER BY hearing_count DESC
LIMIT 20;
```

#### Get Witness Appearances by Organization Type

```sql
SELECT
    wa.witness_type,
    COUNT(DISTINCT wa.witness_id) as unique_witnesses,
    COUNT(*) as total_appearances
FROM witness_appearances wa
GROUP BY wa.witness_type
ORDER BY total_appearances DESC;
```

#### Find Committee Membership

```sql
SELECT
    c.name as committee_name,
    m.full_name,
    m.party,
    m.state,
    cm.role
FROM committees c
JOIN committee_memberships cm ON c.committee_id = cm.committee_id
JOIN members m ON cm.member_id = m.member_id
WHERE c.system_code = 'hsif00'  -- Energy and Commerce
    AND cm.is_active = 1
ORDER BY
    CASE cm.role
        WHEN 'Chair' THEN 1
        WHEN 'Ranking Member' THEN 2
        ELSE 3
    END,
    m.last_name;
```

## Database Schema

### Core Tables

#### hearings

```sql
CREATE TABLE hearings (
    hearing_id INTEGER PRIMARY KEY,
    event_id TEXT,
    congress INTEGER,
    chamber TEXT,
    title TEXT,
    hearing_date_only DATE,
    hearing_time TEXT,
    location TEXT,
    status TEXT,
    hearing_type TEXT,
    url TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### committees

```sql
CREATE TABLE committees (
    committee_id INTEGER PRIMARY KEY,
    system_code TEXT UNIQUE,
    name TEXT,
    chamber TEXT,
    committee_type TEXT,
    parent_committee_id INTEGER,
    url TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (parent_committee_id) REFERENCES committees(committee_id)
);
```

#### witnesses

```sql
CREATE TABLE witnesses (
    witness_id INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT NOT NULL,
    title TEXT,
    organization TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### members

```sql
CREATE TABLE members (
    member_id INTEGER PRIMARY KEY,
    bioguide_id TEXT UNIQUE,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    party TEXT,
    state TEXT,
    district TEXT,
    chamber TEXT,
    url TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Relationship Tables

#### hearing_committees

```sql
CREATE TABLE hearing_committees (
    hearing_id INTEGER,
    committee_id INTEGER,
    is_primary BOOLEAN DEFAULT 0,
    PRIMARY KEY (hearing_id, committee_id),
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id)
);
```

#### witness_appearances

```sql
CREATE TABLE witness_appearances (
    appearance_id INTEGER PRIMARY KEY,
    hearing_id INTEGER,
    witness_id INTEGER,
    witness_type TEXT,
    position INTEGER,
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (witness_id) REFERENCES witnesses(witness_id)
);
```

#### committee_memberships

```sql
CREATE TABLE committee_memberships (
    membership_id INTEGER PRIMARY KEY,
    committee_id INTEGER,
    member_id INTEGER,
    role TEXT,
    is_active BOOLEAN DEFAULT 1,
    start_date DATE,
    end_date DATE,
    FOREIGN KEY (committee_id) REFERENCES committees(committee_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);
```

### Document Tables

#### hearing_transcripts

```sql
CREATE TABLE hearing_transcripts (
    transcript_id INTEGER PRIMARY KEY,
    hearing_id INTEGER NOT NULL,
    jacket_number TEXT,
    title TEXT,
    document_url TEXT,
    pdf_url TEXT,
    html_url TEXT,
    format_type TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
);
```

#### witness_documents

```sql
CREATE TABLE witness_documents (
    document_id INTEGER PRIMARY KEY,
    hearing_id INTEGER,
    witness_id INTEGER,
    title TEXT,
    document_url TEXT,
    pdf_url TEXT,
    html_url TEXT,
    document_type TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id),
    FOREIGN KEY (witness_id) REFERENCES witnesses(witness_id)
);
```

## Python Client Example

```python
import requests
import sqlite3
from typing import Dict, List

class HearingDatabaseClient:
    """Client for Congressional Hearing Database API"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')

    def get_stats(self) -> Dict:
        """Get database statistics"""
        response = requests.get(f"{self.base_url}/api/stats")
        response.raise_for_status()
        return response.json()

    def get_update_status(self) -> Dict:
        """Get update status and history"""
        response = requests.get(f"{self.base_url}/api/update-status")
        response.raise_for_status()
        return response.json()

    def get_debug_info(self) -> Dict:
        """Get system debug information"""
        response = requests.get(f"{self.base_url}/api/debug")
        response.raise_for_status()
        return response.json()

class DatabaseQuery:
    """Direct database query interface"""

    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute SQL query and return results as list of dicts"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return results

    def get_recent_hearings(self, days: int = 30) -> List[Dict]:
        """Get hearings from last N days"""
        query = """
            SELECT
                h.hearing_id,
                h.title,
                h.hearing_date_only,
                h.chamber,
                c.name as committee_name
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            LEFT JOIN committees c ON hc.committee_id = c.committee_id
            WHERE h.hearing_date_only >= date('now', '-' || ? || ' days')
            ORDER BY h.hearing_date_only DESC
        """
        return self.execute_query(query, (days,))

    def search_hearings(self, keyword: str) -> List[Dict]:
        """Search hearings by keyword in title"""
        query = """
            SELECT
                h.hearing_id,
                h.title,
                h.hearing_date_only,
                h.chamber
            FROM hearings h
            WHERE h.title LIKE ?
            ORDER BY h.hearing_date_only DESC
        """
        return self.execute_query(query, (f'%{keyword}%',))

# Usage Example
if __name__ == "__main__":
    # API Client
    client = HearingDatabaseClient()
    stats = client.get_stats()
    print(f"Total hearings: {stats['hearings']}")

    # Database Query
    db = DatabaseQuery()
    recent = db.get_recent_hearings(7)
    print(f"Hearings in last 7 days: {len(recent)}")

    climate_hearings = db.search_hearings("climate")
    for hearing in climate_hearings[:5]:
        print(f"{hearing['hearing_date_only']}: {hearing['title']}")
```

## Rate Limiting

**Current**: No rate limiting on API endpoints

**Recommendations**:
- Be respectful with request frequency
- Cache responses when appropriate
- For bulk queries, use direct database access

## CORS

**Current**: CORS not explicitly configured

**For Cross-Origin Access**:
- Run your own instance
- Request CORS headers if needed (can be added)

## Future API Enhancements

Potential future endpoints:

- `GET /api/hearings` - Paginated hearing list with filtering
- `GET /api/hearings/{id}` - Hearing details
- `GET /api/witnesses` - Witness list
- `GET /api/committees` - Committee list
- `GET /api/search` - Unified search endpoint
- `POST /api/export` - Data export (CSV/JSON)

## Support

For API questions or feature requests:

- **GitHub Issues**: Report bugs or suggest endpoints
- **Documentation**: Check other docs for context
- **Database Schema**: Query information_schema for details

---

**Note**: The API is read-only and public. All data comes from Congress.gov and is updated daily.
