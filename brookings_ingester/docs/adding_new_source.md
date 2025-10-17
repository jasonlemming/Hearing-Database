# Playbook: Adding a New Content Source

**Follow these steps for every new source to ensure consistency and quality.**

---

## Prerequisites

- [ ] Source identified and approved for addition
- [ ] Legal/terms of service reviewed (ensure scraping is permitted)
- [ ] Rate limits understood
- [ ] Access verified (no hard paywalls blocking content)

---

## Step 1: Initial Reconnaissance (30-60 minutes)

### 1.1 Manual Browser Inspection

1. **Visit the target site** in Chrome/Firefox with DevTools open
2. **Navigate to article listing page** (e.g., `/articles/`, `/research/`)
3. **Inspect the page structure**:
   - Right-click on an article title → "Inspect"
   - Note the CSS classes and HTML structure
   - Check if content is in initial HTML or loaded via JavaScript

4. **Open 3-5 sample articles** in new tabs
5. **For each article**, inspect and document:
   - Title selector (`h1.entry-title`, etc.)
   - Content/body selector (`div.entry-content`, etc.)
   - Author selector (`span.author`, etc.)
   - Date selector (`time[datetime]`, etc.)
   - Elements to remove (ads, related posts, etc.)

### 1.2 Fill Out Analysis Document

```bash
# Copy the template
cp brookings_ingester/docs/source_analysis_template.md \
   brookings_ingester/docs/sources/[source_name]_analysis.md

# Fill it out completely
```

**Complete ALL sections**:
- Basic information
- Discovery method (pagination/sitemap/API)
- Content selectors
- Cleanup selectors
- Date formats
- Edge cases
- **At least 10 sample URLs**

**Quality Check**: Could someone else understand the site structure from this doc alone?

---

## Step 2: Generate Ingester Scaffold (5 minutes)

### 2.1 Run the Generator

```bash
python brookings_ingester/scripts/generate_ingester.py [source_name]
```

This creates:
- `brookings_ingester/ingesters/[source_name].py` - Main ingester class
- `brookings_ingester/ingesters/utils/[source_name]_parser.py` - HTML parser

### 2.2 Review Generated Code

The scaffold will have `# TODO:` markers for customization. Don't implement yet - just review the structure.

---

## Step 3: Implement Custom Logic (2-4 hours)

Work through TODOs incrementally. **Test each piece before moving to the next.**

### 3.1 Implement Article URL Discovery

**File**: `brookings_ingester/ingesters/[source_name].py`

**Method**: `discover()`

**Test incrementally**:
```python
# Add temporary debug code in discover()
logger.info(f"Found {len(documents)} URLs")
for url in documents[:5]:
    logger.info(f"  - {url}")

# Run just discovery
from brookings_ingester.ingesters.[source_name] import [ClassName]Ingester
ingester = [ClassName]Ingester()
docs = ingester.discover(limit=10)
print(f"Discovered {len(docs)} documents")
```

**Checkpoint**: Can you reliably get 10+ article URLs?

### 3.2 Implement HTML Parser

**File**: `brookings_ingester/ingesters/utils/[source_name]_parser.py`

**Follow the pattern** from `BrookingsHTMLParser` or `HeritageHTMLParser`:

1. Define selector constants:
```python
CONTENT_SELECTORS = ['div.entry-content', 'article .post-content']
METADATA_SELECTORS = {
    'title': ['h1.entry-title', 'article h1'],
    'authors': ['span.author-name a', 'a[rel="author"]'],
    'date': ['time[datetime]', 'span.publish-date'],
}
REMOVE_SELECTORS = [
    'aside.related-content',
    'div.newsletter-signup',
    'div.social-sharing',
    # ... from analysis doc
]
```

2. Implement `parse()` method following existing parser pattern

**Test with saved HTML**:
```bash
# Save a sample article's HTML
curl "https://example.org/articles/sample/" > /tmp/test_article.html

# Test parser
python -c "
from brookings_ingester.ingesters.utils.[source_name]_parser import [ClassName]HTMLParser
with open('/tmp/test_article.html') as f:
    html = f.read()
parser = [ClassName]HTMLParser()
parsed = parser.parse(html, 'https://example.org/articles/sample/')
print(f'Title: {parsed.title}')
print(f'Authors: {parsed.authors}')
print(f'Date: {parsed.publication_date}')
print(f'Word count: {parsed.word_count}')
"
```

**Checkpoint**: Does parsing extract clean, readable content?

### 3.3 Implement fetch() Method

