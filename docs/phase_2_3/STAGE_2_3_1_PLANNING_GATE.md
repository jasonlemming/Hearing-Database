# Phase 2.3 Stage 2.3.1: Batch Processing - Planning Gate

**Date**: October 13, 2025
**Stage**: 2.3.1 - Batch Processing with Validation Checkpoints
**Gate**: Planning Gate (Day 1)
**Status**: ⏳ In Review

---

## Gate Purpose

Validate the plan for Stage 2.3.1 before beginning development. This gate ensures we have:
- Clear problem statement
- Measurable success criteria
- Identified risks with mitigation plans
- Sound technical approach
- Realistic timeline

**Decision Required**: ✅ Approve to Proceed / ❌ Revise Plan / ❌ Abort Stage

---

## Problem Statement

### Current Situation (Phase 2.2)

The current update system (Phase 2.2) processes all updates in a single transaction:

```python
# Current Phase 2.2 Flow (Simplified)
def run_daily_update():
    # Step 1: Fetch all changes (updates + additions)
    changes = fetch_recent_hearings()

    # Step 2: Create single backup
    backup_path = create_backup()

    try:
        # Step 3: Apply ALL changes in one transaction
        apply_all_updates(changes)  # ← ALL OR NOTHING

        # Step 4: Validate AFTER all applied
        validation_passed = validate_all()

        if not validation_passed:
            # Rollback EVERYTHING
            rollback_database(backup_path)
            raise Exception("Validation failed")

    except Exception as e:
        # Any error = rollback EVERYTHING
        rollback_database(backup_path)
```

### Problems with Current Approach

1. **Wasted Processing Time**
   - If validation fails at the end, all processing time is wasted
   - Example: Process 500 hearings (5 minutes), validation fails → 5 minutes wasted
   - No partial progress is saved

2. **Good Data Rejected Along with Bad**
   - If 1 out of 500 hearings has an issue, all 499 good hearings are rolled back
   - No way to commit the good data and skip only the problematic records
   - "All or nothing" approach is overly conservative

3. **Large Blast Radius**
   - A single bad record causes entire update to fail
   - No isolation between independent changes
   - Difficult to identify which specific record caused the failure

4. **Long Feedback Loop**
   - Must wait until the end to discover issues
   - Can't detect problems early during processing
   - Debugging requires re-running entire update

### Impact

**Real-world scenario**:
- Update with 300 hearings (200 updates, 100 new)
- Hearing #250 has a foreign key violation
- Current behavior:
  - Process 249 hearings successfully (3-4 minutes)
  - Hit error on #250
  - Rollback all 249 successful changes
  - Update fails completely
  - Net result: 0 hearings updated, 4 minutes wasted

**Desired behavior**:
- Process hearings in batches of 50
- Batch 1-4: Success (200 hearings committed)
- Batch 5: Contains hearing #250, fails validation
- Batch 5 rolled back (50 hearings)
- Batch 6: Success (50 hearings committed)
- Net result: 250 hearings updated successfully, 50 skipped

---

## Proposed Solution

### Batch Processing Architecture

```python
# Proposed Phase 2.3.1 Flow
def run_daily_update_with_batches():
    changes = fetch_recent_hearings()

    # Divide into batches
    batches = divide_into_batches(changes, batch_size=50)

    for batch in batches:
        # Create checkpoint for THIS BATCH only
        checkpoint = create_checkpoint()

        try:
            # Apply THIS BATCH
            apply_batch(batch)

            # Validate THIS BATCH
            validation_result = validate_batch(batch)

            if validation_result.passed:
                # Commit THIS BATCH
                commit_checkpoint()
                log_batch_success(batch)
            else:
                # Rollback THIS BATCH ONLY
                rollback_to_checkpoint(checkpoint)
                log_batch_failure(batch, validation_result)
                # Continue with next batch

        except Exception as e:
            # Rollback THIS BATCH ONLY
            rollback_to_checkpoint(checkpoint)
            log_batch_error(batch, e)
            # Continue with next batch

    # Summary: X batches succeeded, Y batches failed
    return batch_summary
```

