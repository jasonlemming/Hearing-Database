# Pre-Deployment Checklist - PostgreSQL Migration
## Congressional Hearing Database - www.capitollabsllc.com

**Status:** ⚠️ NOT DEPLOYED TO PRODUCTION YET
**Current Production:** Still using SQLite (cron jobs failing)
**Target:** PostgreSQL on Neon

---

## Summary of Changes
Migrating from SQLite to PostgreSQL (Neon) to fix Vercel cron job failures caused by read-only filesystem.

### Files Modified
- `database/manager.py` (~200 lines changed)
- Requirements.txt` (psycopg2-binary added)
- `.env` (POSTGRES_URL added - not in git)

### Data Migration Status
✅ **17,500+ rows successfully migrated** to Neon PostgreSQL
- committees: 239 rows
- members: 538 rows
- hearings: 1,340 rows
- witnesses: 2,234 rows
- committee_memberships: 3,869 rows
- hearing_committees: 1,340 rows
- witness_appearances: 2,425 rows

---

## Risk Assessment

### 🔴 HIGH RISK - MUST ADDRESS BEFORE DEPLOYMENT

#### 1. Missing POSTGRES_URL in Vercel
**Impact:** App falls back to SQLite, cron still fails
**Checklist:**
- [ ] Add POSTGRES_URL to Vercel environment variables
- [ ] Value: `postgresql://neondb_owner:npg_GSy1KMXHlO4h@ep-floral-pond-ad29ffc4-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require`
- [ ] Verify it's set in Vercel dashboard (Settings → Environment Variables)
- [ ] Scope: Production, Preview, Development

#### 2. Test Full Update Cycle Locally
**Impact:** Write operations could fail in production
**Checklist:**
- [ ] Run manual update against PostgreSQL: `python -m scripts.manual_update`
- [ ] Verify new records inserted
- [ ] Check update_logs table for success
- [ ] Monitor for any SQL errors in output

#### 3. Connection Pool Limits
**Impact:** Hit Neon free tier limits, functions fail
**Current Status:** Using pooler connection (good!)
**Checklist:**
- [ ] Monitor Neon dashboard during first 24 hours
- [ ] Watch for "too many connections" errors
- [ ] Free tier limit: Check Neon dashboard

### 🟡 MEDIUM RISK - MONITOR CLOSELY

#### 4. Network Latency & Timeouts
**Impact:** Functions timeout on large updates
**Vercel Limits:**
- API Routes: 10 seconds (Hobby), 60 seconds (Pro)
- Cron Jobs: 60 seconds max
**Checklist:**
- [ ] Test daily update completes in <60 seconds locally
- [ ] Monitor Vercel function logs for timeout errors
- [ ] If timeouts occur, consider batching strategy

#### 5. SQL Compatibility Edge Cases
**Impact:** Unexpected query failures
**Checklist:**
- [ ] Review first 3 days of Vercel logs carefully
- [ ] Check for any database errors
- [ ] Have rollback plan ready (see below)

### 🟢 LOW RISK - FIXED

#### 6. Type Hints
**Status:** ✅ FIXED - All type hints updated to `Dict[str, Any]`

#### 7. Vacuum/Analyze
**Status:** ✅ FIXED - Added PostgreSQL handling

---

## Pre-Deployment Testing

###  Test 1: Local Connection ✅ PASSED
```bash
python test_postgres_connection.py
```
**Expected:** All green checks
**Result:** ✅ Connection successful, data retrieved

### Test 2: Manual Update (REQUIRED BEFORE DEPLOY)
```bash
source .venv/bin/activate
python -m scripts.manual_update
```
**Expected:**
- No errors
- New records inserted (if API has new data)
- update_logs table shows success
**Result:** ⏳ NOT YET RUN

### Test 3: Web App Locally
```bash
python app.py
```
**Visit:** http://localhost:5000
**Check:**
- [ ] Homepage loads
- [ ] Browse hearings works
- [ ] Search works
- [ ] No database errors in console

**Result:** ⏳ NOT YET RUN

---

## Deployment Steps

