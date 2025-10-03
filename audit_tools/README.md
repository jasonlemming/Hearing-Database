# Committee Audit Tools

This directory contains comprehensive audit tools for the Congressional Hearing Database `/committees` tab. The tools validate database integrity, analyze template consistency, and test HTTP functionality.

## Quick Start

```bash
# Run complete audit
python3 audit_tools/comprehensive_audit.py

# Or run individual components
python3 audit_tools/simple_validator.py      # Database validation
python3 audit_tools/style_analyzer.py        # Template analysis
python3 audit_tools/http_tester.py          # HTTP testing
```

## Tools Overview

### 🔍 `simple_validator.py`
**Purpose**: Database integrity validation
**Checks**:
- Committee hierarchy relationships
- Hearing association accuracy
- System code patterns and uniqueness
- Chamber-type combination validity
- Orphaned references and circular dependencies

**Usage**:
```bash
python3 simple_validator.py
```

### 🎨 `style_analyzer.py`
**Purpose**: Template styling consistency
**Checks**:
- Bootstrap class usage patterns
- FontAwesome icon consistency
- HTML structure compliance
- Accessibility (ARIA) attributes
- Responsive design patterns
- CSS class usage

**Usage**:
```bash
python3 style_analyzer.py
```

### 🌐 `http_tester.py`
**Purpose**: HTTP interface testing
**Checks**:
- Server response codes
- HTML structure validation
- Filter functionality
- Navigation links
- Data consistency between database and UI
- Committee detail page integrity

**Usage**:
```bash
python3 http_tester.py
```

**Prerequisites**: Requires BeautifulSoup4
```bash
pip3 install beautifulsoup4
```

### 🚀 `comprehensive_audit.py`
**Purpose**: Orchestrates all tools and generates unified report
**Features**:
- Runs all audit phases automatically
- Generates priority matrix based on severity/effort
- Creates executive summary with recommendations
- Provides database statistics and context

**Usage**:
```bash
python3 comprehensive_audit.py
```

## Configuration

### Environment Variables
Create `.env` file in project root:
```bash
API_KEY=dummy_key_for_audit
DATABASE_PATH=database_audit.db
LOG_LEVEL=INFO
```

### Database Safety
All tools use `database_audit.db` (copy of production database) to ensure safety:
```bash
cp database.db database_audit.db
```

## Output Files

Reports are generated in `audit_tools/reports/`:
- `comprehensive_audit_report_YYYYMMDD_HHMMSS.md` - Unified report
- `validation_report_YYYYMMDD_HHMMSS.md` - Database validation
- `style_analysis_report_YYYYMMDD_HHMMSS.md` - Style analysis
- `http_test_report_YYYYMMDD_HHMMSS.md` - HTTP testing

## Issue Classification

### Severity Levels
- **HIGH**: Data corruption, broken functionality, security issues
- **MEDIUM**: UX problems, accessibility issues, performance concerns
- **LOW**: Minor styling inconsistencies, cosmetic improvements

### Effort Estimation
- **Quick**: Template tweaks, CSS adjustments (< 2 hours)
- **Moderate**: Logic changes, new validation rules (2-8 hours)
- **Complex**: Schema changes, major refactoring (> 8 hours)

### Priority Matrix
Issues are classified into actionable categories:
- 🔴 **Critical/Quick**: High severity, easy fix (immediate action)
- 🟠 **High/Moderate**: High severity, moderate effort (next sprint)
- 🟡 **Medium/Quick**: Medium severity, easy fix (next sprint)
- 🟡 **Medium/Moderate**: Medium severity, moderate effort (backlog)
- 🟢 **Low Priority**: Low severity, any effort (optional)

## Integration with Development Workflow

### Pre-commit Hook (Recommended)
```bash
# Add to .git/hooks/pre-commit
#!/bin/bash
python3 audit_tools/simple_validator.py
exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo "❌ Database validation failed. Commit aborted."
    exit 1
fi
```

### CI/CD Integration
Add to GitHub Actions or similar:
```yaml
- name: Run Committee Audit
  run: |
    cp database.db database_audit.db
    python3 audit_tools/comprehensive_audit.py
    # Parse results and fail if critical issues found
```

### Regular Monitoring
Schedule weekly audits to catch issues early:
```bash
# Add to crontab
0 2 * * 1 cd /path/to/project && python3 audit_tools/comprehensive_audit.py
```

## Extending the Tools

### Adding New Validators
1. Create new validation method in `SimpleCommitteeValidator`
2. Add call to `run_all_validations()`
3. Update issue categories and severity levels

### Custom Style Checks
1. Add new analysis method to `TemplateStyleAnalyzer`
2. Define new issue categories as needed
3. Update comparison logic for template patterns

### Additional HTTP Tests
1. Extend `CommitteeHTTPTester` with new test methods
2. Add new page types or functionality checks
3. Include performance timing measurements

## Troubleshooting

### Common Issues

**Server startup fails**:
```bash
# Check .env file exists with API_KEY
echo "API_KEY=dummy_key_for_audit" > .env
```

**Import errors**:
```bash
# Install dependencies
pip3 install -r requirements.txt
pip3 install beautifulsoup4
```

**Permission denied**:
```bash
# Make scripts executable
chmod +x audit_tools/*.py
```

**Database not found**:
```bash
# Ensure audit database exists
cp database.db database_audit.db
```

### Debug Mode
Add debugging to any tool:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Dependencies

**Required**:
- sqlite3 (built-in)
- requests
- flask
- pathlib (built-in)

**Optional**:
- beautifulsoup4 (for HTML parsing)
- lxml (for better HTML performance)

## Contributing

When adding new checks:
1. Follow existing pattern of severity classification
2. Include specific line numbers when possible
3. Provide actionable fix recommendations
4. Add tests for new validation logic
5. Update documentation

## Results Interpretation

### Database Validation
- ✅ **0 issues**: Database is in excellent condition
- ⚠️ **1-5 issues**: Minor data inconsistencies, monitor closely
- 🚨 **>5 issues**: Significant problems requiring immediate attention

### Style Analysis
- Accessibility issues should be prioritized for user experience
- Bootstrap inconsistencies may indicate template maintenance needs
- Icon usage patterns help maintain visual consistency

### HTTP Testing
- Server errors indicate environment configuration issues
- HTML structure problems suggest template rendering issues
- Data mismatches reveal synchronization problems

## Support

For questions or issues with the audit tools:
1. Check this README for common solutions
2. Review the comprehensive audit report for context
3. Examine individual phase reports for detailed findings
4. Use debug mode for troubleshooting specific tools

---

*Created as part of the Congressional Hearing Database quality assurance initiative*