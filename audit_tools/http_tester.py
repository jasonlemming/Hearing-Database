#!/usr/bin/env python3
"""
HTTP Committee Interface Tester
Tests the committee pages via HTTP requests and validates HTML structure
"""

import requests
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, parse_qs
import subprocess
import signal
import sys
import threading

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    print("⚠️  BeautifulSoup4 not available. Install with: pip3 install beautifulsoup4")
    BS4_AVAILABLE = False


@dataclass
class UIIssue:
    severity: str  # HIGH, MEDIUM, LOW
    category: str  # HTML_STRUCTURE, DATA_MISMATCH, NAVIGATION, STYLING
    page: str
    message: str
    details: str
    url: Optional[str] = None


class CommitteeHTTPTester:
    """Tests committee pages via HTTP and validates UI consistency"""

    def __init__(self, base_url: str = "http://127.0.0.1:5000", db_path: str = "database_audit.db"):
        self.base_url = base_url
        self.db_path = db_path
        self.session = requests.Session()
        self.issues: List[UIIssue] = []
        self.server_process = None

    def add_issue(self, severity: str, category: str, page: str, message: str,
                  details: str, url: Optional[str] = None):
        """Add UI issue to the list"""
        self.issues.append(UIIssue(
            severity=severity,
            category=category,
            page=page,
            message=message,
            details=details,
            url=url
        ))

    def start_server(self) -> bool:
        """Start the Flask development server"""
        print("🚀 Starting Flask development server...")

        try:
            # Start server in background
            self.server_process = subprocess.Popen(
                ["python3", "cli.py", "web", "serve", "--host", "127.0.0.1", "--port", "5000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )

            # Wait for server to start
            max_retries = 30
            for i in range(max_retries):
                try:
                    response = self.session.get(f"{self.base_url}/", timeout=2)
                    if response.status_code == 200:
                        print(f"✅ Server started successfully on {self.base_url}")
                        return True
                except requests.exceptions.RequestException:
                    time.sleep(1)

            print("❌ Failed to start server")
            return False

        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False

    def stop_server(self):
        """Stop the Flask development server"""
        if self.server_process:
            print("🛑 Stopping Flask server...")
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(self.server_process.pid), signal.SIGTERM)
            else:
                self.server_process.terminate()
            self.server_process.wait()

    def get_database_committees(self) -> List[Dict]:
        """Get committee data from database for comparison"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT c.committee_id, c.system_code, c.name, c.chamber, c.type,
                   COUNT(DISTINCT CASE
                       WHEN hc.hearing_id IN (
                           SELECT hearing_id
                           FROM hearing_committees hc2
                           WHERE hc2.hearing_id = hc.hearing_id
                           GROUP BY hearing_id
                           HAVING COUNT(*) = 1
                       ) THEN hc.hearing_id
                       ELSE NULL
                   END) as hearing_count,
                   COUNT(DISTINCT sub.committee_id) as subcommittee_count
            FROM committees c
            LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
            LEFT JOIN committees sub ON c.committee_id = sub.parent_committee_id
            WHERE c.parent_committee_id IS NULL
            GROUP BY c.committee_id
            ORDER BY c.chamber, c.name
        """)

        committees = []
        for row in cursor.fetchall():
            committees.append({
                'committee_id': row[0],
                'system_code': row[1],
                'name': row[2],
                'chamber': row[3],
                'type': row[4],
                'hearing_count': row[5],
                'subcommittee_count': row[6]
            })

        conn.close()
        return committees

    def test_committees_page(self) -> bool:
        """Test the main committees page"""
        print("🔍 Testing /committees page...")

        url = f"{self.base_url}/committees"
        try:
            response = self.session.get(url, timeout=10)

            if response.status_code != 200:
                self.add_issue(
                    "HIGH", "HTTP_ERROR", "/committees",
                    f"HTTP {response.status_code} error",
                    f"Expected 200, got {response.status_code}",
                    url
                )
                return False

            if not BS4_AVAILABLE:
                print("⚠️  Skipping HTML analysis (BeautifulSoup4 not available)")
                return True

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check basic structure
            self.validate_page_structure(soup, "/committees", url)

            # Validate committee hierarchy
            self.validate_committee_hierarchy_html(soup, url)

            # Test filter functionality
            self.test_committee_filters(url)

            return True

        except requests.exceptions.RequestException as e:
            self.add_issue(
                "HIGH", "HTTP_ERROR", "/committees",
                f"Request failed: {str(e)}",
                f"Unable to reach {url}",
                url
            )
            return False

    def validate_page_structure(self, soup: BeautifulSoup, page: str, url: str):
        """Validate basic HTML structure"""
        if not soup.find('title'):
            self.add_issue(
                "MEDIUM", "HTML_STRUCTURE", page,
                "Missing page title",
                "HTML page should have a <title> element",
                url
            )

        # Check for main navigation
        nav = soup.find('nav', class_='navbar')
        if not nav:
            self.add_issue(
                "MEDIUM", "HTML_STRUCTURE", page,
                "Missing main navigation",
                "Expected navbar with class 'navbar'",
                url
            )
        else:
            # Check if committees link is present and properly highlighted
            committees_link = nav.find('a', href="/committees")
            if not committees_link:
                self.add_issue(
                    "LOW", "NAVIGATION", page,
                    "Committees navigation link not found",
                    "Expected link to /committees in navigation",
                    url
                )

    def validate_committee_hierarchy_html(self, soup: BeautifulSoup, url: str):
        """Validate committee hierarchy display"""
        # Check for chamber sections
        expected_chambers = ['House Committees', 'Senate Committees', 'Joint Committees']

        for chamber in expected_chambers:
            chamber_header = soup.find('h2', string=lambda text: text and chamber in text)
            if not chamber_header:
                self.add_issue(
                    "MEDIUM", "HTML_STRUCTURE", "/committees",
                    f"Missing {chamber} section",
                    f"Expected h2 element containing '{chamber}'",
                    url
                )
                continue

            # Check for committee cards in this section
            section = chamber_header.find_parent()
            if section:
                committee_cards = section.find_all('div', class_='card')
                if not committee_cards:
                    self.add_issue(
                        "LOW", "HTML_STRUCTURE", "/committees",
                        f"No committee cards found in {chamber} section",
                        "Expected committee cards with class 'card'",
                        url
                    )

    def test_committee_filters(self, base_url: str):
        """Test committee filter functionality"""
        print("  🔍 Testing filter functionality...")

        # Test chamber filter
        for chamber in ['House', 'Senate', 'Joint']:
            filter_url = f"{base_url}?chamber={chamber}"
            try:
                response = self.session.get(filter_url, timeout=5)
                if response.status_code != 200:
                    self.add_issue(
                        "MEDIUM", "NAVIGATION", "/committees",
                        f"Chamber filter failed for {chamber}",
                        f"HTTP {response.status_code} when filtering by chamber={chamber}",
                        filter_url
                    )
                elif BS4_AVAILABLE:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Verify that only the selected chamber is shown
                    chamber_headers = soup.find_all('h2')
                    chamber_texts = [h.get_text() for h in chamber_headers if 'Committees' in h.get_text()]

                    if len(chamber_texts) > 1:
                        self.add_issue(
                            "LOW", "NAVIGATION", "/committees",
                            f"Chamber filter not working properly for {chamber}",
                            f"Expected only {chamber} committees, found: {chamber_texts}",
                            filter_url
                        )

            except requests.exceptions.RequestException as e:
                self.add_issue(
                    "MEDIUM", "HTTP_ERROR", "/committees",
                    f"Filter request failed for chamber={chamber}",
                    str(e),
                    filter_url
                )

    def test_committee_detail_pages(self) -> bool:
        """Test individual committee detail pages"""
        print("🔍 Testing committee detail pages...")

        # Get some committee IDs from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("""
            SELECT committee_id, name, chamber
            FROM committees
            WHERE parent_committee_id IS NULL
            LIMIT 5
        """)

        committees = cursor.fetchall()
        conn.close()

        if not committees:
            self.add_issue(
                "HIGH", "DATA_MISMATCH", "/committee/<id>",
                "No committees found in database",
                "Cannot test committee detail pages without committee data",
                None
            )
            return False

        for committee_id, name, chamber in committees:
            url = f"{self.base_url}/committee/{committee_id}"
            try:
                response = self.session.get(url, timeout=10)

                if response.status_code != 200:
                    self.add_issue(
                        "HIGH", "HTTP_ERROR", f"/committee/{committee_id}",
                        f"Committee detail page error for '{name}'",
                        f"HTTP {response.status_code}",
                        url
                    )
                    continue

                if BS4_AVAILABLE:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Check if committee name appears on page
                    if name not in response.text:
                        self.add_issue(
                            "HIGH", "DATA_MISMATCH", f"/committee/{committee_id}",
                            f"Committee name '{name}' not found on detail page",
                            "Committee name should appear on its detail page",
                            url
                        )

                    # Check for breadcrumbs
                    breadcrumb = soup.find('nav', attrs={'aria-label': 'breadcrumb'})
                    if not breadcrumb:
                        self.add_issue(
                            "LOW", "NAVIGATION", f"/committee/{committee_id}",
                            "Missing breadcrumb navigation",
                            "Committee detail pages should have breadcrumb navigation",
                            url
                        )

            except requests.exceptions.RequestException as e:
                self.add_issue(
                    "HIGH", "HTTP_ERROR", f"/committee/{committee_id}",
                    f"Request failed for committee '{name}'",
                    str(e),
                    url
                )

        return True

    def compare_data_consistency(self):
        """Compare database data with rendered page data"""
        print("🔍 Comparing database vs. rendered data...")

        try:
            db_committees = self.get_database_committees()

            # Get the main committees page
            response = self.session.get(f"{self.base_url}/committees", timeout=10)
            if response.status_code != 200:
                return

            if not BS4_AVAILABLE:
                print("⚠️  Skipping data comparison (BeautifulSoup4 not available)")
                return

            soup = BeautifulSoup(response.text, 'html.parser')

            # Count displayed committees by chamber
            displayed_counts = {}
            for chamber in ['House', 'Senate', 'Joint']:
                chamber_section = soup.find('h2', string=lambda t: t and f'{chamber} Committees' in t)
                if chamber_section:
                    # Find the count in the subtitle
                    subtitle = chamber_section.find_next_sibling('p')
                    if subtitle and 'committees' in subtitle.get_text():
                        import re
                        count_match = re.search(r'(\d+)', subtitle.get_text())
                        if count_match:
                            displayed_counts[chamber] = int(count_match.group(1))

            # Compare with database counts
            db_counts = {}
            for committee in db_committees:
                chamber = committee['chamber']
                db_counts[chamber] = db_counts.get(chamber, 0) + 1

            for chamber in ['House', 'Senate', 'Joint']:
                db_count = db_counts.get(chamber, 0)
                displayed_count = displayed_counts.get(chamber, 0)

                if db_count != displayed_count:
                    self.add_issue(
                        "MEDIUM", "DATA_MISMATCH", "/committees",
                        f"{chamber} committee count mismatch",
                        f"Database: {db_count}, Displayed: {displayed_count}",
                        f"{self.base_url}/committees"
                    )

        except Exception as e:
            self.add_issue(
                "MEDIUM", "DATA_MISMATCH", "/committees",
                f"Data comparison failed: {str(e)}",
                "Unable to compare database and rendered data",
                f"{self.base_url}/committees"
            )

    def run_all_tests(self) -> List[UIIssue]:
        """Run all HTTP tests"""
        print("🚀 Starting HTTP committee interface tests...")

        if not self.start_server():
            self.add_issue(
                "HIGH", "HTTP_ERROR", "server",
                "Unable to start Flask server",
                "Cannot run HTTP tests without server",
                None
            )
            return self.issues

        try:
            # Wait a moment for server to fully initialize
            time.sleep(2)

            # Run tests
            if self.test_committees_page():
                self.test_committee_detail_pages()
                self.compare_data_consistency()

        finally:
            self.stop_server()

        print(f"✅ HTTP tests complete. Found {len(self.issues)} issues.")
        return self.issues

    def generate_report(self, output_file: str = None) -> str:
        """Generate HTTP test report"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"audit_tools/reports/http_test_report_{timestamp}.md"

        # Group issues by severity
        high_issues = [i for i in self.issues if i.severity == "HIGH"]
        medium_issues = [i for i in self.issues if i.severity == "MEDIUM"]
        low_issues = [i for i in self.issues if i.severity == "LOW"]

        report = f"""# Committee HTTP Interface Test Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Base URL: {self.base_url}
Database: {self.db_path}

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
- **Page**: {issue.page}
- **URL**: {issue.url or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Medium Severity Issues\n"
        for issue in medium_issues:
            report += f"""
### {issue.category}: {issue.message}
- **Page**: {issue.page}
- **URL**: {issue.url or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Low Severity Issues\n"
        for issue in low_issues:
            report += f"""
### {issue.category}: {issue.message}
- **Page**: {issue.page}
- **URL**: {issue.url or 'N/A'}
- **Details**: {issue.details}
"""

        # Write report to file
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(report)

        return output_file


if __name__ == "__main__":
    import os

    tester = CommitteeHTTPTester()
    issues = tester.run_all_tests()

    report_file = tester.generate_report()
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