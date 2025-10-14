# Phase 2.3.1 Days 10-12: Trial Gate Implementation Plan

**Date**: October 13, 2025
**Stage**: 2.3.1 - Batch Processing with Validation Checkpoints
**Days**: 10-12 of 13
**Status**: 📋 **READY FOR EXECUTION**

---

## Executive Summary

Days 10-12 constitute the **Trial Gate** - deploying Phase 2.3.1 to a staging environment and observing performance, reliability, and behavior over a 48-hour period before production deployment.

**Objective**: Validate that batch processing works correctly in a real environment with real data and meets all performance and reliability requirements.

---

## Prerequisites (All Complete ✅)

- [x] Days 1-8: Core implementation complete
- [x] Day 9: Integration implementation complete
- [x] All 25 tests passing
- [x] Feature flag implemented
- [x] Phase 2.2 fallback verified
- [x] Documentation complete

**Ready to Begin Trial Gate**: ✅ YES

---

## Trial Gate Overview

### Timeline

| Day | Phase | Duration | Description |
|-----|-------|----------|-------------|
| **Day 10** | Setup + Baseline | 2-3 hours active | Deploy to staging, run Phase 2.2 baseline |
| **Day 10-11** | Observation (Phase 1) | 24 hours passive | Monitor Phase 2.2 baseline behavior |
| **Day 11** | Enable Batch Processing | 1-2 hours active | Enable feature flag, monitor first run |
| **Day 11-12** | Observation (Phase 2) | 24 hours passive | Monitor batch processing behavior |
| **Day 12** | Performance Testing | 2-3 hours active | Test various scenarios and batch sizes |
| **Day 12** | Trial Gate Report | 1 hour | Document findings and recommendation |

**Total Active Time**: 6-9 hours
**Total Observation Time**: 48 hours
**Overall Duration**: 3 days

---

## Day 10: Setup + Phase 2.2 Baseline

### Objectives
1. Deploy current codebase to staging
2. Run Phase 2.2 baseline (feature flag disabled)
3. Collect baseline metrics
4. Begin 24-hour observation

### Tasks

#### Task 1: Staging Environment Verification (~30 min)

**Checklist**:
- [ ] Staging environment accessible
- [ ] Database accessible and up-to-date
- [ ] Congress.gov API key configured
- [ ] Logging configured
- [ ] Monitoring/alerting configured (if available)

**Commands**:
```bash
# Verify environment
python3 -c "from config.settings import Settings; s = Settings(); print(f'DB: {s.database_path}'); print(f'API: {s.api_key[:10]}...')"

# Verify database
sqlite3 database.db "SELECT COUNT(*) FROM hearings;"

# Verify API access
curl -H "x-api-key: YOUR_KEY" "https://api.congress.gov/v3/hearing/119?limit=1"
```

#### Task 2: Deploy to Staging (~30 min)

**Steps**:
1. Pull latest code from main branch
2. Verify feature flag is disabled by default
3. Install dependencies
4. Verify all tests pass in staging environment

**Commands**:
```bash
# Pull latest
git pull origin main

# Verify feature flag
grep "enable_batch_processing" config/settings.py
# Should see: enable_batch_processing: bool = Field(default=False, ...)

# Install dependencies
source .venv/bin/activate
pip install -r requirements-local.txt

# Run tests
pytest tests/test_batch_processing.py -v
# Should see: 25 passed, 6 skipped
```

#### Task 3: Run Phase 2.2 Baseline (~1 hour)

**Objective**: Collect baseline performance metrics with Phase 2.2 (batch processing disabled)

**Steps**:
1. Ensure `ENABLE_BATCH_PROCESSING=false` (or not set - defaults to false)
2. Run daily update with 7-day lookback
3. Capture metrics
4. Document baseline performance

**Commands**:
```bash
# Verify flag is disabled
echo $ENABLE_BATCH_PROCESSING
# Should be empty or "false"

# Run daily update
time python3 -m updaters.daily_updater \
    --congress 119 \
    --lookback-days 7 \
    2>&1 | tee logs/trial_gate_phase22_baseline.log

# Extract metrics from log
tail -50 logs/trial_gate_phase22_baseline.log | grep -A 20 "Daily update completed"
```

**Metrics to Capture**:
- Total duration (seconds)
- Hearings checked
- Hearings updated
- Hearings added
- API requests made
- Errors encountered
- Memory usage (if available)