### Key Concepts

#### 1. Checkpoint System
- **Purpose**: Create savepoints before each batch
- **Implementation**: SQLite savepoints or in-memory state tracking
- **Benefit**: Can rollback to checkpoint without affecting previous batches

#### 2. Batch Validation
- **Purpose**: Validate each batch independently
- **Checks**:
  - Foreign key integrity within batch
  - Data format validation
  - Duplicate detection within batch
- **Fast**: < 200ms per batch (50 hearings)

#### 3. Independent Batch Processing
- **Isolation**: Each batch succeeds or fails independently
- **Partial Success**: Commit successful batches even if others fail
- **Error Reporting**: Track which specific batches failed

#### 4. Feature Flag
- **Configuration**: `ENABLE_BATCH_PROCESSING = True/False`
- **Rollback**: Can disable feature and revert to Phase 2.2 behavior
- **Safety**: No risk of breaking existing system

---

## Success Criteria

These are **specific, measurable criteria** that define success for Stage 2.3.1:

### Functional Requirements

| # | Criterion | Target | Measurement Method |
|---|-----------|--------|-------------------|
| F1 | Process updates in configurable batches | 50 hearings/batch | Test with 500 hearings = 10 batches |
| F2 | Failed batch doesn't affect other batches | Independent | Inject failure in batch 5, verify batches 1-4, 6-10 succeed |
| F3 | Good batches committed on partial failure | >= 95% | With 1 bad batch, 95% of data should commit |
| F4 | Batch failures logged with details | 100% | Each failure must have log entry with reason |
| F5 | Feature flag allows disabling | Works | Toggle flag, verify fallback to Phase 2.2 |

### Performance Requirements

| # | Criterion | Target | Measurement Method |
|---|-----------|--------|-------------------|
| P1 | Total processing time (500 hearings) | < 5 seconds | Timed test with 500 hearings |
| P2 | Checkpoint creation overhead | < 50ms | Measure checkpoint creation time |
| P3 | Batch validation overhead | < 200ms | Measure validation time per batch |
| P4 | Memory usage | < 100MB increase | Monitor memory during batch processing |
| P5 | No performance degradation vs Phase 2.2 | ± 10% | Compare total time with Phase 2.2 |

### Quality Requirements

| # | Criterion | Target | Measurement Method |
|---|-----------|--------|-------------------|
| Q1 | Test coverage | > 85% | pytest --cov |
| Q2 | No data loss | 0 incidents | Verify all committed data persists |
| Q3 | Rollback works correctly | 100% | Test rollback scenarios, verify data restored |
| Q4 | Error messages are clear | Reviewable | Manual review of error messages |
| Q5 | Code is maintainable | Reviewable | Code review passes |

### Reliability Requirements

| # | Criterion | Target | Measurement Method |
|---|-----------|--------|-------------------|
| R1 | Partial success rate (with failures) | >= 95% | Inject 5% failures, measure success rate |
| R2 | Zero corruption incidents | 0 | Database integrity checks pass |
| R3 | Checkpoint rollback success | 100% | Test all rollback scenarios |
| R4 | Feature flag toggle works | 100% | Test enable/disable multiple times |

---

## Technical Approach

### Architecture Decision: Savepoints vs In-Memory State

**Considered Options**:

#### Option 1: SQLite Savepoints
```python
def create_checkpoint():
    conn.execute("SAVEPOINT batch_checkpoint")

def rollback_to_checkpoint():
    conn.execute("ROLLBACK TO SAVEPOINT batch_checkpoint")

def commit_checkpoint():
    conn.execute("RELEASE SAVEPOINT batch_checkpoint")
```

**Pros**:
- Native SQLite feature
- Database handles state management
- Atomic operations

**Cons**:
- Nested transaction complexity
- May interact poorly with Phase 2.2 backup system
- Limited control over rollback scope

