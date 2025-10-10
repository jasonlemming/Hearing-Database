# PostgreSQL Migration Deployment Guide

This guide walks you through completing the PostgreSQL migration for your CRS database to resolve the Vercel 512MB /tmp storage limit.

## 📋 What's Already Done

✅ PostgreSQL schema created with full-text search
✅ Database configuration module with connection pooling
✅ Data migration script with verification
✅ All SQLite queries converted to PostgreSQL
✅ Requirements updated with psycopg2-binary
✅ Changes committed to `postgres-migration` branch

## 🎯 What You Need To Do

### Step 1: Set Up Neon PostgreSQL Database (5 minutes)

Neon offers a free tier with 512MB storage - perfect for your needs.

1. **Sign up for Neon:**
   ```
   Visit: https://neon.tech/
   Click "Sign up" (use GitHub auth for quick signup)
   ```

2. **Create a new project:**
   ```
   Project name: "CRS Products Database"
   Region: Choose closest to your Vercel deployment (e.g., US East)
   PostgreSQL version: 16 (default)
   ```

3. **Copy your connection string:**
   ```
   After creation, you'll see a connection string like:
   postgresql://username:password@ep-xyz-123.us-east-2.aws.neon.tech/neondb

   IMPORTANT: Save this - you'll need it for all following steps!
   ```

4. **Set environment variable locally:**
   ```bash
   export DATABASE_URL='postgresql://your-connection-string-here'

   # Verify it's set:
   echo $DATABASE_URL
   ```

   **Optional: Add to your shell profile for persistence:**
   ```bash
   # Add to ~/.zshrc or ~/.bashrc:
   echo 'export DATABASE_URL="postgresql://your-connection-string-here"' >> ~/.zshrc
   source ~/.zshrc
   ```

---

### Step 2: Install PostgreSQL Client Tools (if not installed)

You need `psql` to run the schema migration:

**macOS:**
```bash
# Check if already installed:
psql --version

# If not installed:
brew install postgresql@16
```

**Verify installation:**
```bash
psql --version
# Should output: psql (PostgreSQL) 16.x
```

---

### Step 3: Run Schema Migration (2 minutes)

This creates all tables, indexes, triggers, and functions in your Neon database:

```bash
# Make sure DATABASE_URL is set:
echo $DATABASE_URL

# Run schema migration:
psql $DATABASE_URL -f database/migrations/postgres_001_initial_schema.sql
```

**Expected output:**
```
CREATE EXTENSION
CREATE TABLE
CREATE INDEX
CREATE INDEX
... (many CREATE statements)
CREATE FUNCTION
CREATE TRIGGER
```

**Verify it worked:**
```bash
psql $DATABASE_URL -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
```

You should see:
```
          tablename
------------------------------
 products
 product_versions
 product_content_fts
 content_ingestion_logs
```

---

### Step 4: Run Data Migration (15-30 minutes)

This migrates 6,589 products and 6,577 versions from SQLite to PostgreSQL:

```bash
# Make sure you're in the project directory:
cd /Users/jasonlemons/Documents/GitHub/Hearing-Database

# Run migration (shows live progress):
python3 scripts/migrate_to_postgres.py
```

**Expected output:**
```
======================================================================
CRS DATABASE MIGRATION: SQLite → PostgreSQL
======================================================================
Started at: 2025-10-10 14:30:00

======================================================================
MIGRATING PRODUCTS TABLE
======================================================================
Total products to migrate: 6589
  Migrated 500/6589 products (7.6%)
  Migrated 1000/6589 products (15.2%)
  Migrated 1500/6589 products (22.8%)
  ...
  Migrated 6589/6589 products (100.0%)
✅ Products migration complete: 6589 products

======================================================================
MIGRATING PRODUCT_VERSIONS TABLE
======================================================================
Total product versions to migrate: 6577
  Migrated 500/6577 versions (7.6%)
  ...
✅ Product versions migration complete: 6577 versions

======================================================================
VERIFYING MIGRATION
======================================================================

Products:         SQLite:   6589  |  PostgreSQL:   6589  |  Match: ✅
Product Versions: SQLite:   6577  |  PostgreSQL:   6577  |  Match: ✅

✅ MIGRATION VERIFIED SUCCESSFULLY!

======================================================================
✅ MIGRATION COMPLETE!
======================================================================

Next steps:
1. Test locally: python3 cli.py web serve
2. Verify search functionality works
3. Deploy to Vercel with DATABASE_URL environment variable
```

**If migration fails:**
- Check that SQLite database exists: `ls -lh crs_products.db`
- Verify DATABASE_URL is set correctly
- Check Neon dashboard for connection limits
- You can re-run the script safely - it uses `ON CONFLICT DO UPDATE`

---

### Step 5: Test Locally (10 minutes)

Test that everything works with PostgreSQL before deploying:

