# Source Analysis: [WEBSITE NAME]

**Analyst**: [Your Name]
**Date**: [YYYY-MM-DD]
**Status**: [Draft/Complete/Verified]

---

## Basic Information

- **Source Name**: [lowercase identifier, e.g., 'aei', 'heritage']
- **Full Name**: [American Enterprise Institute]
- **Base URL**: [https://www.example.org]
- **Target Section**: [/research/, /articles/, etc.]
- **Content Type**: [Policy research, Commentary, Reports, etc.]
- **Update Frequency**: [Daily/Weekly/Monthly]
- **Estimated Articles per Day**: [Number]

---

## Technical Reconnaissance

### Article Discovery

**How are articles listed?**
- [ ] Standard pagination (prev/next links)
- [ ] Numbered pagination (`page=1`, `page=2`)
- [ ] Infinite scroll
- [ ] Load more button (JavaScript)
- [ ] RSS/API feed available
- [ ] Sitemap.xml
- [ ] Other: ___________

**Article Listing URL Pattern**:
```
Example: https://example.com/articles/
Pagination: https://example.com/articles/page/2/
```

**Selectors for Article Links**:
- **CSS Selector**: `article.post-item h3 a`
- **XPath** (if needed):
- **JavaScript rendering required?**: Yes / No
- **Notes**:

---

### Article Page Structure

**Technical Requirements**:
- **Requires JavaScript Rendering?**: Yes / No
- **Authentication Required?**: Yes / No / Partial (paywalled content)
- **Rate Limiting Observed?**: Yes / No (if yes, describe)
- **Robots.txt Restrictions**: [Check /robots.txt - permissive/restrictive]
- **CAPTCHA or Bot Detection?**: Yes / No

---

### Content Selectors

Document the CSS/XPath selectors for each field:

| Field | Primary Selector | Fallback Selector | Notes |
|-------|-----------------|-------------------|-------|
| **Title** | `h1.entry-title` | `article h1` | Always first h1 |
| **Content** | `div.entry-content` | `article .post-content` | Main text container |
| **Author** | `span.author-name a` | `a[rel="author"]` | May be multiple authors |
| **Date** | `time[datetime]` | `span.publish-date` | Check format below |
| **Categories/Tags** | `a.tag` | `a[rel="category"]` | Optional |
| **Summary/Excerpt** | `.article-summary` | `meta[name="description"]` | Optional |

---

### Content Cleanup Needs

**Elements to remove** (ads, navigation, junk content):
- [ ] Ads: `div.advertisement`, `.ad-container`
- [ ] Related articles: `div.related-posts`, `.related-content`
- [ ] Share buttons: `div.social-share`, `.share-buttons`
- [ ] Comments section: `div.comments`, `section#comments`
- [ ] Newsletter signup: `form.newsletter`, `.newsletter-signup`
- [ ] Author bio boxes: `aside.author-bio`
- [ ] Navigation/breadcrumbs: `nav`, `.breadcrumb`
- [ ] Other: ___________

---

### Date Format

**Example raw date strings found on the site**:
```
1. "January 15, 2025 at 10:30 AM EST"
2. "2025-01-15T10:30:00-05:00"
3. "Jan 15, 2025"
```

**datetime attribute** (if available): `time[datetime]` contains ISO 8601?
- [ ] Yes (preferred - easy to parse)
- [ ] No (must parse display text)

**Format pattern** (for dateparser): `%B %d, %Y` or `%Y-%m-%d`

**Timezone**: EST / UTC / PST / Other: ___________

**Relative dates used?**: ("2 hours ago", "Yesterday")
- [ ] Yes (if so, how to handle?)
- [ ] No

---

### Edge Cases Observed

Check all that apply and add notes:

- [ ] **Articles without authors** (institutional pieces)
  - How to handle: [Use organization name / Leave blank]

- [ ] **Multiple authors**
  - How to handle: [Join with commas / Store separately]

- [ ] **Sponsored/promotional content**
  - How to identify: [URL pattern, class name, label]
  - How to handle: [Skip / Mark in metadata]

- [ ] **Video-only articles** (no text content)
  - How to handle: [Skip / Extract transcript if available]

- [ ] **Multi-page articles** (paginated content)
  - Pagination pattern:
  - How to handle: [Follow pagination / Single page view]

- [ ] **Slideshows**
  - How to handle: [Skip / Extract captions]

- [ ] **Paywalled content**
  - Paywall type: [Hard / Soft / Metered]
  - How to handle: [Skip / Extract preview]

- [ ] **Different content types** (articles, reports, op-eds)
  - How to distinguish: [URL pattern / Metadata / Tags]

- [ ] **Embedded media** (images, charts, videos)
  - How to handle: [Extract alt text / Describe / Skip]

- [ ] **Special characters in titles** (em dashes, quotes, unicode)
  - Observed:
  - Handling needed: [Yes / No]

- [ ] **Old vs new article formats** (site redesigns)
  - Cutoff date:
  - Different selectors needed: [Yes / No]

- [ ] **Other**:

---

### Sample URLs for Testing

Provide **10+ sample article URLs** representing different:
- Content types (articles, reports, op-eds)
- Date ranges (recent, 1 year old, 2+ years old)
- Authors (single, multiple, institutional)
- Special cases (edge cases identified above)

```
1. https://www.example.org/articles/sample-article-1/
2. https://www.example.org/research/sample-report-1/
3. https://www.example.org/op-eds/sample-opinion-1/
4. https://www.example.org/articles/no-author-example/
5. https://www.example.org/articles/multiple-authors-example/
6. https://www.example.org/articles/old-format-example/ (pre-2020)
7. https://www.example.org/articles/recent-article/
8. https://www.example.org/reports/pdf-available/
9. https://www.example.org/articles/sponsored-content/ (if applicable)
10. https://www.example.org/articles/special-characters-title/
```

---

### Initial Scraping Test

**Manual browser DevTools test results**:

- **Can access articles without JavaScript?**
  - [ ] Yes (use requests)
  - [ ] No (must use Playwright)
  - [ ] Partial (some content loads without JS)

- **Selectors work across different articles?**
  - [ ] Yes (consistent)
  - [ ] Mostly (minor variations)
  - [ ] No (highly variable - need robust fallbacks)

- **CAPTCHAs or bot detection?**
  - [ ] None observed
  - [ ] Cloudflare challenge (Playwright can handle)
  - [ ] reCAPTCHA (problematic)

- **Rate limiting observed?**
  - [ ] None
  - [ ] Yes (describe limits and recommended delay)

- **Network performance**:
  - Average page load time: ___ seconds
  - Page size: ___ KB
  - Requires `wait_until='networkidle'`?: Yes / No

---

## Discovery Strategy Recommendation

Based on analysis above, recommend the best discovery method:

**Recommended Approach**: [Sitemap / Pagination / API / RSS]

**Reasoning**:

**Implementation Notes**:
- Discovery method: [Describe approach]
- Pagination strategy: [Describe if applicable]
- URL filtering: [Patterns to include/exclude]
- Date filtering: [How to filter by date]

---

## Parsing Strategy Recommendation

**HTML Parser Type Needed**:
- [ ] Simple (like SubstackHTMLParser - minimal cleanup)
- [ ] Moderate (like HeritageHTMLParser - some edge cases)
- [ ] Complex (like BrookingsHTMLParser - many edge cases, PDF support)

**Special Handling Needed**:
- [ ] PDF extraction
- [ ] Multiple authors with metadata
- [ ] Table conversion
- [ ] Figure/image captions
- [ ] Footnotes
- [ ] Other: ___________

---

## Implementation Checklist

Before generating the ingester scaffold, confirm:

- [ ] All selectors tested on **5+ sample articles**
- [ ] Edge cases documented with sample URLs
- [ ] Date parsing strategy validated
- [ ] Content cleanup selectors identified
- [ ] Discovery method tested (can retrieve article URLs)
- [ ] No blocking issues (CAPTCHAs, hard paywalls, etc.)

---

## Next Steps

1. [ ] Complete this analysis document
2. [ ] Run scaffold generator: `python scripts/generate_ingester.py [source_name]`
3. [ ] Implement custom logic in generated ingester
4. [ ] Test on sample URLs
5. [ ] Deploy to staging

---

## Notes / Special Considerations

[Any additional notes, quirks, or considerations for this source]

---

## Revision History

| Date | Changes | Author |
|------|---------|--------|
| YYYY-MM-DD | Initial analysis | [Name] |
| YYYY-MM-DD | Updated selectors after site redesign | [Name] |
