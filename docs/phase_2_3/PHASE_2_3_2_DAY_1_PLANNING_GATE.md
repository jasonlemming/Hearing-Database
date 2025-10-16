# Phase 2.3.2 Day 1: Planning Gate - Historical Pattern Validation

**Date**: October 13, 2025
**Stage**: 2.3.2 - Historical Pattern Validation
**Day**: 1 of 8
**Status**: 📋 **PLANNING**

---

## Executive Summary

Phase 2.3.2 adds **historical pattern-based anomaly detection** to the update validation system. This builds on Phase 2.3.1 (Batch Processing) by detecting anomalies based on statistical patterns rather than just static thresholds.

**Current State**: Phase 2.3.1 deployed successfully in Phase 2.2 mode (Week 1 complete)
**Goal**: Implement pattern-based validation using historical update metrics
**Duration**: 8 days (Day 1: Planning → Day 8: Trial Gate)

---

## Problem Statement

### Current Limitations (Phase 2.2 Validation)

Phase 2.2 uses **static threshold-based validation**:

```python
# Examples from scripts/verify_updates.py:
if counts['hearings'] < 1000:                    # Static threshold
    self.warnings.append("Low hearing count")

if counts[0] < avg_count * 0.3:                  # Fixed percentage
    self.warnings.append("Recent count too low")

if latest > avg_additions * 3 and latest > 50:   # Fixed multiplier
    self.warnings.append("Unusually high additions")
```

### Problems with Static Thresholds

1. **Misses Subtle Patterns**: Gradual data quality degradation not detected
2. **False Positives**: Seasonal variations (recess periods) trigger warnings
3. **False Negatives**: Anomalies within static bounds go undetected
4. **Not Adaptive**: Doesn't learn from historical patterns

### Example Scenarios

**Scenario 1: Gradual Data Quality Degradation**
```
Week 1: 150 hearings/week with 95% having witnesses
Week 2: 145 hearings/week with 90% having witnesses
Week 3: 140 hearings/week with 85% having witnesses
Week 4: 135 hearings/week with 80% having witnesses
```
→ Static thresholds miss gradual 15% decline in witness coverage

**Scenario 2: Seasonal Variation (False Positive)**
```
Normal week: 150 hearings/week
Recess week: 20 hearings/week (legitimate low)
```
→ Static threshold flags recess as anomaly incorrectly

**Scenario 3: Sudden Spike (Should Detect)**
```
Average: 150 hearings/week
Current: 450 hearings/week (possible duplicate import)
```
→ Should detect, but what's the right threshold? 2x? 3x? 5x?

---

## Proposed Solution

### Statistical Pattern-Based Validation

Instead of static thresholds, use **statistical analysis of historical patterns**:

1. **Calculate historical statistics** from update logs (mean, std dev, trends)
2. **Detect anomalies** using statistical tests (z-score, moving averages, trend analysis)
3. **Adaptive thresholds** that learn from historical data
4. **Multiple signals** required before alerting (reduce false positives)

### Statistical Approaches

#### 1. Z-Score Analysis

```python
z_score = (current_value - mean) / std_dev

if z_score > 3:  # 99.7% confidence (3 standard deviations)
    # Anomaly detected
```

**Example**:
```
Historical hearing additions: [150, 145, 155, 148, 152] (mean=150, std=3.5)
Current: 450 additions
z_score = (450 - 150) / 3.5 = 85.7 (extreme anomaly!)
```

**Benefits**:
- Statistically rigorous (3σ = 99.7% confidence)
- Self-adjusting (adapts to data variability)
- Well-understood method

#### 2. Moving Average Trend Analysis

```python
ma_7day = mean(last_7_updates)
ma_30day = mean(last_30_updates)

if current < ma_7day * 0.5:  # Sudden drop below 50% of recent average
    # Anomaly detected
```

**Example**:
```
7-day MA: 150 hearings/update
30-day MA: 145 hearings/update
Current: 20 hearings

Check: Is this a known congressional recess period?
```

**Benefits**:
- Captures recent trends
- Less sensitive to outliers (uses averages)
- Good for detecting sudden changes

#### 3. Percentile-Based Thresholds

```python
# Historical distribution
p5 = 5th percentile of historical values
p95 = 95th percentile of historical values

if current < p5 or current > p95:
    # Anomaly detected (outside normal range)
```

**Benefits**:
- No assumptions about distribution (non-parametric)
- Handles skewed data well
- Easy to interpret (5% outlier threshold)

