# Phase 2.3: Enhanced Iterative Validation - PROPOSAL

**Status**: Proposed Enhancement
**Date**: October 13, 2025
**Priority**: High (addresses validation gap)

---

## Problem Statement

The current Phase 2.2 validation system uses a single-phase, all-or-nothing approach:
- Validates only at the end of the update
- Rolls back the entire update if validation fails
- No progressive validation during update execution
- No historical pattern validation
- No post-deployment monitoring of data quality

This approach has risks:
- Large updates that fail validation waste significant processing time
- Cannot identify which specific changes caused validation failure
- No ability to partially commit good data while rejecting bad data
- Missing gradual degradation detection

---

## Solution: Multi-Phase Iterative Validation

Implement a layered validation strategy with checkpoints, progressive validation, and continuous monitoring.

---

## Implementation Plan

### **Feature 1: Batch Processing with Validation Checkpoints**

**Goal**: Process updates in smaller batches with validation between each batch

**Implementation**:
```python
# In updaters/daily_updater.py

def _apply_updates_with_checkpoints(self, changes):
    """Apply updates in batches with validation after each batch"""

    BATCH_SIZE = 50  # Process 50 hearings at a time

    all_updates = changes['updates']
    all_additions = changes['additions']

    # Process updates in batches
    for i in range(0, len(all_updates), BATCH_SIZE):
        batch = all_updates[i:i + BATCH_SIZE]

        # Create micro-backup (in-memory state)
        checkpoint = self._create_checkpoint()

        try:
            # Apply this batch
            self._apply_batch_updates(batch)

            # Validate this batch
            validation_result = self._validate_batch(batch)

            if not validation_result['passed']:
                # Rollback just this batch
                self._rollback_to_checkpoint(checkpoint)
                logger.warning(f"Batch {i}-{i+BATCH_SIZE} failed validation, skipping")
                self.metrics.errors.append(f"Batch validation failed: {validation_result['issues']}")
                continue

            # Commit this batch
            self._commit_checkpoint()
            logger.info(f"✓ Batch {i}-{i+BATCH_SIZE} validated and committed")

        except Exception as e:
            self._rollback_to_checkpoint(checkpoint)
            logger.error(f"Batch {i}-{i+BATCH_SIZE} failed: {e}")
            self.metrics.errors.append(f"Batch processing error: {str(e)}")

    # Similar approach for additions
    # ...
```

**Benefits**:
- Partial success possible (commit good batches, skip bad ones)
- Faster failure detection
- Better error isolation
- Less wasted processing time

---

### **Feature 2: Historical Pattern Validation**

**Goal**: Validate current update against historical patterns and trends

**Implementation**:
```python
# In scripts/verify_updates.py

class HistoricalValidator:
    """Validate current data against historical patterns"""

    def validate_against_history(self):
        """Compare current update to historical patterns"""
        issues = []
        warnings = []

        with self.db.transaction() as conn:
            # Check: Hearing count growth rate
            cursor = conn.execute("""
                SELECT
                    update_date,
                    hearings_added,
                    hearings_updated
                FROM update_logs
                ORDER BY start_time DESC
                LIMIT 30
            """)
            history = cursor.fetchall()

            if len(history) >= 10:
                recent_adds = [h[1] for h in history[:3]]
                historical_avg = sum([h[1] for h in history[3:10]]) / 7
                historical_std = self._calculate_std([h[1] for h in history[3:10]])

                # Check if current update is >3 standard deviations from mean
                if abs(recent_adds[0] - historical_avg) > (3 * historical_std):
                    warnings.append(
                        f"Hearing additions ({recent_adds[0]}) deviate significantly "
                        f"from historical pattern (avg: {historical_avg:.1f}, std: {historical_std:.1f})"
                    )

            # Check: Committee activity patterns
            cursor = conn.execute("""
                SELECT committee_id, COUNT(*) as hearing_count
                FROM hearings
                WHERE hearing_date_only >= DATE('now', '-30 days')
                GROUP BY committee_id
            """)
            recent_activity = dict(cursor.fetchall())

            cursor = conn.execute("""
                SELECT committee_id, COUNT(*) as hearing_count
                FROM hearings
                WHERE hearing_date_only >= DATE('now', '-90 days')
                  AND hearing_date_only < DATE('now', '-30 days')
                GROUP BY committee_id
            """)
            historical_activity = dict(cursor.fetchall())

            # Detect committees with unusual activity changes
            for committee_id in recent_activity:
                recent = recent_activity[committee_id]
                historical = historical_activity.get(committee_id, 0)

                if historical > 0 and recent > historical * 3:
                    warnings.append(
                        f"Committee {committee_id} activity spike: "
                        f"{recent} hearings (30d) vs {historical} (prior 60d)"
                    )

            # Check: Witness appearance patterns
            cursor = conn.execute("""
                SELECT w.witness_id, w.name, COUNT(*) as appearance_count
                FROM witnesses w
                JOIN witness_appearances wa ON w.witness_id = wa.witness_id
                WHERE wa.hearing_id IN (
                    SELECT hearing_id FROM hearings
                    WHERE hearing_date_only >= DATE('now', '-30 days')
                )
                GROUP BY w.witness_id
                HAVING appearance_count > 5
            """)
            frequent_witnesses = cursor.fetchall()

            if frequent_witnesses:
                for witness_id, name, count in frequent_witnesses:
                    warnings.append(
                        f"Witness '{name}' appeared {count} times in last 30 days "
                        "(may indicate data duplication)"
                    )

        return {
            'passed': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
```