**Expected Baseline** (example):
```json
{
  "duration_seconds": 45.2,
  "hearings_checked": 150,
  "hearings_updated": 23,
  "hearings_added": 5,
  "api_requests": 155,
  "error_count": 0,
  "validation_passed": true
}
```

#### Task 4: Begin 24-Hour Observation (~15 min)

**Setup**:
1. Schedule hourly health checks
2. Monitor error logs
3. Monitor database integrity

**Monitoring Script**:
```bash
#!/bin/bash
# trial_gate_monitor.sh
# Run every hour during observation period

echo "=== Trial Gate Health Check: $(date) ==="

# Check database integrity
sqlite3 database.db "PRAGMA integrity_check;" | head -1

# Check for errors in logs
echo "Recent errors:"
tail -1000 logs/daily_update_*.log | grep -i "error" | tail -5

# Check disk space
df -h database.db

# Check process status
ps aux | grep daily_updater | grep -v grep

echo "=== End Health Check ==="
```

**Add to crontab**:
```bash
# Monitor every hour during Trial Gate
0 * * * * /path/to/trial_gate_monitor.sh >> /path/to/trial_gate_health.log 2>&1
```

---

## Day 11: Enable Batch Processing

### Objectives
1. Enable batch processing via feature flag
2. Monitor first run with batch processing
3. Begin 24-hour observation with batch processing

### Tasks

#### Task 1: Enable Feature Flag (~5 min)

**Method 1: Environment Variable** (Recommended)
```bash
# Set environment variable
export ENABLE_BATCH_PROCESSING=true
export BATCH_PROCESSING_SIZE=50

# Verify
echo $ENABLE_BATCH_PROCESSING
```

**Method 2: .env File**
```bash
# Add to .env
echo "ENABLE_BATCH_PROCESSING=true" >> .env
echo "BATCH_PROCESSING_SIZE=50" >> .env
```

#### Task 2: First Run with Batch Processing (~1 hour)

**Objective**: Monitor first execution of batch processing in staging

**Steps**:
1. Enable verbose logging
2. Run daily update
3. Monitor in real-time
4. Capture detailed metrics

**Commands**:
```bash
# Enable verbose logging (optional)
export LOG_LEVEL=DEBUG

# Run daily update with batch processing
time python3 -m updaters.daily_updater \
    --congress 119 \
    --lookback-days 7 \
    2>&1 | tee logs/trial_gate_batch_first_run.log

# Monitor in real-time (in another terminal)
tail -f logs/trial_gate_batch_first_run.log
```

**Key Log Lines to Watch For**:
```
✓ Batch processing ENABLED - using Phase 2.3.1 batch processing
Divided into X batches of up to 50 changes each
✓ Batch 1/X succeeded: Y records
Batch Processing Summary:
  Total batches: X
  Succeeded: Y
  Failed: Z
```

#### Task 3: Analyze First Run Results (~30 min)

**Verification Checklist**:
- [ ] Batch processing activated (check log for "ENABLED" message)
- [ ] All batches processed successfully
- [ ] No errors or exceptions
- [ ] Batch metrics recorded
- [ ] Performance comparable to Phase 2.2 baseline
- [ ] Database integrity maintained

**Metrics Comparison**:
```bash
# Compare Phase 2.2 vs Batch Processing
echo "Phase 2.2 Baseline:"
grep "duration_seconds" logs/trial_gate_phase22_baseline.log

echo "Batch Processing First Run:"
grep "duration_seconds" logs/trial_gate_batch_first_run.log

# Check batch metrics
grep -A 5 "batch_processing" logs/trial_gate_batch_first_run.log
```

**Expected Batch Metrics**:
```json
{
  "duration_seconds": 42.8,  // ±10% of baseline (45.2s)
  "hearings_checked": 150,
  "hearings_updated": 23,
  "hearings_added": 5,
  "batch_processing": {
    "enabled": true,
    "batch_count": 1,
    "batches_succeeded": 1,
    "batches_failed": 0,
    "batch_errors": []
  }
}
```

#### Task 4: Continue 24-Hour Observation (~passive)

**Monitoring**:
- Same health checks as Day 10
- Additional batch-specific metrics
- Watch for any anomalies

---

## Day 12: Performance Testing + Trial Gate Report

### Objectives
1. Conduct comprehensive performance testing
2. Test failure scenarios
3. Measure performance with various batch sizes
4. Create Trial Gate Report with recommendation

### Tasks

#### Task 1: Performance Testing (~2 hours)

##### Test 1.1: Batch Size Variation (~30 min)

**Objective**: Find optimal batch size

