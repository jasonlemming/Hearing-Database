#!/usr/bin/env python3
"""
Template Style Consistency Analyzer
Compares styling patterns across templates to identify inconsistencies
"""

import re
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class StyleIssue:
    severity: str  # HIGH, MEDIUM, LOW
    category: str  # BOOTSTRAP, CSS, HTML_STRUCTURE, ICON_USAGE, ACCESSIBILITY
    file: str
    message: str
    details: str
    line_number: Optional[int] = None


class TemplateStyleAnalyzer:
    """Analyzes template files for styling consistency"""

    def __init__(self, templates_dir: str = "web/templates"):
        self.templates_dir = Path(templates_dir)
        self.issues: List[StyleIssue] = []
        self.templates: Dict[str, str] = {}
        self.load_templates()

    def add_issue(self, severity: str, category: str, file: str, message: str,
                  details: str, line_number: Optional[int] = None):
        """Add style issue to the list"""
        self.issues.append(StyleIssue(
            severity=severity,
            category=category,
            file=file,
            message=message,
            details=details,
            line_number=line_number
        ))

    def load_templates(self):
        """Load all template files"""
        if not self.templates_dir.exists():
            print(f"❌ Templates directory not found: {self.templates_dir}")
            return

        for template_file in self.templates_dir.glob("*.html"):
            try:
                with open(template_file, 'r', encoding='utf-8') as f:
                    self.templates[template_file.name] = f.read()
            except Exception as e:
                print(f"⚠️  Error reading {template_file}: {e}")

        print(f"📁 Loaded {len(self.templates)} template files")

    def analyze_bootstrap_usage(self):
        """Analyze Bootstrap class usage consistency"""
        print("🔍 Analyzing Bootstrap usage...")

        # Common Bootstrap patterns to check
        bootstrap_patterns = {
            'cards': r'class="[^"]*card[^"]*"',
            'buttons': r'class="[^"]*btn[^"]*"',
            'badges': r'class="[^"]*badge[^"]*"',
            'containers': r'class="[^"]*container[^"]*"',
            'rows': r'class="[^"]*row[^"]*"',
            'cols': r'class="[^"]*col[^"]*"',
            'forms': r'class="[^"]*form[^"]*"',
            'navs': r'class="[^"]*nav[^"]*"'
        }

        usage_by_template = {}
        for template_name, content in self.templates.items():
            usage_by_template[template_name] = {}
            for pattern_name, pattern in bootstrap_patterns.items():
                matches = re.findall(pattern, content, re.IGNORECASE)
                usage_by_template[template_name][pattern_name] = matches

        # Analyze committees.html specifically
        committees_content = self.templates.get('committees.html', '')
        if committees_content:
            # Check for inconsistent Bootstrap versions
            if 'bootstrap@5.1.3' not in committees_content and 'base.html' in self.templates:
                base_content = self.templates['base.html']
                if 'bootstrap@5.1.3' in base_content:
                    self.add_issue(
                        "LOW", "BOOTSTRAP", "committees.html",
                        "Bootstrap version consistency should be verified",
                        "All templates should use the same Bootstrap version from base.html",
                    )

            # Check for old Bootstrap classes
            old_classes = ['float-left', 'float-right', 'text-left', 'text-right', 'ml-', 'mr-', 'pl-', 'pr-']
            for old_class in old_classes:
                if old_class in committees_content:
                    self.add_issue(
                        "MEDIUM", "BOOTSTRAP", "committees.html",
                        f"Deprecated Bootstrap class: {old_class}",
                        "Should use Bootstrap 5 utility classes (ms-, me-, ps-, pe-, text-start, text-end)",
                    )

    def analyze_icon_usage(self):
        """Analyze FontAwesome icon usage consistency"""
        print("🔍 Analyzing icon usage...")

        icon_pattern = r'<i class="[^"]*fa[s]?[^"]*"[^>]*></i>'
        icon_usage = {}

        for template_name, content in self.templates.items():
            icons = re.findall(icon_pattern, content)
            icon_usage[template_name] = icons

        # Compare committees.html with other templates
        committees_icons = icon_usage.get('committees.html', [])
        other_template_icons = []
        for name, icons in icon_usage.items():
            if name != 'committees.html':
                other_template_icons.extend(icons)

        # Check for icon consistency patterns
        committees_content = self.templates.get('committees.html', '')
        if committees_content:
            # Check if icons are consistently used with me-* spacing classes
            icon_lines = []
            for i, line in enumerate(committees_content.split('\n'), 1):
                if 'fas fa-' in line:
                    icon_lines.append((i, line.strip()))

            missing_spacing = []
            for line_num, line in icon_lines:
                if 'me-' not in line and 'ms-' not in line:
                    # Check if this icon is followed by text (needs spacing)
                    if '</i>' in line and line.index('</i>') < len(line) - 4:
                        missing_spacing.append(line_num)

            if missing_spacing:
                self.add_issue(
                    "LOW", "ICON_USAGE", "committees.html",
                    "Icons missing consistent spacing classes",
                    f"Lines {missing_spacing} have icons that might need me-* or ms-* spacing classes",
                )

    def analyze_html_structure(self):
        """Analyze HTML structure consistency"""
        print("🔍 Analyzing HTML structure...")

        committees_content = self.templates.get('committees.html', '')
        if not committees_content:
            return

        # Check for consistent card structure
        card_pattern = r'<div class="[^"]*card[^"]*">'
        cards = re.findall(card_pattern, committees_content)

        # Check for accessibility issues
        accessibility_checks = [
            (r'<button[^>]*>', r'aria-label|aria-describedby|aria-expanded', "Buttons should have ARIA attributes"),
            (r'<select[^>]*>', r'aria-label|id.*for=', "Select elements should be properly labeled"),
            (r'<input[^>]*>', r'aria-label|id.*for=', "Input elements should be properly labeled"),
            (r'data-bs-toggle="collapse"', r'aria-expanded', "Collapse toggles should have aria-expanded"),
        ]

        for element_pattern, aria_pattern, message in accessibility_checks:
            elements = re.findall(element_pattern, committees_content, re.IGNORECASE)
            for element in elements:
                if not re.search(aria_pattern, element, re.IGNORECASE):
                    # Find the line number
                    lines = committees_content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if element in line:
                            self.add_issue(
                                "MEDIUM", "ACCESSIBILITY", "committees.html",
                                "Missing accessibility attributes",
                                message,
                                i
                            )
                            break

    def analyze_css_classes(self):
        """Analyze CSS class usage patterns"""
        print("🔍 Analyzing CSS classes...")

        committees_content = self.templates.get('committees.html', '')
        base_content = self.templates.get('base.html', '')

        if not committees_content:
            return

        # Extract custom CSS classes from base.html
        custom_classes = set()
        if base_content:
            style_section = re.search(r'<style>(.*?)</style>', base_content, re.DOTALL)
            if style_section:
                css_content = style_section.group(1)
                # Find class definitions
                class_matches = re.findall(r'\.([a-zA-Z][a-zA-Z0-9_-]*)', css_content)
                custom_classes.update(class_matches)

        # Check if committees.html uses custom classes consistently
        committees_classes = re.findall(r'class="([^"]*)"', committees_content)
        for class_attr in committees_classes:
            classes = class_attr.split()
            for cls in classes:
                if cls in custom_classes:
                    # Verify the class is used appropriately
                    if cls == 'collapse-toggle' and 'data-bs-toggle="collapse"' not in committees_content:
                        self.add_issue(
                            "MEDIUM", "CSS", "committees.html",
                            f"Custom class '{cls}' used without proper Bootstrap integration",
                            "collapse-toggle class should be used with data-bs-toggle=\"collapse\"",
                        )

    def compare_with_other_templates(self):
        """Compare committees.html structure with other templates"""
        print("🔍 Comparing with other templates...")

        committees_content = self.templates.get('committees.html', '')
        if not committees_content:
            return

        # Compare filter sections
        other_templates_with_filters = ['hearings.html']
        for template_name in other_templates_with_filters:
            if template_name in self.templates:
                other_content = self.templates[template_name]

                # Compare filter form structures
                committees_form = re.search(r'<form[^>]*>.*?</form>', committees_content, re.DOTALL)
                other_form = re.search(r'<form[^>]*>.*?</form>', other_content, re.DOTALL)

                if committees_form and other_form:
                    # Check for consistent form structure
                    committees_form_classes = re.findall(r'class="([^"]*)"', committees_form.group(0))
                    other_form_classes = re.findall(r'class="([^"]*)"', other_form.group(0))

                    # Look for inconsistent class usage
                    committees_flat = [cls for class_list in committees_form_classes for cls in class_list.split()]
                    other_flat = [cls for class_list in other_form_classes for cls in class_list.split()]

                    # Check for common patterns
                    if 'row g-3' in ' '.join(committees_flat) and 'row g-3' not in ' '.join(other_flat):
                        self.add_issue(
                            "LOW", "HTML_STRUCTURE", "committees.html",
                            f"Form structure differs from {template_name}",
                            "Filter forms should use consistent Bootstrap grid classes",
                        )

    def analyze_responsive_design(self):
        """Analyze responsive design patterns"""
        print("🔍 Analyzing responsive design...")

        committees_content = self.templates.get('committees.html', '')
        if not committees_content:
            return

        # Check for consistent responsive breakpoints
        responsive_patterns = [
            'col-md-', 'col-lg-', 'col-sm-', 'col-xl-',
            'd-none', 'd-block', 'd-md-', 'd-lg-'
        ]

        found_responsive = []
        for pattern in responsive_patterns:
            if pattern in committees_content:
                found_responsive.append(pattern)

        # Check if responsive classes are used consistently
        col_classes = re.findall(r'col-[a-z]*-[0-9]+', committees_content)
        unique_breakpoints = set()
        for col_class in col_classes:
            parts = col_class.split('-')
            if len(parts) >= 2:
                breakpoint = '-'.join(parts[:2])  # e.g., 'col-md'
                unique_breakpoints.add(breakpoint)

        if len(unique_breakpoints) > 3:
            self.add_issue(
                "LOW", "HTML_STRUCTURE", "committees.html",
                "Many different responsive breakpoints used",
                f"Found breakpoints: {sorted(unique_breakpoints)}. Consider consolidating for consistency.",
            )

    def run_all_analyses(self) -> List[StyleIssue]:
        """Run all style analyses"""
        print("🚀 Starting comprehensive style analysis...")

        if not self.templates:
            self.add_issue(
                "HIGH", "HTML_STRUCTURE", "templates",
                "No template files found",
                f"Could not load templates from {self.templates_dir}",
            )
            return self.issues

        self.analyze_bootstrap_usage()
        self.analyze_icon_usage()
        self.analyze_html_structure()
        self.analyze_css_classes()
        self.compare_with_other_templates()
        self.analyze_responsive_design()

        print(f"✅ Style analysis complete. Found {len(self.issues)} issues.")
        return self.issues

    def generate_report(self, output_file: str = None) -> str:
        """Generate style analysis report"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"audit_tools/reports/style_analysis_report_{timestamp}.md"

        # Group issues by severity
        high_issues = [i for i in self.issues if i.severity == "HIGH"]
        medium_issues = [i for i in self.issues if i.severity == "MEDIUM"]
        low_issues = [i for i in self.issues if i.severity == "LOW"]

        report = f"""# Template Style Consistency Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Templates Directory: {self.templates_dir}