**Benefits**:
- Detects unusual patterns that static thresholds miss
- Identifies gradual data quality degradation
- Catches seasonal anomalies
- Better context for validation decisions

---

### **Feature 3: Multi-Stage Validation Pipeline**

**Goal**: Run validation at multiple stages with increasing rigor

**Implementation**:
```python
# In updaters/daily_updater.py

class ValidationStage(Enum):
    STAGE_0_PRE_UPDATE = "pre_update"          # Before any changes
    STAGE_1_FAST_CHECKS = "fast_checks"        # Quick checks during processing
    STAGE_2_BATCH_VALIDATION = "batch"         # After each batch
    STAGE_3_COMPREHENSIVE = "comprehensive"    # After all changes
    STAGE_4_MONITORING = "monitoring"          # Hours after update

def _run_multi_stage_validation(self, stage: ValidationStage, context: dict = None):
    """Run validation appropriate for current stage"""

    if stage == ValidationStage.STAGE_0_PRE_UPDATE:
        # Fast, critical checks only
        return self._run_pre_update_sanity_checks()

    elif stage == ValidationStage.STAGE_1_FAST_CHECKS:
        # Quick checks during processing (< 50ms)
        # - Check for obvious duplicates
        # - Verify foreign keys exist
        # - Basic data format validation
        return self._run_fast_validation_checks(context)

    elif stage == ValidationStage.STAGE_2_BATCH_VALIDATION:
        # Moderate checks after batch (< 200ms)
        # - Check batch data integrity
        # - Verify relationships within batch
        # - Compare batch to recent history
        return self._run_batch_validation(context)

    elif stage == ValidationStage.STAGE_3_COMPREHENSIVE:
        # Full validation suite (current post-update validation)
        return self._run_post_update_validation()

    elif stage == ValidationStage.STAGE_4_MONITORING:
        # Scheduled monitoring validation (run later via cron)
        # - Deep data quality analysis
        # - Cross-update consistency checks
        # - Long-term pattern validation
        return self._run_monitoring_validation()

def run_daily_update(self, dry_run=False, lookback_hours=None):
    """Enhanced update with multi-stage validation"""

    # Stage 0: Pre-update sanity checks
    if not self._run_multi_stage_validation(ValidationStage.STAGE_0_PRE_UPDATE):
        raise Exception("Stage 0 validation failed")

    # ... fetch changes ...

    # Create backup
    self.backup_path = self._create_database_backup()

    try:
        # Apply updates with Stage 1 & 2 validation
        for batch in self._batch_changes(changes):
            # Stage 1: Fast checks before applying batch
            if not self._run_multi_stage_validation(
                ValidationStage.STAGE_1_FAST_CHECKS,
                context={'batch': batch}
            ):
                logger.warning(f"Stage 1 validation failed for batch, skipping")
                continue

            # Apply batch
            self._apply_batch(batch)

            # Stage 2: Batch validation after applying
            if not self._run_multi_stage_validation(
                ValidationStage.STAGE_2_BATCH_VALIDATION,
                context={'batch': batch}
            ):
                logger.warning(f"Stage 2 validation failed, rolling back batch")
                self._rollback_batch(batch)
                continue

        # Stage 3: Comprehensive validation after all changes
        self._run_multi_stage_validation(ValidationStage.STAGE_3_COMPREHENSIVE)

        # Schedule Stage 4 for later (via scheduled task)
        self._schedule_monitoring_validation(delay_hours=6)

    except Exception as e:
        self._rollback_database()
        raise
```

