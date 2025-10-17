# Policy Library Sources

This document tracks all content sources integrated into the Policy Library system.

---

## Heritage Foundation

- **Source Code**: `HERITAGE`
- **URL**: https://www.heritage.org
- **Content Type**: Policy research, commentary, reports, backgrounders, testimony
- **Status**: ✅ Active / Production Ready
- **Update Frequency**: Daily (7:00 AM ET)
- **Avg Articles/Day**: 8-15
- **Success Rate**: 96%+
- **Last Verified**: 2025-01-17
- **Owner**: Policy Library Team
- **Notes**:
  - Uses sitemap-based discovery (efficient, date-filterable)
  - Rich author metadata (name, title, affiliation, profile URL, Twitter)
  - Requires Playwright for JS-rendered content
  - Multiple content types: Commentary, Reports, Backgrounders, Issue Briefs, Legal Memoranda, Testimony
  - Special handling for author bio signatures and "min read" date quirks

**Documentation**:
- Analysis: `brookings_ingester/docs/sources/heritage_analysis.md`
- README: `brookings_ingester/docs/sources/heritage_README.md`
- Code: `brookings_ingester/ingesters/heritage.py`
- Parser: `brookings_ingester/ingesters/utils/heritage_parser.py`
- Tests: `tests/test_heritage_ingester.py`

---

## Brookings Institution

- **Source Code**: `BROOKINGS`
- **URL**: https://www.brookings.edu
- **Content Type**: Policy research, analysis, commentary
- **Status**: ✅ Active
- **Update Frequency**: Daily
- **Avg Articles/Day**: 10-20
- **Success Rate**: 95%+
- **Last Verified**: 2025-01-17
- **Owner**: Policy Library Team
- **Notes**:
  - Uses WordPress API for discovery with sitemap fallback
  - Requires Playwright for Cloudflare bypass
  - PDF extraction support for research papers

**Documentation**:
- Code: `brookings_ingester/ingesters/brookings.py`
- Parser: `brookings_ingester/ingesters/utils/brookings_parser.py`

---

## Source Status Legend

- ✅ **Active**: Production-ready, automated updates running
- 🚧 **In Progress**: Under development or testing
- ⏸️ **Paused**: Temporarily disabled (site issues, maintenance)
- ❌ **Deprecated**: No longer maintained or needed
- 📝 **Planned**: Identified for future addition

---

## Adding New Sources

See the comprehensive playbook: `brookings_ingester/docs/adding_new_source.md`

**Quick checklist**:
1. Create analysis document from template
2. Generate scaffold with `generate_ingester.py`
3. Implement discovery, fetch, parse methods
4. Test with `test_single_url.py` and `test_ingester.py`
5. Create README and tests
6. Add entry to this SOURCES.md file
7. Deploy and monitor

**Time estimate**: 3-6 hours per source (with systematic framework)

---

## Systematic Framework

The Policy Library uses a **systematic crawler development framework** to ensure:
- Consistent quality across all sources
- Repeatable, documented processes
- Easy maintenance and troubleshooting
- Fast onboarding for new sources

**Framework components**:
- `docs/source_analysis_template.md` - Reconnaissance template
- `docs/adding_new_source.md` - Step-by-step playbook
- `docs/ingester_qa_checklist.md` - Quality gates
- `scripts/generate_ingester.py` - Scaffold generator
- `scripts/test_single_url.py` - Quick testing tool
- `scripts/save_html_fixture.py` - Fixture creation
- `scripts/test_ingester.py` - Full pipeline testing

---

## Source Quality Standards

All sources must meet these criteria before production deployment:

### Code Quality
- ✅ Follows `BaseIngester` pattern
- ✅ Implements all required methods: `discover()`, `fetch()`, `parse()`
- ✅ Error handling for network issues and missing elements
- ✅ Logging implemented
- ✅ Rate limiting configured appropriately
- ✅ No hardcoded credentials

### Functionality
- ✅ >95% success rate on 50+ test articles
- ✅ All required fields extracting correctly (title, content, date)
- ✅ Content is clean (no HTML tags, ads, or junk)
- ✅ Handles edge cases gracefully (no authors, multiple authors, etc.)

### Testing
- ✅ Unit tests for parser methods
- ✅ Integration tests with HTML fixtures
- ✅ Smoke tests with live URLs
- ✅ All tests passing

### Documentation
- ✅ Source analysis document complete
- ✅ Source README created with selectors, known issues, troubleshooting
- ✅ SOURCES.md updated with new entry
- ✅ Code comments explain non-obvious logic

---

## Monitoring & Maintenance

### Weekly Checks
- Monitor `ingestion_logs` table for errors
- Check success rates (should be >95%)
- Review error patterns

### Monthly Spot Checks
- Validate 10 random articles for content quality
- Verify author extraction working
- Check date parsing accuracy

### Quarterly Reviews
- Full regression testing with HTML fixtures
- Update selectors if site redesigns detected
- Performance review (speed, memory)
- Documentation updates

---

**Last Updated**: 2025-01-17
**Next Review**: 2025-02-17
