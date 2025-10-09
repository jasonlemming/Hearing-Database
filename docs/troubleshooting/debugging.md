# Debugging Guide

Advanced debugging techniques for developers working on the Congressional Hearing Database.

## Enabling Debug Mode

### Application-Wide Debug Mode

```bash
# Set in .env file
LOG_LEVEL=DEBUG

# Or via environment variable
LOG_LEVEL=DEBUG python cli.py import full
```

### Flask Debug Mode

```bash
# For development only - never use in production
FLASK_DEBUG=1 python web/app.py
```

## Database Debugging

### Query Logging

Enable SQL query logging to see all database operations:

```python
import logging
logging.getLogger('database').setLevel(logging.DEBUG)
```

### Inspect Database State

```bash
# Open database in SQLite shell
sqlite3 database.db

# Check table structure
.schema hearings

# Count records
SELECT COUNT(*) FROM hearings;

# View recent errors
SELECT * FROM import_errors ORDER BY error_date DESC LIMIT 10;
```

### Common Diagnostic Queries

```sql
-- Find hearings with missing data
SELECT hearing_id, title,
       CASE WHEN video_url IS NULL THEN 'No video' ELSE 'Has video' END
FROM hearings
WHERE hearing_date_only >= date('now', '-30 days');

-- Check foreign key integrity
PRAGMA foreign_key_check;

-- View index usage
EXPLAIN QUERY PLAN
SELECT * FROM hearings WHERE chamber = 'House' ORDER BY hearing_date_only DESC;
```

## API Debugging

### Log API Requests

```python
# In api/congress_client.py, add logging
import logging
logger = logging.getLogger(__name__)
logger.debug(f"API Request: {url}")
logger.debug(f"Response: {response.status_code}")
```

### Test API Endpoints Directly

```bash
# Test Congress.gov API
curl -H "x-api-key: YOUR_KEY" \
  "https://api.congress.gov/v3/hearing?api_key=YOUR_KEY&limit=1"

# Test local API
curl http://localhost:5000/api/stats
curl http://localhost:5000/api/update-status
```

### Monitor Rate Limiting

```python
# Check rate limit headers in API responses
headers = response.headers
print(f"Rate Limit: {headers.get('X-RateLimit-Limit')}")
print(f"Remaining: {headers.get('X-RateLimit-Remaining')}")
```

## Import/Update Debugging

### Verbose Logging

```bash
# Full verbose output
python cli.py import full --congress 119 --verbose

# Dry run to see what would happen
python cli.py update incremental --dry-run
```

### Track Import Progress

```sql
-- View import history
SELECT * FROM sync_tracking ORDER BY sync_start DESC LIMIT 10;

-- Check recent errors
SELECT error_date, component, error_message
FROM import_errors
WHERE error_date >= date('now', '-7 days')
ORDER BY error_date DESC;
```

### Test Individual Components

```python
# Test fetcher in isolation
from fetchers.hearing_fetcher import HearingFetcher
from api.congress_client import CongressAPIClient

client = CongressAPIClient()
fetcher = HearingFetcher(client)
hearings = fetcher.fetch_hearings_by_congress(119, limit=5)
print(f"Fetched {len(hearings)} hearings")

# Test parser
from parsers.hearing_parser import HearingParser
parser = HearingParser()
result = parser.parse(hearings[0])
print(result)
```

## Web Interface Debugging

### Flask Debug Toolbar

Install and enable the Flask Debug Toolbar:

```bash
pip install flask-debugtoolbar
```

```python
# In web/app.py
from flask_debugtoolbar import DebugToolbarExtension

app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['DEBUG_TB_ENABLED'] = True
toolbar = DebugToolbarExtension(app)
```

### Template Debugging

```html
<!-- In templates, dump variables -->
<pre>{{ hearing | pprint }}</pre>

<!-- Check if variable exists -->
{% if hearing %}
  Hearing exists
{% else %}
  Hearing is None/missing
{% endif %}
```

### JavaScript Console

```javascript
// Add debug logging in static/js files
console.log('Filters:', filters);
console.log('Response:', response);

// Check for errors
window.addEventListener('error', (e) => {
  console.error('JavaScript Error:', e);
});
```

## Python Debugging Tools

### PDB (Python Debugger)

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use built-in breakpoint() (Python 3.7+)
breakpoint()

# Common PDB commands:
# n - next line
# s - step into function
# c - continue execution
# p variable_name - print variable
# l - list code around current line
```

### IPython for Interactive Debugging

```bash
pip install ipython
```

```python
from IPython import embed
embed()  # Drops into interactive shell at this point
```

### Logging Best Practices

```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed diagnostic information")
logger.info("Informational messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical issues")
```

## Performance Profiling

### Profile Python Code

```python
import cProfile
import pstats

# Profile a function
profiler = cProfile.Profile()
profiler.enable()

# Your code here
import_hearings()

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 slowest functions
```

### Profile Database Queries

```bash
# Enable SQLite query timing
sqlite3 database.db
.timer ON
SELECT * FROM hearings WHERE chamber = 'House';
```

### Monitor Memory Usage

```python
import tracemalloc

tracemalloc.start()

# Your code here
fetch_and_import_hearings()

current, peak = tracemalloc.get_traced_memory()
print(f"Current memory: {current / 10**6:.1f} MB")
print(f"Peak memory: {peak / 10**6:.1f} MB")
tracemalloc.stop()
```

## Network Debugging

### Monitor HTTP Traffic

```bash
# Use mitmproxy to inspect requests
pip install mitmproxy
mitmproxy

# Or use curl with verbose output
curl -v https://api.congress.gov/v3/hearing
```

### Test Connectivity

```python
import requests
import time

def test_api_connectivity():
    urls = [
        "https://api.congress.gov/v3/",
        "https://www.senate.gov/",
        "https://www.house.gov/"
    ]

    for url in urls:
        try:
            start = time.time()
            response = requests.get(url, timeout=5)
            duration = time.time() - start
            print(f"✓ {url}: {response.status_code} ({duration:.2f}s)")
        except Exception as e:
            print(f"✗ {url}: {e}")

test_api_connectivity()
```

## Common Debugging Scenarios

### "Why isn't this hearing showing up?"

1. Check if hearing exists: `SELECT * FROM hearings WHERE event_id = 'XXXXX';`
2. Verify it was fetched: Check sync_tracking for recent imports
3. Check for errors: `SELECT * FROM import_errors WHERE component LIKE '%hearing%';`
4. Test fetch directly: Use HearingFetcher with hearing_id

### "Why is the update taking so long?"

1. Enable verbose logging to see progress
2. Check API rate limiting headers
3. Profile the update process
4. Verify batch sizes aren't too large
5. Check network latency to Congress.gov

### "Why are witnesses missing?"

1. Check if witness data exists in API response
2. Verify WitnessParser is being called
3. Look for parsing errors in logs
4. Test parser with sample data
5. Check foreign key constraints

## Additional Resources

- **[Development Guide](../guides/developer/DEVELOPMENT.md)** - Development environment setup
- **[Testing Guide](../guides/developer/testing.md)** - Writing tests to prevent bugs
- **[Common Issues](common-issues.md)** - Frequently encountered problems
- **[Monitoring Guide](../guides/operations/MONITORING.md)** - Production monitoring

---

**Last Updated**: October 9, 2025
**Target Audience**: Developers and Contributors

[← Back: Common Issues](common-issues.md) | [Up: Documentation Hub](../README.md) | [Next: Development Guide →](../guides/developer/DEVELOPMENT.md)
