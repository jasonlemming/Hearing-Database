# Brookings Ingester - Quick Start Guide

Get up and running with the Brookings Content Ingestion System in 5 minutes.

## Prerequisites

- Python 3.9+
- pip package manager

## Step 1: Install Dependencies (1 min)

```bash
cd /path/to/Hearing-Database
pip install -r requirements.txt
```

## Step 2: Initialize Database (30 seconds)

```bash
python -m brookings_ingester.init_db
```

Expected output:
```
======================================================================
Brookings Ingestion System - Database Initialization
======================================================================

Creating storage directories...
✓ PDF storage: /path/to/data/pdfs
✓ Text storage: /path/to/data/text
✓ HTML storage: /path/to/data/html

Initializing database: sqlite:///data/brookings.db
✓ Database tables created

Seeding sources...
✓ Created source: CRS
✓ Created source: BROOKINGS
✓ Created source: GAO

Seeding organizations...
✓ Created organization: Brookings Institution
✓ Created organization: Congressional Research Service
✓ Created organization: Government Accountability Office

======================================================================
Initialization Complete!
  Sources: 3
  Organizations: 3
  Database: sqlite:///data/brookings.db
======================================================================
```

## Step 3: Test Ingestion (2 min)

Run a test with 5 documents to validate the system:

```bash
python -m brookings_ingester.test_ingestion --limit 5
```

This will:
1. Test document discovery via WordPress API
2. Test fetching and parsing a single document
3. Run full ingestion pipeline with 5 documents

Expected output:
```
======================================================================
Brookings Ingestion System - Test Suite
======================================================================
Database: sqlite:///data/brookings.db
Test mode: all
Limit: 5

======================================================================
TEST 1: Document Discovery (method=api)
======================================================================

✓ Discovered 5 documents

Sample documents:

1. The future of AI governance
   URL: https://www.brookings.edu/articles/...
   Identifier: the-future-of-ai-governance
   Date: 2025-01-15

...

======================================================================
TEST 2: Single Document Fetch & Parse
======================================================================

Testing with: https://www.brookings.edu/articles/...

Fetching content...
✓ Fetched HTML (45,234 bytes)
✓ Downloaded PDF (892,451 bytes)

Parsing content...
✓ Parsed document
  Title: The future of AI governance
  Type: article
  Authors: Jane Smith, John Doe
  Subjects: Artificial Intelligence, Technology Policy
  Word count: 3,245
  Publication date: 2025-01-15

======================================================================
TEST 3: Full Ingestion Pipeline (limit=5)
======================================================================

Ingesting documents: 100%|████████████| 5/5 [00:15<00:00,  3.2s/doc]

✓ Ingestion completed successfully

Statistics:
  Checked: 5
  Fetched: 5
  Updated: 0
  Skipped: 0
  Errors: 0
  Total size: 4.2 MB

======================================================================
Test Summary
======================================================================
discovery       ✓ PASS
single          ✓ PASS
full            ✓ PASS
======================================================================

🎉 All tests passed!

Next steps:
  1. Review ingested documents in database
  2. Run full backfill: python cli.py brookings backfill --limit 100
  3. Implement search functionality
```

## Step 4: Ingest More Documents (Optional)

### Option A: Programmatic

```python
from brookings_ingester.ingesters import BrookingsIngester

ingester = BrookingsIngester()

# Ingest 100 documents from 2025
result = ingester.run_ingestion(
    limit=100,
    skip_existing=True,
    run_type='backfill',
    method='api',
    since_date='2025-01-01'
)

print(f"Fetched: {result['stats']['documents_fetched']}")
print(f"Errors: {result['stats']['errors_count']}")
```

### Option B: CLI Integration (Advanced)

1. Follow instructions in `cli_brookings_commands.txt`
2. Add imports and command group to `cli.py`
3. Run:

```bash
python cli.py brookings backfill --limit 100 --since-date 2025-01-01
python cli.py brookings stats
```

## Step 5: Query the Database

```python
from brookings_ingester.models import get_session, Document

session = get_session()

# Get recent documents
recent = session.query(Document).order_by(
    Document.publication_date.desc()
).limit(10).all()

for doc in recent:
    print(f"{doc.title} ({doc.publication_date})")
    print(f"  Type: {doc.document_type}")
    print(f"  Words: {doc.word_count:,}")
    print(f"  URL: {doc.url}")
    print()

session.close()
```

## Common Commands

### Test specific component
```bash
# Test discovery only
python -m brookings_ingester.test_ingestion --test discovery --limit 10

# Test single document
python -m brookings_ingester.test_ingestion --test single \
  --url https://www.brookings.edu/articles/example-article/

# Test full pipeline
python -m brookings_ingester.test_ingestion --test full --limit 5
```

### Discovery methods
```bash
# WordPress API (recommended)
python -m brookings_ingester.test_ingestion --method api --limit 20

# Sitemap
python -m brookings_ingester.test_ingestion --method sitemap --limit 20

# Both
python -m brookings_ingester.test_ingestion --method both --limit 50
```

## Verify Everything Works

```bash
# Check database was created
ls -lh data/brookings.db

# Check storage directories exist
ls -la data/pdfs/
ls -la data/text/
ls -la data/html/

# Count ingested documents
python -c "from brookings_ingester.models import get_session, Document; \
session = get_session(); \
print(f'Documents: {session.query(Document).count()}'); \
session.close()"
```

## Troubleshooting

### "ModuleNotFoundError: No module named 'brookings_ingester'"

Make sure you're in the correct directory:
```bash
cd /Users/jasonlemons/Documents/GitHub/Hearing-Database
python -m brookings_ingester.init_db
```

### "No such module: fts5"

Your SQLite version is too old. Check version:
```bash
python -c "import sqlite3; print(sqlite3.sqlite_version)"
```

If < 3.35, either upgrade SQLite or use PostgreSQL:
```bash
export DATABASE_URL="postgresql://localhost/brookings"
python -m brookings_ingester.init_db
```

### "Failed to fetch content"

- Check internet connection
- Verify you can access https://www.brookings.edu in browser
- Rate limiting may be active (normal delay is 1.5s between requests)

### Test fails but no specific error

Run with verbose output:
```bash
python -m brookings_ingester.test_ingestion --limit 1 2>&1 | tee test_output.log
```

## Next Steps

Once you've successfully run the test ingestion:

1. **Review the data**: Explore the database to see ingested documents
2. **Scale up**: Run larger backfills (100-1,000 documents)
3. **Integrate with CLI**: Add commands to main cli.py
4. **Implement search**: Build search functionality using FTS
5. **Automate updates**: Set up scheduled ingestion runs

## Performance Expectations

With default settings (1.5s delay between requests):

- **Discovery**: Instant (API returns 100 documents per call)
- **Ingestion**: ~1,500-2,000 documents/hour
- **Storage**: ~300-700 MB per 1,000 documents

For 10,000 documents:
- **Time**: ~5-7 hours
- **Storage**: ~3-7 GB total

## Getting Help

- Read the full **README.md** for detailed documentation
- Check **INVESTIGATION_FINDINGS.md** for implementation details
- Review **SCHEMA_DESIGN.md** for database architecture
- Examine test output for validation examples

## Success Criteria

You've successfully set up the system when:

✅ Database initialized without errors
✅ Test ingestion passes all 3 tests
✅ Documents appear in database
✅ PDF files downloaded to data/pdfs/
✅ Text extracted to data/text/
✅ No errors in logs

**Congratulations!** You're ready to start ingesting Brookings content at scale.