#### 4. Trend Reversal Detection

```python
# Calculate trend over last 30 days
trend = linear_regression(last_30_days)

if trend.slope > 0:  # Increasing trend
    if current < prev * 0.7:  # Sudden 30% drop
        # Unexpected trend reversal
```

**Benefits**:
- Detects sudden changes in direction
- Contextual (considers recent trend)
- Good for catching data pipeline issues

---

## Implementation Architecture

### New Classes

#### 1. `HistoricalValidator` Class

**Location**: `scripts/verify_updates.py`

**Responsibilities**:
- Load historical update logs
- Calculate statistical metrics
- Detect pattern-based anomalies
- Cache results for performance

**Interface**:
```python
class HistoricalValidator:
    def __init__(self, db: DatabaseManager, min_history_days: int = 30):
        """Initialize with database and minimum history requirement"""

    def calculate_stats(self) -> Dict[str, HistoricalStats]:
        """Calculate mean, std dev, percentiles for key metrics"""

    def detect_anomalies(self, current_metrics: UpdateMetrics) -> List[Anomaly]:
        """Compare current metrics to historical patterns"""

    def get_explanation(self, anomaly: Anomaly) -> str:
        """Generate human-readable explanation of anomaly"""
```

#### 2. `HistoricalStats` Dataclass

**Purpose**: Store calculated statistics

```python
@dataclass
class HistoricalStats:
    metric_name: str
    mean: float
    std_dev: float
    p5: float          # 5th percentile
    p95: float         # 95th percentile
    sample_size: int
    last_updated: datetime
```

#### 3. `Anomaly` Dataclass

**Purpose**: Represent detected anomalies

```python
@dataclass
class Anomaly:
    metric_name: str
    current_value: float
    expected_value: float  # mean or MA
    z_score: float
    severity: str  # "warning", "critical"
    explanation: str
    confidence: float  # 0.0 to 1.0
```

### Integration Points

#### 1. `updaters/daily_updater.py`

**Modification**: Add historical validation after current validation

```python
def run_daily_update(self):
    # ... existing code ...

    # Step 4: Post-update validation (existing)
    self._run_post_update_validation()

    # Step 4.5: Historical pattern validation (NEW)
    if self.settings.enable_historical_validation:
        self._run_historical_validation()

    # ... rest of code ...
```

#### 2. `config/settings.py`

**Add Feature Flag**:

```python
# Historical Validation Configuration (Phase 2.3.2)
enable_historical_validation: bool = Field(default=False, env='ENABLE_HISTORICAL_VALIDATION')
historical_min_days: int = Field(default=30, env='HISTORICAL_MIN_DAYS')
historical_z_threshold: float = Field(default=3.0, env='HISTORICAL_Z_THRESHOLD')
```

#### 3. `updaters/daily_updater.py` - UpdateMetrics

**Add Historical Metrics**:

```python
class UpdateMetrics:
    # ... existing fields ...

    # Historical validation metrics (Phase 2.3.2)
    historical_validation_enabled = False
    anomalies_detected = 0
    anomaly_details = []  # List[Dict]
```

---

## Success Criteria

Per PHASE_2_3_ITERATIVE_PLAN.md (adjusted for current data availability):

### Primary Success Criteria

| ID | Criterion | Target | Measurement Method | Status |
|----|-----------|--------|--------------------|--------|
| **H1** | Detection rate (synthetic anomalies) | >= 90% | Create 10 synthetic anomalies, measure detection | 📋 Pending |
| **H2** | False positive rate (historical data) | < 5% | Run on 17 historical updates, measure false alarms | 📋 Pending |
| **H3** | Performance overhead | < 500ms | Measure time for historical stat calculation | 📋 Pending |
| **H4** | Works with limited history | >= 17 days | Test with current 17 update logs | 📋 Pending |

**Note**: We have 17 historical update logs (less than ideal 30), but sufficient to implement and test the system. Historical validation will improve as more data accumulates.

### Secondary Success Criteria

| ID | Criterion | Target | Notes | Status |
|----|-----------|--------|-------|--------|
| **H5** | Graceful degradation | Yes | Falls back to static thresholds if < 17 days history | 📋 Pending |
| **H6** | Clear explanations | Yes | Anomaly alerts explain why (which pattern violated) | 📋 Pending |
| **H7** | Configurable thresholds | Yes | Admins can tune z-score threshold via env var | 📋 Pending |
| **H8** | Caching works | Yes | Stats recalculated daily, not per update | 📋 Pending |