#### Option 2: In-Memory State Tracking (Selected)
```python
class Checkpoint:
    def __init__(self):
        self.hearing_ids = []
        self.witness_ids = []
        self.document_ids = []

def create_checkpoint(batch):
    # Track what will be modified
    checkpoint = Checkpoint()
    checkpoint.hearing_ids = [h.id for h in batch.updates]
    return checkpoint

def rollback_to_checkpoint(checkpoint):
    # Delete/revert records added in this batch
    conn.execute("DELETE FROM hearings WHERE hearing_id IN (?)",
                 checkpoint.hearing_ids)
```

**Pros**:
- Full control over rollback scope
- Can inspect what will be rolled back
- Works cleanly with Phase 2.2 backup
- Easier to debug

**Cons**:
- Must track all changes manually
- More code to maintain

**Decision**: **Option 2 (In-Memory State Tracking)**

**Rationale**:
- Better control and debuggability
- Cleaner integration with existing Phase 2.2 system
- Easier to test and validate
- More transparent behavior

---

### Implementation Components

#### Component 1: Checkpoint Class

```python
class Checkpoint:
    """Tracks database changes for potential rollback"""

    def __init__(self, batch_number: int):
        self.batch_number = batch_number
        self.timestamp = datetime.now()

        # Track IDs of records to be modified
        self.hearings_to_update = []
        self.hearings_to_add = []
        self.witnesses_to_add = []
        self.documents_to_add = []

        # Track pre-modification state
        self.original_hearing_data = {}

    def track_update(self, hearing_id: str, original_data: dict):
        """Track a hearing that will be updated"""
        self.hearings_to_update.append(hearing_id)
        self.original_hearing_data[hearing_id] = original_data

    def track_addition(self, hearing_id: str):
        """Track a hearing that will be added"""
        self.hearings_to_add.append(hearing_id)
```

#### Component 2: Batch Processor

```python
def _process_batch(self, batch: List[HearingData], batch_num: int) -> BatchResult:
    """Process a single batch with checkpoint"""

    # Create checkpoint
    checkpoint = Checkpoint(batch_num)

    try:
        # Track what will change
        for hearing in batch:
            if hearing.is_update:
                original = self.db.get_hearing(hearing.hearing_id)
                checkpoint.track_update(hearing.hearing_id, original)
            else:
                checkpoint.track_addition(hearing.hearing_id)

        # Apply changes
        self._apply_batch_updates(batch)

        # Validate batch
        validation = self._validate_batch(batch, checkpoint)

        if not validation.passed:
            # Rollback this batch
            self._rollback_checkpoint(checkpoint)
            return BatchResult(success=False, issues=validation.issues)

        # Success
        return BatchResult(success=True, records=len(batch))

    except Exception as e:
        # Error in batch processing
        self._rollback_checkpoint(checkpoint)
        return BatchResult(success=False, error=str(e))
```

#### Component 3: Batch Validator

```python
def _validate_batch(self, batch: List[HearingData], checkpoint: Checkpoint) -> ValidationResult:
    """Fast validation checks for a batch"""

    issues = []

    # Check 1: Foreign key integrity (FAST - only check new records)
    for hearing_id in checkpoint.hearings_to_add:
        committee_id = self.db.get_hearing_committee(hearing_id)
        if committee_id and not self.db.committee_exists(committee_id):
            issues.append(f"Hearing {hearing_id} references non-existent committee")

    # Check 2: Duplicate detection within batch
    hearing_ids = [h.hearing_id for h in batch]
    if len(hearing_ids) != len(set(hearing_ids)):
        issues.append("Duplicate hearing IDs within batch")

    # Check 3: Data format validation
    for hearing in batch:
        if not hearing.title or len(hearing.title) > 500:
            issues.append(f"Invalid title for hearing {hearing.hearing_id}")

    # More checks...

    return ValidationResult(passed=len(issues) == 0, issues=issues)
```

#### Component 4: Checkpoint Rollback

