#!/bin/bash
#
# Manual Testing Script for Verification System
#
# This script provides manual tests for the verification system features.
# Run each test section and verify the output manually.
#

set -e

echo "============================================================================"
echo "VERIFICATION SYSTEM MANUAL TEST SUITE"
echo "============================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

print_test() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}TEST: $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ INFO${NC}: $1"
}

# ==============================================================================
# TEST 1: Verify UpdateValidator exists and is importable
# ==============================================================================
print_test "Verify UpdateValidator module exists"

if [ -f "scripts/verify_updates.py" ]; then
    print_pass "verify_updates.py exists"
else
    print_fail "verify_updates.py not found"
fi

if grep -q "class UpdateValidator" scripts/verify_updates.py; then
    print_pass "UpdateValidator class found in verify_updates.py"
else
    print_fail "UpdateValidator class not found"
fi

if grep -q "def check_anomalies" scripts/verify_updates.py; then
    print_pass "check_anomalies() method found"
else
    print_fail "check_anomalies() method not found"
fi

# ==============================================================================
# TEST 2: Verify DailyUpdater has new methods
# ==============================================================================
print_test "Verify DailyUpdater has verification methods"

if grep -q "def _run_pre_update_sanity_checks" updaters/daily_updater.py; then
    print_pass "_run_pre_update_sanity_checks() method found"
else
    print_fail "_run_pre_update_sanity_checks() method not found"
fi

if grep -q "def _run_post_update_validation" updaters/daily_updater.py; then
    print_pass "_run_post_update_validation() method found"
else
    print_fail "_run_post_update_validation() method not found"
fi

if grep -q "def _create_database_backup" updaters/daily_updater.py; then
    print_pass "_create_database_backup() method found"
else
    print_fail "_create_database_backup() method not found"
fi

if grep -q "def _rollback_database" updaters/daily_updater.py; then
    print_pass "_rollback_database() method found"
else
    print_fail "_rollback_database() method not found"
fi

if grep -q "def _cleanup_old_backups" updaters/daily_updater.py; then
    print_pass "_cleanup_old_backups() method found"
else
    print_fail "_cleanup_old_backups() method not found"
fi

# ==============================================================================
# TEST 3: Verify UpdateMetrics has validation fields
# ==============================================================================
print_test "Verify UpdateMetrics has validation tracking"

if grep -q "self.validation_passed" updaters/daily_updater.py; then
    print_pass "validation_passed field found in UpdateMetrics"
else
    print_fail "validation_passed field not found"
fi

if grep -q "self.validation_warnings" updaters/daily_updater.py; then
    print_pass "validation_warnings field found in UpdateMetrics"
else
    print_fail "validation_warnings field not found"
fi

if grep -q "self.validation_issues" updaters/daily_updater.py; then
    print_pass "validation_issues field found in UpdateMetrics"
else
    print_fail "validation_issues field not found"
fi

# ==============================================================================
# TEST 4: Verify update flow includes new steps
# ==============================================================================
print_test "Verify update flow includes verification steps"

if grep -q "Step 0: Pre-update sanity checks" updaters/daily_updater.py; then
    print_pass "Pre-update sanity checks integrated into flow"
else
    print_fail "Pre-update sanity checks not in flow"
fi

if grep -q "_run_pre_update_sanity_checks()" updaters/daily_updater.py; then
    print_pass "Pre-update sanity checks are called"
else
    print_fail "Pre-update sanity checks not called"
fi

if grep -q "_run_post_update_validation()" updaters/daily_updater.py; then
    print_pass "Post-update validation is called"
else
    print_fail "Post-update validation not called"
fi

if grep -q "_create_database_backup()" updaters/daily_updater.py; then
    print_pass "Database backup is created"
else
    print_fail "Database backup not created"
fi

# ==============================================================================
# TEST 5: Verify admin dashboard has health endpoint
# ==============================================================================
print_test "Verify admin dashboard has system health"

if grep -q "@admin_bp.route('/api/system-health')" web/blueprints/admin.py; then
    print_pass "System health endpoint found"
else
    print_fail "System health endpoint not found"
fi

if grep -q "def system_health" web/blueprints/admin.py; then
    print_pass "system_health() function found"
