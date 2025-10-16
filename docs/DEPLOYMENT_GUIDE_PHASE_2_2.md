# Phase 2.2 Deployment Guide

**Version**: 1.0
**Date**: October 13, 2025
**Status**: Production Ready

---

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Local Testing](#local-testing)
3. [Database Preparation](#database-preparation)
4. [Vercel Deployment](#vercel-deployment)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring Setup](#monitoring-setup)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)

---

## Pre-Deployment Checklist

Before deploying Phase 2.2 features to production, verify the following:

### Code Verification

- [ ] All Phase 2.2 code changes committed to repository
- [ ] No uncommitted local changes
- [ ] Git branch is clean (run `git status`)
- [ ] All tests passing locally

### File Verification

**Modified Files**:
- [ ] `updaters/daily_updater.py` - Contains all 5 new methods
- [ ] `scripts/verify_updates.py` - Enhanced anomaly detection
- [ ] `web/blueprints/admin.py` - System health endpoint added
- [ ] `web/templates/admin_dashboard.html` - Health widget added

**New Files**:
- [ ] `tests/test_verification_system.py` - Unit tests exist
- [ ] `scripts/test_verification_manual.sh` - Manual test script exists
- [ ] `scripts/test_integration_simple.sh` - Integration tests exist
- [ ] `docs/PHASE_2_2_COMPLETE.md` - Documentation complete
- [ ] `docs/DEPLOYMENT_GUIDE_PHASE_2_2.md` - This file

### Environment Verification

- [ ] Python version >= 3.8
- [ ] All dependencies in `requirements.txt` installed
- [ ] Database file exists and is accessible
- [ ] Sufficient disk space for backups (minimum 500MB recommended)

---

## Local Testing

### Step 1: Run Manual Test Suite

```bash
# Make script executable
chmod +x scripts/test_verification_manual.sh

# Run tests
./scripts/test_verification_manual.sh
```

**Expected Output**: All tests should pass (40+ checks)

### Step 2: Run Integration Tests

```bash
# Make script executable
chmod +x scripts/test_integration_simple.sh

# Run tests
./scripts/test_integration_simple.sh
```

**Expected Output**:
- All critical tables exist
- Hearing count >= 1000
- Committee count >= 200
- Database integrity: OK
- No foreign key violations

### Step 3: Test Backup System

```bash
# Verify backup directory can be created
mkdir -p database/backups

# Check write permissions
touch database/backups/.test_write && rm database/backups/.test_write

# List existing backups
ls -lh database/backups/
```

### Step 4: Test Health Endpoint (Local Flask)

```bash
# Start Flask development server
python app.py

# In another terminal, test health endpoint
curl http://localhost:5000/admin/api/system-health | python -m json.tool
```

**Expected Response**:
```json
{
  "status": "healthy",
  "database": {
    "hearings": 1340,
    "committees": 239,
    "witnesses": 2425
  },
  "last_update": {
    "date": "2025-10-13",
    "success": true,
    "hours_ago": 6.5
  },
  "warnings": [],
  "issues": []
}
```

### Step 5: Test Admin Dashboard

1. Open browser to `http://localhost:5000/admin`
2. Verify "System Health" widget appears
3. Check that health status shows (green/yellow/red badge)
4. Verify auto-refresh is working (watch for updates)
5. Click "Refresh" button manually to test immediate update

---

## Database Preparation

### Create Backup Directory

```bash
# Navigate to project root
cd /Users/jason/Documents/GitHub/Hearing-Database

# Create backup directory if it doesn't exist
mkdir -p database/backups

# Verify permissions
ls -ld database/backups
```

### Verify Database Health

```bash
# Check database integrity
sqlite3 database.db "PRAGMA integrity_check;"

# Expected output: ok

# Check foreign key violations
sqlite3 database.db "PRAGMA foreign_keys = ON; PRAGMA foreign_key_check;"

# Expected output: (empty - no violations)

# Check record counts
sqlite3 database.db "SELECT COUNT(*) FROM hearings;"
sqlite3 database.db "SELECT COUNT(*) FROM committees;"
sqlite3 database.db "SELECT COUNT(*) FROM witnesses;"
```

### Create Manual Backup (Pre-Deployment)

```bash
# Create timestamped backup before deployment
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
cp database.db "database/backups/database_backup_${TIMESTAMP}.db"

# Verify backup
ls -lh "database/backups/database_backup_${TIMESTAMP}.db"
```

**Store this backup filename** - you may need it for rollback.

---

## Vercel Deployment

### Step 1: Commit and Push Changes

```bash
# Verify current branch
git branch

# Add all Phase 2.2 files
git add updaters/daily_updater.py
git add scripts/verify_updates.py
git add web/blueprints/admin.py
git add web/templates/admin_dashboard.html
git add tests/test_verification_system.py
git add scripts/test_verification_manual.sh
git add scripts/test_integration_simple.sh
git add docs/PHASE_2_2_COMPLETE.md
git add docs/DEPLOYMENT_GUIDE_PHASE_2_2.md

# Commit
git commit -m "Deploy Phase 2.2: Update Verification System

- Add automatic post-update validation
- Add pre-update sanity checks
- Add database backup and rollback capability
- Add enhanced anomaly detection (5 new algorithms)
- Add system health monitoring endpoint
- Add admin dashboard health widget
- Add comprehensive test suite

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to main
git push origin main
```

### Step 2: Verify Vercel Auto-Deployment

1. Push will trigger automatic Vercel deployment
2. Monitor deployment in Vercel dashboard
3. Wait for deployment to complete (~2-3 minutes)

**Vercel Dashboard**: `https://vercel.com/dashboard`

### Step 3: Check Deployment Logs

In Vercel dashboard:
1. Go to your project
2. Click on the latest deployment
3. Check "Build Logs" for any errors
4. Check "Function Logs" for runtime errors

---

## Post-Deployment Verification

### Step 1: Verify Application is Running

```bash
# Test main application endpoint
curl https://your-app.vercel.app/

# Expected: HTTP 200 response
```

### Step 2: Test Health Endpoint in Production

```bash
# Test system health endpoint
curl https://your-app.vercel.app/admin/api/system-health | python -m json.tool
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-13T20:00:00",
  "database": {
    "hearings": 1340,
    "committees": 239,
    "witnesses": 2425
  },
  "last_update": {
    "success": true,
    "hours_ago": 6.5
  }
}
```

### Step 3: Verify Admin Dashboard

1. Open browser to `https://your-app.vercel.app/admin`
2. Verify "System Health" widget loads
3. Check that health status displays correctly
4. Verify data is being fetched from production database
5. Test auto-refresh (wait 60 seconds, watch for update)

### Step 4: Verify Backup Directory Exists

```bash
# SSH into server or check file system
ls -la database/backups/

# Should see directory with proper permissions
# drwxr-xr-x  backups/
```

### Step 5: Monitor First Automated Update

**IMPORTANT**: Monitor the first scheduled update after deployment to ensure:
- Pre-update sanity checks run successfully
- Backup is created
- Update completes without errors
- Post-update validation runs
- No rollback is triggered (unless there are actual issues)

**How to Monitor**:
1. Check Vercel Function Logs during scheduled update time
2. Watch admin dashboard health status before/after update
3. Verify new backup file created in `database/backups/`
4. Check `update_logs` table for validation results

```bash
# Check latest update log
sqlite3 database.db "
SELECT log_id, update_date, start_time, end_time,
       hearings_checked, hearings_updated, success
FROM update_logs
ORDER BY start_time DESC LIMIT 1;"
```

---

## Monitoring Setup

### Daily Monitoring Tasks

**Every Day**:
1. Check admin dashboard health status
2. Verify no red "unhealthy" status
3. Review any warnings or issues displayed

**Every Week**:
1. Review backup directory size
2. Verify old backups are being cleaned up (7-day retention)
3. Check for any failed updates in last 7 days

### Log Monitoring

**Key Log Messages to Watch For**:

✅ **Good Signs**:
- `"Running pre-update sanity checks..."`
- `"All pre-update sanity checks passed ✓"`
- `"Creating database backup at..."`
- `"✓ Database backup created successfully"`
- `"Running post-update validation..."`
- `"✓ Validation passed with N warnings"`
- `"Cleaned up N old backup(s)"`

⚠️ **Warning Signs**:
- `"Failed to create database backup"`
- `"Unusually high hearing additions"` (from anomaly detection)
- `"High rate of witnesses missing organization"`
- `"Error rate spike: X%"`

❌ **Critical Issues**:
- `"Pre-update sanity checks failed - aborting update"`
- `"✗ Validation failed with N issues"`
- `"Rolling back database from backup:"`
- `"Post-Update Validation Failed"` (notification)
- `"Database Rollback Performed"` (notification)

### Health Status Thresholds

| Status | Conditions | Action Required |
|--------|-----------|-----------------|
| **Healthy** (Green) | All checks pass, last update < 30h ago | None - normal operation |
| **Degraded** (Yellow) | Last update 30-48h ago OR 3+ failed updates in 7 days | Investigate cause of delays/failures |
| **Unhealthy** (Red) | Last update > 48h ago OR hearing count < 1000 | Immediate investigation required |

### Backup Monitoring

```bash
# Check backup directory size
du -sh database/backups/

# Count backups (should be ~7 or fewer with 7-day retention)
ls -1 database/backups/database_backup_*.db | wc -l

# Check oldest backup age
ls -lt database/backups/database_backup_*.db | tail -1

# Verify backups are being created (check modification times)
ls -lth database/backups/database_backup_*.db | head -3
```

---

## Rollback Procedures

### Scenario 1: Automatic Rollback Occurred

If you see logs indicating automatic rollback happened:

1. **Don't panic** - the system protected the database automatically
2. **Check validation issues**:
   ```bash
   sqlite3 database.db "
   SELECT start_time, error_count, success
   FROM update_logs
   ORDER BY start_time DESC LIMIT 5;"
   ```
3. **Review what triggered rollback**:
   - Check Vercel function logs for "Rolling back database from backup"
   - Look for validation issues listed in logs
4. **Investigate root cause**:
   - Was there an API issue?
   - Was there a data quality problem?
   - Was there a code bug?
5. **Fix the issue** before next scheduled update

### Scenario 2: Manual Rollback Required

If you need to manually rollback to a previous state:

```bash
# List available backups
ls -lth database/backups/database_backup_*.db

# Choose backup to restore (e.g., from before deployment)
BACKUP_FILE="database_backup_20251013_120000.db"

# Stop any running processes accessing database
# (Important: ensure no active database connections)

# Backup current state (just in case)
cp database.db database.db.before_manual_rollback

# Restore from backup
cp "database/backups/$BACKUP_FILE" database.db

# Verify restore
sqlite3 database.db "PRAGMA integrity_check;"
sqlite3 database.db "SELECT COUNT(*) FROM hearings;"

# Restart application if needed
```

### Scenario 3: Complete Rollback of Phase 2.2

If Phase 2.2 features are causing critical issues:

1. **Create emergency backup**:
   ```bash
   cp database.db database.db.emergency_backup_$(date +%Y%m%d_%H%M%S)
   ```

2. **Revert code changes**:
   ```bash
   # Find commit before Phase 2.2
   git log --oneline

   # Revert to previous commit (replace COMMIT_HASH)
   git revert COMMIT_HASH

   # Or create new branch from previous state
   git checkout -b rollback-phase-2-2 COMMIT_HASH
   ```

3. **Push revert**:
   ```bash
   git push origin main
   # Or: git push origin rollback-phase-2-2
   ```

4. **Vercel will auto-deploy reverted version**

5. **Verify rollback**:
   ```bash
   # Test that old code is running
   curl https://your-app.vercel.app/admin/api/system-health

   # Should return 404 (endpoint doesn't exist in old code)
   ```

---

## Troubleshooting

### Issue: Health Endpoint Returns 500 Error

**Symptoms**: `/admin/api/system-health` returns HTTP 500

**Possible Causes**:
1. Database connection issues
2. Missing tables
3. Database corruption

**Diagnosis**:
```bash
# Check database accessibility
sqlite3 database.db "SELECT 1;"

# Verify required tables exist
sqlite3 database.db "
SELECT name FROM sqlite_master
WHERE type='table'
AND name IN ('hearings', 'committees', 'witnesses', 'update_logs');"

# Check database integrity
sqlite3 database.db "PRAGMA integrity_check;"
```

**Fix**:
- If tables missing: Re-run database initialization
- If corrupted: Restore from backup
- If connection issue: Check file permissions

### Issue: Backup Creation Fails

**Symptoms**: Log shows "Failed to create database backup"

**Possible Causes**:
1. Insufficient disk space
2. Permission issues
3. Directory doesn't exist

**Diagnosis**:
```bash
# Check disk space
df -h .

# Check backup directory exists and is writable
ls -ld database/backups
touch database/backups/.test && rm database/backups/.test

# Check database file permissions
ls -l database.db
```

**Fix**:
```bash
# Create backup directory with proper permissions
mkdir -p database/backups
chmod 755 database/backups

# Free up disk space if needed
# (Delete old backups manually if auto-cleanup failed)
find database/backups -name "database_backup_*.db" -mtime +14 -delete
```

### Issue: Validation Always Fails

**Symptoms**: Every update triggers rollback due to validation failure

**Possible Causes**:
1. Validation thresholds too strict
2. Legitimate data quality issue
3. UpdateValidator bug

**Diagnosis**:
```bash
# Run validation manually to see specific issues
python scripts/verify_updates.py

# Check recent validation results
sqlite3 database.db "
SELECT start_time, success, error_count
FROM update_logs
ORDER BY start_time DESC LIMIT 10;"
```

**Fix**:
1. Review validation issues in logs
2. If false positives, adjust thresholds in `scripts/verify_updates.py`
3. If legitimate issues, fix data quality problems
4. Temporarily disable validation if needed (not recommended):
   ```python
   # In updaters/daily_updater.py, comment out:
   # self._run_post_update_validation()
   ```

### Issue: Dashboard Health Widget Not Loading

**Symptoms**: Admin dashboard shows empty or error in health widget

**Possible Causes**:
1. JavaScript error
2. API endpoint not responding
3. CORS issues

**Diagnosis**:
1. Open browser Developer Tools (F12)
2. Check Console for JavaScript errors
3. Check Network tab for failed API requests
4. Test endpoint directly:
   ```bash
   curl https://your-app.vercel.app/admin/api/system-health
   ```

**Fix**:
- If JavaScript error: Check browser console for details
- If API error: Check Vercel function logs
- If CORS: Verify admin blueprint CORS settings
- Clear browser cache and reload

### Issue: Rollback Doesn't Work

**Symptoms**: Rollback is triggered but database isn't restored

**Possible Causes**:
1. Backup file doesn't exist
2. Backup file corrupted
3. File permission issues
4. Active database connections

**Diagnosis**:
```bash
# Check if backup exists
ls -l database/backups/database_backup_*.db

# Verify backup integrity
sqlite3 database/backups/database_backup_YYYYMMDD_HHMMSS.db "PRAGMA integrity_check;"

# Check for active connections
lsof database.db
```

**Fix**:
1. Ensure backup exists before triggering rollback
2. Verify backup file integrity
3. Close all database connections before rollback
4. Check file permissions on backup and database files

### Issue: Old Backups Not Being Cleaned Up

**Symptoms**: Backup directory keeps growing, old files not deleted

**Possible Causes**:
1. Cleanup function not running
2. Permission issues
3. Update not completing successfully

**Diagnosis**:
```bash
# List all backups with age
find database/backups -name "database_backup_*.db" -type f -mtime +7 -ls

# Check if cleanup function is being called
grep "_cleanup_old_backups" /path/to/vercel/function/logs
```

**Fix**:
```bash
# Manual cleanup (remove backups older than 7 days)
find database/backups -name "database_backup_*.db" -type f -mtime +7 -delete

# Verify cleanup function is in code
grep "_cleanup_old_backups" updaters/daily_updater.py

# Check it's being called in update flow
grep "Step 7.*Cleanup" updaters/daily_updater.py
```

---

## Support Contacts

**Repository**: https://github.com/jasonlemming/Hearing-Database

**Documentation**:
- Phase 2.2 Complete: `docs/PHASE_2_2_COMPLETE.md`
- This Deployment Guide: `docs/DEPLOYMENT_GUIDE_PHASE_2_2.md`

**Key Files for Reference**:
- Main updater: `updaters/daily_updater.py`
- Validation logic: `scripts/verify_updates.py`
- Health endpoint: `web/blueprints/admin.py`
- Admin dashboard: `web/templates/admin_dashboard.html`

---

## Post-Deployment Success Criteria

Phase 2.2 deployment is considered successful when:

- [✓] All code deployed to production without errors
- [✓] Health endpoint returning valid JSON
- [✓] Admin dashboard health widget displaying correctly
- [✓] Backup directory created with proper permissions
- [✓] First scheduled update completes successfully with:
  - [✓] Pre-update sanity checks pass
  - [✓] Backup created
  - [✓] Post-update validation passes
  - [✓] No rollback triggered
- [✓] System status shows "Healthy" (green)
- [✓] No critical errors in logs

---

**Deployment Guide Version**: 1.0
**Last Updated**: October 13, 2025
**Status**: ✅ Ready for Production Deployment
