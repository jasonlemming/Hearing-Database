#!/usr/bin/env python3
"""
Simplified Committee Database Validator
Direct SQLite access without dependency on settings
"""

import sqlite3
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import re


@dataclass
class ValidationIssue:
    severity: str  # HIGH, MEDIUM, LOW
    category: str  # HIERARCHY, HEARING_COUNT, DATA_INTEGRITY, CONGRESS_GOV
    message: str
    details: str
    table: str
    record_id: Optional[int] = None


class SimpleCommitteeValidator:
    """Validates committee data integrity using direct SQLite access"""

    def __init__(self, db_path: str = "database_audit.db"):
        self.db_path = db_path
        self.issues: List[ValidationIssue] = []

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def add_issue(self, severity: str, category: str, message: str, details: str,
                  table: str, record_id: Optional[int] = None):
        """Add validation issue to the list"""
        self.issues.append(ValidationIssue(
            severity=severity,
            category=category,
            message=message,
            details=details,
            table=table,
            record_id=record_id
        ))

    def validate_committee_hierarchy(self) -> None:
        """Validate committee parent-child relationships"""
        print("🔍 Validating committee hierarchy...")

        with self.get_connection() as conn:
            # Check for orphaned parent references
            cursor = conn.execute("""
                SELECT c.committee_id, c.name, c.parent_committee_id
                FROM committees c
                LEFT JOIN committees parent ON c.parent_committee_id = parent.committee_id
                WHERE c.parent_committee_id IS NOT NULL
                AND parent.committee_id IS NULL
            """)

            orphaned = cursor.fetchall()
            for row in orphaned:
                self.add_issue(
                    "HIGH", "HIERARCHY",
                    f"Orphaned parent reference: Committee '{row[1]}' references non-existent parent {row[2]}",
                    f"committee_id={row[0]}, parent_committee_id={row[2]}",
                    "committees",
                    row[0]
                )

            # Check for potential circular references using a simpler approach
            cursor = conn.execute("""
                SELECT c1.committee_id, c1.name, c1.parent_committee_id,
                       c2.parent_committee_id as grandparent_id
                FROM committees c1
                JOIN committees c2 ON c1.parent_committee_id = c2.committee_id
                WHERE c2.parent_committee_id = c1.committee_id
            """)

            circular = cursor.fetchall()
            for row in circular:
                self.add_issue(
                    "HIGH", "HIERARCHY",
                    f"Circular reference: Committee '{row[1]}' and its parent form a cycle",
                    f"committee_id={row[0]}, parent_id={row[2]}",
                    "committees",
                    row[0]
                )

            # Check for subcommittees with subcommittees (if this should be prevented)
            cursor = conn.execute("""
                SELECT child.committee_id, child.name, parent.name as parent_name
                FROM committees child
                JOIN committees parent ON child.parent_committee_id = parent.committee_id
                WHERE parent.parent_committee_id IS NOT NULL
            """)

            nested_subs = cursor.fetchall()
            for row in nested_subs:
                self.add_issue(
                    "MEDIUM", "HIERARCHY",
                    f"Nested subcommittee: '{row[1]}' is a subcommittee of subcommittee '{row[2]}'",
                    f"committee_id={row[0]}",
                    "committees",
                    row[0]
                )

    def validate_hearing_associations(self) -> None:
        """Validate hearing-committee associations and counts"""
        print("🔍 Validating hearing associations...")

        with self.get_connection() as conn:
            # Check for hearing_committees entries with invalid committee_ids
            cursor = conn.execute("""
                SELECT hc.hearing_id, hc.committee_id
                FROM hearing_committees hc
                LEFT JOIN committees c ON hc.committee_id = c.committee_id
                WHERE c.committee_id IS NULL
            """)

            invalid_committees = cursor.fetchall()
            for row in invalid_committees:
                self.add_issue(
                    "HIGH", "HEARING_COUNT",
                    f"Invalid committee reference in hearing association",
                    f"hearing_id={row[0]}, committee_id={row[1]}",
                    "hearing_committees"
                )

            # Check for hearing_committees entries with invalid hearing_ids
            cursor = conn.execute("""
                SELECT hc.hearing_id, hc.committee_id
                FROM hearing_committees hc
                LEFT JOIN hearings h ON hc.hearing_id = h.hearing_id
                WHERE h.hearing_id IS NULL
            """)

            invalid_hearings = cursor.fetchall()
            for row in invalid_hearings:
                self.add_issue(
                    "HIGH", "HEARING_COUNT",
                    f"Invalid hearing reference in committee association",
                    f"hearing_id={row[0]}, committee_id={row[1]}",
                    "hearing_committees"
                )

            # Validate exclusive hearing count logic matches blueprint logic
            cursor = conn.execute("""
                SELECT c.committee_id, c.name,
                       COUNT(DISTINCT CASE
                           WHEN hc.hearing_id IN (
                               SELECT hearing_id
                               FROM hearing_committees hc2
                               WHERE hc2.hearing_id = hc.hearing_id
                               GROUP BY hearing_id
                               HAVING COUNT(*) = 1
                           ) THEN hc.hearing_id
                           ELSE NULL
                       END) as exclusive_hearings,
                       COUNT(DISTINCT hc.hearing_id) as total_hearings
                FROM committees c
                LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
                WHERE c.parent_committee_id IS NULL
                GROUP BY c.committee_id
                HAVING total_hearings > 0
            """)

            hearing_counts = cursor.fetchall()
            for row in hearing_counts:
                if row[2] > row[3]:  # exclusive > total (impossible)
                    self.add_issue(
                        "HIGH", "HEARING_COUNT",
                        f"Impossible hearing count: Committee '{row[1]}' has more exclusive hearings than total hearings",
                        f"exclusive={row[2]}, total={row[3]}",
                        "committees",
                        row[0]
                    )

    def validate_system_codes(self) -> None:
        """Validate committee system codes against Congress.gov patterns"""
        print("🔍 Validating system codes...")

        with self.get_connection() as conn:
            # Check for duplicate system codes
            cursor = conn.execute("""
                SELECT system_code, COUNT(*) as count, GROUP_CONCAT(committee_id) as ids
                FROM committees
                WHERE system_code IS NOT NULL
                GROUP BY system_code
                HAVING COUNT(*) > 1
            """)

            duplicates = cursor.fetchall()
            for row in duplicates:
                self.add_issue(
                    "HIGH", "DATA_INTEGRITY",
                    f"Duplicate system code: '{row[0]}' appears {row[1]} times",
                    f"system_code={row[0]}, committee_ids={row[2]}",
                    "committees"
                )

            # Check system code patterns using Python regex since SQLite regex support varies
            cursor = conn.execute("""
                SELECT committee_id, system_code, name, chamber
                FROM committees
                WHERE system_code IS NOT NULL
            """)

            all_codes = cursor.fetchall()
            pattern = re.compile(r'^[a-z]{2,4}[0-9]{2}$')
            for row in all_codes:
                if not pattern.match(row[1]):
                    self.add_issue(
                        "MEDIUM", "CONGRESS_GOV",
                        f"Invalid system code format: '{row[1]}' for committee '{row[2]}'",
                        f"Expected format: 2-4 lowercase letters + 2 digits (e.g., 'hsif00')",
                        "committees",
                        row[0]
                    )

            # Check for missing system codes in current committees
            cursor = conn.execute("""
                SELECT committee_id, name, chamber
                FROM committees
                WHERE system_code IS NULL AND is_current = 1
            """)

            missing_codes = cursor.fetchall()
            for row in missing_codes:
                self.add_issue(
                    "MEDIUM", "DATA_INTEGRITY",
                    f"Missing system code for current committee: '{row[1]}'",
                    f"committee_id={row[0]}, chamber={row[2]}",
                    "committees",
                    row[0]
                )

    def validate_chamber_type_combinations(self) -> None:
        """Validate chamber and type combinations"""
        print("🔍 Validating chamber-type combinations...")

        # Known valid combinations based on Congress.gov and schema
        valid_combinations = {
            ('House', 'Standing'), ('House', 'Select'), ('House', 'Special'), ('House', 'Subcommittee'),
            ('Senate', 'Standing'), ('Senate', 'Select'), ('Senate', 'Special'), ('Senate', 'Subcommittee'),
            ('Joint', 'Joint'), ('Joint', 'Select'), ('Joint', 'Subcommittee'),
            ('NoChamber', 'Commission or Caucus'), ('NoChamber', 'Task Force'), ('NoChamber', 'Other')
        }

        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT chamber, type, COUNT(*) as count
                FROM committees
                GROUP BY chamber, type
            """)

            combinations = cursor.fetchall()
            for row in combinations:
                combination = (row[0], row[1])
                if combination not in valid_combinations:
                    self.add_issue(
                        "MEDIUM", "CONGRESS_GOV",
                        f"Unusual chamber-type combination: {row[0]} + {row[1]}",
                        f"Found {row[2]} committees with this combination",
                        "committees"
                    )

    def get_database_stats(self) -> Dict[str, int]:
        """Get basic database statistics"""
        stats = {}
        with self.get_connection() as conn:
            # Committee counts
            cursor = conn.execute("SELECT COUNT(*) FROM committees")
            stats['total_committees'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NULL")
            stats['parent_committees'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NOT NULL")
            stats['subcommittees'] = cursor.fetchone()[0]

            # Hearing counts
            cursor = conn.execute("SELECT COUNT(*) FROM hearings")
            stats['total_hearings'] = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(DISTINCT hearing_id) FROM hearing_committees")
            stats['hearings_with_committees'] = cursor.fetchone()[0]

            # Chamber breakdown
            cursor = conn.execute("""
                SELECT chamber, COUNT(*)
                FROM committees
                WHERE parent_committee_id IS NULL
                GROUP BY chamber
            """)
            for row in cursor.fetchall():
                stats[f'{row[0].lower()}_committees'] = row[1]

        return stats

    def run_all_validations(self) -> List[ValidationIssue]:
        """Run all validation checks"""
        print("🚀 Starting comprehensive committee validation...")
        print(f"📊 Database: {self.db_path}")

        # Get database stats first
        stats = self.get_database_stats()
        print(f"📈 Statistics:")
        for key, value in stats.items():
            print(f"   {key}: {value}")

        self.validate_committee_hierarchy()
        self.validate_hearing_associations()
        self.validate_system_codes()
        self.validate_chamber_type_combinations()

        print(f"✅ Validation complete. Found {len(self.issues)} issues.")
        return self.issues

    def generate_report(self, output_file: str = None) -> str:
        """Generate detailed validation report"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"audit_tools/reports/validation_report_{timestamp}.md"

        # Group issues by severity
        high_issues = [i for i in self.issues if i.severity == "HIGH"]
        medium_issues = [i for i in self.issues if i.severity == "MEDIUM"]
        low_issues = [i for i in self.issues if i.severity == "LOW"]

        # Get database stats
        stats = self.get_database_stats()

        report = f"""# Committee Database Validation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Database: {self.db_path}

## Database Statistics
"""
        for key, value in stats.items():
            report += f"- **{key.replace('_', ' ').title()}**: {value}\n"

        report += f"""
## Summary
- **Total Issues**: {len(self.issues)}
- **High Severity**: {len(high_issues)}
- **Medium Severity**: {len(medium_issues)}
- **Low Severity**: {len(low_issues)}

## High Severity Issues
"""

        for issue in high_issues:
            report += f"""
### {issue.category}: {issue.message}
- **Table**: {issue.table}
- **Record ID**: {issue.record_id or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Medium Severity Issues\n"
        for issue in medium_issues:
            report += f"""
### {issue.category}: {issue.message}
- **Table**: {issue.table}
- **Record ID**: {issue.record_id or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Low Severity Issues\n"
        for issue in low_issues:
            report += f"""
### {issue.category}: {issue.message}
- **Table**: {issue.table}
- **Record ID**: {issue.record_id or 'N/A'}
- **Details**: {issue.details}
"""

        # Write report to file
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(report)

        return output_file


if __name__ == "__main__":
    validator = SimpleCommitteeValidator()
    issues = validator.run_all_validations()

    report_file = validator.generate_report()
    print(f"📋 Report saved to: {report_file}")

    # Print summary
    if issues:
        print("\n⚠️  Issues found:")
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            severity_issues = [i for i in issues if i.severity == severity]
            if severity_issues:
                print(f"  {severity}: {len(severity_issues)} issues")
    else:
        print("\n✅ No issues found!")