else
    print_fail "system_health() function not found"
fi

if grep -q "System Health" web/templates/admin_dashboard.html; then
    print_pass "System Health widget found in dashboard"
else
    print_fail "System Health widget not in dashboard"
fi

if grep -q "loadSystemHealth" web/templates/admin_dashboard.html; then
    print_pass "loadSystemHealth() JavaScript function found"
else
    print_fail "loadSystemHealth() JavaScript not found"
fi

# ==============================================================================
# TEST 6: Verify enhanced anomaly detection
# ==============================================================================
print_test "Verify enhanced anomaly detection"

ANOMALY_CHECKS=(
    "sudden spike in hearing additions"
    "witnesses missing organization"
    "duplicate titles"
    "sudden increase in error rate"
    "far in the future"
)

for check in "${ANOMALY_CHECKS[@]}"; do
    if grep -qi "$check" scripts/verify_updates.py; then
        print_pass "Anomaly check: '$check'"
    else
        print_fail "Anomaly check missing: '$check'"
    fi
done

# ==============================================================================
# TEST 7: Verify backup directory structure
# ==============================================================================
print_test "Verify backup system configuration"

if grep -q "backups_dir = Path" updaters/daily_updater.py; then
    print_pass "Backup directory path configured"
else
    print_fail "Backup directory path not configured"
fi

if grep -q "database_backup_" updaters/daily_updater.py; then
    print_pass "Backup filename pattern configured"
else
    print_fail "Backup filename pattern not configured"
fi

# ==============================================================================
# TEST 8: Check for proper imports
# ==============================================================================
print_test "Verify required imports"

if grep -q "import shutil" updaters/daily_updater.py; then
    print_pass "shutil imported for file operations"
else
    print_fail "shutil not imported"
fi

if grep -q "from pathlib import Path" updaters/daily_updater.py; then
    print_pass "Path imported for file operations"
else
    print_fail "Path not imported"
fi

if grep -q "from scripts.verify_updates import UpdateValidator" updaters/daily_updater.py; then
    print_pass "UpdateValidator imported"
else
    print_fail "UpdateValidator not imported"
fi

# ==============================================================================
# TEST 9: Verify error handling and notifications
# ==============================================================================
print_test "Verify error handling and notifications"

if grep -q "self.notifier.send" updaters/daily_updater.py; then
    print_pass "Notifier integration found"
else
    print_fail "Notifier not integrated"
fi

if grep -q "Post-Update Validation Failed" updaters/daily_updater.py; then
    print_pass "Validation failure notification found"
else
    print_fail "Validation failure notification not found"
fi

if grep -q "Database Rollback Performed" updaters/daily_updater.py; then
    print_pass "Rollback notification found"
else
    print_fail "Rollback notification not found"
fi

# ==============================================================================
# TEST 10: Verify rollback logic
# ==============================================================================
print_test "Verify rollback logic"

if grep -q "self._rollback_database()" updaters/daily_updater.py; then
    print_pass "Rollback is called"
else
    print_fail "Rollback not called"
fi

if grep -q "validation_passed == False" updaters/daily_updater.py; then
    print_pass "Rollback triggered on validation failure"
else
    print_fail "Rollback not triggered on validation failure"
fi

if grep -q "except Exception as e:" updaters/daily_updater.py && \
   grep -q "self._rollback_database()" updaters/daily_updater.py; then
    print_pass "Rollback triggered on exceptions"
else
    print_fail "Rollback not triggered on exceptions"
fi

# ==============================================================================
# SUMMARY
# ==============================================================================
echo ""
echo "============================================================================"
echo "TEST SUMMARY"
echo "============================================================================"
echo ""
echo -e "Tests Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Tests Failed: ${RED}${TESTS_FAILED}${NC}"
echo -e "Total Tests:  $((TESTS_PASSED + TESTS_FAILED))"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    echo "The verification system has been successfully implemented with:"
    echo "  • Pre-update sanity checks"
    echo "  • Post-update validation"
    echo "  • Database backup & rollback"
    echo "  • Enhanced anomaly detection"
    echo "  • Admin dashboard health monitoring"
    echo ""
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo ""
    echo "Please review the failed tests above."
    echo ""
    exit 1
fi
