# Brookings HTML Structure Patterns Analysis

## Documents Analyzed
- **Total documents**: 20
- **Successfully parsed**: 11 (word count > 400)
- **404 pages**: 9 (all showed exactly 20 words, "Page not found | Brookings")

## Universal Structure Pattern

All successfully parsed Brookings articles follow this consistent pattern:

```html
<main>
  <section>          <!-- Header: 30-230 words -->
    Title, byline, date
  </section>

  <section>          <!-- Main content: 346-4,839 words ← TARGET -->
    <div class="byo-blocks -with-sidebars article-content ...">
      <aside class="sidebar sidebar-left"></aside>     <!-- Navigation -->
      <aside class="sidebar sidebar-right"></aside>    <!-- TOC -->

      <div class="byo-block -narrow wysiwyg-block wysiwyg">
        <p>Main content paragraphs...</p>
      </div>

      <div class="byo-block -narrow chapter-marker">
        Section heading
      </div>

      <div class="byo-block -narrow wysiwyg-block wysiwyg">
        <p>More content...</p>
      </div>

      <!-- More byo-blocks with various types -->

      <div class="byo-block -narrow authors">
        Author info
      </div>

      <div class="byo-block -narrow related-content">
        Related articles
      </div>
    </div>
  </section>

  <section>          <!-- Footer: 107-171 words -->
    Footer content
  </section>
</main>
```

## Content Selectors - Priority Order

### Primary Content Container
1. **`div.article-content`** - Main content wrapper (ALWAYS present)
   - Also has class `byo-blocks`
   - Contains 346-4,839 words
   - Word count: matches stored word count

### Secondary Selectors (fallback)
2. **`div.byo-blocks`** - Same as `div.article-content` (they're the same element)
3. **`main`** - Contains all 3 sections (includes header/footer noise)
4. **`article`** - Sometimes present, low word count

## Content Block Types (within article-content)

### Include in Content
| Class Pattern | Purpose | Word Count Range |
|--------------|---------|------------------|
| `byo-block -narrow wysiwyg-block wysiwyg` | Main text content | 49-4,501 words |
| `byo-block -narrow chapter-marker` | Section headings | 1-15 words |
| `byo-block -narrow section-title` | Section titles | 1 word |
| `byo-block -narrow embed-shareable` | Embedded content | 4-6 words |
| `byo-block -narrow image-block` | Image captions | 12 words |
| `byo-block -narrow video` | Video embeds | 0 words |

### Exclude from Content
| Class Pattern | Purpose | Should Remove |
|--------------|---------|---------------|
| `aside.sidebar-left` | Navigation | ✓ Yes |
| `aside.sidebar-right` | Table of contents | ✓ Yes |
| `byo-block authors` | Author biographies | ✓ Yes |
| `byo-block related-content` | Related articles | ✓ Yes |
| `byo-block footnotes` | Footnotes | Maybe keep |

## Word Count Analysis

### Paragraph Tags
- Found 30-122 `<p>` tags per article
- P tags contain 322-4,677 words
- P tags represent 95-98% of total content word count

### Comparison: Selector vs Stored
| Doc ID | Stored Words | article-content Words | main Words | Notes |
|--------|-------------|----------------------|-----------|-------|
| 3 | 44,139 | 2,665 | 2,972 | Stored includes ALL text? |
| 11 | 451 | 346 | 491 | Close match |
| 12 | 3,701 | 3,569 | 3,733 | Close match |
| 13 | 5,058 | 4,839 | 5,105 | Close match |
| 15 | 10,212 | 2,358 | 2,675 | Stored 4x higher? |

**Note**: Most documents match closely, but some have large discrepancies. This suggests the stored word count might include PDF text or other sources.

## Author Extraction Patterns

### Author Metadata Locations
1. **`div.authors`** or **`div.byo-block.authors`** - Primary location
   - Contains author names and titles
   - Format: Name + Title + Affiliation

2. **`div[class*="author"]`** - Broader selector
   - Includes "Follow the authors" sections
   - May include social media links

### Example Author HTML
```html
<div class="byo-block -narrow authors sm:overflow-hidden py-5">
  Author Name
  Title
  Affiliation
</div>
```

## Document Type Variations

All analyzed documents are type "Article". No variations observed yet.

Potential other types to test:
- Research papers
- Reports
- Books
- Blog posts
- Collections

## Recommendations for Parser

### 1. Primary Selector Strategy
```python
CONTENT_SELECTORS = [
    'div.article-content',    # Most reliable, contains clean content
    'div.byo-blocks',         # Same as above
    'main',                   # Fallback (includes header/footer)
]
```

### 2. Removal Strategy
```python
REMOVE_SELECTORS = [
    'aside.sidebar-left',
    'aside.sidebar-right',
    'div.byo-block.authors',
    'div.byo-block.related-content',
    'nav',
    'header',
    'footer',
    '.advertisement',
    'script',
    'style'
]
```

### 3. Content Extraction Strategy

**Option A: Take all byo-blocks** (Current approach)
- Select `div.article-content`
- Remove sidebars and non-content blocks
- Extract all remaining text

**Option B: Select specific content blocks** (More precise)
- Select only `div.byo-block.wysiwyg-block` elements
- Combine all text from these blocks
- Cleaner content, but might miss some structural elements

**Recommendation**: Use Option A (current approach) but improve the removal list.

### 4. Author Extraction
```python
AUTHOR_SELECTORS = [
    'div.byo-block.authors',
    'div.authors',
    '[data-component="authors"]'
]
```

## Known Issues

1. **Word count discrepancies**: Some documents show stored word count much higher than HTML word count. Investigate if this includes PDF text.

2. **404 pages**: All 404 pages return exactly 20 words in `main`, 67 words in `body`. Parser should detect and reject these.

3. **Author extraction**: Currently returning 0 authors. Need to implement author parsing logic.

## Next Steps

1. ✓ Identify structural patterns (DONE)
2. Update `REMOVE_SELECTORS` to exclude sidebars and metadata
3. Implement author extraction from `div.authors`
4. Add 404 page detection (reject if title contains "Page not found")
5. Test with different document types (reports, papers, etc.)
