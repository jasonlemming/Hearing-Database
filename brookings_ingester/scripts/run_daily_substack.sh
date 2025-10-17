#!/bin/bash
# Wrapper script for daily Substack ingestion
# This activates the virtual environment and runs the Python script

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Change to project directory
cd "$PROJECT_ROOT" || exit 1

# Activate virtual environment
source .venv/bin/activate || exit 1

# Run the ingestion script
python brookings_ingester/scripts/daily_substack_ingest.py

# Exit with the same code as the Python script
exit $?