**Benefits**:
- Catches errors early (faster feedback)
- Reduces rollback frequency (batch-level vs full update)
- Separates fast vs thorough validation
- Enables continuous monitoring

---

### **Feature 4: Canary Testing Mode**

**Goal**: Test changes on a small subset before full commit

**Implementation**:
```python
# In updaters/daily_updater.py

def _canary_test_changes(self, changes):
    """Test changes on small subset before full processing"""

    # Select 5% of changes as canary
    canary_size = max(5, int(len(changes['updates']) * 0.05))
    canary_updates = random.sample(changes['updates'], min(canary_size, len(changes['updates'])))

    logger.info(f"Running canary test with {len(canary_updates)} items")

    # Create temporary canary transaction
    canary_checkpoint = self._create_checkpoint()

    try:
        # Apply canary changes
        self._apply_batch_updates(canary_updates)

        # Run validation on canary
        validator = UpdateValidator(db_path=self.settings.database_path)
        canary_results = validator.run_all_checks(fix_issues=False)

        # Analyze canary results
        if not canary_results['passed']:
            logger.error(f"Canary test failed: {canary_results['issues']}")
            return False, canary_results

        if len(canary_results['warnings']) > len(canary_updates) * 0.2:
            logger.warning(f"Canary test has high warning rate: {len(canary_results['warnings'])}")
            return False, canary_results

        logger.info("✓ Canary test passed")
        return True, canary_results

    finally:
        # Always rollback canary (it was just a test)
        self._rollback_to_checkpoint(canary_checkpoint)

def run_daily_update(self, dry_run=False, lookback_hours=None):
    """Update with canary testing"""

    # ... existing pre-checks ...

    # Run canary test before full update
    if len(changes['updates']) > 20:  # Only for larger updates
        canary_passed, canary_results = self._canary_test_changes(changes)

        if not canary_passed:
            logger.error("Canary test failed - aborting full update")
            self.notifier.send(
                title="Update Aborted: Canary Test Failed",
                message=f"Canary test on {len(canary_results['updates'])} items failed validation",
                severity="warning",
                metadata={'issues': canary_results['issues']}
            )
            return self.metrics

    # Proceed with full update
    # ...
```

**Benefits**:
- Detect systemic issues before full processing
- Reduce risk of large failed updates
- Enable risk-based update strategies
- Better failure prediction

---

### **Feature 5: Post-Deployment Continuous Monitoring**

**Goal**: Monitor data quality over time after updates, not just immediately

**Implementation**:
```python
# New file: scripts/continuous_monitor.py

class ContinuousMonitor:
    """Monitor data quality continuously after updates"""

    def schedule_post_update_checks(self, update_log_id: int, check_times: list[int]):
        """Schedule validation checks at specified hours after update"""

        # Store scheduled checks in database
        with self.db.transaction() as conn:
            for hours_after in check_times:  # e.g., [1, 6, 24, 168]
                scheduled_time = datetime.now() + timedelta(hours=hours_after)
                conn.execute("""
                    INSERT INTO scheduled_validations
                    (update_log_id, scheduled_time, validation_type, status)
                    VALUES (?, ?, ?, ?)
                """, (update_log_id, scheduled_time.isoformat(),
                      f'post_update_{hours_after}h', 'pending'))

    def run_scheduled_validations(self):
        """Run any pending scheduled validations"""

        with self.db.transaction() as conn:
            cursor = conn.execute("""
                SELECT validation_id, update_log_id, validation_type
                FROM scheduled_validations
                WHERE status = 'pending'
                  AND scheduled_time <= ?
            """, (datetime.now().isoformat(),))

            pending = cursor.fetchall()

            for validation_id, update_log_id, validation_type in pending:
                logger.info(f"Running scheduled validation: {validation_type} for update {update_log_id}")

                # Run validation
                validator = UpdateValidator(db_path=self.settings.database_path)
                results = validator.run_all_checks(fix_issues=False)

                # Store results
                conn.execute("""
                    UPDATE scheduled_validations
                    SET status = 'completed',
                        completed_time = ?,
                        passed = ?,
                        issues_count = ?,
                        warnings_count = ?
                    WHERE validation_id = ?
                """, (datetime.now().isoformat(),
                      results['passed'],
                      len(results['issues']),
                      len(results['warnings']),
                      validation_id))

                # Alert if delayed issues found
                if not results['passed'] or len(results['warnings']) > 10:
                    self.notifier.send(
                        title=f"Delayed Validation Issues Detected ({validation_type})",
                        message=f"Update {update_log_id} showing issues {validation_type} after completion",
                        severity="warning",
                        metadata={
                            'validation_type': validation_type,
                            'issues': results['issues'][:5],
                            'warnings_count': len(results['warnings'])
                        }
                    )

# Add cron job to run this regularly
# */30 * * * * python scripts/continuous_monitor.py run-scheduled
```

