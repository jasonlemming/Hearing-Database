# Issues Directory

Use this directory to track extraction and parsing issues during validation.

## Structure

```
issues/
├── README.md (this file)
├── ISSUE_LOG.md (master log of all issues)
├── heritage_validation_issues.md (Heritage-specific issues found during validation)
└── issue_1/ (detailed debug package for complex issues)
    ├── debug.html
    ├── parsed.json
    └── notes.md
```

## Quick Start

### Report a simple issue:

```bash
cat >> brookings_ingester/docs/issues/heritage_validation_issues.md << 'ISSUE'

## Issue: Missing Author

**URL**: https://www.heritage.org/article-url
**Date**: 2025-01-17
**Problem**: Author not extracted
**Expected**: John Doe
**Actual**: (none)
**Status**: Open

ISSUE
```

### Create debug package for complex issue:

```bash
# Create directory
mkdir -p brookings_ingester/docs/issues/issue_1

# Save HTML
python brookings_ingester/scripts/save_html_fixture.py heritage "URL" \
  --output brookings_ingester/docs/issues/issue_1/debug.html

# Save parsed output
python brookings_ingester/scripts/test_single_url.py heritage "URL" \
  --json-output brookings_ingester/docs/issues/issue_1/parsed.json

# Add your notes
echo "## Investigation Notes" > brookings_ingester/docs/issues/issue_1/notes.md
```

See `../REPORTING_ISSUES.md` for full documentation.
