# Reporting Extraction & Parsing Issues

**Purpose**: Track and fix content extraction problems systematically.

---

## Quick Issue Report

When you find a parsing problem, create an issue with these details:

### 1. Article Information
- **URL**: The exact article URL that failed
- **Source**: Which ingester? (Heritage, Brookings, AEI, etc.)
- **Date tested**: When you discovered the issue

### 2. What's Wrong?
Pick the category that matches your issue:

- [ ] **Title Issues**: Wrong title, site name not removed, special characters broken
- [ ] **Author Issues**: Missing authors, wrong names, incomplete metadata, duplicates
- [ ] **Date Issues**: Wrong date, date not extracted, wrong format
- [ ] **Content Issues**: Missing content, truncated, HTML tags in text, junk content included
- [ ] **Summary Issues**: Missing summary, wrong summary, contaminated with other text
- [ ] **Metadata Issues**: Wrong document type, missing subjects/topics
- [ ] **Other**: Describe below

### 3. Expected vs Actual

**Expected** (what should happen):
```
Title: "Trump's Immigration Policy Reforms"
Author: John Smith (Senior Fellow)
Date: 2024-01-15
Content: Clean text, 1500 words, no HTML
```

**Actual** (what you got):
```
Title: "Trump's Immigration Policy Reforms | The Heritage Foundation"
Author: (none)
Date: None
Content: 150 words, contains "Share this article" text
```

### 4. Additional Context

- Is this happening on multiple articles or just one?
- Did you notice a pattern? (e.g., all old articles, all reports, etc.)
- Any error messages in output?

---

## Issue Reporting Methods

### Method 1: Quick Local File (Fastest)

Create a file to track issues during validation:

```bash
# Create an issues log
touch brookings_ingester/docs/issues/heritage_validation_issues.md
```

**Template for each issue**:

```markdown
## Issue #1: Missing Author on Commentary Articles

**URL**: https://www.heritage.org/immigration/commentary/border-security-matters
**Source**: Heritage
**Date Found**: 2025-01-17
**Severity**: Medium

### Problem
Author not extracted even though author card is visible on website.

### Expected
Author: "John Malcolm"
Title: "Vice President, Institute for Constitutional Government"

### Actual
Authors: (none)

### Test Command
```bash
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/immigration/commentary/border-security-matters"
```

### Debug Info
- Author card HTML class: `div.author-card__info-wrapper` (note: missing "author" prefix)
- Selector used: `div.author-card__author-info-wrapper` (doesn't match!)

### Status
- [ ] Reported
- [ ] Investigating
- [ ] Fixed
- [ ] Verified

### Fix Notes
Update selector to also check `div.author-card__info-wrapper` without "author" prefix.

---
```

### Method 2: GitHub Issues (For Tracking)

If using GitHub for your project:

**Title format**: `[SOURCE] Category: Brief description`

**Examples**:
- `[Heritage] Author: Missing authors on 2016 articles`
- `[Brookings] Content: HTML tags in text_content`
- `[AEI] Date: Date parsing fails on articles with time`

**Issue Template**:

```markdown
**Source**: Heritage Foundation
**Category**: Author Extraction
**Severity**: High / Medium / Low
**Affects**: All articles / Specific articles / Edge cases

## Problem Description
Clear description of what's wrong...

## Sample URLs
- https://www.heritage.org/article-1
- https://www.heritage.org/article-2
- https://www.heritage.org/article-3

## Reproduction Steps
```bash
python brookings_ingester/scripts/test_single_url.py heritage "URL"
```

## Expected Behavior
What should happen...

## Actual Behavior
What actually happens...

## Debug Information
- Selector used: `div.author-card__author-info-wrapper`
- HTML snippet: `<div class="author-info">...</div>`
- Error messages: (if any)

## Possible Fix
(Optional) Your suggestion for how to fix it...

## Impact
How many articles does this affect? Is it blocking production?
```

### Method 3: Structured CSV Log (For Bulk Testing)

If you're testing many articles and want to track systematically:

```bash
# Create a CSV to track issues
cat > brookings_ingester/docs/issues/validation_results.csv << 'EOF'
URL,Source,Issue_Category,Severity,Title_OK,Author_OK,Date_OK,Content_OK,Word_Count,Notes
https://heritage.org/article-1,Heritage,Author,Medium,Y,N,Y,Y,1250,Author missing - check selector
https://heritage.org/article-2,Heritage,Content,High,Y,Y,Y,N,50,Content truncated - only 50 words
https://heritage.org/article-3,Heritage,None,N/A,Y,Y,Y,Y,1800,Perfect - all fields extracted
EOF
```

**Fields**:
- `URL`: Article URL
- `Source`: Ingester name
- `Issue_Category`: Title/Author/Date/Content/Summary/Metadata/None
- `Severity`: High/Medium/Low/N/A
- `Title_OK`: Y/N
- `Author_OK`: Y/N
- `Date_OK`: Y/N
- `Content_OK`: Y/N
- `Word_Count`: Actual word count extracted
- `Notes`: Brief description of issue

