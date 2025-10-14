#!/bin/bash
#
# Health Check Script for Congressional Hearing Database
#
# This script checks the health endpoint and exits with appropriate status codes
# for integration with monitoring systems like cron, UptimeRobot, or Nagios.
#
# Exit codes:
#   0 - Healthy
#   1 - Degraded (warnings present)
#   2 - Unhealthy (critical issues)
#   3 - Cannot connect to health endpoint
#
# Usage:
#   ./scripts/check_health.sh [URL]
#
# Examples:
#   ./scripts/check_health.sh https://hearing-database.vercel.app/api/cron/health
#   ./scripts/check_health.sh  # Uses HEALTH_CHECK_URL environment variable
#
# For cron monitoring, add to crontab:
#   */30 * * * * /path/to/check_health.sh || echo "Health check failed!" | mail -s "Database Health Alert" admin@example.com
#

# Default health check URL (can be overridden via environment variable or argument)
HEALTH_CHECK_URL="${1:-${HEALTH_CHECK_URL:-http://localhost:5000/api/cron/health}}"

# Colors for output (disable if not a TTY)
if [ -t 1 ]; then
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    GREEN='\033[0;32m'
    NC='\033[0m' # No Color
else
    RED=''
    YELLOW=''
    GREEN=''
    NC=''
fi

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Check if jq is available (optional, for pretty output)
HAS_JQ=false
if command -v jq &> /dev/null; then
    HAS_JQ=true
fi

# Fetch health check data
echo "Checking health endpoint: $HEALTH_CHECK_URL"
echo "---"

HTTP_CODE=$(curl -s -o /tmp/health_response.json -w "%{http_code}" "$HEALTH_CHECK_URL")

if [ $? -ne 0 ] || [ -z "$HTTP_CODE" ]; then
    print_status "$RED" "❌ ERROR: Cannot connect to health endpoint"
    rm -f /tmp/health_response.json
    exit 3
fi

# Check HTTP status code
if [ "$HTTP_CODE" -eq 200 ]; then
    STATUS_COLOR="$GREEN"
    STATUS_EMOJI="✅"
    STATUS_TEXT="HEALTHY"
    EXIT_CODE=0
elif [ "$HTTP_CODE" -eq 503 ]; then
    STATUS_COLOR="$RED"
    STATUS_EMOJI="❌"
    STATUS_TEXT="UNHEALTHY"
    EXIT_CODE=2
else
    STATUS_COLOR="$YELLOW"
    STATUS_EMOJI="⚠️ "
    STATUS_TEXT="DEGRADED"
    EXIT_CODE=1
fi

# Parse response
if [ "$HAS_JQ" = true ]; then
    # Pretty print with jq
    RESPONSE_STATUS=$(jq -r '.status // "unknown"' /tmp/health_response.json)
    WARNING_COUNT=$(jq -r '.warnings | length' /tmp/health_response.json 2>/dev/null || echo "0")
    ERROR_COUNT=$(jq -r '.errors | length' /tmp/health_response.json 2>/dev/null || echo "0")

    print_status "$STATUS_COLOR" "${STATUS_EMOJI} Status: $STATUS_TEXT (HTTP $HTTP_CODE)"
    echo ""

    # Print checks
    echo "Health Checks:"
    jq -r '.checks | to_entries[] | "  \(.key): \(.value)"' /tmp/health_response.json 2>/dev/null

    echo ""

    # Print warnings
    if [ "$WARNING_COUNT" -gt 0 ]; then
        print_status "$YELLOW" "⚠️  Warnings ($WARNING_COUNT):"
        jq -r '.warnings[]' /tmp/health_response.json | sed 's/^/  - /'
        echo ""
    fi

    # Print errors
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_status "$RED" "❌ Errors ($ERROR_COUNT):"
        jq -r '.errors[]' /tmp/health_response.json | sed 's/^/  - /'
        echo ""
    fi

    # Print circuit breaker status if present
    CB_STATE=$(jq -r '.checks.circuit_breaker.state // "N/A"' /tmp/health_response.json 2>/dev/null)
    if [ "$CB_STATE" != "N/A" ] && [ "$CB_STATE" != "null" ]; then
        if [ "$CB_STATE" = "open" ]; then
            print_status "$RED" "⛔ Circuit Breaker: OPEN"
        elif [ "$CB_STATE" = "half_open" ]; then
            print_status "$YELLOW" "🔄 Circuit Breaker: HALF-OPEN (testing recovery)"
        else
            print_status "$GREEN" "✅ Circuit Breaker: CLOSED"
        fi
    fi

else
    # No jq available, simple output
    print_status "$STATUS_COLOR" "${STATUS_EMOJI} Status: $STATUS_TEXT (HTTP $HTTP_CODE)"
    echo ""
    echo "Response:"
    cat /tmp/health_response.json
    echo ""
fi

# Cleanup
rm -f /tmp/health_response.json

# Exit with appropriate code
exit $EXIT_CODE
