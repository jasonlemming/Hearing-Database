#!/usr/bin/env python3
"""
Committee Database Integrity Validator
Comprehensive validation of committee hierarchies, hearing associations, and data integrity
"""

import sqlite3
import sys
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from database.manager import DatabaseManager


@dataclass
class ValidationIssue:
    severity: str  # HIGH, MEDIUM, LOW
    category: str  # HIERARCHY, HEARING_COUNT, DATA_INTEGRITY, CONGRESS_GOV
    message: str
    details: str
    table: str
    record_id: Optional[int] = None


class CommitteeValidator:
    """Validates committee data integrity and relationships"""

    def __init__(self, db_path: str = "database_audit.db"):
        self.db = DatabaseManager(db_path)
        self.issues: List[ValidationIssue] = []

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

        with self.db.transaction() as conn:
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

            # Check for circular references (committee being its own ancestor)
            cursor = conn.execute("""
                WITH RECURSIVE committee_path AS (
                    SELECT committee_id, parent_committee_id, name,
                           committee_id as root_id, 1 as depth
                    FROM committees
                    WHERE parent_committee_id IS NOT NULL

                    UNION ALL

                    SELECT c.committee_id, c.parent_committee_id, c.name,
                           cp.root_id, cp.depth + 1
                    FROM committees c
                    JOIN committee_path cp ON c.committee_id = cp.parent_committee_id
                    WHERE cp.depth < 10  -- Prevent infinite recursion
                )
                SELECT root_id, committee_id, name, depth
                FROM committee_path
                WHERE committee_id = root_id AND depth > 1
            """)

            circular = cursor.fetchall()
            for row in circular:
                self.add_issue(
                    "HIGH", "HIERARCHY",
                    f"Circular reference: Committee '{row[2]}' is its own ancestor",
                    f"committee_id={row[0]}, depth={row[3]}",
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

        with self.db.transaction() as conn:
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

            # Validate exclusive hearing count logic
            # Compare the complex query from committees.py with a simpler count
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

        with self.db.transaction() as conn:
            # Check for duplicate system codes
            cursor = conn.execute("""
                SELECT system_code, COUNT(*) as count
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
                    f"system_code={row[0]}",
                    "committees"
                )

            # Check system code patterns (Congress.gov uses specific formats)
            cursor = conn.execute("""
                SELECT committee_id, system_code, name, chamber
                FROM committees
                WHERE system_code IS NOT NULL
                AND system_code NOT REGEXP '^[a-z]{2,4}[0-9]{2}$'
            """)

            invalid_codes = cursor.fetchall()
            for row in invalid_codes:
                self.add_issue(
                    "MEDIUM", "CONGRESS_GOV",
                    f"Invalid system code format: '{row[1]}' for committee '{row[2]}'",
                    f"Expected format: 2-4 lowercase letters + 2 digits (e.g., 'hsif00')",
                    "committees",
                    row[0]
                )

    def validate_chamber_type_combinations(self) -> None:
        """Validate chamber and type combinations"""
        print("🔍 Validating chamber-type combinations...")

        # Known valid combinations based on Congress.gov
        valid_combinations = {
            ('House', 'Standing'), ('House', 'Select'), ('House', 'Special'),
            ('Senate', 'Standing'), ('Senate', 'Select'), ('Senate', 'Special'),
            ('Joint', 'Joint'), ('Joint', 'Select'),
            ('NoChamber', 'Commission or Caucus')
        }

        with self.db.transaction() as conn:
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

    def run_all_validations(self) -> List[ValidationIssue]:
        """Run all validation checks"""
        print("🚀 Starting comprehensive committee validation...")
        print(f"📊 Database: {self.db.db_path}")

        self.validate_committee_hierarchy()
        self.validate_hearing_associations()
        self.validate_system_codes()
        self.validate_chamber_type_combinations()

        print(f"✅ Validation complete. Found {len(self.issues)} issues.")
        return self.issues

    def generate_report(self, output_file: str = None) -> str:
        """Generate detailed validation report"""
        if not output_file:
            output_file = f"audit_tools/reports/validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        # Group issues by severity
        high_issues = [i for i in self.issues if i.severity == "HIGH"]
        medium_issues = [i for i in self.issues if i.severity == "MEDIUM"]
        low_issues = [i for i in self.issues if i.severity == "LOW"]

        report = f"""# Committee Database Validation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Database: {self.db.db_path}

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
    validator = CommitteeValidator()
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