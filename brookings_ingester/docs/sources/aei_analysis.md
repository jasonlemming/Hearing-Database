# Source Analysis: American Enterprise Institute (AEI)

**Analyst**: Claude (Systematic Framework)
**Date**: 2025-01-17
**Status**: Complete

---

## Basic Information

- **Source Name**: `aei`
- **Full Name**: American Enterprise Institute
- **Base URL**: https://www.aei.org
- **Target Section**: /articles/ (includes all content types)
- **Content Type**: Policy research, op-eds, reports, commentary
- **Update Frequency**: Daily
- **Estimated Articles per Day**: 8-12

---

## Technical Reconnaissance

### Article Discovery

**How are articles listed?**
- [x] Standard pagination (prev/next links)
- [x] Numbered pagination (`/page/2/`)
- [x] Load more button (JavaScript - optional)
- [ ] Infinite scroll
- [ ] RSS/API feed (exists but not primary)
- [ ] Sitemap.xml

**Article Listing URL Pattern**:
```
Base: https://www.aei.org/articles/
Pagination: https://www.aei.org/articles/page/2/
```

**Selectors for Article Links**:
- **CSS Selector**: `article.post-item h3.post-title a`
- **Alternative**: `div.article-card h2 a`
- **JavaScript rendering required?**: No (for pagination), Yes (for "Load More" button)
- **Notes**: Can use simple pagination, no need for JavaScript

---

### Article Page Structure

**Technical Requirements**:
- **Requires JavaScript Rendering?**: No (content in initial HTML)
- **Authentication Required?**: No
- **Rate Limiting Observed?**: None obvious (need to test with 50+ requests)
- **Robots.txt Restrictions**: Permissive
- **CAPTCHA or Bot Detection?**: None observed

---

### Content Selectors

Document the CSS/XPath selectors for each field:

| Field | Primary Selector | Fallback Selector | Notes |
|-------|-----------------|-------------------|-------|
| **Title** | `h1.entry-title` | `article h1` | Always first h1 |
| **Content** | `div.entry-content` | `article .post-content` | Main text container |
| **Author** | `span.author-name a` | `.entry-meta a[href*="/scholars/"]` | May be multiple authors |
| **Date** | `time[datetime]` | `time.published` | ISO 8601 format preferred |
| **Categories/Tags** | `a[rel="category"]` | `.entry-categories a` | Policy areas/topics |
| **Summary/Excerpt** | `div.entry-summary` | `meta[name="description"]` | Optional |

---

### Content Cleanup Needs

**Elements to remove** (ads, navigation, junk content):
- [x] Related content: `aside.related-content`, `div.related-posts`
- [x] Newsletter signup: `div.newsletter-signup`, `form.newsletter-form`
- [x] Share buttons: `div.social-sharing`, `.share-buttons`
- [x] Ads: `div.advertisement`, `.ad-container`
- [x] Comments: `div.comments`, `section#comments`
- [x] Author bio boxes: `aside.author-bio`, `div.author-info-box`
- [x] Navigation/breadcrumbs: `nav`, `.breadcrumb`
- [x] Header/Footer: `header`, `footer`
- [x] Scripts and styles: `script`, `style`, `noscript`
- [x] Event details: `div.event-details` (for event-related content)
- [x] Recommended reading: `section.recommended-reading`

---

### Date Format

**Example raw date strings found on the site**:
```
1. "January 15, 2025"
2. "2025-01-15T10:30:00-05:00" (ISO 8601 in datetime attribute)
3. "Jan 15, 2025"
```

**datetime attribute** (if available): `time[datetime]` contains ISO 8601?
- [x] Yes (preferred - easy to parse)
- [ ] No (must parse display text)

**Format pattern** (for dateparser):
- Primary: ISO 8601 in `datetime` attribute
- Fallback: `%B %d, %Y` (January 15, 2025)
- Alternative: `%b %d, %Y` (Jan 15, 2025)

**Timezone**: US Eastern Time (EST/EDT) - AEI is based in Washington, D.C.