**Test Cases**:
| Test | Batch Size | Expected Result |
|------|------------|-----------------|
| A | 25 | Slower (more batches, more overhead) |
| B | 50 | Baseline (default) |
| C | 100 | Faster (fewer batches) |
| D | 200 | Similar to C (diminishing returns) |

**Commands**:
```bash
for SIZE in 25 50 100 200; do
  echo "Testing batch size: $SIZE"
  export BATCH_PROCESSING_SIZE=$SIZE

  time python3 -m updaters.daily_updater \
      --congress 119 \
      --lookback-days 7 \
      2>&1 | tee logs/trial_gate_batch_size_${SIZE}.log

  # Extract duration
  grep "duration_seconds" logs/trial_gate_batch_size_${SIZE}.log

  sleep 60  # Wait between runs
done
```

##### Test 1.2: Large Dataset Test (~30 min)

**Objective**: Test with large number of changes (500+ hearings)

**Commands**:
```bash
# Use longer lookback to get more changes
time python3 -m updaters.daily_updater \
    --congress 119 \
    --lookback-days 90 \
    2>&1 | tee logs/trial_gate_large_dataset.log

# Verify performance requirement: 500 hearings in < 5 seconds
grep "duration_seconds" logs/trial_gate_large_dataset.log
grep "hearings_checked" logs/trial_gate_large_dataset.log
```

**Success Criteria**:
- 500 hearings processed in < 5 seconds (P1 requirement)
- No memory issues
- All batches succeed

##### Test 1.3: Memory Usage Monitoring (~15 min)

**Objective**: Verify memory increase < 100MB (P4 requirement)

**Commands**:
```bash
# Monitor memory during update
python3 -c "
import psutil
import subprocess
import time

# Get baseline memory
baseline = psutil.Process().memory_info().rss / 1024 / 1024  # MB

print(f'Baseline memory: {baseline:.2f} MB')

# Run update
proc = subprocess.Popen(['python3', '-m', 'updaters.daily_updater',
                         '--congress', '119', '--lookback-days', '7'])

# Monitor memory usage
peak_memory = baseline
while proc.poll() is None:
    mem = psutil.Process(proc.pid).memory_info().rss / 1024 / 1024
    if mem > peak_memory:
        peak_memory = mem
    time.sleep(1)

increase = peak_memory - baseline
print(f'Peak memory: {peak_memory:.2f} MB')
print(f'Memory increase: {increase:.2f} MB')
print(f'Requirement (< 100MB): {'✅ PASS' if increase < 100 else '❌ FAIL'}')
"
```

#### Task 2: Failure Injection Testing (~1 hour)

##### Test 2.1: Validation Failure (~20 min)

**Objective**: Verify batch validation catches issues and skips bad batches

**Setup**: Create test data with intentionally invalid hearings

**Test Script**:
```python
# test_failure_injection.py
from updaters.daily_updater import DailyUpdater

updater = DailyUpdater(congress=119, lookback_days=7)
updater.settings.enable_batch_processing = True
updater.settings.batch_processing_size = 2  # Small batches for testing

# Create test changes with one invalid hearing
changes = {
    'updates': [],
    'additions': [
        # Valid hearing
        {
            'eventId': 'TEST-119-001',
            'chamber': 'House',
            'title': 'Valid Hearing'
        },
        # Invalid hearing (missing eventId)
        {
            'chamber': 'Senate',
            'title': 'Invalid Hearing'
        },
        # Another valid hearing
        {
            'eventId': 'TEST-119-002',
            'chamber': 'House',
            'title': 'Another Valid Hearing'
        }
    ]
}

# Process - should skip invalid batch but succeed on valid ones
updater._apply_updates_with_batches(changes)

# Check metrics
print(f"Total batches: {updater.metrics.batch_count}")
print(f"Succeeded: {updater.metrics.batches_succeeded}")
print(f"Failed: {updater.metrics.batches_failed}")

# Expected: 2 batches total, 1 succeeded, 1 failed (validation)
assert updater.metrics.batch_count == 2
assert updater.metrics.batches_failed == 1
assert updater.metrics.batches_succeeded == 1
print("✅ Partial failure test PASSED")
```

**Success Criteria**:
- Invalid batch is skipped (not rolled back, just not processed)
- Valid batches succeed
- >= 95% of data commits (F3 requirement)

##### Test 2.2: Rollback Test (~20 min)

**Objective**: Verify rollback works when batch processing fails

**Note**: This is hard to test without deliberately breaking the database or causing transaction failures. Document expected behavior.