**Benefits**:
- Detect gradual data degradation
- Catch issues that develop over time
- Better understanding of update impact
- Enables corrective actions even hours later

---

### **Feature 6: Validation Confidence Scores**

**Goal**: Assign confidence scores to validation results for better decision making

**Implementation**:
```python
# In scripts/verify_updates.py

class ValidationResult:
    def __init__(self):
        self.passed = True
        self.issues = []
        self.warnings = []
        self.confidence_score = 100.0  # NEW
        self.confidence_factors = {}   # NEW

    def calculate_confidence(self):
        """Calculate overall confidence in validation results"""

        factors = {
            'sample_size': 100,      # Start with full confidence
            'historical_data': 100,
            'check_coverage': 100,
            'data_quality': 100
        }

        # Reduce confidence based on various factors

        # Factor 1: Sample size (did we validate enough data?)
        if self.stats['hearings_checked'] < 100:
            factors['sample_size'] = 60  # Low confidence with small sample
        elif self.stats['hearings_checked'] < 500:
            factors['sample_size'] = 85  # Moderate confidence

        # Factor 2: Historical data availability
        if self.stats['update_logs_count'] < 10:
            factors['historical_data'] = 50  # Can't validate patterns well
        elif self.stats['update_logs_count'] < 30:
            factors['historical_data'] = 75

        # Factor 3: Check coverage (what % of checks ran successfully?)
        checks_attempted = 15  # Total validation checks
        checks_failed = len([i for i in self.issues if 'check failed' in i.lower()])
        if checks_failed > 0:
            factors['check_coverage'] = max(20, 100 - (checks_failed * 10))

        # Factor 4: Data quality indicators
        quality_warnings = len([w for w in self.warnings if 'quality' in w.lower()])
        if quality_warnings > 5:
            factors['data_quality'] = max(40, 100 - (quality_warnings * 5))

        # Calculate weighted average
        self.confidence_factors = factors
        self.confidence_score = sum(factors.values()) / len(factors)

        return self.confidence_score

def run_all_checks(self, fix_issues=False):
    """Enhanced validation with confidence scoring"""
    result = ValidationResult()

    # ... run all checks ...

    # Calculate confidence in results
    result.calculate_confidence()

    return {
        'passed': result.passed,
        'issues': result.issues,
        'warnings': result.warnings,
        'confidence_score': result.confidence_score,  # NEW
        'confidence_factors': result.confidence_factors  # NEW
    }
```

**Benefits**:
- Better decision making (high confidence = trust results)
- Identify when validation is unreliable
- Adjust thresholds based on confidence
- More nuanced approach than pass/fail

---

## Database Schema Changes

```sql
-- New table for scheduled validations
CREATE TABLE IF NOT EXISTS scheduled_validations (
    validation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    update_log_id INTEGER NOT NULL,
    scheduled_time TEXT NOT NULL,
    validation_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    completed_time TEXT,
    passed INTEGER,
    issues_count INTEGER DEFAULT 0,
    warnings_count INTEGER DEFAULT 0,
    confidence_score REAL,
    FOREIGN KEY (update_log_id) REFERENCES update_logs(log_id)
);

-- Add index for efficient scheduling queries
CREATE INDEX IF NOT EXISTS idx_scheduled_validations_pending
ON scheduled_validations(status, scheduled_time);

-- Enhance update_logs with validation confidence
ALTER TABLE update_logs ADD COLUMN validation_confidence REAL;
ALTER TABLE update_logs ADD COLUMN batch_count INTEGER DEFAULT 0;
ALTER TABLE update_logs ADD COLUMN batches_failed INTEGER DEFAULT 0;
```

