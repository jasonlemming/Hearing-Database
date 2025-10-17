#!/bin/bash
# Script to set up the daily Substack ingestion cron job

echo "Setting up daily Substack ingestion cron job..."

# Get the absolute path to the script
SCRIPT_PATH="/Users/jason/Documents/GitHub/Hearing-Database/brookings_ingester/scripts/run_daily_substack.sh"

# Create a temporary file with the new cron job
TEMP_CRON=$(mktemp)

# Get existing crontab (if any)
crontab -l 2>/dev/null > "$TEMP_CRON" || true

# Check if the job already exists
if grep -q "run_daily_substack.sh" "$TEMP_CRON"; then
    echo "Cron job already exists. Updating..."
    # Remove existing job
    grep -v "run_daily_substack.sh" "$TEMP_CRON" > "$TEMP_CRON.new"
    mv "$TEMP_CRON.new" "$TEMP_CRON"
fi

# Add the new cron job
# Runs daily at 6:00 AM
echo "0 6 * * * $SCRIPT_PATH >> /Users/jason/Documents/GitHub/Hearing-Database/logs/substack_cron.log 2>&1" >> "$TEMP_CRON"

# Install the new crontab
crontab "$TEMP_CRON"

# Clean up
rm "$TEMP_CRON"

echo "✓ Cron job installed successfully!"
echo ""
echo "Schedule: Daily at 6:00 AM"
echo "Script: $SCRIPT_PATH"
echo "Log: /Users/jason/Documents/GitHub/Hearing-Database/logs/substack_cron.log"
echo ""
echo "To view all cron jobs: crontab -l"
echo "To edit cron jobs: crontab -e"
echo "To remove cron jobs: crontab -r"
