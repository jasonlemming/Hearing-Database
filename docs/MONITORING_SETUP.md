# Monitoring Setup Guide

**Purpose**: Configure external monitoring and alerting for the Congressional Hearing Database daily updates

**Estimated Setup Time**: 30-45 minutes

---

## Overview

This guide covers setting up automated monitoring to ensure daily updates run successfully and alert you to any issues.

### Monitoring Approaches

1. **Health Check Script** (Recommended for self-hosting)
2. **External Monitoring Services** (Recommended for production)
3. **Built-in Notifications** (Email/Webhook alerts)

---

## Option 1: Health Check Script

Use the included `check_health.sh` script for manual or cron-based monitoring.

### Manual Health Check

```bash
# Check your deployed application
./scripts/check_health.sh https://your-app.vercel.app/api/cron/health

# Or set environment variable
export HEALTH_CHECK_URL=https://your-app.vercel.app/api/cron/health
./scripts/check_health.sh
```

**Output**:
- ✅ HEALTHY (exit code 0)
- ⚠️  DEGRADED (exit code 1) - warnings present
- ❌ UNHEALTHY (exit code 2) - critical issues
- ❌ ERROR (exit code 3) - cannot connect

### Automated Monitoring with Cron

Add to your crontab to check health every 30 minutes:

```bash
# Edit crontab
crontab -e

# Add this line (replace paths and email):
*/30 * * * * /path/to/check_health.sh https://your-app.vercel.app/api/cron/health || echo "Health check failed at $(date)" | mail -s "Database Health Alert" admin@example.com
```

**Alternative**: Save results to log file:

```bash
*/30 * * * * /path/to/check_health.sh https://your-app.vercel.app/api/cron/health >> /var/log/hearing-db-health.log 2>&1
```

---

## Option 2: External Monitoring Services

### UptimeRobot (Free Tier Available)

**Setup**:
1. Sign up at https://uptimerobot.com
2. Create new monitor:
   - **Monitor Type**: HTTP(s)
   - **URL**: `https://your-app.vercel.app/api/cron/health`
   - **Monitoring Interval**: 5 minutes (free tier)
   - **Monitor Timeout**: 30 seconds

3. Configure Alert Contacts:
   - Email
   - SMS (limited on free tier)
   - Webhook (Slack/Discord)

4. **Advanced Settings**:
   - Custom HTTP Headers: None required
   - Status Codes: Expect 200 (healthy) or 503 (unhealthy)
   - Response Time Threshold: 5000ms

**Alert Thresholds**:
- Alert when status code is 503
- Alert when response time > 10 seconds
- Alert when down for > 5 minutes

### Pingdom

**Setup**:
1. Sign up at https://www.pingdom.com
2. Add Uptime Check:
   - **Name**: Hearing Database Health
   - **URL**: `https://your-app.vercel.app/api/cron/health`
   - **Check Interval**: 5 minutes

3. Configure Response Time Alerts:
   - Slow: > 5 seconds
   - Critical: > 15 seconds

### Healthchecks.io (Free, Open Source)

**Setup**:
1. Sign up at https://healthchecks.io
2. Create new check:
   - **Name**: Daily Update Health
   - **Schedule**: Every 6 hours (should run daily at 6 AM UTC)
   - **Grace Time**: 1 hour

3. **Integration Method**: Use cron job to ping healthchecks.io after successful health check:

```bash
# Add to crontab
0 7 * * * /path/to/check_health.sh https://your-app.vercel.app/api/cron/health && curl -fsS https://hc-ping.com/YOUR-UUID-HERE > /dev/null
```

---

## Option 3: Built-in Notifications

Configure the application to send notifications on failures.

### Setup Email Notifications (SendGrid)

1. **Get SendGrid API Key**:
   - Sign up at https://sendgrid.com (free tier: 100 emails/day)
   - Create API key with "Mail Send" permissions

2. **Configure Environment Variables** in Vercel:

```bash
vercel env add NOTIFICATION_ENABLED
# Enter: true

vercel env add NOTIFICATION_TYPE
# Enter: email

vercel env add SENDGRID_API_KEY
# Enter: your-sendgrid-api-key

vercel env add NOTIFICATION_EMAIL
# Enter: admin@example.com
```

3. **Redeploy**:

```bash
vercel --prod
```

4. **Test** (optional):

```bash
# Manually trigger update to test notifications
curl -X POST \
  -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/test-schedule/3
```

### Setup Webhook Notifications (Discord/Slack)

#### Discord Webhook

1. **Create Discord Webhook**:
   - Open Discord Server Settings
   - Go to Integrations → Webhooks
   - Create New Webhook
   - Copy Webhook URL

2. **Configure Environment Variables**:

```bash
vercel env add NOTIFICATION_ENABLED
# Enter: true

vercel env add NOTIFICATION_TYPE
# Enter: webhook

vercel env add NOTIFICATION_WEBHOOK_URL
# Enter: https://discord.com/api/webhooks/...
```

3. **Redeploy**:

```bash
vercel --prod
```

#### Slack Webhook

1. **Create Slack Incoming Webhook**:
   - Go to https://api.slack.com/apps
   - Create New App → From scratch
   - Enable Incoming Webhooks
   - Add New Webhook to Workspace
   - Copy Webhook URL

2. **Configure Environment Variables**:

```bash
vercel env add NOTIFICATION_ENABLED
# Enter: true

vercel env add NOTIFICATION_TYPE
# Enter: webhook

vercel env add NOTIFICATION_WEBHOOK_URL
# Enter: https://hooks.slack.com/services/...
```

3. **Redeploy**:

```bash
vercel --prod
```

---

## Monitoring Dashboard Setup (Advanced)

### Custom Dashboard with Grafana

If you want advanced monitoring with graphs and dashboards:

1. **Set up Prometheus exporter** (requires custom endpoint):

```python
# Add to api/cron-update.py
@app.route('/api/cron/metrics', methods=['GET'])
def metrics():
    """Prometheus-compatible metrics endpoint"""
    # Export metrics in Prometheus format
    pass
```

2. **Configure Prometheus** to scrape metrics
3. **Set up Grafana** with Prometheus data source
4. **Create dashboards** for:
   - Update success rate
   - API request rate
   - Error rate over time
   - Database size growth

### Simple Web Dashboard

Create a simple status page using the health endpoint:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Database Health Status</title>
    <script>
        async function checkHealth() {
            const response = await fetch('https://your-app.vercel.app/api/cron/health');
            const data = await response.json();
            document.getElementById('status').textContent = data.status;
            document.getElementById('details').textContent = JSON.stringify(data, null, 2);
        }
        setInterval(checkHealth, 60000); // Check every minute
        checkHealth(); // Initial check
    </script>
</head>
<body>
    <h1>Congressional Hearing Database Status</h1>
    <p>Status: <span id="status">Loading...</span></p>
    <pre id="details"></pre>