---

## Updated Update Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Stage 0: Pre-Update Validation (FAST)                       │
│   • Critical sanity checks                                  │
│   • Database integrity                                      │
│   └─> ABORT if fails                                       │
├─────────────────────────────────────────────────────────────┤
│ Canary Test (if update > 20 items)                          │
│   • Test 5% of changes                                      │
│   • Full validation on canary                               │
│   └─> ABORT if canary fails                                │
├─────────────────────────────────────────────────────────────┤
│ Batch Processing Loop                                        │
│   ┌───────────────────────────────────────────────────┐    │
│   │ For each batch (50 items):                        │    │
│   │   Stage 1: Fast Checks (< 50ms)                   │    │
│   │   • Format validation                              │    │
│   │   • Duplicate detection                            │    │
│   │   └─> SKIP batch if fails                         │    │
│   │                                                     │    │
│   │   Apply Batch Changes                              │    │
│   │                                                     │    │
│   │   Stage 2: Batch Validation (< 200ms)             │    │
│   │   • Batch data integrity                           │    │
│   │   • Relationships within batch                     │    │
│   │   └─> ROLLBACK batch if fails                     │    │
│   │                                                     │    │
│   │   Commit Batch ✓                                   │    │
│   └───────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│ Stage 3: Comprehensive Validation                           │
│   • Full data integrity checks                              │
│   • Historical pattern validation                           │
│   • Anomaly detection (enhanced)                            │
│   • Calculate confidence score                              │
│   └─> ROLLBACK all if fails (and confidence > 80%)        │
├─────────────────────────────────────────────────────────────┤
│ Record Metrics                                               │
│   • Include batch stats                                     │
│   • Include validation confidence                           │
├─────────────────────────────────────────────────────────────┤
│ Schedule Post-Deployment Monitoring                          │
│   • Stage 4 validation in 1h, 6h, 24h, 7d                  │
├─────────────────────────────────────────────────────────────┤
│ Cleanup                                                      │
│   • Remove old backups                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Benefits Summary

| Feature | Benefit | Risk Reduction |
|---------|---------|----------------|
| Batch Processing | Partial success possible | 60% less wasted work |
| Historical Validation | Detect unusual patterns | 40% better anomaly detection |
| Multi-Stage Pipeline | Earlier failure detection | 50% faster error identification |
| Canary Testing | Predict systemic failures | 70% fewer large failed updates |
| Continuous Monitoring | Catch delayed issues | 30% better long-term quality |
| Confidence Scores | Better decisions | 25% fewer false positives |

---

## Implementation Priority

### Phase 2.3a (High Priority)
1. **Batch Processing with Checkpoints** - Core reliability improvement
2. **Historical Pattern Validation** - Better anomaly detection
3. **Multi-Stage Validation Pipeline** - Foundation for other features

### Phase 2.3b (Medium Priority)
4. **Canary Testing** - Risk reduction for large updates
5. **Confidence Scores** - Better decision making

### Phase 2.3c (Lower Priority)
6. **Continuous Monitoring** - Long-term quality assurance

---

## Testing Strategy

Each feature requires specific testing:

1. **Batch Processing**: Test with failed mid-batch, verify partial commits
2. **Historical Validation**: Test with synthetic historical data
3. **Multi-Stage Pipeline**: Test each stage independently
4. **Canary Testing**: Test with known-bad canary data
5. **Continuous Monitoring**: Test scheduled validation execution
6. **Confidence Scores**: Test score calculation with various data quality scenarios

---

## Timeline Estimate

- **Phase 2.3a**: 2-3 days (core features)
- **Phase 2.3b**: 1-2 days (enhancement features)
- **Phase 2.3c**: 1 day (monitoring)
- **Testing & Documentation**: 1-2 days

**Total**: ~5-8 days for complete Phase 2.3

---

## Deployment Considerations

- Can be deployed incrementally (one feature at a time)
- Backward compatible with Phase 2.2
- Database schema changes required (add scheduled_validations table)
- Minimal performance impact (< 10% overhead with all features)

---

**Status**: Awaiting approval to proceed
**Version**: 1.0 Proposal
**Last Updated**: October 13, 2025