```python
def _rollback_checkpoint(self, checkpoint: Checkpoint):
    """Rollback changes from this checkpoint"""

    logger.warning(f"Rolling back batch {checkpoint.batch_number}")

    with self.db.transaction() as conn:
        # Delete added hearings
        if checkpoint.hearings_to_add:
            placeholders = ','.join('?' * len(checkpoint.hearings_to_add))
            conn.execute(
                f"DELETE FROM hearings WHERE hearing_id IN ({placeholders})",
                checkpoint.hearings_to_add
            )

        # Restore updated hearings to original state
        for hearing_id, original_data in checkpoint.original_hearing_data.items():
            conn.execute("""
                UPDATE hearings
                SET title = ?, hearing_date = ?, status = ?, ...
                WHERE hearing_id = ?
            """, (*original_data.values(), hearing_id))

        # Delete added witnesses
        if checkpoint.witnesses_to_add:
            # Similar deletion logic
            pass

    logger.info(f"Batch {checkpoint.batch_number} rolled back successfully")
```

---

## Dependencies

### External Dependencies
- ✅ Phase 2.2 backup system (already exists)
- ✅ Database transaction support (SQLite, already exists)
- ✅ UpdateMetrics tracking (already exists)
- ✅ Logging system (already exists)

### Internal Dependencies
- None (Stage 2.3.1 is foundational)

### Data Requirements
- Database with test data (already exists: 1,340 hearings)
- Staging environment for trial (need to set up)

---

## Risks & Mitigation Strategies

### High-Priority Risks

| Risk | Probability | Impact | Severity | Mitigation |
|------|-------------|--------|----------|------------|
| **Checkpoint rollback fails** | Low | High | 🔴 Critical | Extensive testing of rollback logic; fallback to Phase 2.2 all-or-nothing; comprehensive logging |
| **Partial commits cause data inconsistency** | Medium | High | 🔴 Critical | Validate cross-batch relationships after all batches; comprehensive post-update validation |

### Medium-Priority Risks

| Risk | Probability | Impact | Severity | Mitigation |
|------|-------------|--------|----------|------------|
| **Batch validation too strict** | Medium | Medium | 🟡 Medium | Track false positive rate; make thresholds configurable; tune based on production data |
| **Batch size too small = slow** | Medium | Medium | 🟡 Medium | Make batch size configurable (default 50); test with 25, 50, 100; measure performance |
| **Memory usage increases** | Low | Medium | 🟡 Medium | Track checkpoint memory; limit checkpoint history; test with large batches |

### Low-Priority Risks

| Risk | Probability | Impact | Severity | Mitigation |
|------|-------------|--------|----------|------------|
| **Feature flag doesn't work** | Low | Low | 🟢 Low | Test toggle multiple times; code review flag logic; document usage |
| **Logging overhead** | Low | Low | 🟢 Low | Use efficient logging; limit log verbosity; test performance |

---

## Rollback Plan

### If Stage 2.3.1 Fails in Development

**Scenario**: Implementation doesn't meet success criteria during Validation Gate

**Actions**:
1. Review which criteria failed
2. Options:
   - **Iterate**: Fix issues and re-validate (recommended for minor issues)
   - **Revise**: Adjust approach or criteria (if fundamental issue)
   - **Abort**: Stop stage, re-plan with different approach

**Impact**: Time delay, no production impact (not deployed yet)

### If Stage 2.3.1 Fails in Trial

**Scenario**: Trial in staging environment reveals critical issues

**Actions**:
1. Do not proceed to production
2. Fix issues in development
3. Re-run Testing Gate
4. Re-run Trial Gate
5. Only proceed when Trial Gate passes

**Impact**: Time delay, no production impact

### If Stage 2.3.1 Fails in Production (Canary)

**Scenario**: Production canary deployment has issues

