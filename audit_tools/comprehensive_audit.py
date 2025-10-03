#!/usr/bin/env python3
"""
Comprehensive Committee Audit Runner
Orchestrates all audit tools and generates unified reports
"""

import os
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import subprocess
import signal
import sys

# Import our audit tools
from simple_validator import SimpleCommitteeValidator
from style_analyzer import TemplateStyleAnalyzer

try:
    from http_tester import CommitteeHTTPTester
    HTTP_TESTING_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  HTTP testing not available: {e}")
    HTTP_TESTING_AVAILABLE = False


class ComprehensiveCommitteeAudit:
    """Orchestrates comprehensive committee audit"""

    def __init__(self, db_path: str = "database_audit.db"):
        self.db_path = db_path
        self.audit_start_time = datetime.now()
        self.results = {}
        self.report_dir = Path("audit_tools/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def run_database_validation(self) -> Dict[str, Any]:
        """Run database integrity validation"""
        print("=" * 60)
        print("📊 PHASE 1: DATABASE VALIDATION")
        print("=" * 60)

        validator = SimpleCommitteeValidator(self.db_path)
        issues = validator.run_all_validations()
        report_file = validator.generate_report()

        return {
            'issues_count': len(issues),
            'issues_by_severity': {
                'HIGH': len([i for i in issues if i.severity == "HIGH"]),
                'MEDIUM': len([i for i in issues if i.severity == "MEDIUM"]),
                'LOW': len([i for i in issues if i.severity == "LOW"])
            },
            'issues': [
                {
                    'severity': i.severity,
                    'category': i.category,
                    'message': i.message,
                    'details': i.details,
                    'table': i.table,
                    'record_id': i.record_id
                }
                for i in issues
            ],
            'report_file': str(report_file)
        }

    def run_style_analysis(self) -> Dict[str, Any]:
        """Run template style analysis"""
        print("=" * 60)
        print("🎨 PHASE 2: STYLE ANALYSIS")
        print("=" * 60)

        analyzer = TemplateStyleAnalyzer()
        issues = analyzer.run_all_analyses()
        report_file = analyzer.generate_report()

        return {
            'issues_count': len(issues),
            'issues_by_severity': {
                'HIGH': len([i for i in issues if i.severity == "HIGH"]),
                'MEDIUM': len([i for i in issues if i.severity == "MEDIUM"]),
                'LOW': len([i for i in issues if i.severity == "LOW"])
            },
            'issues': [
                {
                    'severity': i.severity,
                    'category': i.category,
                    'message': i.message,
                    'details': i.details,
                    'file': i.file,
                    'line_number': i.line_number
                }
                for i in issues
            ],
            'templates_analyzed': len(analyzer.templates),
            'report_file': str(report_file)
        }

    def run_http_testing(self) -> Dict[str, Any]:
        """Run HTTP interface testing"""
        print("=" * 60)
        print("🌐 PHASE 3: HTTP INTERFACE TESTING")
        print("=" * 60)

        if not HTTP_TESTING_AVAILABLE:
            return {
                'skipped': True,
                'reason': 'HTTP testing dependencies not available'
            }

        try:
            tester = CommitteeHTTPTester(db_path=self.db_path)
            issues = tester.run_all_tests()
            report_file = tester.generate_report()

            return {
                'issues_count': len(issues),
                'issues_by_severity': {
                    'HIGH': len([i for i in issues if i.severity == "HIGH"]),
                    'MEDIUM': len([i for i in issues if i.severity == "MEDIUM"]),
                    'LOW': len([i for i in issues if i.severity == "LOW"])
                },
                'issues': [
                    {
                        'severity': i.severity,
                        'category': i.category,
                        'message': i.message,
                        'details': i.details,
                        'page': i.page,
                        'url': i.url
                    }
                    for i in issues
                ],
                'report_file': str(report_file)
            }
        except Exception as e:
            return {
                'failed': True,
                'error': str(e)
            }

    def analyze_database_statistics(self) -> Dict[str, Any]:
        """Generate database statistics for context"""
        print("📈 Collecting database statistics...")

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row

            stats = {}

            # Basic counts
            cursor = conn.execute("SELECT COUNT(*) FROM committees")
            stats['total_committees'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NULL")
            stats['parent_committees'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NOT NULL")
            stats['subcommittees'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            stats['total_hearings'] = cursor.fetchone()[0]

            # Chamber breakdown
            cursor = conn.execute("""
                SELECT chamber, COUNT(*) as count
                FROM committees
                WHERE parent_committee_id IS NULL
                GROUP BY chamber
            """)
            chamber_counts = {row[0]: row[1] for row in cursor.fetchall()}
            stats['committees_by_chamber'] = chamber_counts

            # Committee types
            cursor = conn.execute("""
                SELECT type, COUNT(*) as count
                FROM committees
                GROUP BY type
                ORDER BY count DESC
            """)
            type_counts = {row[0]: row[1] for row in cursor.fetchall()}
            stats['committees_by_type'] = type_counts

            # Hearing associations
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT hearing_id) FROM hearing_committees
            """)
            stats['hearings_with_committee_associations'] = cursor.fetchone()[0]

            # System code coverage
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(system_code) as with_system_code
                FROM committees
                WHERE is_current = 1
            """)
            row = cursor.fetchone()
            stats['system_code_coverage'] = {
                'total_current_committees': row[0],
                'with_system_code': row[1],
                'percentage': round((row[1] / row[0]) * 100, 1) if row[0] > 0 else 0
            }

            conn.close()
            return stats

        except Exception as e:
            return {'error': f"Failed to collect statistics: {e}"}

    def calculate_priority_matrix(self) -> Dict[str, List[Dict]]:
        """Calculate issue priority matrix based on severity and effort"""
        all_issues = []

        # Collect all issues from different phases
        for phase_name, phase_results in self.results.items():
            if 'issues' in phase_results:
                for issue in phase_results['issues']:
                    issue_copy = issue.copy()
                    issue_copy['source_phase'] = phase_name
                    all_issues.append(issue_copy)

        # Classify by priority matrix
        priority_matrix = {
            'critical_quick': [],      # High severity, easy fix
            'high_moderate': [],       # High severity, moderate effort
            'medium_quick': [],        # Medium severity, easy fix
            'medium_moderate': [],     # Medium severity, moderate effort
            'low_any': []              # Low severity, any effort
        }

        for issue in all_issues:
            severity = issue.get('severity', 'LOW')
            category = issue.get('category', '')

            # Estimate effort based on category
            quick_fix_categories = ['BOOTSTRAP', 'ICON_USAGE', 'CSS']
            moderate_fix_categories = ['HTML_STRUCTURE', 'ACCESSIBILITY', 'DATA_INTEGRITY']

            if category in quick_fix_categories:
                effort = 'quick'
            elif category in moderate_fix_categories:
                effort = 'moderate'
            else:
                effort = 'moderate'  # Default to moderate

            # Classify into priority matrix
            if severity == 'HIGH' and effort == 'quick':
                priority_matrix['critical_quick'].append(issue)
            elif severity == 'HIGH':
                priority_matrix['high_moderate'].append(issue)
            elif severity == 'MEDIUM' and effort == 'quick':
                priority_matrix['medium_quick'].append(issue)
            elif severity == 'MEDIUM':
                priority_matrix['medium_moderate'].append(issue)
            else:
                priority_matrix['low_any'].append(issue)

        return priority_matrix

    def generate_unified_report(self) -> str:
        """Generate comprehensive unified report"""
        timestamp = self.audit_start_time.strftime('%Y%m%d_%H%M%S')
        report_file = self.report_dir / f"comprehensive_audit_report_{timestamp}.md"

        duration = datetime.now() - self.audit_start_time
        db_stats = self.analyze_database_statistics()
        priority_matrix = self.calculate_priority_matrix()

        # Calculate total issues
        total_issues = sum(
            result.get('issues_count', 0)
            for result in self.results.values()
            if isinstance(result, dict) and 'issues_count' in result
        )

        report = f"""# Comprehensive Committee Audit Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Duration**: {duration.total_seconds():.1f} seconds
**Database**: {self.db_path}
**Total Issues Found**: {total_issues}

## Executive Summary

This comprehensive audit examined the `/committees` tab for both functional correctness and stylistic consistency. The audit included database integrity validation, template style analysis, and HTTP interface testing.

### Key Findings

"""

        # Add priority matrix summary
        for priority, issues in priority_matrix.items():
            if issues:
                priority_label = priority.replace('_', ' ').title()
                report += f"- **{priority_label}**: {len(issues)} issues\n"

        report += f"""
### Database Statistics

"""
        if 'error' not in db_stats:
            report += f"""- **Total Committees**: {db_stats['total_committees']}
- **Parent Committees**: {db_stats['parent_committees']}
- **Subcommittees**: {db_stats['subcommittees']}
- **Total Hearings**: {db_stats['total_hearings']}
- **System Code Coverage**: {db_stats['system_code_coverage']['percentage']}% ({db_stats['system_code_coverage']['with_system_code']}/{db_stats['system_code_coverage']['total_current_committees']})

#### Committees by Chamber
"""
            for chamber, count in db_stats['committees_by_chamber'].items():
                report += f"- **{chamber}**: {count}\n"

            report += "\n#### Committees by Type\n"
            for committee_type, count in list(db_stats['committees_by_type'].items())[:5]:
                report += f"- **{committee_type}**: {count}\n"
        else:
            report += f"- **Error collecting statistics**: {db_stats['error']}\n"

        report += f"""
## Phase Results

"""

        # Add detailed phase results
        phase_names = {
            'database_validation': 'Database Validation',
            'style_analysis': 'Style Analysis',
            'http_testing': 'HTTP Interface Testing'
        }

        for phase_key, phase_name in phase_names.items():
            if phase_key in self.results:
                result = self.results[phase_key]
                report += f"### {phase_name}\n\n"

                if result.get('skipped'):
                    report += f"⚠️ **Skipped**: {result.get('reason', 'Unknown reason')}\n\n"
                elif result.get('failed'):
                    report += f"❌ **Failed**: {result.get('error', 'Unknown error')}\n\n"
                else:
                    issues_count = result.get('issues_count', 0)
                    severity_breakdown = result.get('issues_by_severity', {})

                    if issues_count == 0:
                        report += "✅ **No issues found**\n\n"
                    else:
                        report += f"⚠️ **{issues_count} issues found**\n"
                        for severity, count in severity_breakdown.items():
                            if count > 0:
                                report += f"- {severity}: {count}\n"
                        report += "\n"

                    if 'report_file' in result:
                        report += f"📋 **Detailed report**: {result['report_file']}\n\n"

        # Add priority matrix section
        report += "## Issue Priority Matrix\n\nIssues are classified by severity and estimated fix effort:\n\n"

        priority_labels = {
            'critical_quick': '🔴 **Critical/Quick** (High severity, easy fix)',
            'high_moderate': '🟠 **High/Moderate** (High severity, moderate effort)',
            'medium_quick': '🟡 **Medium/Quick** (Medium severity, easy fix)',
            'medium_moderate': '🟡 **Medium/Moderate** (Medium severity, moderate effort)',
            'low_any': '🟢 **Low Priority** (Low severity, any effort)'
        }

        for priority, label in priority_labels.items():
            issues = priority_matrix[priority]
            report += f"### {label}\n\n"

            if not issues:
                report += "✅ No issues in this category\n\n"
            else:
                for issue in issues[:5]:  # Show first 5 issues
                    source = issue.get('source_phase', 'unknown')
                    category = issue.get('category', 'UNKNOWN')
                    message = issue.get('message', 'No message')
                    report += f"- **{category}** ({source}): {message}\n"

                if len(issues) > 5:
                    report += f"- ... and {len(issues) - 5} more issues\n"
                report += "\n"

        # Add recommendations
        report += """## Recommendations

### Immediate Actions (Critical/Quick fixes)
"""
        critical_quick = priority_matrix['critical_quick']
        if critical_quick:
            report += "These issues should be addressed immediately as they are high-impact with minimal effort:\n\n"
            for issue in critical_quick[:3]:
                report += f"1. **{issue.get('category', 'UNKNOWN')}**: {issue.get('message', 'No message')}\n"
        else:
            report += "✅ No critical quick fixes needed.\n"

        report += """
### Next Sprint (High/Medium priority)
"""
        next_sprint_issues = priority_matrix['high_moderate'] + priority_matrix['medium_quick']
        if next_sprint_issues:
            report += "These issues should be prioritized for the next development cycle:\n\n"
            for issue in next_sprint_issues[:5]:
                report += f"1. **{issue.get('category', 'UNKNOWN')}**: {issue.get('message', 'No message')}\n"
        else:
            report += "✅ No high/medium priority issues found.\n"

        report += f"""
### Long-term Improvements
Consider implementing automated testing to prevent regression of these issues.

## Detailed Reports

Individual detailed reports have been generated for each phase:
"""

        for phase_key in phase_names:
            if phase_key in self.results and 'report_file' in self.results[phase_key]:
                report += f"- **{phase_names[phase_key]}**: {self.results[phase_key]['report_file']}\n"

        report += f"""
## Methodology

This audit followed a systematic approach:

1. **Database Integrity**: Validated committee hierarchies, hearing associations, and data consistency
2. **Style Analysis**: Compared template patterns for Bootstrap usage, accessibility, and consistency
3. **HTTP Testing**: Verified server responses and UI functionality
4. **Priority Assessment**: Classified issues by severity and implementation effort

## Tools Used

- `simple_validator.py`: Database integrity validation
- `style_analyzer.py`: Template style consistency analysis
- `http_tester.py`: HTTP interface testing
- `comprehensive_audit.py`: Orchestration and unified reporting

---
*Generated by Congressional Hearing Database Audit Tools*
*Audit completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        # Write report
        with open(report_file, 'w') as f:
            f.write(report)

        return str(report_file)

    def run_comprehensive_audit(self) -> str:
        """Run all audit phases and generate unified report"""
        print("🚀 STARTING COMPREHENSIVE COMMITTEE AUDIT")
        print("=" * 60)
        print(f"Database: {self.db_path}")
        print(f"Started at: {self.audit_start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Phase 1: Database Validation
        self.results['database_validation'] = self.run_database_validation()

        # Phase 2: Style Analysis
        self.results['style_analysis'] = self.run_style_analysis()

        # Phase 3: HTTP Testing
        self.results['http_testing'] = self.run_http_testing()

        # Generate unified report
        print("=" * 60)
        print("📋 GENERATING UNIFIED REPORT")
        print("=" * 60)

        report_file = self.generate_unified_report()

        # Final summary
        duration = datetime.now() - self.audit_start_time
        total_issues = sum(
            result.get('issues_count', 0)
            for result in self.results.values()
            if isinstance(result, dict) and 'issues_count' in result
        )

        print(f"""
🎯 AUDIT COMPLETE!
📋 Unified report: {report_file}
⏱️  Duration: {duration.total_seconds():.1f} seconds
⚠️  Total issues: {total_issues}

""")

        return report_file


if __name__ == "__main__":
    auditor = ComprehensiveCommitteeAudit()
    report_file = auditor.run_comprehensive_audit()