**Analyze results**:
```bash
# Count issues by category
awk -F',' 'NR>1 {print $3}' validation_results.csv | sort | uniq -c

# Find all high-severity issues
grep ",High," validation_results.csv

# Calculate success rate
total=$(wc -l < validation_results.csv)
success=$(grep ",None," validation_results.csv | wc -l)
echo "Success rate: $success / $total"
```

### Method 4: Interactive Debug Session (For Complex Issues)

For issues you can't figure out, save all debug info:

```bash
# Save HTML for inspection
python brookings_ingester/scripts/save_html_fixture.py heritage \
  "https://www.heritage.org/problematic-article" \
  --output /tmp/debug_issue_1.html

# Save parsed output as JSON
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/problematic-article" \
  --json-output /tmp/debug_issue_1.json

# Create an issue package
mkdir -p brookings_ingester/docs/issues/issue_1
cp /tmp/debug_issue_1.html brookings_ingester/docs/issues/issue_1/
cp /tmp/debug_issue_1.json brookings_ingester/docs/issues/issue_1/
```

Then create a report:

```markdown
# Issue #1: Complete Debug Package

See files in `brookings_ingester/docs/issues/issue_1/`:
- `debug_issue_1.html` - Raw HTML from article
- `debug_issue_1.json` - Parsed output

## Quick Analysis

### Find author in HTML:
```bash
grep -i "author" brookings_ingester/docs/issues/issue_1/debug_issue_1.html | head -10
```

### Check what was extracted:
```bash
cat brookings_ingester/docs/issues/issue_1/debug_issue_1.json | jq '.authors'
```

## Next Steps
- [ ] Inspect HTML to find correct selector
- [ ] Update parser with new selector
- [ ] Test fix
- [ ] Verify on multiple articles
```

---

## Issue Severity Guidelines

### 🔴 High Severity (Fix Immediately)
- Success rate <85%
- Content completely missing or truncated
- HTML tags appearing in text_content
- Crashes or errors on most articles
- Security issues (exposing credentials, etc.)

**Action**: Stop deployment, fix immediately

### 🟡 Medium Severity (Fix Soon)
- Success rate 85-95%
- Authors missing on >25% of articles
- Dates missing on >20% of articles
- Some junk content getting through
- Special characters not displaying correctly

**Action**: Create issue, fix in next update

### 🟢 Low Severity (Fix Eventually)
- Success rate >95%
- Edge cases only (rare article formats)
- Minor metadata issues (topics missing occasionally)
- Cosmetic issues (title formatting)

**Action**: Document issue, fix when convenient

---

## Common Issues & Quick Fixes

### Issue: No Authors Extracted

**Check**:
1. Does the article have authors on the website?
2. Save HTML and search for "author" class names
3. Compare to parser's `METADATA_SELECTORS['authors']`

**Quick fix**:
```python
# In heritage_parser.py, add new selector to list
METADATA_SELECTORS = {
    'authors': [
        'div.author-card__author-info-wrapper',
        'div.author-info-wrapper',  # Add this
        'div.author-card',  # Or this
        # ...
    ],
}
```

### Issue: Date Not Extracted

**Check**:
1. What does the date look like on the website?
2. Save HTML and search for date text
3. Check if it matches expected format

**Quick fix**:
```python
# In heritage_parser.py, add date format to list
def _parse_date(self, date_str: str) -> Optional[str]:
    for fmt in [
        '%Y-%m-%d',
        '%B %d, %Y',
        '%b %d, %Y',
        '%m/%d/%Y',
        '%d %B %Y',  # Add this if dates are "15 January 2024"
    ]:
        # ...
```

### Issue: HTML Tags in Content

**Check**:
1. Is `_extract_text()` being called?
2. Are cleanup selectors removing junk?

**Quick fix**:
```python
# In heritage_parser.py, add more cleanup selectors
REMOVE_SELECTORS = [
    # ... existing selectors ...
    '.new-junk-element',  # Add the offending element
    'div.advertisement',
]
```

### Issue: Content Truncated (Low Word Count)

**Check**:
1. Is the right content area being selected?
2. Are paragraphs being removed accidentally?

**Quick fix**:
```python
# In heritage_parser.py, try alternative content selector
CONTENT_SELECTORS = [
    'div.article-body',
    'div.field--name-body',
    'article',  # Try more general selector
]
```

### Issue: Junk Content Included

**Check**:
1. What's the junk text? (share buttons, nav, ads?)
2. Find the HTML element containing it
3. Add to `REMOVE_SELECTORS`

**Quick fix**:
```python
REMOVE_SELECTORS = [
    # ... existing selectors ...
    '.social-media-share',  # Add specific junk selector
    'div.newsletter-signup',
]
```

---

## Testing Your Fix

After fixing an issue:

### 1. Test on Original Problem Article
```bash
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/problematic-article"
```

Expected: Issue should be fixed ✅

### 2. Test on 5-10 Other Articles
```bash
# Make sure fix didn't break other articles
python brookings_ingester/scripts/test_ingester.py heritage --limit 10
```

Expected: Success rate still >95% ✅