**Actions**:
1. **Immediate**: Set feature flag `ENABLE_BATCH_PROCESSING = False`
2. **Verify**: System falls back to Phase 2.2 behavior
3. **Investigate**: Review logs, identify issue
4. **Fix**: Correct issue in development
5. **Re-validate**: Run through all gates again
6. **Re-deploy**: Attempt canary again

**Impact**: Minimal (canary is limited scope), quick rollback available

### Rollback Safety Features

- **Feature Flag**: One-line config change to disable
- **Phase 2.2 Fallback**: Known-working code path remains intact
- **No Schema Changes**: Database schema unchanged, no migration needed
- **Isolated Code**: Batch processing is new code, doesn't modify Phase 2.2 code

---

## Alternative Approaches Considered

### Alternative 1: Batch Size = 1 (Validate Every Hearing)

**Approach**: Process one hearing at a time with validation

**Pros**:
- Maximum isolation
- Pinpoint exact problem record

**Cons**:
- Too slow (1,000 hearings = 1,000 checkpoints)
- High overhead per record
- Not practical for production

**Decision**: ❌ Rejected

---

### Alternative 2: Adaptive Batch Size

**Approach**: Start with large batches (100), reduce size if failures occur

**Pros**:
- Optimized for success case (large batches when all good)
- Automatically adapts to data quality

**Cons**:
- Complex implementation
- Harder to predict behavior
- Difficult to test

**Decision**: ❌ Deferred to future (v2 of batch processing)

**Rationale**: Fixed batch size (50) is simpler, easier to test, and "good enough" for v1

---

### Alternative 3: No Batch Validation (Only Final Validation)

**Approach**: Process in batches but only validate at the end

**Pros**:
- Simpler implementation
- Faster (one validation instead of N)

**Cons**:
- Doesn't solve the problem! Still "all or nothing" validation
- Can't identify which batch caused issue

**Decision**: ❌ Rejected - doesn't meet goal

---

## Effort Estimate

### Development Time Breakdown

| Task | Estimate | Confidence |
|------|----------|------------|
| Checkpoint class implementation | 2 hours | High |
| Batch processing logic | 3 hours | High |
| Batch validation implementation | 2 hours | Medium |
| Rollback logic | 2 hours | Medium |
| Feature flag integration | 1 hour | High |
| UpdateMetrics enhancements | 1 hour | High |
| **Subtotal Development** | **11 hours** | |
| | | |
| Unit test writing | 4 hours | Medium |
| Integration test writing | 2 hours | Medium |
| **Subtotal Testing** | **6 hours** | |
| | | |
| Code review prep | 1 hour | High |
| Documentation | 2 hours | High |
| **Subtotal Other** | **3 hours** | |
| | | |
| **Total** | **20 hours** | |
| **Buffer (20%)** | **4 hours** | |
| **Grand Total** | **24 hours** | |

### Timeline: 12 Working Days

- **Day 1**: Planning Gate (this document) - 2 hours
- **Day 2-5**: Development (4 days × 4 hours) - 16 hours
- **Day 6-7**: Testing Gate (2 days × 3 hours) - 6 hours
- **Day 8**: Review Gate - 4 hours
- **Day 9**: Validation Gate - 4 hours
- **Day 10-12**: Trial Gate (48h observation) - 4 hours active, 48h passive
- **Day 13**: Decision Gate - 2 hours

**Total active time**: ~38 hours over 12 days
**Calendar time**: 2 weeks

---

## Configuration

### Environment Variables (New)

```bash
# Feature flag - enable/disable batch processing
ENABLE_BATCH_PROCESSING=true  # or false

# Batch size - number of hearings per batch
BATCH_SIZE=50  # adjustable: 25, 50, 100

# Batch validation timeout (milliseconds)
BATCH_VALIDATION_TIMEOUT=200
```

### Default Configuration

```python
# config/settings.py additions
class Settings:
    # ... existing settings ...

    # Batch processing settings
    enable_batch_processing: bool = True
    batch_size: int = 50
    batch_validation_timeout_ms: int = 200
```

---

## Files to Create/Modify

### Files to Modify

