# Manual Validation Guide for Policy Library Ingesters

**Purpose**: This guide helps you manually validate ingester quality before trusting automated results.

**Use this guide when**:
- Adding a new source
- Major changes to existing ingester
- Quality concerns or unexpected results
- Before production deployment

---

## Quick Start: Validate Heritage Ingester

Follow these steps to manually verify Heritage ingester quality:

### Step 1: Test a Single Article (2 minutes)

```bash
# Activate virtual environment
source .venv/bin/activate

# Test a known good Heritage article
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/election-integrity/commentary/the-trump-list-possible-justices-great-two-names-are-missing"
```

**What to check in the output**:

✅ **Title Section**:
- Title extracted correctly?
- Site name removed? (should not say "| The Heritage Foundation")
- Special characters display correctly?

✅ **Authors Section**:
- Author name present?
- Job title/position included?
- Affiliation text makes sense?
- Profile URL looks valid?

✅ **Publication Date Section**:
- Date in YYYY-MM-DD format?
- Date seems reasonable for the article?

✅ **Document Type Section**:
- Correct type? (Commentary, Report, Backgrounder, etc.)
- Matches URL pattern?

✅ **Content Stats Section**:
- Word count >100 for real articles?
- Full text length seems reasonable? (8000+ chars for typical article)
- Text content matches full text?

✅ **Summary Section**:
- Summary extracted and readable?
- Makes sense as article intro?
- No HTML tags or junk?

✅ **Validation Results**:
- All checks passed? ✅
- Or warnings about missing fields? ⚠️

---

### Step 2: Inspect the Full Content (5 minutes)

Run the same test with `--verbose` to see content preview:

```bash
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/election-integrity/commentary/the-trump-list-possible-justices-great-two-names-are-missing" \
  --verbose
```

**What to check in content preview**:

✅ **No HTML tags**: Should be plain text, not `<p>`, `<div>`, etc.

✅ **No junk content**:
- No "Share this article" buttons
- No "Subscribe to newsletter" text
- No navigation menu text
- No author bio signatures like "- John Malcolm is..."

✅ **Proper spacing**:
- Words not run together ("helloworld" ❌ vs "hello world" ✅)
- Sentences separated
- Paragraphs identifiable

✅ **Special characters handled**:
- Em dashes (—) display correctly
- Curly quotes (" ") display correctly
- No weird encoding like `&amp;` or `&#39;`

✅ **Content makes sense**:
- Read first 3-4 sentences
- Does it read like the actual article?
- No random snippets from ads or sidebars?

---

### Step 3: Compare with Source Website (5 minutes)

Open the article in your browser and compare:

1. **Visit the URL**: https://www.heritage.org/election-integrity/commentary/the-trump-list-possible-justices-great-two-names-are-missing

2. **Compare title**:
   - Browser title: "The Trump List of Possible Justices is Great but Two Names are Missing"
   - Extracted title: Should match exactly (without site name suffix)

3. **Compare author**:
   - Look for author card on page
   - Check name, title, affiliation match
   - Verify profile URL works

4. **Compare date**:
   - Find publication date on page (look for "min read" text or date element)
   - Should match extracted date

5. **Compare content**:
   - Copy first paragraph from website
   - Search for it in extracted `text_content`
   - Should be present and readable

6. **Spot check 3-4 paragraphs**:
   - Pick random paragraphs from middle and end
   - Verify they're in extracted content
   - Check for accuracy (no words cut off, proper spacing)

---

### Step 4: Test Multiple Content Types (10 minutes)

Heritage has different content types - test at least one of each:

#### Commentary

```bash
python brookings_ingester/scripts/test_single_url.py heritage \
  "https://www.heritage.org/crime-and-justice/commentary/law-and-order-president-trump-can-improve-criminal-justice-everyone"
```

Expected: Document Type = "Commentary"

#### Report

```bash
# Find a report URL from sitemap
curl -s "https://www.heritage.org/sitemap.xml?page=1" | \
  grep -o '<loc>[^<]*report[^<]*</loc>' | sed 's/<\/*loc>//g' | head -1

# Test that URL
python brookings_ingester/scripts/test_single_url.py heritage "PASTE_URL_HERE"
```

Expected: Document Type = "Report"

#### Other Types

Repeat for: Backgrounder, Issue Brief, Legal Memorandum, Testimony

**Check**: Document type correctly identified from URL pattern?

---

### Step 5: Test Edge Cases (10 minutes)

#### No Author (Institutional Content)

Find an article without a named author:

```bash
# Look for institutional content
# Test and verify:
# - Parser doesn't crash
# - Authors list is empty (not an error)
# - Content still extracted
```

#### Multiple Authors

Find an article with multiple authors:

```bash
# Look for articles with co-authors
# Verify:
# - Both/all authors extracted
# - Each has metadata
# - No duplicates
```

#### Old Articles (Different Format)

Test articles from different years:

```bash
# Test article from 2016-2018 (older format)
python brookings_ingester/scripts/test_single_url.py heritage \
  "URL_FROM_2016"

# Test article from 2024 (current format)
python brookings_ingester/scripts/test_single_url.py heritage \
  "URL_FROM_2024"

# Both should work
```

#### Special Characters in Titles

Find articles with em dashes, quotes, ampersands:

```bash
# Example: "Trump's Plan—A New Direction for America & the World"
# Verify:
# - Em dash (—) displays correctly
# - Quotes display correctly
# - Ampersand (&) not encoded as &amp;
```

---

### Step 6: Test Discovery (5 minutes)

Verify article discovery works:

```bash
python brookings_ingester/scripts/test_ingester.py heritage --limit 10
```

**What to check**:

✅ **Discovery Stats**:
- URLs discovered: Should be 10 (or whatever limit you set)
- All URLs from heritage.org?
- All URLs match content patterns? (/commentary/, /report/, etc.)

✅ **Processing Stats**:
- Success rate: Should be >90% (ideally >95%)
- Average time per article: Should be <10 seconds

✅ **Content Quality**:
- Spot check 2-3 articles from output
- Titles make sense?
- Word counts reasonable? (>100 words)
- No HTML in content samples?

---

## Detailed Validation Checklist

Use this comprehensive checklist for thorough validation:

### Title Extraction

- [ ] Title extracted for all test articles
- [ ] Site name suffix removed ("| The Heritage Foundation")
- [ ] Special characters display correctly (em dashes, quotes, ampersands)
- [ ] No HTML tags in title
- [ ] Title matches source website

### Author Extraction

- [ ] Author name extracted when present
- [ ] Job title/position included
- [ ] Affiliation text makes sense (not truncated)
- [ ] Profile URL is valid Heritage staff URL
- [ ] Twitter URL works (if present)
- [ ] Multiple authors all extracted (no missing co-authors)
- [ ] No duplicate authors
- [ ] Institutional content (no author) doesn't crash
- [ ] Author bio signatures removed from content

### Date Extraction

- [ ] Date extracted for >95% of articles
- [ ] Date format is YYYY-MM-DD
- [ ] Dates seem reasonable (not future dates, not ancient history)
- [ ] "Min read" text properly handled ("Nov 21, 2016 4 min read" → "2016-11-21")
- [ ] Year-stuck-to-number quirk handled ("20164 min read" → "2016-11-21")

### Content Extraction

- [ ] Content extracted for all test articles
- [ ] Word count >100 for typical articles
- [ ] No HTML tags in text_content (`<p>`, `<div>`, etc.)
- [ ] No junk content (share buttons, navigation, ads)
- [ ] No author bio signatures in text
- [ ] Proper word spacing (words not run together)
- [ ] Sentences properly separated
- [ ] Paragraphs identifiable
- [ ] Special characters handled (em dashes, quotes, etc.)
- [ ] Content matches source website (spot check 3+ paragraphs)
- [ ] Images converted to absolute URLs (in html_content)

### Summary Extraction

- [ ] Summary extracted for >90% of articles
- [ ] Summary length reasonable (>50 chars)
- [ ] Summary makes sense as intro/description
- [ ] No HTML tags in summary
- [ ] Not contaminated with author info

### Metadata & Structure