### 3. Update HTML Fixture
```bash
python brookings_ingester/scripts/save_html_fixture.py heritage \
  "https://www.heritage.org/problematic-article" \
  --output tests/fixtures/heritage_issue_1_fixed.html
```

### 4. Add Regression Test
```python
# In tests/test_heritage_ingester.py
def test_issue_1_author_extraction_fix():
    """Regression test for Issue #1: Authors not extracted"""
    parser = HeritageHTMLParser()

    with open('tests/fixtures/heritage_issue_1_fixed.html') as f:
        html = f.read()

    parsed = parser.parse(html, 'https://www.heritage.org/test')

    # This should now pass
    assert len(parsed.authors) > 0
    assert parsed.authors[0]['name'] == 'Expected Author Name'
```

### 5. Document the Fix
Update the issue report:

```markdown
## Issue #1: Missing Author on Commentary Articles

**Status**: ✅ FIXED

### Fix Applied
Updated `METADATA_SELECTORS['authors']` to include `div.author-info-wrapper` selector.

**File**: `brookings_ingester/ingesters/utils/heritage_parser.py`
**Line**: 65

### Verification
- ✅ Tested on original problematic article
- ✅ Tested on 10 other articles (10/10 success)
- ✅ Added regression test
- ✅ Success rate: 98% (was 75%)

**Fixed**: 2025-01-17
```

---

## Issue Tracking Workflow

```
1. Discover Issue
   ↓
2. Report Issue (using one of the methods above)
   ↓
3. Investigate
   - Save HTML
   - Inspect selectors
   - Check parser logic
   ↓
4. Fix
   - Update selectors
   - Update parser logic
   - Test locally
   ↓
5. Verify Fix
   - Test on problem article
   - Test on 10+ other articles
   - Check success rate still >95%
   ↓
6. Document
   - Update issue report with fix
   - Add regression test
   - Update README if needed
   ↓
7. Deploy
   - Commit changes
   - Update production
   - Monitor for new issues
```

---

## Issue Log Template

Create: `brookings_ingester/docs/issues/ISSUE_LOG.md`

```markdown
# Extraction & Parsing Issues Log

## Active Issues

### Issue #1: [Title]
- **Reported**: 2025-01-17
- **Severity**: High/Medium/Low
- **Status**: Open / Investigating / Fixed / Verified
- **Description**: ...
- **URLs Affected**: ...

## Resolved Issues

### Issue #1: Missing Authors on 2016 Articles
- **Reported**: 2025-01-17
- **Resolved**: 2025-01-17
- **Severity**: Medium
- **Root Cause**: Selector didn't match old HTML structure
- **Fix**: Added fallback selector for legacy author cards
- **Verification**: Tested on 20 articles from 2016-2024, all passed

## Known Limitations

### Heritage: Topics/Subjects
- Not all articles have topic tags
- This is expected, not an issue
- Success rate: ~60% have topics

### Heritage: Institutional Content
- Some articles have no named author (by design)
- Parser correctly handles this (empty authors list)
- Not an error condition

## Success Metrics

**Heritage Foundation**:
- Overall success rate: 96%
- Title extraction: 100%
- Author extraction: 92% (institutional articles have no author)
- Date extraction: 95%
- Content extraction: 99%
- Last updated: 2025-01-17
```

---

## Quick Commands for Issue Debugging

```bash
# Test single article
python brookings_ingester/scripts/test_single_url.py heritage "URL"

# Save HTML for inspection
python brookings_ingester/scripts/save_html_fixture.py heritage "URL" \
  --output /tmp/debug.html

# Search for text in saved HTML
grep -i "author" /tmp/debug.html
grep -i "date" /tmp/debug.html

# Check what selectors would match
python -c "
from bs4 import BeautifulSoup
html = open('/tmp/debug.html').read()
soup = BeautifulSoup(html, 'lxml')
print('Author elements:', soup.select('div[class*=author]'))
print('Date elements:', soup.select('time, div[class*=date]'))
"

# Test parser directly on saved HTML
python -c "
from brookings_ingester.ingesters.utils.heritage_parser import HeritageHTMLParser
html = open('/tmp/debug.html').read()
parser = HeritageHTMLParser()
parsed = parser.parse(html, 'https://test.url')
print(f'Title: {parsed.title}')
print(f'Authors: {parsed.authors}')
print(f'Date: {parsed.publication_date}')
print(f'Word count: {parsed.word_count}')
"

# Run tests to check for regressions
pytest tests/test_heritage_ingester.py -v

# Check success rate on batch
python brookings_ingester/scripts/test_ingester.py heritage --limit 50
```

---

## Need Help?

If you're stuck on an issue:

1. **Save a complete debug package**:
   - HTML file
   - JSON output
   - Screenshot of the article on the website
   - Description of what's wrong

2. **Check existing documentation**:
   - `heritage_README.md` - Known issues section
   - `heritage_analysis.md` - Expected selectors
   - This REPORTING_ISSUES.md file

3. **Create a detailed issue report** using templates above

4. **Test incremental fixes** - don't change too much at once

5. **Verify fixes don't break other articles** - always test on 10+ articles

---

**Last Updated**: 2025-01-17
