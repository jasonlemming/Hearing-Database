# Extraction & Parsing Issues Log

**Purpose**: Master log of all parsing issues found during validation and production.

---

## How to Use This Log

1. **When you find an issue during validation**, add it to "Active Issues" section
2. **When you fix an issue**, move it to "Resolved Issues" with fix details
3. **Document known limitations** so they're not reported as issues

---

## Active Issues

_No active issues currently. Add issues below as you find them._

<!-- Template for new issues:

### Issue #X: [Brief Title]
- **Source**: Heritage / Brookings / AEI
- **Reported**: YYYY-MM-DD
- **Severity**: High / Medium / Low
- **Status**: Open / Investigating / Fix in Progress
- **URLs Affected**:
  - https://example.com/article-1
  - https://example.com/article-2
- **Description**: What's wrong...
- **Impact**: How many articles affected? Blocks production?
- **Investigation Notes**: What you've found so far...
- **Next Steps**: What needs to be done...

-->

---

## Resolved Issues

_Resolved issues will be documented here with fix details._

<!-- Example of resolved issue:

### Issue #1: Missing Authors on Heritage 2016 Articles
- **Source**: Heritage Foundation
- **Reported**: 2025-01-17
- **Resolved**: 2025-01-17
- **Severity**: Medium
- **Root Cause**: Parser selector `div.author-card__author-info-wrapper` didn't match old HTML structure which used `div.author-info-wrapper`
- **URLs Affected**: ~30% of articles from 2016-2018
- **Fix Applied**:
  - Added fallback selector to `METADATA_SELECTORS['authors']`
  - File: `brookings_ingester/ingesters/utils/heritage_parser.py`
  - Line: 65
- **Verification**:
  - Tested on 20 articles from 2016-2024
  - Success rate improved from 75% to 96%
  - Added regression test: `test_heritage_old_author_format()`
- **Committed**: [commit hash]

-->

---

## Known Limitations (Not Issues)

These are expected behaviors, not bugs:

### Heritage: Institutional Content Has No Authors
- **What**: Some Heritage articles have no named author (organizational content)
- **Expected**: Parser returns empty authors list `[]`
- **Why**: This is correct - article legitimately has no author
- **Action**: None needed - working as intended

### Heritage: Not All Articles Have Topics
- **What**: Topic/subject tags missing on ~40% of articles
- **Expected**: Parser returns empty subjects list `[]`
- **Why**: Heritage doesn't tag all articles
- **Action**: None needed - this is a source limitation, not parser issue

### Heritage: Very Old Articles (Pre-2015) May Have Different Formats
- **What**: Articles from 2010-2015 occasionally use different HTML structure
- **Expected**: Lower success rate on very old articles (~85% vs 96%)
- **Why**: Heritage has redesigned their site multiple times
- **Action**: Acceptable - we're primarily focused on recent content

---

## Validation Success Metrics

Track overall quality metrics here after validation runs:

### Heritage Foundation

**Last Validation**: YYYY-MM-DD

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Overall Success Rate | >95% | __% | ✅/⚠️/❌ |
| Title Extraction | 100% | __% | ✅/⚠️/❌ |
| Author Extraction | >90% | __% | ✅/⚠️/❌ |
| Date Extraction | >95% | __% | ✅/⚠️/❌ |
| Content Extraction | >98% | __% | ✅/⚠️/❌ |
| Clean Content (No HTML) | 100% | __% | ✅/⚠️/❌ |

**Sample Size**: __ articles tested

**Test Command**:
```bash
python brookings_ingester/scripts/test_ingester.py heritage --limit 50
```

**Notes**: Any observations...

---

### Brookings Institution

**Last Validation**: YYYY-MM-DD

| Metric | Target | Actual | Status |
|--------|--------|--------|--------|
| Overall Success Rate | >95% | __% | ✅/⚠️/❌ |
| Title Extraction | 100% | __% | ✅/⚠️/❌ |
| Author Extraction | >90% | __% | ✅/⚠️/❌ |
| Date Extraction | >95% | __% | ✅/⚠️/❌ |
| Content Extraction | >98% | __% | ✅/⚠️/❌ |

**Sample Size**: __ articles tested

**Notes**: ...

---

## Issue Statistics

Track issue trends over time:

| Date | Source | Total Issues | High | Medium | Low | Open | Resolved |
|------|--------|--------------|------|--------|-----|------|----------|
| 2025-01-17 | Heritage | 0 | 0 | 0 | 0 | 0 | 0 |

---

## Common Issue Patterns

Document recurring issues and their common fixes:

### Pattern: Selector Breaks After Site Redesign
- **Symptom**: Sudden drop in success rate, fields not extracted
- **Diagnosis**: Save HTML, compare to old fixtures, find new class names
- **Fix**: Update selectors in parser's `METADATA_SELECTORS` and `CONTENT_SELECTORS`
- **Prevention**: Monitor success rates, run weekly smoke tests

### Pattern: Date Format Changes
- **Symptom**: Dates not parsing on new articles
- **Diagnosis**: Save HTML, inspect date element, check format
- **Fix**: Add new date format to `_parse_date()` method
- **Prevention**: Use multiple format attempts, log unparsable dates

### Pattern: New Junk Content Appearing
- **Symptom**: Word counts too high, content includes "Subscribe", "Share" text
- **Diagnosis**: Save HTML, find new element, note its class/id
- **Fix**: Add to `REMOVE_SELECTORS` list
- **Prevention**: Regularly spot-check content quality

---

## Validation History

Keep a record of validation runs:

### 2025-01-17: Initial Heritage Validation
- **Validator**: [Your Name]
- **Articles Tested**: 10
- **Success Rate**: 100% (10/10)
- **Issues Found**: 0
- **Status**: ✅ PASS - Approved for production
- **Notes**: All test articles parsed correctly. Rich author metadata working well.

---

**Log Maintained By**: Policy Library Team
**Last Updated**: 2025-01-17