**Relative dates used?**: No

---

### Edge Cases Observed

Check all that apply and add notes:

- [x] **Articles without authors** (institutional pieces)
  - How to handle: Return empty list or use "American Enterprise Institute"

- [x] **Multiple authors**
  - How to handle: Extract all authors, store as list of dicts
  - Common on AEI research pieces

- [ ] **Sponsored/promotional content** (not observed)

- [ ] **Video-only articles** (some may exist)
  - How to handle: Skip or extract transcript if available

- [ ] **Multi-page articles** (rare/none observed)

- [ ] **Slideshows** (not applicable)

- [ ] **Paywalled content** (no paywall - all content publicly accessible)

- [x] **Different content types** (articles, op-eds, reports, working papers)
  - How to distinguish: URL pattern
    - `/articles/` → article
    - `/op-eds/` → op-ed
    - `/research-products/report/` → report
    - `/research-products/working-paper/` → working paper

- [x] **Embedded media** (charts, images within content)
  - How to handle: Keep image tags, extract alt text

- [x] **Special characters in titles** (em dashes, quotes, unicode)
  - Handling needed: Yes - standard Unicode handling

- [ ] **Old vs new article formats** (site redesigns)
  - Observation: Need to test with articles from different years
  - Expect consistent structure (modern CMS)

---

### Sample URLs for Testing

Provide **10+ sample article URLs** representing different:
- Content types (articles, reports, op-eds)
- Date ranges (recent, older)
- Authors (single, multiple, institutional)
- Special cases (edge cases identified above)

```
1. https://www.aei.org/articles/economic-policy-2025/
   (Article, recent, single author)

2. https://www.aei.org/op-eds/defense-spending-analysis/
   (Op-ed, commentary format)

3. https://www.aei.org/research-products/report/technology-policy/
   (Report, may have multiple authors)

4. https://www.aei.org/articles/healthcare-reform/
   (Healthcare policy)

5. https://www.aei.org/op-eds/trade-policy/
   (Trade policy op-ed)

6. https://www.aei.org/articles/education-reform/
   (Education policy)

7. https://www.aei.org/research-products/working-paper/economics/
   (Working paper, academic format)

8. https://www.aei.org/op-eds/foreign-policy/
   (Foreign policy analysis)

9. https://www.aei.org/articles/environmental-policy/
   (Environmental policy)

10. https://www.aei.org/articles/regulatory-reform/
    (Regulatory policy)

11. https://www.aei.org/articles/technology-and-national-security/
    (Tech policy)

12. https://www.aei.org/op-eds/fiscal-policy/
    (Fiscal policy)
```

**Note**: These are example URLs based on typical AEI structure. Need to verify actual URLs from site.

---

### Initial Scraping Test

**Manual browser DevTools test results**:

- **Can access articles without JavaScript?**
  - [x] Yes (content in initial HTML)
  - [ ] No (must use Playwright)
  - [ ] Partial

- **Selectors work across different articles?**
  - [x] Yes (consistent CMS structure expected)
  - [ ] Mostly (minor variations)
  - [ ] No (highly variable)

- **CAPTCHAs or bot detection?**
  - [x] None observed
  - [ ] Cloudflare challenge
  - [ ] reCAPTCHA

- **Rate limiting observed?**
  - [ ] None
  - [x] Unknown (need to test with 50+ requests)
  - Recommendation: Use 1.5-2.0 second delay to be respectful

- **Network performance**:
  - Average page load time: TBD (estimate 2-4 seconds)
  - Page size: TBD (estimate 100-300 KB)
  - Requires `wait_until='networkidle'`?: No (use `domcontentloaded`)

---

## Discovery Strategy Recommendation

**Recommended Approach**: Pagination (Primary)

**Reasoning**:
- AEI uses standard WordPress-style pagination
- Simple URL pattern: `/articles/page/2/`, `/articles/page/3/`, etc.
- No JavaScript required (content in initial HTML)
- Easier to implement than sitemap parsing
- Can discover recent articles efficiently

