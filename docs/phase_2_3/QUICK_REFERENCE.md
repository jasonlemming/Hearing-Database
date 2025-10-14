# Phase 2.3.1: Quick Reference Card

**For**: Production Deployment & Operations
**Version**: 1.0
**Status**: ✅ Production Ready

---

## 🚀 Quick Start

### Enable Batch Processing

```bash
# Set environment variable
export ENABLE_BATCH_PROCESSING=true

# Optional: Configure batch size (default: 50)
export BATCH_PROCESSING_SIZE=50

# Run daily update
python3 -m updaters.daily_updater --congress 119 --lookback-days 7
```

### Disable Batch Processing (Rollback to Phase 2.2)

```bash
# Unset or set to false
export ENABLE_BATCH_PROCESSING=false

# Or remove from .env file
```

---

## 📊 Check If Batch Processing Is Active

### In Logs

Look for this line:
```
✓ Batch processing ENABLED - using Phase 2.3.1 batch processing
```

Or for Phase 2.2:
```
Batch processing DISABLED - using Phase 2.2 standard processing
```

### In Code

```python
from config.settings import Settings
settings = Settings()
print(f"Batch processing: {settings.enable_batch_processing}")
```

---

## 📈 Monitor Batch Processing

### Key Log Lines

```bash
# Batch processing enabled
grep "Batch processing ENABLED" logs/daily_update_*.log

# Batch summary
grep "Batch Processing Summary" logs/daily_update_*.log -A 5

# Batch failures
grep "Batch.*failed" logs/daily_update_*.log

# Validation failures
grep "failed validation" logs/daily_update_*.log
```

### Key Metrics

From update logs, look for:
```json
{
  "batch_processing": {
    "enabled": true,
    "batch_count": 5,
    "batches_succeeded": 5,
    "batches_failed": 0,
    "batch_errors": []
  }
}
```

---

## 🚨 Common Issues & Solutions

### Issue 1: Batch Processing Not Activating

**Symptom**: Logs show "Batch processing DISABLED"

**Solution**:
```bash
# Check environment variable
echo $ENABLE_BATCH_PROCESSING

# Should be "true", if not:
export ENABLE_BATCH_PROCESSING=true

# Or add to .env file
echo "ENABLE_BATCH_PROCESSING=true" >> .env
```

### Issue 2: High Batch Failure Rate (> 10%)

**Symptom**: Many batches failing validation

**Solution**:
1. Check batch_errors in logs for specific issues
2. Review data quality
3. Consider increasing batch size to reduce batch count

```bash
# Increase batch size
export BATCH_PROCESSING_SIZE=100
```

### Issue 3: Performance Degradation

**Symptom**: Processing taking longer than Phase 2.2

**Solution**:
1. Check batch size (optimal: 50)
2. Review system resources
3. Consider disabling temporarily

```bash
# Try different batch sizes
export BATCH_PROCESSING_SIZE=25  # More batches, less per batch
# or
export BATCH_PROCESSING_SIZE=100  # Fewer batches, more per batch
```

### Issue 4: Database Corruption Suspected

**Symptom**: PRAGMA integrity_check fails

**Solution** (CRITICAL):
```bash
# 1. IMMEDIATELY disable batch processing
export ENABLE_BATCH_PROCESSING=false

# 2. Check integrity
sqlite3 database.db "PRAGMA integrity_check;"

# 3. If not "ok", restore from backup
cp backups/database_backup_YYYYMMDD_HHMMSS.db database.db

# 4. Verify restore
sqlite3 database.db "PRAGMA integrity_check;"

# 5. Document issue and notify team
```

---

## 🔍 Troubleshooting Commands

### Check Database Integrity

```bash
sqlite3 database.db "PRAGMA integrity_check;"
# Expected: ok
```

### Check Foreign Keys

```bash
sqlite3 database.db "PRAGMA foreign_key_check;"
# Expected: (empty output)
```

### Count Hearings

```bash
sqlite3 database.db "SELECT COUNT(*) FROM hearings WHERE congress = 119;"
```

### Find Latest Backup

```bash
ls -lt backups/database_backup_*.db | head -1
```

### View Recent Errors

```bash
tail -100 logs/daily_update_$(date +%Y%m%d).log | grep -i error
```

### Check Batch Metrics

```bash
tail -50 logs/daily_update_$(date +%Y%m%d).log | grep -A 10 "Batch Processing Summary"
```

---

## 📝 Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_BATCH_PROCESSING` | `false` | Enable/disable batch processing |
| `BATCH_PROCESSING_SIZE` | `50` | Number of hearings per batch |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG for details) |

### Recommended Batch Sizes

| Dataset Size | Recommended Size | Rationale |
|--------------|------------------|-----------|
| < 100 hearings | 25-50 | Small batches, quick processing |
| 100-500 hearings | 50 | Optimal balance (tested) |
| > 500 hearings | 50-100 | Larger batches, fewer overhead |

---

## 🎯 Success Criteria

### Daily Checks

- [ ] Batch processing enabled: `true` or `false`
- [ ] Batch count > 0 (if data to process)
- [ ] Batch failure rate < 10%
- [ ] Processing duration within ±20% of baseline
- [ ] No errors in logs

### Weekly Checks

- [ ] Average batch success rate >= 95%
- [ ] Performance stable (±10% week-over-week)
- [ ] No data corruption (PRAGMA integrity_check = "ok")
- [ ] Disk space sufficient (backups growing)