**Expected Behavior**:
1. Batch fails during _process_batch()
2. _rollback_checkpoint() is called
3. All changes in that batch are reversed
4. Other batches are unaffected

**Manual Test**:
- Temporarily modify _process_batch() to throw an exception after tracking changes
- Verify rollback is called
- Verify checkpoint data is used to reverse changes
- Restore original _process_batch()

##### Test 2.3: Database Integrity Test (~20 min)

**Objective**: Verify no corruption after batch processing

**Commands**:
```bash
# Run batch processing
python3 -m updaters.daily_updater --congress 119 --lookback-days 7

# Check database integrity
sqlite3 database.db "PRAGMA integrity_check;"
# Expected: "ok"

# Check for orphaned records
sqlite3 database.db "PRAGMA foreign_key_check;"
# Expected: empty (no violations)

# Check hearing counts (should match before/after)
sqlite3 database.db "SELECT COUNT(*) FROM hearings WHERE congress = 119;"

# Run validation script (if available)
python3 -m scripts.verify_updates
```

**Success Criteria**:
- PRAGMA integrity_check returns "ok"
- No foreign key violations
- Hearing counts match expectations
- No data loss (R2 requirement)

#### Task 3: Create Trial Gate Report (~1 hour)

**Report Sections**:
1. **Executive Summary**
   - Overall result (Pass/Fail)
   - Recommendation

2. **Deployment Timeline**
   - Day 10 activities
   - Day 11 activities
   - Day 12 activities

3. **Performance Results**
   - Phase 2.2 baseline metrics
   - Batch processing metrics
   - Comparison (% difference)
   - Batch size optimization results

4. **Reliability Results**
   - 48-hour observation summary
   - Error counts
   - Validation failures
   - Rollback successes

5. **Test Results**
   - Performance tests (P1-P5)
   - Reliability tests (R1-R4)
   - Functional tests (F1-F5)

6. **Issues Identified**
   - Any problems encountered
   - Workarounds applied
   - Recommendations for fixes

7. **Recommendation**
   - Proceed to production
   - Iterate (address issues first)
   - Abort (critical issues)

**Report Template**: See `DAY_10_12_TRIAL_GATE_REPORT_TEMPLATE.md`

---

## Success Criteria (Trial Gate)

### Performance Requirements (P1-P5)

- [ ] **P1**: 500 hearings processed in < 5 seconds
  - **Test**: Large dataset test (Test 1.2)
  - **Measurement**: grep duration_seconds + hearings_checked from log

- [ ] **P2**: Checkpoint creation < 50ms
  - **Status**: ✅ Already verified in Day 6-7 (< 1ms)

- [ ] **P3**: Batch validation < 200ms
  - **Status**: ✅ Already verified in Day 6-7 (~15ms)

- [ ] **P4**: Memory increase < 100MB
  - **Test**: Memory monitoring test (Test 1.3)
  - **Measurement**: psutil monitoring during execution

- [ ] **P5**: Performance ± 10% of Phase 2.2
  - **Test**: Comparison of Phase 2.2 baseline vs batch processing
  - **Measurement**: duration_seconds comparison

### Reliability Requirements (R1-R4)

- [ ] **R1**: >= 95% partial success rate with failures
  - **Test**: Failure injection test (Test 2.1)
  - **Measurement**: batches_succeeded / batch_count >= 0.95

- [ ] **R2**: Zero corruption incidents
  - **Test**: Database integrity test (Test 2.3)
  - **Measurement**: PRAGMA integrity_check = "ok"

- [ ] **R3**: 100% checkpoint rollback success
  - **Test**: Rollback test (Test 2.2)
  - **Status**: ✅ Verified in Day 5 tests (Tests 15-18)

- [ ] **R4**: Feature flag toggle works 100%
  - **Status**: ✅ Verified in Day 9 tests (Tests 19-21)

### Functional Requirements (F1-F5)

- [ ] **F1**: Process in batches of 50 hearings
  - **Verification**: Check batch_count in logs
  - **Expected**: hearings_total / 50 (rounded up)

- [ ] **F2**: Failed batch doesn't affect other batches
  - **Test**: Partial failure test (Test 2.1)
  - **Expected**: Other batches succeed

- [ ] **F3**: >= 95% of data commits on partial failure
  - **Test**: Partial failure test (Test 2.1)
  - **Measurement**: batches_succeeded / batch_count >= 0.95

- [ ] **F4**: Batch failures logged with details
  - **Verification**: Check batch_errors in logs
  - **Expected**: Error details for each failed batch

