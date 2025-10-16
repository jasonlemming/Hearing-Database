# Daily Updates Deployment Checklist

**Purpose**: Activate automated daily updates on Vercel
**Estimated Time**: 15-20 minutes
**Prerequisites**: Vercel account, Congress.gov API key

---

## Pre-Deployment Checklist

### ✅ Prerequisites

- [ ] Congress.gov API key obtained (https://api.congress.gov/sign-up/)
- [ ] Vercel CLI installed (`npm install -g vercel`)
- [ ] Vercel account configured (`vercel login`)
- [ ] Database is healthy (run `scripts/verify_updates.py`)
- [ ] Current code committed to git

### ✅ Environment Variables

Verify these are set in Vercel dashboard:

- [ ] `CONGRESS_API_KEY` - Your API key
- [ ] `CRON_SECRET` - Random secure token (generate with `openssl rand -hex 32`)
- [ ] `DATABASE_PATH` - Set to `database.db`
- [ ] `LOG_LEVEL` - Set to `INFO`

### ✅ Database Configuration

Check `scheduled_tasks` table:

```sql
SELECT task_id, name, schedule_cron, lookback_days, mode, is_active
FROM scheduled_tasks
WHERE task_id = 3;
```

Expected values:
- [ ] `name` = "Daily at 6 AM UTC"
- [ ] `schedule_cron` = "0 6 * * *"
- [ ] `lookback_days` = 7
- [ ] `mode` = "incremental"
- [ ] `is_active` = 1

---

## Deployment Steps

### Step 1: Test Locally (Optional but Recommended)

```bash
# Test the cron endpoint locally
python3 -m flask --app api/cron-update run

# In another terminal, test with curl:
curl -X POST http://localhost:5000/api/cron/test-schedule/3
```

Expected: JSON response with update results

### Step 2: Deploy to Vercel

```bash
# From project root
vercel --prod

# Note the deployment URL (e.g., https://hearing-database.vercel.app)
```

Wait for deployment to complete (~2-3 minutes)

### Step 3: Verify vercel.json is Deployed

Check that cron configuration is active:

```bash
vercel cron list
```

Expected output:
```
path                            schedule
/api/cron/scheduled-update/3    0 6 * * *
```

### Step 4: Mark Schedule as Deployed

```sql
UPDATE scheduled_tasks
SET is_deployed = 1
WHERE task_id = 3;
```

Commit and deploy this change:
```bash
git add database.db
git commit -m "Mark daily update schedule as deployed"
vercel --prod
```

### Step 5: Test Health Endpoint

```bash
curl https://your-app.vercel.app/api/cron/health
```

Expected: Status 200 with JSON health data

### Step 6: Test Cron Endpoint Manually

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/scheduled-update/3
```

Expected: JSON response with update results

---

## Post-Deployment Verification

### Wait for First Automated Run

The cron job runs at 6 AM UTC. Convert to your timezone:
- **EST**: 1 AM
- **CST**: 12 AM (midnight)
- **MST**: 11 PM (previous day)
- **PST**: 10 PM (previous day)

### Verify First Run (Next Day)

1. **Check update_logs**:
```sql
SELECT * FROM update_logs
WHERE trigger_source = 'vercel_cron'
ORDER BY start_time DESC
LIMIT 1;
```

Expected:
- [ ] Record exists
- [ ] `success = 1`
- [ ] `error_count = 0`
- [ ] `hearings_updated > 0` or `hearings_added > 0` (if changes exist)

2. **Check scheduled_tasks**:
```sql
SELECT last_run_at FROM scheduled_tasks WHERE task_id = 3;
```

Expected:
- [ ] `last_run_at` is recent (within last hour of 6 AM UTC)

3. **Run validation**:
```bash
python3 scripts/verify_updates.py
```

Expected:
- [ ] Validation passes
- [ ] No critical issues
- [ ] Warnings (if any) are acceptable

4. **Check health endpoint**:
```bash
curl https://your-app.vercel.app/api/cron/health | jq
```

Expected:
- [ ] `status`: "healthy" or "degraded"
- [ ] `hours_since_last_update` < 24
- [ ] `error_rate_7days.error_rate_pct` < 10

---

## Monitoring Setup

### Daily Checks (Automated)

Set up monitoring service (e.g., UptimeRobot, Pingdom, or custom):

1. **Health Check Monitor**
   - URL: `https://your-app.vercel.app/api/cron/health`
   - Frequency: Every 6 hours
   - Alert on: Status 503 or `status != "healthy"`

2. **Database Size Monitor**
   ```sql
   SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
   FROM pragma_page_count('main'), pragma_page_size();
   ```
   - Alert on: size > 50 MB

3. **Update Freshness Monitor**
   ```sql
   SELECT
       ROUND((JULIANDAY('now') - JULIANDAY(start_time)) * 24, 1) as hours_ago
   FROM update_logs
   ORDER BY start_time DESC
   LIMIT 1;
   ```
   - Alert on: hours_ago > 30

### Weekly Checks (Manual)

- [ ] Review `update_logs` for patterns
- [ ] Check error rates
- [ ] Run full validation: `python3 scripts/verify_updates.py --verbose`
- [ ] Review Vercel cron logs in dashboard

### Monthly Maintenance

- [ ] Run database maintenance: `python3 scripts/database_maintenance.py --full`
- [ ] Review and clean old logs
- [ ] Check database size trends
- [ ] Review API usage patterns

---

## Troubleshooting

### Issue: Cron not running

**Check 1**: Vercel cron configuration
```bash
vercel cron list
```

If not listed, verify `vercel.json` and redeploy.

**Check 2**: Cron authorization
- Verify `CRON_SECRET` environment variable is set
- Check Vercel function logs for auth errors

**Check 3**: Task is active
```sql
SELECT is_active, is_deployed FROM scheduled_tasks WHERE task_id = 3;
```

Both should be 1.

### Issue: Updates failing

**Check 1**: Update logs
```sql
SELECT * FROM update_logs WHERE success = 0 ORDER BY start_time DESC LIMIT 3;
```

Review `errors` column for details.

**Check 2**: API key validity
```bash
curl "https://api.congress.gov/v3/committee-meeting/119/house?api_key=YOUR_KEY&limit=1"
```

Should return JSON data, not 401 error.

**Check 3**: Database integrity
```bash
python3 scripts/verify_updates.py
```

Fix any critical issues found.

### Issue: No new hearings

This may be normal if:
- Congress is in recess
- No hearings held in last 7 days
- No changes to existing hearings

To verify:
1. Check Congress.gov manually
2. Increase lookback window temporarily:
   ```sql
   UPDATE scheduled_tasks SET lookback_days = 30 WHERE task_id = 3;
   ```
3. Manually trigger update:
   ```bash
   curl -X POST -H "Authorization: Bearer YOUR_CRON_SECRET" \
     https://your-app.vercel.app/api/cron/test-schedule/3
   ```

### Issue: Database size growing rapidly

**Check growth rate**:
```sql
SELECT DATE(created_at) as date, COUNT(*) as hearings_added
FROM hearings
GROUP BY DATE(created_at)
ORDER BY date DESC
LIMIT 30;
```

**Solutions**:
1. Run maintenance: `python3 scripts/database_maintenance.py --vacuum`
2. Clean old logs: `python3 scripts/database_maintenance.py --cleanup-logs 60`
3. If > 50 MB, consider PostgreSQL migration

---

## Rollback Procedure

If automated updates cause issues:

### Immediate Rollback

1. **Disable cron schedule**:
```sql
UPDATE scheduled_tasks SET is_active = 0 WHERE task_id = 3;
```

2. **Redeploy** to update database:
```bash
git add database.db
git commit -m "Disable automated updates temporarily"
vercel --prod
```

3. **Verify cron is stopped**:
```bash
vercel cron list
# Should still show in list, but won't trigger due to is_active = 0
```

### Restore from Backup

If database is corrupted:

1. **Download backup** (from previous deployment or local copy)

2. **Replace database**:
```bash
cp backup/database.db ./database.db
```

3. **Verify integrity**:
```bash
python3 scripts/verify_updates.py
```

4. **Redeploy**:
```bash
git add database.db
git commit -m "Restore database from backup"
vercel --prod
```

### Re-enable After Fix

1. **Identify and fix root cause**
2. **Test manually**:
```bash
curl -X POST -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/test-schedule/3
```
3. **Re-enable**:
```sql
UPDATE scheduled_tasks SET is_active = 1 WHERE task_id = 3;
```
4. **Deploy**:
```bash
git add database.db
git commit -m "Re-enable automated updates"
vercel --prod
```

---

## Success Criteria

Daily updates are successfully deployed when:

- [ ] ✅ Cron job appears in `vercel cron list`
- [ ] ✅ First automated run completed successfully
- [ ] ✅ `update_logs` shows `trigger_source = 'vercel_cron'`
- [ ] ✅ Health endpoint returns status 200
- [ ] ✅ Validation script passes
- [ ] ✅ No foreign key violations
- [ ] ✅ Hearing count is increasing (when Congress is active)
- [ ] ✅ Error rate < 5%

---

## Monitoring Dashboard (Optional)

For advanced monitoring, set up a custom dashboard:

### Metrics to Track

1. **Update Success Rate** (last 7 days)
   ```sql
   SELECT
       ROUND(100.0 * SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
   FROM update_logs
   WHERE start_time >= datetime('now', '-7 days');
   ```

2. **Average Update Duration**
   ```sql
   SELECT ROUND(AVG(duration_seconds), 2) as avg_duration
   FROM update_logs
   WHERE success = 1 AND start_time >= datetime('now', '-7 days');
   ```

3. **Data Growth Rate**
   ```sql
   SELECT DATE(created_at) as date, COUNT(*) as new_hearings
   FROM hearings
   WHERE created_at >= datetime('now', '-30 days')
   GROUP BY DATE(created_at)
   ORDER BY date DESC;
   ```

4. **API Usage Trend**
   ```sql
   SELECT DATE(start_time) as date, AVG(api_requests) as avg_requests
   FROM update_logs
   WHERE start_time >= datetime('now', '-7 days')
   GROUP BY DATE(start_time)
   ORDER BY date DESC;
   ```

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Success Rate | < 95% | < 90% |
| Hours Since Update | > 30h | > 48h |
| Error Rate | > 5% | > 10% |
| Database Size | > 30 MB | > 50 MB |
| API Requests | > 3000 | > 4500 |

---

## Next Steps After Deployment

1. **Monitor for 1 week** to establish baseline metrics
2. **Adjust lookback window** if needed (based on update patterns)
3. **Set up email/Slack notifications** for failures
4. **Document any issues** encountered
5. **Update this checklist** with lessons learned

---

## Support

For issues or questions:
- **Documentation**: `/docs/DAILY_UPDATE_SYSTEM.md`
- **Health Check**: `GET /api/cron/health`
- **Validation**: `python3 scripts/verify_updates.py`
- **GitHub Issues**: Report bugs and feature requests

---

**Checklist Version**: 1.0
**Last Updated**: October 13, 2025
**Next Review**: After first successful deployment