Templates Analyzed: {len(self.templates)}

## Summary
- **Total Issues**: {len(self.issues)}
- **High Severity**: {len(high_issues)}
- **Medium Severity**: {len(medium_issues)}
- **Low Severity**: {len(low_issues)}

## Template Files Analyzed
"""
        for template_name in sorted(self.templates.keys()):
            report += f"- {template_name}\n"

        report += "\n## High Severity Issues\n"
        for issue in high_issues:
            report += f"""
### {issue.category}: {issue.message}
- **File**: {issue.file}
- **Line**: {issue.line_number or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Medium Severity Issues\n"
        for issue in medium_issues:
            report += f"""
### {issue.category}: {issue.message}
- **File**: {issue.file}
- **Line**: {issue.line_number or 'N/A'}
- **Details**: {issue.details}
"""

        report += "\n## Low Severity Issues\n"
        for issue in low_issues:
            report += f"""
### {issue.category}: {issue.message}
- **File**: {issue.file}
- **Line**: {issue.line_number or 'N/A'}
- **Details**: {issue.details}
"""

        # Write report to file
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(report)

        return output_file


if __name__ == "__main__":
    analyzer = TemplateStyleAnalyzer()
    issues = analyzer.run_all_analyses()

    report_file = analyzer.generate_report()
    print(f"📋 Report saved to: {report_file}")

    # Print summary
    if issues:
        print("\n⚠️  Issues found:")
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            severity_issues = [i for i in issues if i.severity == severity]
            if severity_issues:
                print(f"  {severity}: {len(severity_issues)} issues")
                for issue in severity_issues[:3]:  # Show first 3 issues of each severity
                    print(f"    - {issue.category}: {issue.message}")
                if len(severity_issues) > 3:
                    print(f"    ... and {len(severity_issues) - 3} more")
    else:
        print("\n✅ No issues found!")