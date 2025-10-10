# PostgreSQL Migration - Quick Start Guide

## 🚀 What I've Done For You

✅ Created complete PostgreSQL schema with full-text search
✅ Built database configuration with connection pooling
✅ Created automated data migration script
✅ Converted all 418 lines of SQL queries from SQLite to PostgreSQL
✅ Updated requirements and blueprints
✅ Committed everything to `postgres-migration` branch
✅ Created comprehensive deployment guide and validation tools

## ⚡ Quick Start Commands

### 1. Get Neon Database (5 min)

```bash
# Visit: https://neon.tech/
# Sign up → Create project → Copy connection string
# It looks like: postgresql://username:password@ep-xyz.us-east-2.aws.neon.tech/neondb

export DATABASE_URL='paste-your-connection-string-here'
```

### 2. Run Schema Migration (1 min)

```bash
psql $DATABASE_URL -f database/migrations/postgres_001_initial_schema.sql
```

### 3. Run Data Migration (20 min)

```bash
python3 scripts/migrate_to_postgres.py
```

This migrates your 6,589 CRS products with live progress updates.

### 4. Validate Setup (30 sec)

```bash
python3 scripts/validate_postgres_setup.py
```

### 5. Test Locally (5 min)

```bash
# Set all environment variables:
export DATABASE_URL='your-neon-connection-string'
export R2_PUBLIC_URL='https://pub-64de0dc4e382450fb3f10d3ab626024c.r2.dev'

# Start server:
python3 cli.py web serve --host 127.0.0.1 --port 5002

# Test in browser:
# - http://127.0.0.1:5002/crs/
# - http://127.0.0.1:5002/crs/search?q=healthcare
```

### 6. Deploy to Vercel

```bash
# Push to GitHub:
git push -u origin postgres-migration

# On GitHub:
# - Create PR: postgres-migration → main
# - Review and merge

# In Vercel dashboard (https://vercel.com):
# Settings → Environment Variables → Add:
#   DATABASE_URL = your-neon-connection-string
# Then redeploy or wait for automatic deployment

# Test production:
# https://www.capitollabsllc.com/crs/
```

---

## 📖 Documentation

- **Detailed instructions:** See `DEPLOYMENT_GUIDE.md`
- **Troubleshooting:** See `DEPLOYMENT_GUIDE.md` → Troubleshooting section
- **Technical details:** See commit messages and code comments

---

## ❓ Common Issues

### "DATABASE_URL not set"
```bash
export DATABASE_URL='postgresql://your-connection-string-here'
echo 'export DATABASE_URL="..."' >> ~/.zshrc  # Make it persistent
```

### "psql: command not found"
```bash
brew install postgresql@16
```

### "Connection refused"
- Check Neon dashboard that database is running
- Verify connection string is correct (copy fresh from Neon)

### Migration shows 0 products
- Verify: `ls -lh crs_products.db` (should be ~620MB)
- Make sure you're in project root directory

---

## 🎯 Why PostgreSQL?

**Problem:** Your 620MB SQLite database exceeds Vercel's 512MB /tmp limit even with compression.

**Solution:** Cloud-hosted Neon PostgreSQL (free tier: 512MB, scalable to 3GB).

**Benefits:**
- No local storage needed on Vercel
- Better full-text search (GIN indexes + TSVECTOR)
- Auto-updating search via triggers (no FTS sync)
- Connection pooling for serverless
- Better concurrent write performance
- Native JSONB support

**Cost:** $0/month (free tier sufficient for your needs)

---

## 📊 What Changed

**Files Created:**
- `database/migrations/postgres_001_initial_schema.sql` - PostgreSQL schema
- `database/postgres_config.py` - Connection management
- `scripts/migrate_to_postgres.py` - Data migration tool
- `scripts/validate_postgres_setup.py` - Validation helper
- `DEPLOYMENT_GUIDE.md` - Full documentation
- `QUICK_START.md` - This file

**Files Modified:**
- `requirements.txt` - Added psycopg2-binary
- `web/blueprints/crs.py` - All SQLite queries → PostgreSQL

**Key Query Changes:**
- SQLite: `WHERE products_fts MATCH 'query'`
- PostgreSQL: `WHERE search_vector @@ websearch_to_tsquery('english', 'query')`

---

## ⏱️ Time Estimate

- **Setup Neon:** 5 minutes
- **Schema migration:** 1 minute
- **Data migration:** 20 minutes (6,589 products)
- **Validation:** 30 seconds
- **Local testing:** 5 minutes
- **Deploy:** 5 minutes
- **Total:** ~35-40 minutes

---

## 🎉 Success Criteria

Your site is working when:

1. ✅ Validation script passes all checks
2. ✅ Local server loads CRS pages without errors
3. ✅ Search returns relevant results
4. ✅ Product detail pages display content from R2
5. ✅ Production site is accessible at https://www.capitollabsllc.com/crs/

---

## 🆘 Need Help?

1. **First:** Run validation script
   ```bash
   python3 scripts/validate_postgres_setup.py
   ```

2. **Check logs:**
   - Terminal output for error messages
   - Neon dashboard for database status
   - Vercel dashboard for deployment logs

3. **Read documentation:**
   - `DEPLOYMENT_GUIDE.md` has detailed troubleshooting

Good luck! 🚀