---

## 📞 Escalation

### When to Disable Batch Processing

**Minor Issues** (monitor):
- Batch failure rate 10-20%
- Performance 10-20% slower than baseline
- Occasional validation errors

**Major Issues** (disable immediately):
- Batch failure rate > 20%
- Performance > 20% slower than baseline
- Repeated errors or crashes

**Critical Issues** (disable + restore):
- Data corruption detected
- Database integrity check fails
- System crashes or hangs

### Emergency Rollback

```bash
# 1. Stop any running updates
pkill -f "daily_updater"

# 2. Disable batch processing
export ENABLE_BATCH_PROCESSING=false

# 3. Restore database from backup (if corruption)
cp backups/database_backup_LATEST.db database.db

# 4. Verify
sqlite3 database.db "PRAGMA integrity_check;"

# 5. Restart with Phase 2.2
python3 -m updaters.daily_updater --congress 119 --lookback-days 7
```

---

## 📚 Documentation Links

- **Complete Summary**: `PHASE_2_3_1_COMPLETE_SUMMARY.md`
- **Decision Gate**: `DAY_13_DECISION_GATE_FINAL.md`
- **Trial Gate**: `DAY_10_12_TRIAL_GATE_REPORT.md`
- **Implementation**: `DAY_9_VALIDATION_GATE.md`
- **Architecture**: `DAY_8_REVIEW_GATE.md`
- **Testing**: `DAY_6_7_TESTING_GATE.md`

---

## 🧪 Test Batch Processing

```python
# Quick test script
from updaters.daily_updater import DailyUpdater

updater = DailyUpdater(congress=119, lookback_days=7)
updater.settings.enable_batch_processing = True
updater.settings.batch_processing_size = 50

print(f"Batch processing: {updater.settings.enable_batch_processing}")
print(f"Batch size: {updater.settings.batch_processing_size}")

# Test with mock data
changes = {
    'updates': [],
    'additions': [
        {'eventId': f'TEST-{i}', 'chamber': 'House', 'title': f'Test {i}'}
        for i in range(100)
    ]
}

updater._apply_updates_with_batches(changes)

print(f"Batches: {updater.metrics.batch_count}")
print(f"Succeeded: {updater.metrics.batches_succeeded}")
print(f"Failed: {updater.metrics.batches_failed}")
```

---

## ✅ Deployment Checklist

### Pre-Deployment

- [ ] Code deployed to production
- [ ] Environment variables configured
- [ ] `ENABLE_BATCH_PROCESSING=false` (start with Phase 2.2)
- [ ] Logs directory exists and writable
- [ ] Backups directory exists and writable
- [ ] Database backup recent (< 24h)

### Week 1: Phase 2.2 Baseline

- [ ] Run daily updates with batch processing disabled
- [ ] Monitor logs for errors
- [ ] Verify database integrity daily
- [ ] Collect baseline metrics (duration, success rate)
- [ ] No issues for 7 consecutive days

### Week 2: Enable Batch Processing

- [ ] Set `ENABLE_BATCH_PROCESSING=true`
- [ ] Monitor first run closely (watch logs in real-time)
- [ ] Verify "Batch processing ENABLED" in logs
- [ ] Check batch count is reasonable
- [ ] Monitor for 7 consecutive days
- [ ] Compare metrics with Phase 2.2 baseline

### Week 3+: Optimization

- [ ] Review batch size performance
- [ ] Test alternative batch sizes if needed
- [ ] Address any minor issues
- [ ] Document lessons learned
- [ ] Consider expansion to other congresses

---

## 💡 Tips & Tricks

### Debug Mode

```bash
# Enable verbose logging
export LOG_LEVEL=DEBUG
python3 -m updaters.daily_updater --congress 119 --lookback-days 7
```

### Monitor in Real-Time

```bash
# Watch logs as they happen
tail -f logs/daily_update_$(date +%Y%m%d).log
```

### Compare Phase 2.2 vs Batch Processing

```bash
# Run with disabled
ENABLE_BATCH_PROCESSING=false time python3 -m updaters.daily_updater --congress 119 --lookback-days 7

# Run with enabled
ENABLE_BATCH_PROCESSING=true time python3 -m updaters.daily_updater --congress 119 --lookback-days 7

# Compare "real" time
```

### Find Optimal Batch Size

```bash
# Test different sizes
for SIZE in 25 50 100 200; do
  echo "Testing batch size: $SIZE"
  BATCH_PROCESSING_SIZE=$SIZE time python3 -m updaters.daily_updater --congress 119 --lookback-days 7
done
```

---

## 📊 Performance Baselines

### Typical Performance (201 changes)

| Batch Size | Duration | Batches | Status |
|------------|----------|---------|--------|
| 25 | 179ms | 9 | Good |
| 50 | 171ms | 5 | **Optimal** |
| 100 | 173ms | 3 | Good |
| 200 | 188ms | 2 | Acceptable |

### Expected Metrics

**Small Update** (< 50 changes):
- Duration: < 200ms
- Batches: 1-2
- Success rate: 100%

**Medium Update** (50-200 changes):
- Duration: < 500ms
- Batches: 2-5
- Success rate: >= 95%

**Large Update** (> 200 changes):
- Duration: < 2s
- Batches: 5-10
- Success rate: >= 95%

---

**Version**: 1.0
**Last Updated**: October 13, 2025
**Status**: ✅ Production Ready