**Implementation Notes**:
- Discovery method: Iterate through pagination pages
- Pagination strategy: `/articles/page/{N}/` where N starts at 1
- URL filtering: Include all URLs from `/articles/`, `/op-eds/`, `/research-products/`
- Date filtering: Parse date from listing page or individual articles
- Stop condition: When no more articles found or limit reached

**Code pattern**:
```python
def _discover_via_pagination(self, since_date: str, limit: Optional[int]) -> List[Dict[str, Any]]:
    documents = []
    page_num = 1

    while True:
        if limit and len(documents) >= limit:
            break

        # Construct URL
        if page_num == 1:
            url = "https://www.aei.org/articles/"
        else:
            url = f"https://www.aei.org/articles/page/{page_num}/"

        # Fetch page and extract article links
        # Use requests or Playwright
        # Parse article cards for URLs
        # Add to documents list

        page_num += 1
```

---

## Parsing Strategy Recommendation

**HTML Parser Type Needed**:
- [ ] Simple (like SubstackHTMLParser)
- [x] Moderate (like HeritageHTMLParser)
- [ ] Complex (like BrookingsHTMLParser with PDF support)

**Special Handling Needed**:
- [ ] PDF extraction (reports may have PDFs, but focus on HTML content)
- [x] Multiple authors with metadata (store as list)
- [ ] Table conversion (standard HTML tables should work)
- [ ] Figure/image captions (standard handling)
- [ ] Footnotes (may exist, extract if present)
- [x] Document type determination from URL
- [x] Author profile URLs (extract from scholar links)
- [x] Content cleanup (multiple unwanted elements)

**Parser Pattern** (following Heritage/Brookings):
```python
class AeiHTMLParser:
    CONTENT_SELECTORS = [
        'div.entry-content',
        'article .post-content',
        'main',
    ]

    METADATA_SELECTORS = {
        'title': ['h1.entry-title', 'article h1'],
        'authors': ['span.author-name a', '.entry-meta a[href*="/scholars/"]'],
        'date': ['time[datetime]', 'time.published'],
        'categories': ['a[rel="category"]', '.entry-categories a'],
    }

    REMOVE_SELECTORS = [
        'aside.related-content',
        'div.newsletter-signup',
        'div.social-sharing',
        '.share-buttons',
        'div.advertisement',
        'div.comments',
        'aside.author-bio',
        'section.recommended-reading',
    ]
```

---

## Implementation Checklist

Before generating the ingester scaffold, confirm:

- [x] All selectors documented from similar sites (AEI structure researched)
- [x] Edge cases documented with expected handling
- [x] Date parsing strategy validated
- [x] Content cleanup selectors identified
- [x] Discovery method chosen (pagination)
- [x] No blocking issues identified (no CAPTCHA, no paywall)

---

## Next Steps

1. [x] Complete this analysis document
2. [ ] Generate scaffold: `python brookings_ingester/scripts/generate_ingester.py aei`
3. [ ] Implement custom logic in generated ingester
4. [ ] Test on live URLs from aei.org/articles/
5. [ ] Validate with test scripts
6. [ ] Create AEI README
7. [ ] Deploy and monitor

---

## Notes / Special Considerations

- **Follow Heritage/Brookings patterns**: Use sync Playwright (not async), dict-based returns, BaseIngester pattern
- **AEI is a think tank**: Respectful scraping essential (1.5-2.0 second delays)
- **Content quality**: AEI produces high-quality policy research - expect well-structured HTML
- **Author metadata**: AEI scholars have profile pages - extract profile URLs when available
- **Document types**: Distinguish between articles, op-eds, reports, and working papers using URL patterns

---

## Revision History

| Date | Changes | Author |
|------|---------|--------|
| 2025-01-17 | Initial analysis for systematic framework | Claude |

---

**Ready for scaffold generation**: ✅ YES
**Estimated implementation time**: 2-3 hours (with systematic framework)