---

## Dependencies

### Phase 2.3.1 (COMPLETE ✅)

- [x] Batch processing implemented
- [x] Feature flag system in place
- [x] Metrics tracking in `UpdateMetrics` class
- [x] Database backup/rollback system
- [x] Post-update validation framework

### Historical Data (AVAILABLE ✅)

**Status**: ✅ 17 historical update logs available

```sql
SELECT COUNT(*) FROM update_logs WHERE hearings_checked > 0;
-- Result: 17

SELECT start_time, hearings_checked, hearings_updated, hearings_added
FROM update_logs
WHERE hearings_checked > 0
ORDER BY start_time DESC
LIMIT 5;
```

**Recent Updates**:
```
2025-10-10 15:41:42 | 1339 checked | 1339 updated | 0 added
2025-10-10 15:05:50 | 934 checked  | 812 updated  | 0 added
2025-10-10 14:47:47 | 934 checked  | 812 updated  | 0 added
2025-10-10 14:27:38 | 1339 checked | 1318 updated | 21 added
2025-10-08 15:59:32 | 939 checked  | 782 updated  | 0 added
```

**Assessment**:
- ✅ Sufficient data to implement historical validation
- ✅ Good variety in metrics (different check/update/add counts)
- ⚠️ Less than ideal 30 days, but adequate for Phase 2.3.2
- ✅ Historical validation will improve over time as more logs accumulate

---

## Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **R1**: Insufficient history (< 17 logs) | Low | High | Graceful degradation: use static thresholds if < 10 logs |
| **R2**: False positives on legitimate changes | Medium | Medium | Use multiple signals (2+ anomalies) before alerting |
| **R3**: Performance overhead (> 500ms) | Low | Medium | Cache stats daily, optimize SQL queries |
| **R4**: Complex to tune thresholds | High | Medium | Provide clear defaults (z=3.0), document tuning guide |
| **R5**: Data quality in historical logs | Medium | Low | Validate historical data before calculating stats |
| **R6**: Congressional recess periods flagged | High | Low | Add recess date awareness (future enhancement) |

### Risk Mitigation Details

#### R1: Insufficient History
```python
def calculate_stats(self):
    if self.get_update_count() < 10:
        logger.warning("Insufficient history (< 10 updates), using fallback")
        return None  # Fallback to Phase 2.2 static thresholds
```

#### R2: False Positives
```python
def should_alert(anomalies: List[Anomaly]) -> bool:
    # Require 2+ anomalies OR 1 critical anomaly
    critical = [a for a in anomalies if a.severity == "critical"]
    return len(anomalies) >= 2 or len(critical) >= 1
```

#### R3: Performance Overhead
```python
# Cache stats for 24 hours
@cached(ttl=86400)
def calculate_stats(self) -> Dict[str, HistoricalStats]:
    # Recalculated once per day, not per update
```

---

## Rollback Plan

### Feature Flag
```bash
# If issues arise, disable historical validation
export ENABLE_HISTORICAL_VALIDATION=false
```

### Fallback Behavior
```python
if not self.settings.enable_historical_validation:
    # Falls back to Phase 2.2 static thresholds
    # No data loss, no impact on updates
```

### Escalation
- **Minor issues** (< 10% false positive rate): Tune thresholds, continue monitoring
- **Major issues** (> 20% false positive rate): Disable feature, investigate
- **Critical issues** (updates failing): Rollback code, restore from backup

---

## Alternative Approaches Considered

### 1. Machine Learning (Anomaly Detection Model)

**Pros**: Could detect complex patterns
**Cons**: Requires significant training data, hard to explain, overkill for this use case
**Decision**: ❌ Too complex for Phase 2.3.2, consider for future phase

### 2. Time Series Analysis (ARIMA, Prophet)

**Pros**: Handles seasonality and trends
**Cons**: Requires more history (100+ points), complex to implement
**Decision**: ❌ Insufficient data, too complex

### 3. Simple Moving Average Only

**Pros**: Easy to implement, fast
**Cons**: Misses nuanced patterns, many false positives
**Decision**: ❌ Not rigorous enough, use z-score instead

### 4. Z-Score + Moving Average + Percentiles (Chosen)

**Pros**: Statistically sound, multiple signals, well-understood
**Cons**: Requires tuning
**Decision**: ✅ **SELECTED** - Best balance of rigor and simplicity

