#!/usr/bin/env python3
"""
PostgreSQL Compatibility Checker

Scans Python codebase for common SQLite-specific syntax that needs PostgreSQL compatibility fixes.
Run this before migrating to PostgreSQL to identify potential issues.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Patterns to check
CHECKS = [
    {
        'name': 'AUTOINCREMENT usage',
        'pattern': r'AUTOINCREMENT',
        'severity': 'ERROR',
        'fix': 'Use SERIAL for PostgreSQL or conditional CREATE TABLE'
    },
    {
        'name': 'Boolean = integer comparison',
        'pattern': r'\b(is_current|is_active|is_primary|success|is_deployed)\s*=\s*[01]\b',
        'severity': 'ERROR',
        'fix': 'Use = TRUE or = FALSE instead of = 1 or = 0'
    },
    {
        'name': 'DATETIME type',
        'pattern': r'\bDATETIME\b',
        'severity': 'WARNING',
        'fix': 'PostgreSQL uses TIMESTAMP instead of DATETIME'
    },
    {
        'name': 'DATE() function',
        'pattern': r"DATE\(['\"]now['\"]\s*,\s*['\"][+-]\d+\s+days?['\"]",
        'severity': 'ERROR',
        'fix': 'Use INTERVAL syntax: (CURRENT_DATE - INTERVAL \'30 days\')'
    },
    {
        'name': 'PRAGMA commands',
        'pattern': r'PRAGMA\s+\w+',
        'severity': 'WARNING',
        'fix': 'Add conditional check for SQLite vs PostgreSQL'
    },
    {
        'name': 'sqlite_master table',
        'pattern': r'\bsqlite_master\b',
        'severity': 'ERROR',
        'fix': 'Use information_schema.tables for PostgreSQL'
    },
    {
        'name': 'INTEGER PRIMARY KEY (implicit ROWID)',
        'pattern': r'INTEGER\s+PRIMARY\s+KEY(?!\s+AUTOINCREMENT)',
        'severity': 'WARNING',
        'fix': 'Consider explicit SERIAL for PostgreSQL'
    },
    {
        'name': 'INSERT OR IGNORE',
        'pattern': r'INSERT\s+OR\s+IGNORE',
        'severity': 'ERROR',
        'fix': 'Use INSERT ... ON CONFLICT DO NOTHING for PostgreSQL'
    },
    {
        'name': 'INSERT OR REPLACE',
        'pattern': r'INSERT\s+OR\s+REPLACE',
        'severity': 'ERROR',
        'fix': 'Use INSERT ... ON CONFLICT DO UPDATE for PostgreSQL'
    },
]


def find_python_files(root_dir: str) -> List[Path]:
    """Find all Python files in the project."""
    root = Path(root_dir)
    python_files = []

    # Directories to skip
    skip_dirs = {'.git', '__pycache__', 'venv', '.venv', 'node_modules', 'env'}

    for path in root.rglob('*.py'):
        # Skip files in excluded directories
        if any(skip in path.parts for skip in skip_dirs):
            continue
        python_files.append(path)

    return sorted(python_files)


def check_file(file_path: Path) -> List[Dict]:
    """Check a single file for compatibility issues."""
    issues = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')

        for check in CHECKS:
            pattern = re.compile(check['pattern'], re.IGNORECASE | re.MULTILINE)

            for match in pattern.finditer(content):
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()

                issues.append({
                    'file': str(file_path),
                    'line': line_num,
                    'check': check['name'],
                    'severity': check['severity'],
                    'matched': match.group(0),
                    'line_content': line_content,
                    'fix': check['fix']
                })

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return issues


def print_report(all_issues: List[Dict]):
    """Print a formatted report of all issues found."""
    if not all_issues:
        print("\n✅ No PostgreSQL compatibility issues found!")
        return

    # Group by severity
    errors = [i for i in all_issues if i['severity'] == 'ERROR']
    warnings = [i for i in all_issues if i['severity'] == 'WARNING']

    print("\n" + "=" * 80)
    print("PostgreSQL Compatibility Report")
    print("=" * 80)
    print(f"\nTotal issues found: {len(all_issues)}")
    print(f"  Errors (must fix): {len(errors)}")
    print(f"  Warnings (should review): {len(warnings)}")
    print()

    # Print errors first
    if errors:
        print("\n🔴 ERRORS (Must Fix):")
        print("-" * 80)
        for issue in errors:
            print(f"\n{issue['file']}:{issue['line']}")
            print(f"  Issue: {issue['check']}")
            print(f"  Found: {issue['matched']}")
            print(f"  Context: {issue['line_content'][:100]}")
            print(f"  Fix: {issue['fix']}")

    # Print warnings
    if warnings:
        print("\n\n⚠️  WARNINGS (Should Review):")
        print("-" * 80)
        for issue in warnings:
            print(f"\n{issue['file']}:{issue['line']}")
            print(f"  Issue: {issue['check']}")
            print(f"  Found: {issue['matched']}")
            print(f"  Context: {issue['line_content'][:100]}")
            print(f"  Fix: {issue['fix']}")

    print("\n" + "=" * 80)
    print(f"\nSummary by Check Type:")
    print("-" * 80)

    # Count by check type
    check_counts = {}
    for issue in all_issues:
        check_name = issue['check']
        check_counts[check_name] = check_counts.get(check_name, 0) + 1

    for check_name, count in sorted(check_counts.items(), key=lambda x: -x[1]):
        print(f"  {check_name}: {count} occurrences")

    print("=" * 80)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Check PostgreSQL compatibility')
    parser.add_argument('--path', default='.', help='Path to check (default: current directory)')
    parser.add_argument('--errors-only', action='store_true', help='Show only errors, not warnings')

    args = parser.parse_args()

    print(f"Scanning Python files in {args.path}...")

    python_files = find_python_files(args.path)
    print(f"Found {len(python_files)} Python files to check\n")

    all_issues = []
    for file_path in python_files:
        issues = check_file(file_path)
        all_issues.extend(issues)

    # Filter if errors only
    if args.errors_only:
        all_issues = [i for i in all_issues if i['severity'] == 'ERROR']

    print_report(all_issues)

    # Exit with error code if there are errors
    errors = [i for i in all_issues if i['severity'] == 'ERROR']
    if errors:
        return 1
    return 0


if __name__ == '__main__':
    exit(main())