</body>
</html>
```

---

## Alert Thresholds & Best Practices

### Recommended Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| **Health Status** | degraded | unhealthy (503) |
| **Hours Since Update** | > 30h | > 48h |
| **Error Rate** | > 5% | > 10% |
| **Database Size** | > 30 MB | > 50 MB |
| **API Requests** | > 3000/day | > 4500/day |
| **Response Time** | > 5s | > 15s |
| **Circuit Breaker** | half_open | open |

### Alert Fatigue Prevention

1. **Escalation**:
   - First failure: Log only
   - Second consecutive failure: Send warning
   - Third consecutive failure: Send critical alert

2. **Quiet Hours**:
   - Suppress non-critical alerts between 11 PM - 7 AM local time
   - Always alert for critical issues (circuit breaker open, > 24h since update)

3. **Alert Grouping**:
   - Group similar alerts within 1-hour window
   - Send digest instead of individual alerts

4. **Maintenance Windows**:
   - Disable monitoring during planned maintenance
   - Use environment variable: `MAINTENANCE_MODE=true`

---

## Monitoring Checklist

### Daily Monitoring (Automated)

- [ ] Health check returns 200 (healthy) or 200 (degraded)
- [ ] Last update within 24 hours
- [ ] Error rate < 10%
- [ ] Circuit breaker closed

### Weekly Review (Manual)

- [ ] Review update_logs for patterns
- [ ] Check database size growth trends
- [ ] Verify hearing count is increasing (when Congress active)
- [ ] Review notification history
- [ ] Check API usage (should be < 5000/day)

### Monthly Maintenance

- [ ] Run database maintenance: `python scripts/database_maintenance.py --full`
- [ ] Review and clean old logs: `--cleanup-logs 90`
- [ ] Update monitoring thresholds based on trends
- [ ] Test notification channels

---

## Troubleshooting Monitoring Issues

### Health Check Returns 503

**Possible causes**:
1. Database corruption → Run `python scripts/verify_updates.py`
2. Last update > 48h ago → Check cron schedule is active
3. Circuit breaker open → Wait for recovery or investigate API issues

**Resolution**:
```bash
# Check logs
vercel logs --follow

# Manually trigger update
curl -X POST -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://your-app.vercel.app/api/cron/test-schedule/3

# Reset circuit breaker (requires code change to add reset endpoint)
```

### No Notifications Received

**Check**:
1. `NOTIFICATION_ENABLED=true` in environment variables
2. Notification credentials configured correctly
3. Check application logs for notification errors
4. Test with manual update trigger

**Debug**:
```bash
# Check environment variables
vercel env ls

# View recent logs
vercel logs --since 1h
```

### External Monitor Shows Down

**Check**:
1. Vercel deployment status
2. Health endpoint accessible in browser
3. Response time (should be < 5s)
4. Vercel function timeout (default: 10s)

---

## Example Monitoring Configurations

### Complete Cron Setup

```bash
# /etc/cron.d/hearing-database-monitor

# Health check every 30 minutes
*/30 * * * * /opt/scripts/check_health.sh https://hearing-database.vercel.app/api/cron/health >> /var/log/hearing-db-health.log 2>&1

# Alert on failure (uses previous exit code)
*/30 * * * * /opt/scripts/check_health.sh https://hearing-database.vercel.app/api/cron/health || /opt/scripts/send_alert.sh "Health check failed"

# Weekly report (Sundays at 9 AM)
0 9 * * 0 /opt/scripts/weekly_report.sh | mail -s "Weekly Database Report" admin@example.com
```

### GitHub Actions Monitoring

```yaml
# .github/workflows/health-check.yml
name: Health Check

on:
  schedule:
    - cron: '*/30 * * * *'  # Every 30 minutes
  workflow_dispatch:  # Manual trigger

jobs:
  health-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check Health
        run: |
          ./scripts/check_health.sh https://hearing-database.vercel.app/api/cron/health

      - name: Send Alert on Failure
        if: failure()
        uses: dawidd6/action-send-mail@v3
        with:
          server_address: smtp.gmail.com
          server_port: 465
          username: ${{secrets.EMAIL_USERNAME}}
          password: ${{secrets.EMAIL_PASSWORD}}
          subject: Health Check Failed
          body: Health check failed. Check logs for details.
          to: admin@example.com
          from: github-actions@example.com
```

---

## Next Steps

After setting up monitoring:

1. **Verify** alerts are working by manually triggering a failure
2. **Document** your monitoring setup in your team wiki
3. **Set calendar reminders** for weekly/monthly reviews
4. **Create runbook** for common alert responses
5. **Test disaster recovery** by simulating failures

---

## Support

- **Health Check Script**: `scripts/check_health.sh --help`
- **Notification Testing**: Manually trigger update via curl
- **Health Endpoint**: `GET /api/cron/health`
- **Documentation**: `/docs/DAILY_UPDATE_SYSTEM.md`

---

**Last Updated**: October 13, 2025
**Version**: 1.0