---

## Effort Estimate

Based on PHASE_2_3_ITERATIVE_PLAN.md and actual complexity:

### Development (Days 2-4): 3 days

| Task | Estimate | Notes |
|------|----------|-------|
| Create `HistoricalValidator` class | 4 hours | Core statistics calculation |
| Implement z-score detection | 2 hours | Standard deviation calculation |
| Implement percentile detection | 2 hours | Percentile calculation |
| Add caching logic | 2 hours | 24-hour TTL cache |
| Integration with `daily_updater.py` | 2 hours | Feature flag, method calls |
| Add configuration settings | 1 hour | `settings.py` updates |
| Add metrics to `UpdateMetrics` | 1 hour | Track anomaly detections |
| **Total** | **14 hours** | **~3 days** |

### Testing (Day 5): 1 day

| Task | Estimate | Notes |
|------|----------|-------|
| Unit tests for `HistoricalValidator` | 2 hours | Test statistics calculation |
| Create 10 synthetic anomalies | 1 hour | Test data generation |
| Test detection rate (>= 90%) | 1 hour | Measure true positive rate |
| Test false positive rate (< 5%) | 1 hour | Run on 17 historical updates |
| Test performance (< 500ms) | 0.5 hours | Benchmark statistics calculation |
| Test graceful degradation | 0.5 hours | Test with < 10 logs |
| **Total** | **6 hours** | **~1 day** |

### Review (Day 6): 1 day

| Task | Estimate | Notes |
|------|----------|-------|
| Code review | 2 hours | Check for issues |
| Design review | 1 hour | Validate approach |
| Documentation review | 1 hour | Ensure clarity |
| **Total** | **4 hours** | **~0.5 day** |

### Validation (Day 7): 1 day

| Task | Estimate | Notes |
|------|----------|-------|
| Verify all success criteria | 2 hours | Check H1-H8 |
| Run comprehensive tests | 2 hours | End-to-end testing |
| Create validation report | 2 hours | Document results |
| **Total** | **6 hours** | **~1 day** |

### Trial (Day 8): 1 day

| Task | Estimate | Notes |
|------|----------|-------|
| Enable in staging/local | 0.5 hours | Set feature flag |
| Run 5 test scenarios | 2 hours | Normal, spike, drop, etc. |
| Monitor for 24 hours | 1 hour | Passive monitoring |
| Create trial report | 2 hours | Document findings |
| **Total** | **5.5 hours** | **~1 day** |

### Summary

**Total Effort**: 35.5 hours (~8 days @ 4-5 hours/day)

**Timeline**:
- Day 1: Planning Gate (this document) ✅
- Days 2-4: Development (3 days)
- Day 5: Testing Gate (1 day)
- Day 6: Review Gate (0.5 day)
- Day 7: Validation Gate (1 day)
- Day 8: Trial Gate (1 day)

---

## Test-Driven Development Plan

### Tests to Write BEFORE Implementation

#### 1. Statistics Calculation Tests
```python
def test_calculate_mean():
    """Test mean calculation from historical logs"""

def test_calculate_std_dev():
    """Test standard deviation calculation"""

def test_calculate_percentiles():
    """Test 5th and 95th percentile calculation"""

def test_insufficient_data_handling():
    """Test graceful degradation with < 10 logs"""
```

#### 2. Anomaly Detection Tests
```python
def test_z_score_detection_high():
    """Test detection of high z-score anomalies (> 3σ)"""

def test_z_score_detection_low():
    """Test detection of low z-score anomalies (< -3σ)"""

def test_percentile_detection():
    """Test detection using percentile method"""

def test_no_false_positive_on_normal_data():
    """Test that normal data doesn't trigger anomalies"""
```

#### 3. Integration Tests
```python
def test_historical_validation_integration():
    """Test integration with daily_updater.py"""

def test_feature_flag_controls_historical_validation():
    """Test feature flag enables/disables validation"""

def test_anomalies_recorded_in_metrics():
    """Test anomaly details stored in UpdateMetrics"""
```

#### 4. Performance Tests
```python
def test_statistics_calculation_performance():
    """Test calculation completes in < 500ms"""

def test_caching_works():
    """Test stats not recalculated on second call"""
```

#### 5. Synthetic Anomaly Tests
```python
def test_detect_sudden_spike():
    """Test detection of 5x spike in hearings_added"""

def test_detect_sudden_drop():
    """Test detection of 80% drop in hearings_checked"""

def test_detect_gradual_degradation():
    """Test detection of gradual quality decline"""
```

