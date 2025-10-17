# Ingester Quality Assurance Checklist

**Use this checklist before deploying any ingester to production.**

---

## Source Information

**Source Name**: _______________
**Source Code**: _______________
**Developer**: _______________
**Reviewer**: _______________
**Date**: _______________
**Status**: [ ] Draft [ ] Review [ ] Approved [ ] Production

---

## 1. Code Quality

- [ ] Follows `BaseIngester` interface pattern
- [ ] Implements all required methods: `discover()`, `fetch()`, `parse()`
- [ ] Uses existing patterns from Brookings/Heritage (sync Playwright, dict-based returns)
- [ ] All `# TODO:` markers removed or documented as future work
- [ ] Error handling for network issues (timeouts, connection errors)
- [ ] Error handling for missing elements (None checks, try/except)
- [ ] Logging implemented (`logger.info`, `logger.error`, `logger.debug`)
- [ ] No hardcoded credentials or secrets
- [ ] Config values used instead of hardcoded strings
- [ ] Rate limiting implemented (`self._rate_limit()`)
- [ ] Code follows existing naming conventions
- [ ] No unused imports or dead code

**Notes**:

---

## 2. Functionality - Article Discovery

- [ ] Successfully discovers article URLs
- [ ] Pagination/sitemap parsing works correctly
- [ ] Returns correct data structure (list of dicts with required keys)
- [ ] Handles date filtering (`since_date` parameter)
- [ ] Respects `limit` parameter
- [ ] No duplicate URLs in returned list
- [ ] Works with various date ranges (recent, 1 month ago, 1 year ago)

**Test Results** (discovery of 50 articles):
- URLs found: _____ / 50
- Duplicates: _____
- Success rate: _____%

**Notes**:

---

## 3. Functionality - Content Fetching

- [ ] Successfully fetches HTML content
- [ ] Playwright browser configuration appropriate for site
- [ ] Waits configured correctly (not too aggressive, not too lax)
- [ ] Handles JavaScript-rendered content if needed
- [ ] Handles timeouts gracefully
- [ ] Closes browser properly on errors
- [ ] Returns correct data structure (dict with `html_content`)
- [ ] Average fetch time < 5 seconds per article

**Test Results** (fetching 20 articles):
- Successfully fetched: _____ / 20
- Average time: _____ seconds
- Errors: _____

**Notes**:

---

## 4. Functionality - Content Parsing