- [ ] Document type correctly identified (Commentary, Report, etc.)
- [ ] URL is absolute (starts with https://)
- [ ] Document identifier extracted from URL
- [ ] Content hash computed
- [ ] Word count matches actual content
- [ ] Topics/subjects extracted (if available)

### Edge Cases

- [ ] No-author articles: Parser doesn't crash, content extracted
- [ ] Multiple authors: All extracted, no duplicates
- [ ] Old articles (pre-2020): Still parse correctly
- [ ] Special characters: Display correctly everywhere
- [ ] Empty/minimal content: Handled gracefully (no crash)
- [ ] Invalid URLs: Return None or error gracefully
- [ ] 404 pages: Detected, don't store as valid content

### Performance

- [ ] Average fetch time: <10 seconds per article
- [ ] Average parse time: <1 second per article
- [ ] Memory usage stable over 50+ articles (no leaks)
- [ ] Rate limiting respected (1.5 second delay between requests)
- [ ] Browser closes properly after each fetch (no zombie processes)

---

## Red Flags: When to Investigate

Stop and investigate if you see:

🚩 **Success rate <90%**: Something is wrong with selectors or site changes

🚩 **Word count <50 for multiple articles**: Content not extracting properly

🚩 **HTML tags in text_content**: Content cleaning not working

🚩 **"Share this", "Subscribe", navigation text in content**: Junk not being removed

🚩 **All authors missing**: Author selector broken

🚩 **All dates missing**: Date selector broken

🚩 **Title is always "The Heritage Foundation"**: Title selector broken or site 404

🚩 **Content is gibberish**: Encoding issues or wrong selector

🚩 **Memory usage increasing**: Memory leak in browser handling

🚩 **Fetch time >30 seconds**: Network issues or wait strategy too aggressive

---

## Testing Database Storage (Advanced)

If you want to test actual database storage:

### Setup Test Database

```bash
# Use a test database, not production!
export DATABASE_URL="postgresql://user:pass@localhost/test_policy_library"

# Initialize schema
python -c "from brookings_ingester.models.database import init_database; init_database()"
```

### Test Storage

```python
from brookings_ingester.ingesters.heritage import HeritageIngester
from brookings_ingester.models.database import init_database

init_database()
ingester = HeritageIngester()

result = ingester.run_ingestion(limit=10, skip_existing=False, run_type='test')

print(f"Success: {result['success']}")
print(f"Stats: {result['stats']}")
```

### Verify in Database

```sql
-- Check documents stored
SELECT
    document_id,
    title,
    publication_date,
    word_count,
    LENGTH(full_text) as text_length
FROM documents
WHERE source_id = (SELECT source_id FROM sources WHERE source_code = 'HERITAGE')
ORDER BY created_at DESC
LIMIT 10;

-- Check authors linked
SELECT
    d.title,
    a.name,
    a.metadata_json->>'title' as author_title
FROM documents d
JOIN document_authors da ON d.document_id = da.document_id
JOIN authors a ON da.author_id = a.author_id
WHERE d.source_id = (SELECT source_id FROM sources WHERE source_code = 'HERITAGE')
LIMIT 10;

-- Check for duplicates (content_hash)
SELECT content_hash, COUNT(*) as count
FROM documents
WHERE source_id = (SELECT source_id FROM sources WHERE source_code = 'HERITAGE')
GROUP BY content_hash
HAVING COUNT(*) > 1;
```

**What to check**:
- [ ] All documents stored with correct metadata
- [ ] Authors properly linked (not duplicated unnecessarily)
- [ ] No duplicate documents (same content_hash)
- [ ] Full text searchable (no HTML, readable content)
- [ ] Dates in correct format
- [ ] Word counts match expectations

---

## Validation Report Template

After completing validation, fill out this report:

```markdown
# Validation Report: Heritage Ingester

**Date**: YYYY-MM-DD
**Validator**: Your Name
**Test Environment**: Local / Staging / Production

## Summary

✅ / ⚠️ / ❌ **Overall Status**: PASS / PASS WITH ISSUES / FAIL

**Recommendation**: APPROVE FOR PRODUCTION / NEEDS FIXES / DO NOT DEPLOY

## Test Results

### Single URL Tests (Step 1-3)

- Articles tested: 5
- Success: 5/5 (100%)
- Issues found: None / See below

**Sample article**: [URL]
- ✅ Title extracted correctly
- ✅ Author metadata complete
- ✅ Date parsed correctly
- ✅ Content clean and accurate
- ✅ Matches source website

### Content Type Tests (Step 4)

- [ ] Commentary: PASS / FAIL
- [ ] Report: PASS / FAIL
- [ ] Backgrounder: PASS / FAIL
- [ ] Issue Brief: PASS / FAIL

### Edge Case Tests (Step 5)

- [ ] No author: PASS / FAIL
- [ ] Multiple authors: PASS / FAIL
- [ ] Old articles: PASS / FAIL
- [ ] Special characters: PASS / FAIL

### Discovery & Pipeline Test (Step 6)

- Articles discovered: 10
- Success rate: 95% (9.5/10)
- Average time: 4.2 seconds/article
- Issues: None / See below

## Issues Found

### Critical Issues (Block Production)

None / List issues...

### Non-Critical Issues (Can fix later)

None / List issues...

### Notes

Any observations, quirks, or recommendations...

## Approval

- [ ] I have manually validated this ingester
- [ ] Content quality is acceptable (>90% success, clean text)
- [ ] Edge cases handled appropriately
- [ ] Ready for production deployment

**Signature**: _______________ **Date**: _______________
```

---

## Quick Commands Reference

```bash
# Activate environment
source .venv/bin/activate

# Test single article
python brookings_ingester/scripts/test_single_url.py heritage "URL"

# Test with verbose output
python brookings_ingester/scripts/test_single_url.py heritage "URL" --verbose

# Test 10 articles (full pipeline)
python brookings_ingester/scripts/test_ingester.py heritage --limit 10

# Save HTML for inspection
python brookings_ingester/scripts/save_html_fixture.py heritage "URL" --output /tmp/test.html

# Find recent URLs from sitemap
curl -s "https://www.heritage.org/sitemap.xml?page=1" | grep -o '<loc>[^<]*</loc>' | sed 's/<\/*loc>//g' | head -10

# Run unit tests
pytest tests/test_heritage_ingester.py -v

# Run unit tests (skip slow tests)
pytest tests/test_heritage_ingester.py -v -m "not slow"
```

---

**Last Updated**: 2025-01-17
**Next Review**: After major ingester changes or new source additions
