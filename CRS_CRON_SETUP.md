# CRS Library Automated Update Setup

This document describes the automated cron job setup for updating CRS (Congressional Research Service) report content from congress.gov.

## Overview

The CRS library auto-update system fetches HTML content for CRS reports from congress.gov and stores it in the database with version tracking. This runs daily via Vercel Cron.

## Architecture

### Components

1. **CRSUpdater** (`updaters/crs_updater.py`)
   - Main update orchestrator
   - Checks for products needing updates
   - Coordinates fetching, parsing, and storage
   - Tracks metrics and logs results

2. **CRSContentFetcher** (`fetchers/crs_content_fetcher.py`)
   - Fetches HTML content from congress.gov
   - Implements rate limiting (2 requests/second)
   - Supports both HTTP and headless browser fetching (for Cloudflare bypass)
   - Tracks fetch statistics

3. **CRSHTMLParser** (`parsers/crs_html_parser.py`)
   - Parses congress.gov HTML pages
   - Extracts clean content and document structure
   - Generates content hashes for change detection
   - Calculates word counts

4. **CRSContentManager** (`database/crs_content_manager.py`)
   - Database operations for CRS content
   - Version tracking and management
   - R2 blob storage integration
   - Ingestion logging

### Cron Endpoint

**URL**: `/api/cron/crs-library-update`

**Schedule**: Daily at 8:00 AM UTC (via Vercel Cron)

**Configuration**:
```json
{
  "lookback_days": 30,    // Check last 30 days for updates
  "max_products": 100     // Update up to 100 products per run
}
```

## Database Schema

**⚠️ IMPORTANT: CRS Library now uses PostgreSQL (Neon) instead of SQLite**

The CRS library has been migrated from SQLite to PostgreSQL for production use with Neon database. The system now uses `database/crs_content_manager_postgres.py` which provides:

- Full PostgreSQL compatibility
- Connection pooling via `postgres_config.py`
- Native JSONB support for structure data
- PostgreSQL full-text search (ts_vector) instead of FTS5
- Better concurrent write performance
- Automatic trigger-based search vector updates

### Migration Setup

Before running CRS updates, apply the PostgreSQL migrations:

```bash
# Apply initial schema (if not already done)
psql $DATABASE_URL -f database/migrations/postgres_001_initial_schema.sql

# Apply CRS enhancements (adds missing fields for scraper compatibility)
psql $DATABASE_URL -f database/migrations/postgres_003_crs_enhancements.sql
```

The CRS content is stored in these tables (PostgreSQL):

### product_versions
- `version_id` - Primary key
- `product_id` - Links to products table
- `version_number` - Version number from CRS
- `html_content` - Cleaned HTML content
- `text_content` - Plain text for full-text search
- `structure_json` - JSON with TOC, sections, headings
- `html_url` - Source URL from congress.gov
- `content_hash` - SHA256 hash for change detection
- `word_count` - Word count
- `blob_url` - R2 storage URL for HTML
- `ingested_at` - Timestamp
- `is_current` - Boolean (only one per product)

### content_ingestion_logs
- `log_id` - Primary key
- `run_type` - 'backfill', 'update', 'manual'
- `started_at` / `completed_at` - Timestamps
- `products_checked` - Number of products evaluated
- `content_fetched` - New versions added
- `content_updated` - Existing versions updated
- `content_skipped` - Skipped (no change)
- `errors_count` - Error count
- `status` - 'running', 'completed', 'failed', 'partial'
- `error_details` - JSON array of errors
- `total_size_bytes` - Total size fetched
- `avg_fetch_time_ms` - Average fetch time
- `total_duration_seconds` - Total run time

## Deployment

### Vercel Configuration

The cron job is configured in `vercel.json`:

```json
{
  "routes": [
    {
      "src": "/api/cron/crs-library-update",
      "dest": "api/cron-update.py"
    }
  ],
  "crons": [
    {
      "path": "/api/cron/crs-library-update",
      "schedule": "0 8 * * *"
    }
  ]
}
```

### Environment Variables Required

- `DATABASE_URL` or `CRS_DATABASE_URL` - **PostgreSQL connection string (Neon)**
  - Example: `postgresql://user:password@host/database?sslmode=require`
  - The system will use `CRS_DATABASE_URL` if set, otherwise falls back to `DATABASE_URL`
- `CRON_SECRET` - Secret token for cron authentication
- `R2_ACCESS_KEY_ID` - Cloudflare R2 access key
- `R2_SECRET_ACCESS_KEY` - Cloudflare R2 secret key
- `R2_ACCOUNT_ID` - Cloudflare R2 account ID
- `R2_BUCKET_NAME` - R2 bucket name
- `R2_PUBLIC_URL` - Public URL for R2 bucket

## How It Works

### Update Flow

1. **Trigger**: Vercel Cron calls `/api/cron/crs-library-update` at 8 AM UTC daily

2. **Authentication**: Endpoint verifies `CRON_SECRET` header

3. **Initialize**: Creates `CRSUpdater` instance with:
   - `lookback_days=30` (check last 30 days)
   - `max_products=100` (limit per run)

4. **Find Products**: Query database for products:
   - Updated in last 30 days (from `products` table)
   - Need content fetch/update
   - Limit to 100 products

5. **Start Ingestion Log**: Create entry in `content_ingestion_logs`

6. **Process Each Product**:
   - Check if version needs update
   - Fetch HTML from congress.gov (with rate limiting)
   - Parse HTML content and extract structure
   - Store in database (`product_versions` table)
   - Upload to R2 blob storage
   - Update full-text search index
   - Mark as current version

7. **Complete Ingestion Log**: Update with final metrics

8. **Return Response**: JSON with status and metrics

### Update Priority