- [ ] Title extraction: 100% success rate
- [ ] Content extraction: >98% success rate
- [ ] Author extraction: >90% success rate (or N/A if site doesn't have authors)
- [ ] Date extraction: >95% success rate
- [ ] Content cleaning removes ads/junk
- [ ] Content cleaning removes social share buttons
- [ ] Content cleaning removes related articles sections
- [ ] Content hash computed correctly
- [ ] Word count calculated
- [ ] Returns correct standardized dict format (matches Brookings/Heritage pattern)

**Test Results** (parsing 50 articles):
- Title extracted: _____ / 50 (____%)
- Content extracted: _____ / 50 (____%)
- Author extracted: _____ / 50 (____%)
- Date extracted: _____ / 50 (____%)
- Clean content (spot-checked 10): _____ / 10

**Notes**:

---

## 5. Edge Cases Handling

- [ ] Handles articles without authors gracefully (doesn't crash)
- [ ] Handles articles with missing dates gracefully
- [ ] Handles multiple authors correctly (joins with commas or stores list)
- [ ] Handles institutional/organizational content (no named author)
- [ ] Handles sponsored/promotional content appropriately
- [ ] Handles paywalled content (skips or handles per strategy)
- [ ] Handles old articles with different HTML structure
- [ ] Handles special characters in titles (unicode, em dashes, quotes)
- [ ] Handles network timeouts without crashing
- [ ] Handles rate limiting from source site

**Edge Cases Tested**:
- No author: [ ] Pass [ ] Fail
- Multiple authors: [ ] Pass [ ] Fail [ ] N/A
- Missing date: [ ] Pass [ ] Fail
- Special characters: [ ] Pass [ ] Fail
- Old format (pre-2020): [ ] Pass [ ] Fail [ ] N/A

**Notes**:

---

## 6. Performance

- [ ] Average time per article < 3 seconds (discovery + fetch + parse)
- [ ] No memory leaks over 100+ articles
- [ ] Respects rate limits (delay configured appropriately)
- [ ] Browser closes properly after each article (no zombie processes)
- [ ] Handles errors without slowing down subsequent articles
- [ ] Efficient selectors (not using overly complex XPath)

**Performance Test** (100 articles):
- Total time: _____ minutes
- Average per article: _____ seconds
- Memory usage start: _____ MB
- Memory usage end: _____ MB
- Memory leak: [ ] Yes [ ] No

**Notes**:

---

## 7. Data Quality

- [ ] No duplicate articles created in database
- [ ] Content is readable (no HTML tags in `full_text`)
- [ ] No ads or promotional content in extracted text
- [ ] No navigation/footer content in extracted text
- [ ] Proper encoding (handles UTF-8, special characters, emojis)
- [ ] URLs are absolute, not relative
- [ ] Dates in correct format (YYYY-MM-DD)
- [ ] Author names properly formatted (no extra whitespace, punctuation)
- [ ] Content hash unique per article (spot-check 10 articles)

**Data Quality Spot Check** (10 random articles):
- Clean content (no HTML/ads): _____ / 10
- Proper encoding: _____ / 10
- Absolute URLs: _____ / 10
- Correct date format: _____ / 10

**Notes**:

---

## 8. Testing

- [ ] Unit tests exist for helper methods
- [ ] HTML fixtures saved for regression testing
- [ ] Integration test passes (full ingestion pipeline)
- [ ] Tested on 10+ sample URLs from analysis doc
- [ ] Tested on recent articles (< 1 week old)
- [ ] Tested on older articles (> 1 month old)
- [ ] Tested across different content types (if applicable)
- [ ] All tests pass with no failures

**Test Files Created**:
- Analysis doc: `brookings_ingester/docs/sources/[source]_analysis.md`
- HTML fixtures: `tests/fixtures/[source]_*.html`
- Test file: `tests/test_[source]_ingester.py`

**Test Coverage**:
- Unit tests: _____ tests
- Integration tests: _____ tests
- HTML fixtures: _____ files

**Notes**:

---

## 9. Documentation

- [ ] Source analysis document complete (`docs/sources/[source]_analysis.md`)
- [ ] Source README created (`docs/sources/[source]_README.md`)
- [ ] README includes selector reference table
- [ ] README includes known issues/quirks
- [ ] README includes troubleshooting section
- [ ] README includes testing instructions
- [ ] Main SOURCES.md updated with new entry
- [ ] Code comments explain non-obvious logic
- [ ] Selector choices documented (why these selectors?)
- [ ] Date parsing strategy documented

**Documentation Quality Check**:
- Could another developer maintain this from docs alone? [ ] Yes [ ] No
- Are all edge cases documented? [ ] Yes [ ] No
- Is troubleshooting section complete? [ ] Yes [ ] No

**Notes**:

---

## 10. Database Integration

- [ ] Source added to `sources` table
- [ ] `source_code` unique and follows naming convention (UPPERCASE)
- [ ] Test ingestion run completed successfully
- [ ] Articles saved to `documents` table
- [ ] Authors saved to `authors` table (with deduplication)
- [ ] `document_authors` relationship created
- [ ] Subjects/tags saved if applicable
- [ ] Metadata stored in `metadata_json` field
- [ ] Ingestion logged in `ingestion_logs` table
- [ ] No errors in `ingestion_errors` table (or acceptable error rate)

**Database Validation**:
```sql
SELECT COUNT(*) FROM documents WHERE source_id = (SELECT source_id FROM sources WHERE source_code = '[SOURCE_CODE]');
```
Result: _____ documents

**Sample Data Check** (5 random articles):
- Complete data: _____ / 5
- Authors populated: _____ / 5
- Subjects populated: _____ / 5

**Notes**:

---

## 11. Production Readiness

- [ ] Tested in staging environment (if available)
- [ ] No errors in 50+ article test run
- [ ] Duplicate detection working (content hash)
- [ ] Error rate < 5% acceptable
- [ ] Rate limiting appropriate for source (not too aggressive)
- [ ] Ready for automated scheduling (if applicable)
- [ ] Monitoring/alerting strategy defined
- [ ] Rollback plan documented

**Production Checklist**:
- [ ] Initial production run successful (limit 50-100 articles)
- [ ] Content quality verified by spot-checking 10 articles
- [ ] No critical errors in logs
- [ ] Performance acceptable (total time for 50 articles < 5 minutes)

**Notes**:

---

## 12. Final Approval

### Developer Sign-off

**I confirm that**:
- [ ] All checklist items reviewed
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Ready for production deployment

**Developer Signature**: _______________ **Date**: _______________

### Reviewer Sign-off

**I confirm that**:
- [ ] Code reviewed and follows patterns
- [ ] Tests verified and passing
- [ ] Documentation reviewed and adequate
- [ ] Sample data quality checked
- [ ] Approved for production

**Reviewer Signature**: _______________ **Date**: _______________

---

## Post-Deployment

### 24-Hour Check

- [ ] Automated run completed successfully (if scheduled)
- [ ] No errors in production logs
- [ ] Data quality spot-checked (10 articles)
- [ ] Performance acceptable

**Notes**:

### 1-Week Check

- [ ] Multiple runs completed successfully
- [ ] Error rate stable and acceptable
- [ ] No degradation in selector accuracy
- [ ] Ready for full production use

**Notes**:

---

## Issue Tracking

**Issues Found** (list any issues and resolution status):

| Issue | Severity | Status | Resolution |
|-------|----------|--------|------------|
|       |          |        |            |
|       |          |        |            |
|       |          |        |            |

**Severity**: Critical / High / Medium / Low
**Status**: Open / In Progress / Resolved / Deferred

---

## Overall Assessment

**Overall Status**: [ ] Pass [ ] Pass with Issues [ ] Fail

**Ready for Production**: [ ] Yes [ ] No [ ] Yes with Caveats

**Caveats** (if any):

**Recommendation**:

---

**Checklist Completed By**: _______________
**Date**: _______________
**Final Approval**: _______________
**Deployment Date**: _______________
