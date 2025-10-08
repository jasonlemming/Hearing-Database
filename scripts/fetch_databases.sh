#!/bin/bash
# Fetch large databases for production deployment

echo "Fetching CRS Products database..."

# GitHub Release URL for crs_products.db
RELEASE_URL="https://github.com/jasonlemming/Hearing-Database/releases/download/v1.0.0/crs_products.db"

# Download if not exists (for Vercel deployment)
if [ ! -f "crs_products.db" ]; then
    echo "Downloading crs_products.db from GitHub Releases..."

    # Try to download, but don't fail if it doesn't exist yet
    if curl -f -L -o crs_products.db "$RELEASE_URL" 2>/dev/null; then
        echo "Download complete!"
    else
        echo "CRS database not available yet (Release not found). App will show 'unavailable' page."
        echo "To enable CRS Products, create GitHub Release v1.0.0 with crs_products.db"
    fi
else
    echo "crs_products.db already exists, skipping download"
fi

echo "Database fetch complete!"
exit 0
