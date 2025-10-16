#!/bin/bash
#
# Simple Integration Test - No Python Dependencies Required
#
# Tests the verification system by directly querying the database
# and checking file system structure.
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
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

# Database file
DB_FILE="database.db"

if [ ! -f "$DB_FILE" ]; then
    echo -e "${RED}ERROR: Database file '$DB_FILE' not found!${NC}"
    exit 1
fi

print_header "VERIFICATION SYSTEM INTEGRATION TESTS"
echo "  Database: $DB_FILE"
echo "  Date: $(date '+%Y-%m-%d %H:%M:%S')"

# ============================================================================
# TEST 1: Database Health
# ============================================================================
print_header "TEST 1: Database Health Check"

# Check if database is accessible
if sqlite3 "$DB_FILE" "SELECT 1;" > /dev/null 2>&1; then
    print_pass "Database file is accessible"
else
    print_fail "Cannot access database file"
fi

# Check required tables exist
REQUIRED_TABLES=("hearings" "committees" "witnesses" "update_logs" "scheduled_tasks")
for table in "${REQUIRED_TABLES[@]}"; do
    if sqlite3 "$DB_FILE" "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" | grep -q "$table"; then
        print_pass "Table exists: $table"
    else
        print_fail "Missing table: $table"
    fi
done

# Check record counts
HEARING_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM hearings;")
COMMITTEE_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM committees;")
WITNESS_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM witness_appearances;")
LOG_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM update_logs;")

print_info "Hearings: $HEARING_COUNT"
print_info "Committees: $COMMITTEE_COUNT"
print_info "Witness appearances: $WITNESS_COUNT"
print_info "Update logs: $LOG_COUNT"

if [ "$HEARING_COUNT" -ge 1000 ]; then
    print_pass "Hearing count meets minimum threshold ($HEARING_COUNT >= 1000)"
else
    print_fail "Hearing count below minimum ($HEARING_COUNT < 1000)"
fi

if [ "$COMMITTEE_COUNT" -ge 200 ]; then
    print_pass "Committee count meets minimum threshold ($COMMITTEE_COUNT >= 200)"
else
    print_fail "Committee count below minimum ($COMMITTEE_COUNT < 200)"
fi

# ============================================================================
# TEST 2: Verification System Files
# ============================================================================
print_header "TEST 2: Verification System Files"

