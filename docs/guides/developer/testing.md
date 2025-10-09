# Testing Guide

Complete guide to testing the Congressional Hearing Database.

## Table of Contents

1. [Overview](#overview)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Unit Tests](#writing-unit-tests)
5. [Writing Integration Tests](#writing-integration-tests)
6. [Test Coverage](#test-coverage)
7. [Testing Best Practices](#testing-best-practices)
8. [Common Testing Scenarios](#common-testing-scenarios)
9. [Continuous Integration](#continuous-integration)

---

## Overview

The Congressional Hearing Database uses **pytest** as its primary testing framework with **unittest** compatibility for test organization.

**Testing Philosophy**:
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Security Tests**: Validate input sanitization and access controls
- **End-to-End Tests**: Test complete workflows

**Current Test Coverage**:
```
tests/
├── documents/              # Document parsing and import tests
│   ├── test_document_fetcher.py (8 tests)
│   └── test_document_import.py (3 tests)
└── security/              # Security validation tests
    └── test_input_validation.py (tests)
```

**Test Statistics**:
- **Total Tests**: 11+
- **Pass Rate**: 100%
- **Coverage**: Core functionality covered

---

## Test Structure

### Directory Organization

```
tests/
├── __init__.py                          # Package initialization
├── conftest.py                          # Pytest fixtures (shared)
│
├── documents/                           # Document-related tests
│   ├── __init__.py
│   ├── test_document_fetcher.py        # DocumentFetcher unit tests
│   └── test_document_import.py         # Document import integration tests
│
├── security/                            # Security tests
│   ├── __init__.py
│   └── test_input_validation.py        # Input validation tests
│
├── parsers/                             # Parser tests (to be added)
│   ├── __init__.py
│   ├── test_hearing_parser.py
│   ├── test_committee_parser.py
│   └── test_witness_parser.py
│
├── fetchers/                            # Fetcher tests (to be added)
│   ├── __init__.py
│   ├── test_hearing_fetcher.py
│   └── test_committee_fetcher.py
│
├── database/                            # Database tests (to be added)
│   ├── __init__.py
│   └── test_database_manager.py
│
└── integration/                         # Integration tests (to be added)
    ├── __init__.py
    ├── test_full_import.py
    └── test_update_workflow.py
```

### Test File Naming

**Convention**: `test_<module_name>.py`

**Examples**:
- `test_document_fetcher.py` - Tests for `fetchers/document_fetcher.py`
- `test_hearing_parser.py` - Tests for `parsers/hearing_parser.py`
- `test_database_manager.py` - Tests for `database/manager.py`

### Test Class Naming

**Convention**: `Test<ClassName>` or `Test<Functionality>`

**Examples**:
```python
class TestDocumentFetcher(unittest.TestCase):
    """Test DocumentFetcher parsing methods"""

class TestHearingParser(unittest.TestCase):
    """Test HearingParser validation and transformation"""

class TestDatabaseManager(unittest.TestCase):
    """Test DatabaseManager CRUD operations"""
```

### Test Method Naming

**Convention**: `test_<what_is_being_tested>_<expected_result>`

**Examples**:
```python
def test_extract_transcripts_from_list():
    """Should extract transcripts from list format"""

def test_parse_hearing_with_missing_title_raises_validation_error():
    """Should raise ValidationError when title missing"""

def test_upsert_hearing_updates_existing_record():
    """Should update existing hearing instead of inserting duplicate"""
```

---

## Running Tests

### Quick Start

```bash
# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run all tests with output capture disabled (see print statements)
pytest -v -s

# Run tests and show coverage
pytest --cov=. --cov-report=html
```

### Running Specific Tests

```bash
# Run tests in specific directory
pytest tests/documents/

# Run specific test file
pytest tests/documents/test_document_fetcher.py

# Run specific test class
pytest tests/documents/test_document_fetcher.py::TestDocumentFetcher

# Run specific test method
pytest tests/documents/test_document_fetcher.py::TestDocumentFetcher::test_extract_transcripts_from_list

# Run tests matching pattern
pytest -k "document"  # Runs all tests with "document" in name

# Run tests matching multiple patterns
pytest -k "document or parser"
```

### Test Output Options

```bash
# Verbose output (show each test name)
pytest -v

# Very verbose output (show test docstrings)
pytest -vv

# Show print output
pytest -s

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x

# Show summary of failures
pytest -ra

# Quiet mode (minimal output)
pytest -q
```

### Running Tests with Coverage

```bash
# Basic coverage report
pytest --cov=.

# Coverage report with missing lines
pytest --cov=. --cov-report=term-missing

# HTML coverage report
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser

# XML coverage report (for CI)
pytest --cov=. --cov-report=xml

# Coverage for specific module
pytest --cov=fetchers tests/fetchers/

# Fail if coverage below threshold
pytest --cov=. --cov-fail-under=80
```

### Test Markers

```python
# Mark tests with categories
@pytest.mark.unit
def test_parser_unit():
    pass

@pytest.mark.integration
def test_full_workflow():
    pass

@pytest.mark.slow
def test_large_import():
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_future_feature():
    pass

@pytest.mark.skipif(sys.version_info < (3, 9), reason="Requires Python 3.9+")
def test_python39_feature():
    pass
```

**Running marked tests**:
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run all except slow tests
pytest -m "not slow"

# Run unit OR integration tests
pytest -m "unit or integration"
```

---

## Writing Unit Tests

### Basic Test Structure

```python
#!/usr/bin/env python3
"""
Unit tests for HearingParser
"""
import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from parsers.hearing_parser import HearingParser
from parsers.models import HearingModel
from pydantic import ValidationError


class TestHearingParser(unittest.TestCase):
    """Test HearingParser validation and transformation"""

    def setUp(self):
        """Set up test fixtures (run before each test)"""
        self.parser = HearingParser()

    def tearDown(self):
        """Clean up after each test (run after each test)"""
        pass  # Usually not needed

    def test_parse_valid_hearing_data(self):
        """Should successfully parse valid hearing data"""
        # Arrange (Given)
        api_data = {
            'eventId': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Hearing on Budget',
            'date': '2025-10-15T10:00:00Z'
        }

        # Act (When)
        result = self.parser.parse(api_data)

        # Assert (Then)
        self.assertIsInstance(result, HearingModel)
        self.assertEqual(result.event_id, 'LC12345')
        self.assertEqual(result.congress, 119)
        self.assertEqual(result.chamber, 'House')
        self.assertEqual(result.title, 'Hearing on Budget')

    def test_parse_missing_required_field_raises_error(self):
        """Should raise ValidationError when required field missing"""
        # Arrange
        incomplete_data = {
            'eventId': 'LC12345',
            # Missing congress (required)
            'chamber': 'House'
        }

        # Act & Assert
        with self.assertRaises(ValidationError):
            self.parser.parse(incomplete_data)

    def test_parse_invalid_chamber_raises_error(self):
        """Should raise ValidationError for invalid chamber"""
        # Arrange
        invalid_data = {
            'eventId': 'LC12345',
            'congress': 119,
            'chamber': 'InvalidChamber',  # Not in [House, Senate, NoChamber]
            'title': 'Test'
        }

        # Act & Assert
        with self.assertRaises(ValidationError) as context:
            self.parser.parse(invalid_data)

        # Check error message
        self.assertIn('chamber', str(context.exception))


if __name__ == '__main__':
    unittest.main()
```

### Assertion Methods

**Equality Assertions**:
```python
self.assertEqual(actual, expected)
self.assertNotEqual(actual, expected)
self.assertTrue(condition)
self.assertFalse(condition)
self.assertIs(actual, expected)  # Identity (same object)
self.assertIsNot(actual, expected)
```

**Type and Membership Assertions**:
```python
self.assertIsInstance(obj, ClassName)
self.assertNotIsInstance(obj, ClassName)
self.assertIn(member, container)
self.assertNotIn(member, container)
```

**Numeric Assertions**:
```python
self.assertGreater(a, b)
self.assertGreaterEqual(a, b)
self.assertLess(a, b)
self.assertLessEqual(a, b)
self.assertAlmostEqual(a, b, places=7)  # Floating point comparison
```

**Exception Assertions**:
```python
with self.assertRaises(ValueError):
    function_that_raises()

with self.assertRaises(ValidationError) as context:
    parser.parse(bad_data)
self.assertIn('expected text', str(context.exception))
```

**Collection Assertions**:
```python
self.assertCountEqual(list1, list2)  # Same elements, any order
self.assertListEqual(list1, list2)   # Same elements, same order
self.assertDictEqual(dict1, dict2)
self.assertSetEqual(set1, set2)
```

### Test Fixtures

**Using setUp and tearDown**:
```python
class TestDatabaseOperations(unittest.TestCase):
    """Test database operations"""

    def setUp(self):
        """Create test database before each test"""
        self.db_path = '/tmp/test_database.db'
        self.db = DatabaseManager(self.db_path)
        self.db.initialize_schema()

    def tearDown(self):
        """Clean up test database after each test"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_insert_hearing(self):
        """Should insert hearing into database"""
        hearing_data = {
            'event_id': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Test Hearing'
        }

        hearing_id = self.db.upsert_hearing(hearing_data)
        self.assertIsNotNone(hearing_id)
        self.assertGreater(hearing_id, 0)
```

**Using pytest fixtures** (in `conftest.py`):
```python
# tests/conftest.py
import pytest
import tempfile
from database.manager import DatabaseManager

@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    db = DatabaseManager(db_path)
    db.initialize_schema()

    yield db  # Test runs here

    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)

# Use in tests
def test_database_operation(temp_db):
    """Test using fixture"""
    hearing_data = {'event_id': 'LC123', 'congress': 119, 'chamber': 'House', 'title': 'Test'}
    hearing_id = temp_db.upsert_hearing(hearing_data)
    assert hearing_id > 0
```

### Mocking External Dependencies

**Mocking API calls**:
```python
from unittest.mock import Mock, patch

class TestHearingFetcher(unittest.TestCase):
    """Test HearingFetcher with mocked API"""

    @patch('api.client.CongressAPIClient.get')
    def test_fetch_hearings_success(self, mock_get):
        """Should fetch hearings from API"""
        # Arrange
        mock_get.return_value = {
            'hearings': [
                {'eventId': 'LC123', 'title': 'Test Hearing 1'},
                {'eventId': 'LC456', 'title': 'Test Hearing 2'}
            ]
        }

        fetcher = HearingFetcher(CongressAPIClient())

        # Act
        hearings = fetcher.fetch_hearings_by_congress(119, 'house')

        # Assert
        self.assertEqual(len(hearings), 2)
        mock_get.assert_called_once()

    @patch('api.client.CongressAPIClient.get')
    def test_fetch_hearings_api_error(self, mock_get):
        """Should handle API errors gracefully"""
        # Arrange
        mock_get.side_effect = requests.exceptions.Timeout("API timeout")

        fetcher = HearingFetcher(CongressAPIClient())

        # Act & Assert
        with self.assertRaises(requests.exceptions.Timeout):
            fetcher.fetch_hearings_by_congress(119, 'house')
```

---

## Writing Integration Tests

### Database Integration Tests

```python
#!/usr/bin/env python3
"""
Integration tests for document import workflow
"""
import unittest
import tempfile
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from database.manager import DatabaseManager
from importers.orchestrator import ImportOrchestrator
from api.client import CongressAPIClient


class TestDocumentImport(unittest.TestCase):
    """Test full document import workflow"""

    def setUp(self):
        """Create temporary database"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = DatabaseManager(self.db_path)
        self.db.initialize_schema()

        self.api_client = CongressAPIClient()
        self.orchestrator = ImportOrchestrator(self.db, self.api_client)

    def tearDown(self):
        """Clean up temporary database"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_import_documents_for_hearing(self):
        """Should import all document types for a hearing"""
        # Arrange: Create test hearing
        hearing_data = {
            'event_id': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Test Hearing'
        }
        hearing_id = self.db.upsert_hearing(hearing_data)

        # Act: Import documents
        result = self.orchestrator.import_documents([hearing_id])

        # Assert: Verify documents imported
        transcripts = self.db.fetch_all(
            "SELECT * FROM hearing_transcripts WHERE hearing_id = ?",
            (hearing_id,)
        )
        # Check count (actual count depends on API data)
        self.assertIsInstance(transcripts, list)

        # Verify result metrics
        self.assertTrue(result['success'])
        self.assertIn('transcripts_imported', result)

    def test_import_with_invalid_hearing_id(self):
        """Should handle invalid hearing IDs gracefully"""
        # Arrange
        invalid_hearing_id = 99999

        # Act
        result = self.orchestrator.import_documents([invalid_hearing_id])

        # Assert
        self.assertIn('errors', result)
        self.assertGreater(len(result['errors']), 0)
```

### End-to-End Workflow Tests

```python
class TestUpdateWorkflow(unittest.TestCase):
    """Test complete update workflow"""

    def setUp(self):
        """Set up test database with baseline data"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()

        self.db = DatabaseManager(self.db_path)
        self.db.initialize_schema()

        # Insert baseline hearing
        self.hearing_data = {
            'event_id': 'LC12345',
            'congress': 119,
            'chamber': 'House',
            'title': 'Original Title',
            'hearing_date': '2025-10-01'
        }
        self.hearing_id = self.db.upsert_hearing(self.hearing_data)

    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_incremental_update_modifies_existing_hearing(self):
        """Should update existing hearing with new data"""
        # Arrange
        from updaters.daily_updater import DailyUpdater
        updater = DailyUpdater(congress=119, lookback_days=30)

        # Act
        result = updater.run_daily_update(dry_run=True)  # Dry run for testing

        # Assert
        self.assertTrue(result['success'])
        self.assertGreater(result['metrics']['hearings_checked'], 0)
```

---

## Test Coverage

### Generating Coverage Reports

```bash
# Terminal coverage report
pytest --cov=. --cov-report=term

# Terminal with missing lines
pytest --cov=. --cov-report=term-missing

# HTML coverage report (best for detailed analysis)
pytest --cov=. --cov-report=html
open htmlcov/index.html

# Generate all formats
pytest --cov=. --cov-report=term --cov-report=html --cov-report=xml
```

### Reading Coverage Reports

**Terminal Output**:
```
---------- coverage: platform darwin, python 3.9.7 -----------
Name                            Stmts   Miss  Cover
---------------------------------------------------
fetchers/document_fetcher.py      145     12    92%
parsers/hearing_parser.py          89      8    91%
database/manager.py               234     45    81%
---------------------------------------------------
TOTAL                            2456    198    92%
```

**Coverage Metrics**:
- **Stmts**: Total statements in file
- **Miss**: Statements not executed by tests
- **Cover**: Percentage coverage

**Target Coverage**:
- **Core modules** (parsers, fetchers, database): > 90%
- **Overall project**: > 80%
- **Critical paths** (upsert methods, data validation): 100%

### Coverage Configuration

Create `.coveragerc`:
```ini
[run]
source = .
omit =
    */tests/*
    */venv/*
    */__pycache__/*
    */migrations/*
    */scripts/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod

precision = 2
```

---

## Testing Best Practices

### 1. Test One Thing Per Test

**Good**:
```python
def test_parse_hearing_title():
    """Should extract title from API data"""
    data = {'title': 'Budget Hearing'}
    result = parser.parse_title(data)
    self.assertEqual(result, 'Budget Hearing')

def test_parse_hearing_date():
    """Should parse date from ISO format"""
    data = {'date': '2025-10-15T10:00:00Z'}
    result = parser.parse_date(data)
    self.assertEqual(result.year, 2025)
```

**Bad**:
```python
def test_parse_hearing():
    """Should parse everything"""  # Too broad!
    # Tests title, date, chamber, status, etc. all in one test
    # Hard to diagnose failures
```

### 2. Use Descriptive Test Names

**Good**:
```python
def test_upsert_hearing_creates_new_record_when_not_exists():
    """Clear what's being tested and expected behavior"""

def test_upsert_hearing_updates_existing_record_without_changing_id():
    """Specific about the scenario and expectation"""
```

**Bad**:
```python
def test_hearing():
    """Too vague"""

def test1():
    """No context"""
```

### 3. Follow AAA Pattern

**Arrange, Act, Assert**:
```python
def test_calculate_total_hearings():
    # Arrange: Set up test data
    db = DatabaseManager(':memory:')
    db.initialize_schema()
    db.upsert_hearing({'event_id': 'LC1', 'congress': 119, 'chamber': 'House', 'title': 'H1'})
    db.upsert_hearing({'event_id': 'LC2', 'congress': 119, 'chamber': 'House', 'title': 'H2'})

    # Act: Perform the action being tested
    total = db.get_hearing_count()

    # Assert: Verify the result
    self.assertEqual(total, 2)
```

### 4. Keep Tests Independent

**Good**:
```python
class TestDatabaseOperations(unittest.TestCase):
    def setUp(self):
        """Each test gets fresh database"""
        self.db = DatabaseManager(':memory:')
        self.db.initialize_schema()

    def test_insert_hearing(self):
        """Independent - doesn't rely on other tests"""
        hearing_id = self.db.upsert_hearing(test_data)
        self.assertIsNotNone(hearing_id)

    def test_update_hearing(self):
        """Independent - creates its own test data"""
        hearing_id = self.db.upsert_hearing(test_data)
        self.db.update_hearing(hearing_id, {'title': 'Updated'})
        # Verify
```

**Bad**:
```python
class TestDatabaseOperations(unittest.TestCase):
    def test_1_insert_hearing(self):
        """First test inserts"""
        self.hearing_id = self.db.upsert_hearing(test_data)

    def test_2_update_hearing(self):
        """Second test depends on first test's data"""
        # Uses self.hearing_id from test_1
        self.db.update_hearing(self.hearing_id, {'title': 'Updated'})
```

### 5. Test Edge Cases

```python
def test_parse_hearing_with_empty_title():
    """Should handle empty title"""
    data = {'eventId': 'LC123', 'congress': 119, 'chamber': 'House', 'title': ''}
    result = parser.parse(data)
    self.assertEqual(result.title, '')  # Or raise error if required

def test_parse_hearing_with_null_date():
    """Should handle null date"""
    data = {'eventId': 'LC123', 'congress': 119, 'chamber': 'House', 'title': 'Test', 'date': None}
    result = parser.parse(data)
    self.assertIsNone(result.hearing_date)

def test_parse_hearing_with_future_date():
    """Should accept future dates for scheduled hearings"""
    future_date = '2026-01-01T10:00:00Z'
    data = {'eventId': 'LC123', 'congress': 119, 'chamber': 'House', 'title': 'Test', 'date': future_date}
    result = parser.parse(data)
    self.assertIsNotNone(result.hearing_date)
```

### 6. Use Test Data Builders

```python
def create_test_hearing(event_id='LC123', **overrides):
    """Builder for test hearing data"""
    defaults = {
        'event_id': event_id,
        'congress': 119,
        'chamber': 'House',
        'title': f'Test Hearing {event_id}',
        'hearing_type': 'Hearing',
        'status': 'Scheduled'
    }
    defaults.update(overrides)
    return defaults

# Usage
def test_upsert_hearing():
    hearing1 = create_test_hearing('LC123')
    hearing2 = create_test_hearing('LC456', chamber='Senate')
    hearing3 = create_test_hearing('LC789', title='Custom Title')
```

---

## Common Testing Scenarios

### Testing Database Operations

```python
def test_upsert_hearing_inserts_new_record(self):
    """Should insert new hearing when event_id not exists"""
    hearing_data = create_test_hearing('LC999')

    hearing_id = self.db.upsert_hearing(hearing_data)

    # Verify inserted
    self.assertGreater(hearing_id, 0)

    # Verify retrievable
    hearing = self.db.get_hearing_by_event_id('LC999')
    self.assertIsNotNone(hearing)
    self.assertEqual(hearing['title'], hearing_data['title'])

def test_upsert_hearing_updates_existing_record(self):
    """Should update existing hearing when event_id exists"""
    # Insert initial
    hearing_data = create_test_hearing('LC999', title='Original Title')
    hearing_id_1 = self.db.upsert_hearing(hearing_data)

    # Update with new title
    updated_data = create_test_hearing('LC999', title='Updated Title')
    hearing_id_2 = self.db.upsert_hearing(updated_data)

    # Verify same ID (not a new record)
    self.assertEqual(hearing_id_1, hearing_id_2)

    # Verify title updated
    hearing = self.db.get_hearing_by_event_id('LC999')
    self.assertEqual(hearing['title'], 'Updated Title')
```

### Testing API Parsers

```python
def test_parse_valid_api_response(self):
    """Should parse complete API response"""
    api_data = {
        'eventId': 'LC12345',
        'congress': 119,
        'chamber': 'House',
        'title': 'Budget Hearing',
        'date': '2025-10-15T10:00:00Z',
        'status': 'Scheduled'
    }

    result = self.parser.parse(api_data)

    self.assertEqual(result.event_id, 'LC12345')
    self.assertEqual(result.congress, 119)
    self.assertEqual(result.chamber, 'House')

def test_parse_handles_missing_optional_fields(self):
    """Should parse with only required fields"""
    minimal_data = {
        'eventId': 'LC12345',
        'congress': 119,
        'chamber': 'House',
        'title': 'Test'
        # No date, status, location, etc.
    }

    result = self.parser.parse(minimal_data)

    self.assertIsNotNone(result)
    self.assertIsNone(result.hearing_date)
```

### Testing Error Handling

```python
def test_parser_raises_validation_error_for_invalid_chamber(self):
    """Should raise ValidationError for invalid chamber"""
    invalid_data = {'eventId': 'LC123', 'congress': 119, 'chamber': 'INVALID', 'title': 'Test'}

    with self.assertRaises(ValidationError) as context:
        self.parser.parse(invalid_data)

    # Verify error message mentions chamber
    self.assertIn('chamber', str(context.exception).lower())

def test_fetcher_handles_api_timeout_gracefully(self):
    """Should handle API timeout without crashing"""
    with patch('api.client.CongressAPIClient.get', side_effect=requests.exceptions.Timeout):
        with self.assertRaises(requests.exceptions.Timeout):
            self.fetcher.fetch_hearings_by_congress(119, 'house')
```

---

## Continuous Integration

### GitHub Actions Workflow

Create `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Run tests with coverage
      run: |
        pytest --cov=. --cov-report=xml --cov-report=term

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

Install pre-commit hooks:
```bash
pip install pre-commit
pre-commit install
```

---

## Additional Resources

### Related Documentation

- **[Development Guide](DEVELOPMENT.md)** - Development workflow
- **[CLI Commands](../../reference/cli-commands.md)** - CLI testing commands
- **[Database Schema](../../reference/architecture/database-schema.md)** - Database structure

### External Resources

- **[pytest Documentation](https://docs.pytest.org/)** - Testing framework
- **[unittest Documentation](https://docs.python.org/3/library/unittest.html)** - Python unittest
- **[coverage.py](https://coverage.readthedocs.io/)** - Code coverage tool
- **[unittest.mock](https://docs.python.org/3/library/unittest.mock.html)** - Mocking library

---

## Quick Reference

### Common Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test
pytest tests/documents/test_document_fetcher.py::TestDocumentFetcher::test_extract_transcripts_from_list -v

# Run and stop on first failure
pytest -x

# Run only failed tests from last run
pytest --lf

# Run tests matching pattern
pytest -k "document"
```

### Writing Tests Checklist

- [ ] Test file named `test_*.py`
- [ ] Test class named `Test<ClassName>`
- [ ] Test methods named `test_<what>_<expected>`
- [ ] Each test has clear docstring
- [ ] Uses AAA pattern (Arrange, Act, Assert)
- [ ] Tests one thing per test method
- [ ] Independent of other tests
- [ ] Tests edge cases and errors
- [ ] Uses appropriate assertions
- [ ] Cleans up resources in tearDown

---

**Last Updated**: October 9, 2025
**Testing Framework**: pytest with unittest
**Test Coverage Target**: > 80%

[← Back: Development Guide](DEVELOPMENT.md) | [Up: Documentation Hub](../../README.md) | [Next: CLI Commands →](../../reference/cli-commands.md)
