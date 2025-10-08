#!/bin/bash
# Fetch large databases for production deployment

set -e

echo "Fetching CRS Products database..."

# GitHub Release URL for crs_products.db
# Replace with your actual release URL after creating the release
RELEASE_URL="https://github.com/jasonlemming/Hearing-Database/releases/download/v1.0.0/crs_products.db"

# Download if not exists (for Vercel deployment)
if [ ! -f "crs_products.db" ]; then
    echo "Downloading crs_products.db from GitHub Releases..."
    curl -L -o crs_products.db "$RELEASE_URL"
    echo "Download complete!"
else
    echo "crs_products.db already exists, skipping download"
fi

echo "Database fetch complete!"