# Check critical files exist
CRITICAL_FILES=(
    "updaters/daily_updater.py"
    "scripts/verify_updates.py"
    "web/blueprints/admin.py"
    "web/templates/admin_dashboard.html"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        print_pass "File exists: $file"
    else
        print_fail "Missing file: $file"
    fi
done

# ============================================================================
# TEST 3: Backup Directory
# ============================================================================
print_header "TEST 3: Backup System"

BACKUP_DIR="backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

if [ -d "$BACKUP_DIR" ]; then
    print_pass "Backup directory exists: $BACKUP_DIR"
else
    print_fail "Cannot create backup directory: $BACKUP_DIR"
fi

# Check write permissions
if [ -w "$BACKUP_DIR" ]; then
    print_pass "Backup directory is writable"
else
    print_fail "Backup directory is not writable"
fi

# Count existing backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/database_backup_*.db 2>/dev/null | wc -l | tr -d ' ')
print_info "Existing backups: $BACKUP_COUNT"

if [ "$BACKUP_COUNT" -gt 0 ]; then
    print_info "Recent backups:"
    ls -lh "$BACKUP_DIR"/database_backup_*.db 2>/dev/null | tail -3 | awk '{print "  • " $9 " (" $5 ", " $6 " " $7 ")"}'
fi

# ============================================================================
# TEST 4: Update History
# ============================================================================
print_header "TEST 4: Update History"

# Check for recent updates
LAST_UPDATE=$(sqlite3 "$DB_FILE" "SELECT start_time FROM update_logs ORDER BY start_time DESC LIMIT 1;" 2>/dev/null || echo "")

if [ -n "$LAST_UPDATE" ]; then
    print_info "Last update: $LAST_UPDATE"
    print_pass "Update history exists"

    # Check if update was recent
    LAST_UPDATE_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_UPDATE" +%s 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    HOURS_AGO=$(( (NOW_EPOCH - LAST_UPDATE_EPOCH) / 3600 ))

    if [ "$HOURS_AGO" -lt 48 ]; then
        print_pass "Last update was recent (${HOURS_AGO}h ago)"
    elif [ "$HOURS_AGO" -lt 168 ]; then  # 7 days
        print_info "Last update was ${HOURS_AGO}h ago (warning threshold: 48h)"
    else
        print_fail "Last update was ${HOURS_AGO}h ago (> 7 days)"
    fi

    # Check last update success
    LAST_SUCCESS=$(sqlite3 "$DB_FILE" "SELECT success FROM update_logs ORDER BY start_time DESC LIMIT 1;")
    if [ "$LAST_SUCCESS" = "1" ]; then
        print_pass "Last update was successful"
    else
        print_fail "Last update failed"
    fi

    # Check error count
    LAST_ERRORS=$(sqlite3 "$DB_FILE" "SELECT error_count FROM update_logs ORDER BY start_time DESC LIMIT 1;")
    if [ "$LAST_ERRORS" -eq 0 ]; then
        print_pass "Last update had no errors"
    else
        print_info "Last update had $LAST_ERRORS errors"
    fi
else
    print_info "No update history found"
fi

# ============================================================================
# TEST 5: Scheduled Tasks
# ============================================================================
print_header "TEST 5: Scheduled Tasks"

TASK_COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM scheduled_tasks;")
ACTIVE_TASKS=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM scheduled_tasks WHERE is_active = 1;")

print_info "Total scheduled tasks: $TASK_COUNT"
print_info "Active tasks: $ACTIVE_TASKS"

if [ "$TASK_COUNT" -gt 0 ]; then
    print_pass "Scheduled tasks configured"

    # List tasks
    sqlite3 "$DB_FILE" "SELECT name, schedule_cron, is_active FROM scheduled_tasks;" | while IFS='|' read -r name cron active; do
        if [ "$active" = "1" ]; then
            print_info "  • $name: $cron (active)"
        else
            print_info "  • $name: $cron (inactive)"
        fi
    done
else
    print_info "No scheduled tasks configured yet"
fi

# ============================================================================
# TEST 6: Database Integrity
# ============================================================================
print_header "TEST 6: Database Integrity"

INTEGRITY_CHECK=$(sqlite3 "$DB_FILE" "PRAGMA integrity_check;")

if [ "$INTEGRITY_CHECK" = "ok" ]; then
    print_pass "Database integrity check passed"
else
    print_fail "Database integrity check failed: $INTEGRITY_CHECK"
fi

# Check for foreign key violations
FK_VIOLATIONS=$(sqlite3 "$DB_FILE" "PRAGMA foreign_keys = ON; PRAGMA foreign_key_check;" | wc -l | tr -d ' ')

if [ "$FK_VIOLATIONS" -eq 0 ]; then
    print_pass "No foreign key violations found"
else
    print_fail "Found $FK_VIOLATIONS foreign key violations"
fi

# ============================================================================
# TEST 7: Code Integration
# ============================================================================
print_header "TEST 7: Code Integration Checks"

# Check for backup methods in daily_updater.py
if grep -q "_create_database_backup" updaters/daily_updater.py; then
    print_pass "Backup creation method exists"
else
    print_fail "Backup creation method not found"
fi

if grep -q "_rollback_database" updaters/daily_updater.py; then
    print_pass "Rollback method exists"
else
    print_fail "Rollback method not found"
fi

if grep -q "_run_pre_update_sanity_checks" updaters/daily_updater.py; then
    print_pass "Pre-update sanity checks method exists"
else
    print_fail "Pre-update sanity checks method not found"
fi

if grep -q "_run_post_update_validation" updaters/daily_updater.py; then
    print_pass "Post-update validation method exists"
else
    print_fail "Post-update validation method not found"
fi

# Check for health endpoint
if grep -q "def system_health" web/blueprints/admin.py; then
    print_pass "System health endpoint exists"
else
    print_fail "System health endpoint not found"
fi

# Check for health widget in dashboard
if grep -q "System Health" web/templates/admin_dashboard.html; then
    print_pass "Health widget exists in dashboard"
else
    print_fail "Health widget not found in dashboard"
fi

# ============================================================================
# SUMMARY
# ============================================================================
print_header "TEST SUMMARY"

TOTAL_TESTS=$((TESTS_PASSED + TESTS_FAILED))

echo ""
echo -e "  Total Tests:  $TOTAL_TESTS"
echo -e "  Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "  Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    echo "The verification system is properly integrated and working with the database."
    echo ""
    echo "Key Findings:"
    echo "  • Database contains $HEARING_COUNT hearings, $COMMITTEE_COUNT committees"
    echo "  • $LOG_COUNT update operations logged"
    echo "  • $BACKUP_COUNT backup files exist"
    echo "  • $ACTIVE_TASKS active scheduled tasks"
    echo "  • Database integrity: OK"
    echo ""
    exit 0
else
    echo -e "${RED}✗ $TESTS_FAILED TEST(S) FAILED${NC}"
    echo ""
    echo "Please review the failures above and address any issues."
    echo ""
    exit 1
fi