**Already scaffolded** - uses Playwright like Brookings/Heritage.

**Customize if needed**:
- Adjust `wait_until` strategy
- Add special waits for dynamic content
- Handle Cloudflare or other challenges

**Test**:
```python
ingester = [ClassName]Ingester()
doc_meta = {'url': 'https://example.org/articles/sample/'}
fetched = ingester.fetch(doc_meta)
print(f"Fetched {len(fetched['html_content'])} bytes")
```

### 3.4 Implement parse() Method (Ingester)

**File**: `brookings_ingester/ingesters/[source_name].py`

This method calls the HTML parser and returns the standardized dict format.

**Follow Brookings/Heritage pattern exactly**:
```python
def parse(self, document_meta: Dict[str, Any], fetched_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        # Parse HTML
        parsed = self.html_parser.parse(
            fetched_content['html_content'],
            document_meta['url']
        )

        if not parsed:
            return None

        # Return standardized format
        return {
            'document_identifier': document_meta['document_identifier'],
            'title': parsed.title,
            'document_type': self._determine_type(document_meta['url']),
            'publication_date': parsed.publication_date,
            'summary': parsed.summary,
            'full_text': parsed.text_content,
            'url': document_meta['url'],
            'pdf_url': None,  # or extract if available
            'authors': parsed.authors,
            'subjects': parsed.subjects,
            'metadata': parsed.metadata,
            'html_content': parsed.html_content,
            'text_content': parsed.text_content,
            'structure': parsed.structure,
            'page_count': None,
            'word_count': parsed.word_count,
            'pdf_bytes': None
        }
    except Exception as e:
        logger.error(f"Error parsing {document_meta['document_identifier']}: {e}")
        return None
```

### 3.5 Handle Edge Cases

Refer to your analysis document and implement special handling for:
- Multiple authors
- Missing authors (institutional content)
- Different content types
- Special date formats

---

## Step 4: Comprehensive Testing (30-45 minutes)

### 4.1 Save HTML Test Fixtures

```bash
python brookings_ingester/scripts/save_html_fixture.py [source_name] \
  "https://example.org/articles/sample-1/" \
  --output tests/fixtures/[source_name]_sample_1.html

# Save 3-5 different article types
```

### 4.2 Test Full Ingester

```bash
python brookings_ingester/scripts/test_ingester.py [source_name] --limit 10
```

**Review output - check for**:
- [ ] All 10 URLs discovered successfully
- [ ] All 10 articles fetched (no errors)
- [ ] All 10 articles parsed successfully
- [ ] Titles extracted correctly
- [ ] Content is clean (no HTML tags, no ads)
- [ ] Authors identified when present
- [ ] Dates parsed correctly
- [ ] No warnings or errors

### 4.3 Test Edge Cases

Test with problematic articles from your sample URL list:
- Articles without authors
- Old articles (different formats?)
- Articles with special characters
- Sponsored content (if applicable)

### 4.4 Volume Testing

```bash
# Scrape 50-100 articles
python brookings_ingester/scripts/test_ingester.py [source_name] --limit 100
```

**Check for**:
- [ ] Success rate > 95%
- [ ] No memory leaks
- [ ] Consistent performance (not slowing down)
- [ ] Error rate < 5%

---

## Step 5: Integration with Base System (15 minutes)

### 5.1 Add Source to Database

```sql
INSERT INTO sources (source_code, name, url, source_type, metadata_json)
VALUES (
    '[SOURCE_CODE]',
    '[Full Source Name]',
    'https://example.org',
    'THINK_TANK',  -- or appropriate type
    '{}'::jsonb
);
```

### 5.2 Test with run_ingestion()

```python
from brookings_ingester.ingesters.[source_name] import [ClassName]Ingester

ingester = [ClassName]Ingester()
result = ingester.run_ingestion(
    limit=10,
    skip_existing=False,
    run_type='manual'
)

print(f"Success: {result['success']}")
print(f"Stats: {result['stats']}")
```

**Verify in database**:
```sql
SELECT COUNT(*), MIN(publication_date), MAX(publication_date)
FROM documents
WHERE source_id = (SELECT source_id FROM sources WHERE source_code = '[SOURCE_CODE]');
```

---

## Step 6: Documentation (10-15 minutes)

### 6.1 Create Source README

**File**: `brookings_ingester/docs/sources/[source_name]_README.md`