- [ ] **F5**: Feature flag toggle works
  - **Status**: ✅ Verified in Day 9 (Tests 19-21)
  - **Re-verify**: Disable flag, confirm Phase 2.2 behavior

---

## Rollback Plan

### If Issues Arise During Trial Gate

**Minor Issues** (proceed with caution):
- Adjust batch size
- Increase logging
- Continue observation

**Major Issues** (pause trial):
1. Set `ENABLE_BATCH_PROCESSING=false`
2. System falls back to Phase 2.2 immediately
3. Document issue
4. Fix issue in development
5. Re-run Day 9 tests
6. Restart Trial Gate

**Critical Issues** (abort):
- Data corruption detected
- Performance degradation > 50%
- Repeated crashes or failures

**Abort Procedure**:
1. Set `ENABLE_BATCH_PROCESSING=false`
2. Restore database from backup (if corruption detected)
3. Document issues thoroughly
4. Return to Day 8 (Review Gate) for re-architecture

---

## Monitoring Checklist

### Day 10-11: Phase 2.2 Baseline
- [ ] Hourly health checks running
- [ ] Database integrity checked (PRAGMA integrity_check)
- [ ] Error logs monitored
- [ ] Baseline metrics captured
- [ ] No anomalies detected

### Day 11-12: Batch Processing Observation
- [ ] Feature flag enabled successfully
- [ ] First run completed successfully
- [ ] Batch metrics captured
- [ ] Hourly health checks continuing
- [ ] Performance compared to baseline
- [ ] No anomalies detected

### Day 12: Testing
- [ ] Performance tests completed
- [ ] Failure injection tests completed
- [ ] Database integrity verified
- [ ] All success criteria met
- [ ] Trial Gate Report completed

---

## Deliverables

### Required Outputs

1. **Log Files**
   - `trial_gate_phase22_baseline.log`
   - `trial_gate_batch_first_run.log`
   - `trial_gate_batch_size_25.log`
   - `trial_gate_batch_size_50.log`
   - `trial_gate_batch_size_100.log`
   - `trial_gate_batch_size_200.log`
   - `trial_gate_large_dataset.log`
   - `trial_gate_health.log`

2. **Metrics**
   - Phase 2.2 baseline metrics (JSON)
   - Batch processing metrics (JSON)
   - Performance comparison table
   - Memory usage measurements

3. **Test Results**
   - Performance test results (P1-P5)
   - Reliability test results (R1-R4)
   - Functional verification (F1-F5)

4. **Trial Gate Report**
   - `DAY_10_12_TRIAL_GATE_REPORT.md`
   - Executive summary
   - Detailed results
   - Recommendation

---

## Next Steps After Trial Gate

### If Trial Gate Passes ✅

**Day 13: Decision Gate**
1. Review Trial Gate Report
2. Verify all success criteria met
3. Document final decision
4. Prepare production deployment plan
5. Create production rollout checklist

### If Trial Gate Needs Iteration 🔄

**Return to Development**
1. Document issues found
2. Prioritize fixes
3. Implement fixes
4. Re-run Day 9 tests
5. Restart Trial Gate

### If Trial Gate Fails ❌

**Abort and Re-architect**
1. Thoroughly document failure reasons
2. Return to Day 8 (Review Gate)
3. Re-evaluate architecture decisions
4. Plan alternative approach
5. Restart implementation

---

## Estimated Time Investment

### Active Work
- Day 10: 2-3 hours (setup + baseline)
- Day 11: 1-2 hours (enable + first run)
- Day 12: 3-4 hours (testing + report)
- **Total Active**: 6-9 hours

### Passive Observation
- Day 10-11: 24 hours (Phase 2.2 observation)
- Day 11-12: 24 hours (Batch processing observation)
- **Total Passive**: 48 hours

### Overall Timeline
- **3 days** (calendar time)
- **6-9 hours** (active work)

---

## Confidence Level

**Preparation**: ✅ **HIGH**

**Reasons**:
1. All code implemented and tested (25/25 tests passing)
2. Feature flag provides safety net
3. Phase 2.2 fallback verified
4. Clear success criteria defined
5. Comprehensive testing plan
6. Detailed monitoring plan
7. Clear rollback procedures

**Ready to Execute Trial Gate**: ✅ **YES**

---

**Document Version**: 1.0
**Created**: October 13, 2025 (After Day 9)
**Purpose**: Implementation guide for Trial Gate execution
**Status**: **READY FOR EXECUTION**