1. **`updaters/daily_updater.py`**
   - Add `Checkpoint` class (~50 lines)
   - Add `_create_checkpoint()` method (~30 lines)
   - Add `_rollback_checkpoint()` method (~50 lines)
   - Add `_apply_batch_updates()` method (~40 lines)
   - Add `_validate_batch()` method (~60 lines)
   - Add `_process_batch()` method (~80 lines)
   - Modify `run_daily_update()` to use batch processing (~50 lines)
   - **Total**: ~360 new lines

2. **`updaters/daily_updater.py` (UpdateMetrics class)**
   - Add `batch_count: int = 0`
   - Add `batches_succeeded: int = 0`
   - Add `batches_failed: int = 0`
   - Add `batch_errors: List[str] = []`
   - Modify `to_dict()` to include batch metrics
   - **Total**: ~20 new lines

3. **`config/settings.py`**
   - Add batch processing configuration
   - **Total**: ~10 new lines

### Files to Create

1. **`tests/test_batch_processing.py`** (new)
   - Unit tests for all batch processing functions
   - **Estimate**: ~300 lines

2. **`docs/phase_2_3/STAGE_2_3_1_PLANNING_GATE.md`** (this file)
   - Planning Gate documentation
   - **Complete**

### Total New Code

- **Production code**: ~390 lines
- **Test code**: ~300 lines
- **Documentation**: This document
- **Total**: ~690 lines

---

## Stakeholder Review Checklist

### Technical Review

- [ ] **Problem statement is clear**: Do reviewers understand the issue?
- [ ] **Solution makes sense**: Is the proposed approach sound?
- [ ] **Success criteria are measurable**: Can we objectively verify success?
- [ ] **Risks are identified**: Are there other risks not considered?
- [ ] **Mitigation strategies are adequate**: Will mitigations actually reduce risk?
- [ ] **Technical approach is sound**: Any architectural concerns?
- [ ] **Effort estimate is reasonable**: Too optimistic? Too conservative?

### Process Review

- [ ] **Aligns with iterative framework**: Using proper validation gates?
- [ ] **Dependencies identified**: Any missing dependencies?
- [ ] **Rollback plan is clear**: Can we safely abort if needed?
- [ ] **Timeline is realistic**: 12 days achievable?

### Business Review

- [ ] **Solves a real problem**: Is this worth the effort?
- [ ] **Success criteria align with goals**: Do metrics matter?
- [ ] **Risk vs reward acceptable**: Worth the 12-day investment?

---

## Approval

### Required Approvals

- [ ] **Technical Lead**: Approves technical approach
- [ ] **Project Stakeholder**: Approves effort/timeline
- [ ] **Security Review**: No security concerns

### Decision

**Status**: ⏳ **Pending Approval**

**Options**:
- ✅ **Approve**: Proceed to Day 2 (Development)
- ⚠️ **Approve with Changes**: Minor revisions needed
- ❌ **Request Major Revision**: Fundamental issues to address
- ❌ **Abort Stage**: Stop this stage, reconsider approach

**Approval Date**: _____________
**Approved By**: _____________
**Decision**: _____________

**Comments**:
```
[Space for reviewer comments]
```

---

## Next Steps (If Approved)

### Immediate (Day 2)

1. Set up development branch: `git checkout -b feature/batch-processing`
2. Create test file: `tests/test_batch_processing.py`
3. Write first test: `test_checkpoint_creation()`
4. Implement `Checkpoint` class (TDD approach)

### Week 1 (Day 2-5)

- Complete all development
- Write tests as you go (TDD)
- Daily progress updates

### Week 2 (Day 6-12)

- Testing Gate (Day 6-7)
- Review Gate (Day 8)
- Validation Gate (Day 9)
- Trial Gate (Day 10-12)
- Decision Gate (Day 13)

---

**Planning Gate Version**: 1.0
**Date Created**: October 13, 2025
**Status**: ⏳ Awaiting Approval
**Next Gate**: Testing Gate (Day 6)