---

## Deliverables

### Code Files

1. **`scripts/verify_updates.py`**
   - Add `HistoricalValidator` class (~200 lines)
   - Add `HistoricalStats` dataclass (~20 lines)
   - Add `Anomaly` dataclass (~15 lines)

2. **`updaters/daily_updater.py`**
   - Add `_run_historical_validation()` method (~50 lines)
   - Update `UpdateMetrics` class (+3 fields)
   - Integrate historical validation call (~10 lines)

3. **`config/settings.py`**
   - Add 3 configuration fields (~5 lines)

4. **`tests/test_historical_validation.py`**
   - New test file (~400 lines)
   - 15-20 comprehensive tests

**Total New Code**: ~700 lines

### Documentation Files

1. **`PHASE_2_3_2_DAY_1_PLANNING_GATE.md`** (this file)
2. **`PHASE_2_3_2_DAY_5_TESTING_GATE.md`** (test results)
3. **`PHASE_2_3_2_DAY_6_REVIEW_GATE.md`** (code review)
4. **`PHASE_2_3_2_DAY_7_VALIDATION_GATE.md`** (success criteria verification)
5. **`PHASE_2_3_2_DAY_8_TRIAL_GATE.md`** (trial results)

**Total Documentation**: ~3,000 lines

---

## Decision Gate

### Prerequisites for Approval

- [x] Problem clearly defined
- [x] Solution approach validated (z-score + percentiles)
- [x] Success criteria defined (H1-H8)
- [x] Dependencies verified (Phase 2.3.1 complete, 17 logs available)
- [x] Risks identified and mitigated
- [x] Effort estimated (8 days)
- [x] Rollback plan defined
- [x] TDD plan created

### Decision Options

1. ✅ **PROCEED** - Approve Phase 2.3.2 implementation
2. ❌ **REVISE** - Adjust plan based on feedback
3. ❌ **ABORT** - Defer Phase 2.3.2 to future

### Approval Checklist

- [ ] Technical approach sound? (z-score + percentiles)
- [ ] Success criteria realistic? (90% detection, 5% FP rate)
- [ ] Sufficient historical data? (17 logs adequate)
- [ ] Effort reasonable? (8 days acceptable)
- [ ] Risks acceptable? (all mitigated)
- [ ] Rollback plan adequate? (feature flag + fallback)

---

## Next Steps (Upon Approval)

**Day 2-4: Development**

1. Create `HistoricalValidator` class
2. Implement statistics calculation
3. Implement anomaly detection
4. Add caching
5. Integrate with `daily_updater.py`
6. Add configuration settings
7. Update `UpdateMetrics`

**Day 5: Testing Gate**

1. Write and run all unit tests
2. Create synthetic anomalies
3. Measure detection rate and false positive rate
4. Benchmark performance
5. Create testing report

---

## Appendices

### Appendix A: Historical Data Analysis

**Current Historical Logs**: 17 updates with data

**Sample Data**:
```
Date       | Checked | Updated | Added
-----------|---------|---------|-------
2025-10-10 | 1339    | 1339    | 0
2025-10-10 | 934     | 812     | 0
2025-10-10 | 934     | 812     | 0
2025-10-10 | 1339    | 1318    | 21
2025-10-08 | 939     | 782     | 0
```

**Preliminary Statistics** (to validate approach):
```
hearings_checked: mean=1045, likely high variance (934-1339)
hearings_added: mean≈1-2, low variance (most are 0)
```

**Insight**: High variance in `hearings_checked` suggests z-score method will work well for detecting anomalies.

### Appendix B: Statistical Formulas

#### Z-Score
```
z = (X - μ) / σ

Where:
  X = current value
  μ = mean of historical values
  σ = standard deviation

Interpretation:
  |z| > 3: 99.7% confidence anomaly (3σ rule)
  |z| > 2: 95% confidence anomaly
  |z| < 2: Normal variation
```

#### Percentiles
```
p5 = 5th percentile (95% of values above this)
p95 = 95th percentile (95% of values below this)

Anomaly if:
  X < p5  (unusually low)
  X > p95 (unusually high)
```

---

**Document Version**: 1.0
**Created**: October 13, 2025 (Day 1)
**Status**: 📋 **AWAITING APPROVAL TO PROCEED**
**Next Step**: Begin Development (Days 2-4) upon approval