```bash
# Set all required environment variables:
export DATABASE_URL='postgresql://your-connection-string-here'
export R2_ACCESS_KEY_ID='3e3c4b3c1f1e889e2d2f7dcea5d3cd39'
export R2_SECRET_ACCESS_KEY='a4969fc156ba736dcc120980774056d01064a8ce968905adce64ec566c2a61bd'
export R2_ACCOUNT_ID='91b9e5b1082e2a907534e03c8945f60c'
export R2_BUCKET_NAME='crs-project'
export R2_PUBLIC_URL='https://pub-64de0dc4e382450fb3f10d3ab626024c.r2.dev'

# Start local server:
python3 cli.py web serve --host 127.0.0.1 --port 5002
```

**Test these URLs in your browser:**

1. **Browse page:** http://127.0.0.1:5002/crs/
   - Should show products list
   - Try filtering by status/type/topic
   - Pagination should work

2. **Search page:** http://127.0.0.1:5002/crs/search?q=healthcare
   - Should return relevant results
   - Try searching for: "cybersecurity", "climate change", "tax policy"
   - Check that ranking looks reasonable

3. **Product detail:** http://127.0.0.1:5002/crs/product/R44722
   - Should show product metadata
   - Check if HTML content loads from R2
   - Verify table of contents appears

4. **CSV export:** http://127.0.0.1:5002/crs/api/export?status=Active
   - Should download CSV file
   - Open it to verify data looks correct

**If you see errors:**
- Check terminal for error messages
- Verify DATABASE_URL is correct
- Check Neon dashboard that database is accessible
- Look for connection pool errors (increase pool_size if needed)

---

### Step 6: Push to GitHub (2 minutes)

```bash
# Push the postgres-migration branch:
git push -u origin postgres-migration
```

**Then on GitHub:**
1. Go to: https://github.com/jasonlemons/Hearing-Database/pulls
2. Click "New pull request"
3. Base: `main` ← Compare: `postgres-migration`
4. Title: "PostgreSQL Migration for CRS Database"
5. Description: "Resolves Vercel 512MB storage limit issue"
6. Click "Create pull request"
7. Review changes, then "Merge pull request"

---

### Step 7: Deploy to Vercel (5 minutes)

1. **Add DATABASE_URL environment variable:**
   ```
   Go to: https://vercel.com/your-username/hearing-database/settings/environment-variables

   Variable name: DATABASE_URL
   Value: postgresql://your-connection-string-here
   Environments: Production, Preview, Development (check all)

   Click "Save"
   ```

2. **Add R2 environment variables (if not already added):**
   ```
   R2_ACCESS_KEY_ID: 3e3c4b3c1f1e889e2d2f7dcea5d3cd39
   R2_SECRET_ACCESS_KEY: a4969fc156ba736dcc120980774056d01064a8ce968905adce64ec566c2a61bd
   R2_ACCOUNT_ID: 91b9e5b1082e2a907534e03c8945f60c
   R2_BUCKET_NAME: crs-project
   R2_PUBLIC_URL: https://pub-64de0dc4e382450fb3f10d3ab626024c.r2.dev
   ```

3. **Trigger new deployment:**
   ```
   Option A: Wait for automatic deployment after merging PR

   Option B: Manual trigger from Vercel dashboard:
   - Go to Deployments tab
   - Click "..." menu on latest deployment
   - Click "Redeploy"
   ```

4. **Monitor deployment:**
   ```
   Watch build logs for any errors
   Look for "Build successful" message
   Deployment typically takes 2-3 minutes
   ```

---

### Step 8: Verify Production (5 minutes)

Once deployed, test your production site:

1. **Homepage:** https://www.capitollabsllc.com/crs/
   - Should load without errors
   - Products should display

2. **Search:** https://www.capitollabsllc.com/crs/search?q=healthcare
   - Should return results quickly
   - Ranking should look good

3. **Product detail:** https://www.capitollabsllc.com/crs/product/R44722
   - Should load product page
   - HTML content should display from R2

4. **Check Vercel logs:**
   ```
   Go to: https://vercel.com/your-username/hearing-database
   Click "Logs" tab
   Look for any errors or warnings
   ```

5. **Check Neon dashboard:**
   ```
   Go to: https://neon.tech/
   Open your project
   Check "Monitoring" tab
   Should see database queries being executed
   ```

---

## 🎉 Success Checklist

- [ ] Neon database created and connection string saved
- [ ] Schema migration completed successfully
- [ ] Data migration verified (6,589 products, 6,577 versions)
- [ ] Local testing passed (browse, search, detail pages work)
- [ ] Code pushed to GitHub and PR merged
- [ ] DATABASE_URL added to Vercel environment variables
- [ ] Production deployment successful
- [ ] Production site tested and working
- [ ] https://www.capitollabsllc.com/crs/ is live and functional

---

## 🔧 Troubleshooting

