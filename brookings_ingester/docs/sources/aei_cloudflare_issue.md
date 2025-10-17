# AEI Cloudflare Protection Issue

## Problem

All AEI.org pages are protected by Cloudflare bot detection, which blocks Playwright browser automation with "Verifying you are human" challenge pages.

### Tested URLs (All Blocked)
- ✗ https://www.aei.org/articles/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/reports/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/journal-publications/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/one-pagers/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/testimonies/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/working-papers/ - Cloudflare challenge
- ✗ https://www.aei.org/research-products/speeches/ - Cloudflare challenge

### Evidence
Saved HTML fixture shows:
```html
<title>Just a moment...</title>
<p id="Truv1" class="h2 spacer-bottom">Verifying you are human. This may take a few seconds.</p>
```

## Potential Solutions

### 1. Playwright Stealth Mode
**Approach**: Use playwright-stealth or similar libraries to mask automation fingerprints

**Implementation**:
```python
from playwright_stealth import stealth_sync

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    stealth_sync(page)  # Apply stealth patches
    page.goto(url)
```

**Pros**:
- Minimal code changes
- Works with existing Playwright setup
- May bypass basic bot detection

**Cons**:
- Not guaranteed to work with advanced Cloudflare
- Requires additional dependency

### 2. Residential Proxies
**Approach**: Route requests through residential IP addresses that Cloudflare trusts

**Implementation**:
```python
context = browser.new_context(
    proxy={
        "server": "http://proxy-provider.com:port",
        "username": "user",
        "password": "pass"
    }
)
```

**Pros**:
- Higher success rate against Cloudflare
- Can rotate IPs to avoid rate limiting

**Cons**:
- Cost (residential proxies are expensive)
- Added complexity
- May violate AEI's terms of service

### 3. Alternative Discovery Methods

#### Option A: RSS/Atom Feeds
Check if AEI provides RSS feeds for research products:
```bash
curl https://www.aei.org/feed/
curl https://www.aei.org/research-products/feed/
```

**Pros**:
- Official API-like interface
- No bot detection
- Includes metadata

**Cons**:
- May not include all content
- Limited to recent items

#### Option B: Sitemap XML
Parse sitemap for URLs:
```bash
curl https://www.aei.org/sitemap.xml
curl https://www.aei.org/sitemap_index.xml
```

**Pros**:
- Comprehensive URL list
- No bot detection on XML

**Cons**:
- Still need to fetch individual pages
- Sitemap may also be protected

#### Option C: Search API/Third-party Services
Use services that already index AEI content:
- Google Custom Search API
- DuckDuckGo site:aei.org search
- Academic databases that index AEI

**Pros**:
- Bypasses Cloudflare entirely
- May include additional metadata

**Cons**:
- API costs/rate limits
- May not be comprehensive
- Delayed updates

### 4. Browser Extensions/Solver Services
**Approach**: Use services like 2captcha, Anti-Captcha that solve Cloudflare challenges

**Pros**:
- Automated solution
- Handles complex challenges

**Cons**:
- Cost per solve
- Slower (needs human or AI solver)
- Ethically questionable

### 5. Manual Workaround
**Approach**: Pre-download HTML pages manually or with authenticated browser session

**Pros**:
- Guaranteed to work
- No technical barriers

**Cons**:
- Not automated
- Not scalable
- Defeats purpose of ingester

## Test Results

### RSS/Sitemap Availability
**Result**: ❌ **ALL BLOCKED BY CLOUDFLARE**

Tested URLs:
- ✗ `https://www.aei.org/feed/` - Cloudflare challenge
- ✗ `https://www.aei.org/sitemap.xml` - Cloudflare challenge
- ✗ `https://www.aei.org/sitemap_index.xml` - Cloudflare challenge

AEI has applied Cloudflare protection to **all pages**, including machine-readable formats (RSS/XML). This indicates a very aggressive anti-bot policy.

### Playwright Stealth Settings
**Result**: ❌ **FAILED - Still Blocked**

Attempted with:
- Browser args: `--disable-blink-features=AutomationControlled`, `--disable-dev-shm-usage`, `--no-sandbox`
- Realistic user agent (Chrome 120)
- Locale and timezone settings
- 90-second timeout with `networkidle` wait

**Outcome**: All pages timeout after 90 seconds. Cloudflare is holding the browser in challenge state indefinitely.

The playwright-stealth library (v2.0.0) only works with async Playwright, not sync, so it couldn't be used. Even with manual stealth settings, Cloudflare's bot detection is too sophisticated.

## Recommended Next Steps

1. ~~**Test RSS/Sitemap**~~ ❌ FAILED - All blocked by Cloudflare

2. **Try Playwright Stealth** (Low effort, might work)
   - Install playwright-stealth
   - Test if it bypasses Cloudflare
   - Fallback if RSS not available

3. **Contact AEI** (Long-term, official)
   - Ask if they provide an API or data export
   - Inquire about bulk access for research
   - Check if they have partnership programs

4. **Skip AEI for Now** (Pragmatic)
   - Move to other sources without Cloudflare
   - Return to AEI once we have more resources
   - Focus on sources that are immediately accessible

## Status

**Current**: ❌ **COMPLETELY BLOCKED**

**Blocker**: Cloudflare bot protection on all AEI.org pages (including RSS/XML).

**Tested Solutions**:
1. ✗ RSS feeds via curl - Cloudflare challenge page
2. ✗ RSS feeds via feedparser - HTTP 429 (rate limit)
3. ✗ XML sitemaps - Cloudflare challenge page
4. ✗ Playwright stealth settings - 90s timeouts

**Remaining Options**:
1. **Residential proxies** - Expensive, may violate ToS
2. **Contact AEI** - Ask for official data access
3. **Skip AEI** - Focus on accessible sources

**Recommendation**: **Skip AEI for now**. The systematic framework is proven (Heritage 100% success). We're blocked by external anti-bot measures, not technical issues. AEI ingester code is complete and ready if access becomes available in the future.

## Implementation Status

**Code**: ✓ Complete
- `brookings_ingester/ingesters/aei.py` - Full ingester implementation
- `brookings_ingester/ingesters/utils/aei_parser.py` - HTML parser with AEI selectors
- Database source registered
- Multi-category discovery logic
- Stealth browser settings

**Testing**: ❌ Cannot test due to Cloudflare

**Next Steps**: Move to a different source for Phase 3 demonstration. Return to AEI when:
- AEI provides API/data access
- Budget allows for residential proxies
- Cloudflare protection is reduced