Products are processed based on:
1. New products (no version in database) - highest priority
2. Updated products (version_number > stored version)
3. Recently published (within 30 days)
4. Oldest unfetched

### Error Handling

- Failed HTTP fetches retry with headless browser (bypasses Cloudflare)
- Individual product errors logged but don't stop batch
- Ingestion log captures all errors for review
- Returns success if majority of products update successfully

## Monitoring

### Metrics Tracked

```json
{
  "products_checked": 50,
  "products_updated": 12,
  "products_added": 3,
  "products_skipped": 35,
  "total_size_bytes": 15728640,
  "avg_fetch_time_ms": 1250,
  "error_count": 0,
  "errors": [],
  "duration_seconds": 45.3
}
```

### Logs

- **Ingestion logs**: Stored in `content_ingestion_logs` table
- **Application logs**: Available in Vercel deployment logs
- **Error tracking**: Errors array in ingestion log + metrics response

### Health Checks

The CRS library doesn't have a dedicated health endpoint yet, but you can check:

1. **Recent ingestion logs**:
   ```sql
   SELECT * FROM content_ingestion_logs
   ORDER BY started_at DESC LIMIT 10;
   ```

2. **Current versions by product**:
   ```sql
   SELECT COUNT(*) as total_products_with_content
   FROM product_versions WHERE is_current = 1;
   ```

3. **Recent errors**:
   ```sql
   SELECT run_type, errors_count, error_details, started_at
   FROM content_ingestion_logs
   WHERE errors_count > 0
   ORDER BY started_at DESC LIMIT 5;
   ```

## Manual Execution

### Test Locally

```bash
cd /Users/jason/Documents/GitHub/Hearing-Database
python updaters/crs_updater.py --lookback-days 7 --max-products 10
```

### Test Endpoint Locally

```bash
# Set environment variables
export CRON_SECRET="your-secret"
export DATABASE_URL="path-to-database"

# Run Flask app
python api/cron-update.py

# In another terminal, trigger the endpoint
curl -X POST http://localhost:5000/api/cron/crs-library-update \
  -H "Authorization: Bearer your-secret"
```

### Trigger on Vercel (Manual)

```bash
curl -X POST https://www.capitollabsllc.com/api/cron/crs-library-update \
  -H "Authorization: Bearer YOUR_CRON_SECRET"
```

## Configuration Options

### Lookback Days

Controls how far back to check for updates:
- **Default**: 30 days
- **Shorter** (7-14 days): Faster, only recent updates
- **Longer** (60-90 days): More comprehensive, slower

### Max Products

Limits products updated per run:
- **Default**: 100 products
- **Lower** (25-50): Faster execution, good for testing
- **Higher** (200-500): More comprehensive, may timeout

### Rate Limiting

Fetcher rate limit (requests per second):
- **Default**: 0.5s delay = 2 req/sec
- **Slower** (1.0s delay): More respectful to congress.gov
- **Faster** (0.25s delay): Faster but riskier

## Troubleshooting

### Common Issues

1. **403 Forbidden errors**: Cloudflare blocking HTTP requests
   - **Solution**: Fetcher automatically falls back to headless browser

2. **Timeout errors**: Vercel function timeout (300s max)
   - **Solution**: Reduce `max_products` or `lookback_days`

3. **Database locked**: SQLite concurrent access
   - **Solution**: Switch to PostgreSQL or reduce concurrency

4. **R2 storage errors**: Blob upload failures
   - **Solution**: Check R2 credentials and bucket permissions

5. **Parse errors**: HTML structure changed on congress.gov
   - **Solution**: Update `CRSHTMLParser` selectors

### Debug Mode

Enable verbose logging:
```python
# In updaters/crs_updater.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Admin Dashboard Integration

**✅ COMPLETED**: The CRS library is now integrated into the admin dashboard at `/admin/`.

### Features

The admin dashboard includes a dedicated CRS Library section with:

1. **Status Banner**: Shows system health, coverage %, and last ingestion time
2. **Metrics Grid**: Total products, products with content, coverage percentage, average word count
3. **Recent Ingestion Logs**: Last 5 ingestion runs with status and statistics
4. **Manual Update Controls**:
   - Adjustable lookback days (1-90)
   - Adjustable max products (10-500)
   - Real-time progress tracking
   - Fire-and-forget execution via async tasks
5. **Products Browser**: Shows last 50 CRS products with metadata and content status

### API Endpoints

The admin dashboard uses these new API endpoints:

- `GET /admin/api/crs/stats` - Get CRS library statistics
- `GET /admin/api/crs/ingestion-logs` - Get recent ingestion logs
- `GET /admin/api/crs/products` - Get CRS products with version info
- `POST /admin/api/crs/trigger-update` - Manually trigger a CRS update
- `GET /admin/api/crs/health` - Get CRS system health status

### Manual Update

To manually trigger a CRS update from the admin dashboard:

1. Navigate to `/admin/`
2. Scroll to the "CRS Library" section
3. Adjust lookback days and max products as needed
4. Click "Start CRS Update"
5. Monitor progress in real-time
6. View updated statistics after completion

## Future Enhancements

- [ ] Implement differential updates (only changed content)
- [ ] Add email notifications for failures
- [ ] Support for full backfill mode (all products)
- [ ] Parallel fetching with worker pool
- [ ] Retry queue for failed products
- [ ] Add CRS to scheduled_tasks for automated daily runs
- [ ] Content version comparison and diff viewing

## Related Documentation

- CRS Content Fetcher: `fetchers/crs_content_fetcher.py`
- CRS HTML Parser: `parsers/crs_html_parser.py`
- CRS Content Manager: `database/crs_content_manager.py`
- Database Migration: `database/migrations/crs_001_add_content_tables.sql`
- Vercel Cron Docs: https://vercel.com/docs/cron-jobs