### Issue: "DATABASE_URL environment variable not set"
**Solution:**
```bash
export DATABASE_URL='postgresql://your-connection-string-here'
# Add to ~/.zshrc for persistence
```

### Issue: "Connection refused" or "could not connect to server"
**Solution:**
- Check Neon dashboard that database is running
- Verify connection string is correct (copy fresh from Neon)
- Check that your IP is not blocked (Neon allows all IPs by default)

### Issue: Migration says "0 products migrated"
**Solution:**
- Verify SQLite database exists: `ls -lh crs_products.db`
- Check you're in correct directory: `pwd`
- Try running with explicit path: `python3 scripts/migrate_to_postgres.py`

### Issue: "Module not found: psycopg2"
**Solution:**
```bash
pip3 install psycopg2-binary
# Or reinstall requirements:
pip3 install -r requirements.txt
```

### Issue: Vercel deployment fails with database errors
**Solution:**
- Verify DATABASE_URL is set in Vercel environment variables
- Check that connection string starts with `postgresql://` not `postgres://`
- Ensure all environments are checked (Production, Preview, Development)
- Redeploy after adding/updating environment variables

### Issue: Search returns no results
**Solution:**
- Check that data migration completed successfully
- Verify search_vector columns are populated:
  ```bash
  psql $DATABASE_URL -c "SELECT product_id, search_vector FROM products LIMIT 1;"
  ```
- Search vectors should auto-populate via triggers
- If empty, re-run migration

### Issue: Slow query performance
**Solution:**
- Check that indexes were created:
  ```bash
  psql $DATABASE_URL -c "\d products"
  ```
- Should see GIN indexes on search_vector and JSONB columns
- Monitor Neon dashboard for query performance
- Consider upgrading Neon tier if consistently slow (free tier: 1 CPU, 512MB RAM)

---

## 📊 Database Monitoring

**Check database size:**
```bash
psql $DATABASE_URL -c "SELECT pg_size_pretty(pg_database_size('neondb'));"
```

**Check row counts:**
```bash
psql $DATABASE_URL -c "
SELECT
  (SELECT COUNT(*) FROM products) as products,
  (SELECT COUNT(*) FROM product_versions) as versions,
  (SELECT COUNT(*) FROM product_content_fts) as content_fts;
"
```

**Check index sizes:**
```bash
psql $DATABASE_URL -c "
SELECT
  tablename,
  indexname,
  pg_size_pretty(pg_relation_size(indexname::regclass)) as size
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexname::regclass) DESC;
"
```

---

## 💰 Cost Considerations

**Neon Free Tier Limits:**
- Storage: 512 MB (your database is ~150-200MB)
- Compute: 0.25 vCPU (sufficient for low-moderate traffic)
- Data transfer: 5 GB/month
- Active time: 100 hours/month (scales to zero when inactive)
- Projects: 1

**When to upgrade:**
- If you exceed 512MB storage (add more products/content)
- If you need >100 hours active time per month
- If queries become slow (need more compute)

**Pro tier ($19/month):**
- Storage: 10 GB
- Compute: 1 vCPU
- Data transfer: 50 GB/month
- No active time limit

---

## 🔄 Future Content Updates

When you ingest new CRS content:

```bash
# Set DATABASE_URL:
export DATABASE_URL='postgresql://your-connection-string-here'

# Run content ingestion (works with PostgreSQL):
python3 cli.py crs-content backfill
# Or for updates:
python3 cli.py crs-content update
```

The system will automatically:
- Insert new products into PostgreSQL
- Update existing products
- Populate search vectors via triggers
- Upload HTML content to R2

No separate FTS sync needed - PostgreSQL triggers handle it!

---

## 📚 Technical Reference

**Query Syntax Differences:**

| SQLite FTS5 | PostgreSQL Full-Text Search |
|-------------|----------------------------|
| `WHERE products_fts MATCH 'query'` | `WHERE search_vector @@ websearch_to_tsquery('english', 'query')` |
| `ORDER BY bm25(products_fts)` | `ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', 'query'))` |
| `json_each(topics)` | `jsonb_array_elements_text(topics)` |
| `topics -> '$[0]'` | `topics @> '["value"]'` |
| `?` parameters | `%s` parameters |

**Connection Pooling:**
- Pool size: 5 connections
- Max overflow: 10 connections
- Pool pre-ping: True (verifies connections before use)
- Pool recycle: 300 seconds (5 minutes)

**Full-Text Search Weights:**
- Title: A (highest)
- Summary: B
- Topics: C
- Content headings: B
- Content text: D (lowest)

---

## ✉️ Need Help?

If you encounter issues:

1. Check Neon dashboard for database status
2. Review Vercel deployment logs
3. Test locally first to isolate issues
4. Check that all environment variables are set
5. Verify migration completed successfully

Good luck with your deployment! 🚀