Include:
- **Overview**: Brief description of source
- **Configuration**: Rate limits, schedule recommendations
- **Selectors**: Quick reference table
- **Known Issues**: Edge cases, quirks, troubleshooting tips
- **Testing**: How to test this ingester
- **Maintenance**: When to review, how to update selectors
- **Last Verified**: Date and who verified

### 6.2 Update Main Documentation

Add entry to `brookings_ingester/docs/SOURCES.md` (create if doesn't exist):

```markdown
## [Source Name]
- **Source Code**: [SOURCE_CODE]
- **URL**: https://example.org
- **Content Type**: Policy research, commentary
- **Status**: ✅ Active
- **Update Frequency**: Daily
- **Avg Articles/Day**: 8-12
- **Success Rate**: 96%+
- **Last Verified**: 2025-01-17
- **Owner**: [Your Name]
- **Notes**: Multiple authors common, requires Playwright for JS rendering
```

---

## Step 7: Deployment (15-30 minutes)

### 7.1 Add to Cron Schedule (if automated)

**Option A: Add to PolicyLibraryUpdater pattern**

Create updater in `updaters/[source_name]_updater.py` following `PolicyLibraryUpdater` pattern.

**Option B: Manual runs**

Create run script:
```bash
# ingest_[source_name].py
from brookings_ingester.ingesters.[source_name] import [ClassName]Ingester
from brookings_ingester.models.database import init_database

init_database()
ingester = [ClassName]Ingester()
result = ingester.run_ingestion(limit=50, run_type='manual')
print(result)
```

### 7.2 Initial Production Run

```bash
# Run with moderate limit first
python ingest_[source_name].py

# Verify in database
# Check for errors in logs
# Validate content quality
```

### 7.3 Monitor

- Check `ingestion_logs` table for success/failure
- Review `ingestion_errors` table for any issues
- Spot-check 5-10 articles in database for quality

---

## Maintenance & Troubleshooting

### When Selectors Break (Site Redesign)

1. **Identify the issue**:
   ```bash
   python brookings_ingester/scripts/test_single_url.py [source_name] \
     "https://example.org/recent-article/"
   ```

2. **Update analysis document** with new selectors
3. **Update parser** (`utils/[source_name]_parser.py`)
4. **Test with recent articles**
5. **Deploy hotfix**

### Performance Issues

**Symptom**: Scraping > 5 seconds per article

**Check**:
1. Network latency (site slow?)
2. Playwright waits (too aggressive?)
3. Rate limiting (getting throttled?)

**Solutions**:
- Reduce rate limit delay
- Adjust `wait_until` strategy
- Use `wait_for_selector` instead of `networkidle`

### Missing Data

**Symptom**: Some fields not extracting

**Debug**:
```bash
# Save recent article HTML
curl "https://example.org/articles/recent/" > /tmp/debug.html

# Test parser on it
python -c "
from brookings_ingester.ingesters.utils.[source_name]_parser import [ClassName]HTMLParser
import json
with open('/tmp/debug.html') as f:
    html = f.read()
parser = [ClassName]HTMLParser()
parsed = parser.parse(html, 'https://example.org/articles/recent/')
print(json.dumps({
    'title': parsed.title,
    'authors': parsed.authors,
    'date': parsed.publication_date,
    'word_count': parsed.word_count
}, indent=2))
"
```

---

## Time Estimates

| Phase | First Source | After 5 Sources | After 10 Sources |
|-------|-------------|-----------------|------------------|
| Reconnaissance | 60 min | 40 min | 30 min |
| Implementation | 4 hours | 3 hours | 2 hours |
| Testing | 45 min | 30 min | 20 min |
| Documentation | 20 min | 15 min | 10 min |
| **Total** | **~6 hours** | **~4 hours** | **~3 hours** |

**Goal**: With practice and good templates, add a new source in 2-3 hours.

---

## Checklist Summary

Before marking a source as "complete":

- [ ] Analysis document filled out completely
- [ ] Ingester implemented and tested
- [ ] HTML parser implemented with cleanup selectors
- [ ] 10+ sample URLs tested successfully
- [ ] Edge cases handled
- [ ] Tests pass (>95% success rate)
- [ ] Source added to database
- [ ] Integration tested with `run_ingestion()`
- [ ] Documentation complete (README + SOURCES.md entry)
- [ ] Initial production run successful
- [ ] Content quality verified in database

---

## Success Criteria

✅ **Source is production-ready when**:
- Success rate > 95% on 50+ test articles
- All required fields extracting correctly
- Content is clean (no HTML, ads, or junk)
- Handles edge cases gracefully
- Tests pass
- Documentation complete
- Team can maintain it from docs alone