### Phase 1: Environment Setup (DO FIRST)
1. **Add POSTGRES_URL to Vercel**
   ```
   Dashboard → Settings → Environment Variables → Add New
   Key: POSTGRES_URL
   Value: <connection string from .env>
   Scope: Production, Preview, Development
   ```

2. **Verify psycopg2-binary in requirements.txt**
   ```bash
   grep psycopg2 requirements.txt
   # Should show: psycopg2-binary>=2.9.9
   ```

### Phase 2: Deploy to Vercel
```bash
git status  # Verify changes
git add database/manager.py
git commit -m "Add PostgreSQL support for Neon database

- Update DatabaseManager to support both SQLite and PostgreSQL
- Add query conversion (? → %s placeholders)
- Implement INSERT RETURNING for PostgreSQL
- Convert INSERT OR REPLACE to ON CONFLICT
- Fix type hints and utility methods
- Migrated 17,500+ rows to Neon successfully

Fixes: Vercel cron job failures due to read-only SQLite"

git push origin main
```

3. **Vercel will auto-deploy**
   - Watch deployment logs in Vercel dashboard
   - Deployment typically takes 2-3 minutes

### Phase 3: Immediate Post-Deployment Checks
**Within 5 minutes of deployment:**

1. **Check Homepage**
   - Visit https://www.capitollabsllc.com
   - Should load normally
   - No 500 errors

2. **Check Database Connection**
   - Go to any hearing detail page
   - Should display data from PostgreSQL

3. **Check Vercel Logs**
   ```
   Dashboard → Deployments → View Function Logs
   Look for: "Using PostgreSQL database"
   ```

4. **Test Manual Update via Web UI**
   - Go to /admin
   - Click "Run Daily Update"
   - Should complete successfully

### Phase 4: Monitor First Cron Run
**Next scheduled cron: Tomorrow 6 AM UTC**

1. **Check Vercel Cron Logs**
   - Dashboard → Cron Jobs → View Logs
   - Should see successful execution

2. **Verify in Database**
   ```bash
   python test_postgres_connection.py
   # Check update_logs table for new entry with trigger_source='vercel_cron'
   ```

---

## Rollback Plan (If Things Go Wrong)

### If Site is Down
1. **Quick Rollback via Vercel**
   ```
   Dashboard → Deployments → [Previous Deployment] → Promote to Production
   ```
   This reverts to previous working version in ~30 seconds

2. **Remove POSTGRES_URL**
   ```
   Settings → Environment Variables → Delete POSTGRES_URL
   Redeploy
   ```

### If Database Issues
1. **Database is safe** - PostgreSQL data persists in Neon
2. **Can switch back to SQLite** for reads (old database.db still exists locally)
3. **Neon data preserved** - can fix code and redeploy

---

## Success Criteria

### Deployment Successful When:
- [  ] Site loads at www.capitollabsllc.com
- [ ] Homepage displays hearings
- [ ] Search functionality works
- [ ] No 500 errors in Vercel logs
- [ ] Logs show "Using PostgreSQL database"

### Migration Successful When:
- [ ] First cron job completes successfully (tomorrow 6 AM UTC)
- [ ] update_logs table shows new entry with trigger_source='vercel_cron'
- [ ] No "read-only database" errors
- [ ] Data persists between cron runs

---

## Monitoring Plan - First 72 Hours

### Day 1
- [ ] Check site every 2 hours
- [ ] Monitor Vercel function logs
- [ ] Monitor Neon connection usage
- [ ] Verify first cron run

### Day 2-3
- [ ] Check site twice daily
- [ ] Review cron logs
- [ ] Check for any timeout errors

### Ongoing
- [ ] Weekly review of Neon usage vs free tier limits
- [ ] Monthly review of connection patterns

---

## Neon Free Tier Limits
- Compute: 191.9 hours/month used (as of now)
- Storage: ~50 MB used (plenty of room)
- **Monitor:** Connection count during peak usage

---

## Contact Info
- **Neon Dashboard:** https://console.neon.tech
- **Vercel Dashboard:** https://vercel.com/dashboard
- **Database Status:** Can check via test_postgres_connection.py

---

## Notes
- Local development still works with SQLite (no POSTGRES_URL locally)
- Can test with PostgreSQL locally by keeping POSTGRES_URL in .env
- All changes backward compatible - SQLite still supported
