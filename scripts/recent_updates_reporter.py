#!/usr/bin/env python3
"""
Recent Updates Reporter

Generates a human-readable summary of recent database updates,
showing what hearings, committees, and witnesses were changed.

Usage:
    python scripts/recent_updates_reporter.py [--days 7] [--format text|json|markdown]
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class RecentUpdatesReporter:
    """Generate reports on recent database updates"""

    def __init__(self, db_path: str = None):
        self.db = DatabaseManager(db_path) if db_path else DatabaseManager()

    def get_recent_updates(self, days: int = 7) -> Dict[str, Any]:
        """
        Get summary of updates from the last N days

        Args:
            days: Number of days to look back

        Returns:
            Dict with update summary
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()

        with self.db.transaction() as conn:
            # Get recent update logs
            cursor = conn.execute('''
                SELECT
                    start_time,
                    end_time,
                    duration_seconds,
                    hearings_checked,
                    hearings_updated,
                    hearings_added,
                    committees_updated,
                    witnesses_updated,
                    success,
                    error_count
                FROM update_logs
                WHERE start_time >= ?
                ORDER BY start_time DESC
            ''', (cutoff_str,))

            updates = []
            for row in cursor.fetchall():
                updates.append({
                    'start_time': row[0],
                    'end_time': row[1],
                    'duration_seconds': row[2],
                    'hearings_checked': row[3],
                    'hearings_updated': row[4],
                    'hearings_added': row[5],
                    'committees_updated': row[6],
                    'witnesses_updated': row[7],
                    'success': bool(row[8]),
                    'error_count': row[9]
                })

            # Get recently modified hearings with details
            cursor = conn.execute('''
                SELECT
                    h.event_id,
                    h.title,
                    h.hearing_date_only,
                    h.chamber,
                    h.updated_at,
                    GROUP_CONCAT(c.name, '; ') as committees
                FROM hearings h
                LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                LEFT JOIN committees c ON hc.committee_id = c.committee_id
                WHERE h.updated_at >= ?
                GROUP BY h.hearing_id
                ORDER BY h.updated_at DESC
                LIMIT 50
            ''', (cutoff_str,))

            recent_hearings = []
            for row in cursor.fetchall():
                recent_hearings.append({
                    'event_id': row[0],
                    'title': row[1],
                    'hearing_date': row[2],
                    'chamber': row[3],
                    'updated_at': row[4],
                    'committees': row[5] or 'Unknown'
                })

            # Get recently added witnesses
            cursor = conn.execute('''
                SELECT
                    w.full_name,
                    w.organization,
                    w.title as witness_title,
                    w.created_at,
                    COUNT(wa.appearance_id) as appearance_count
                FROM witnesses w
                LEFT JOIN witness_appearances wa ON w.witness_id = wa.witness_id
                WHERE w.created_at >= ?
                GROUP BY w.witness_id
                ORDER BY w.created_at DESC
                LIMIT 50
            ''', (cutoff_str,))

            recent_witnesses = []
            for row in cursor.fetchall():
                recent_witnesses.append({
                    'name': row[0],
                    'organization': row[1] or 'Unknown',
                    'title': row[2] or 'N/A',
                    'created_at': row[3],
                    'appearance_count': row[4]
                })

        return {
            'generated_at': datetime.now().isoformat(),
            'days_lookback': days,
            'update_runs': updates,
            'recent_hearings': recent_hearings,
            'recent_witnesses': recent_witnesses,
            'summary': {
                'total_update_runs': len(updates),
                'total_hearings_modified': len(recent_hearings),
                'total_witnesses_added': len(recent_witnesses),
                'total_hearings_checked': sum(u['hearings_checked'] for u in updates),
                'total_hearings_updated': sum(u['hearings_updated'] for u in updates),
                'total_hearings_added': sum(u['hearings_added'] for u in updates),
            }
        }

    def format_as_text(self, data: Dict[str, Any]) -> str:
        """Format update summary as human-readable text"""
        lines = []
        lines.append("=" * 80)
        lines.append("RECENT UPDATES SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Generated: {data['generated_at']}")
        lines.append(f"Lookback Period: {data['days_lookback']} days")
        lines.append("")

        # Summary
        summary = data['summary']
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"  Update Runs: {summary['total_update_runs']}")
        lines.append(f"  Hearings Checked: {summary['total_hearings_checked']}")
        lines.append(f"  Hearings Updated: {summary['total_hearings_updated']}")
        lines.append(f"  Hearings Added: {summary['total_hearings_added']}")
        lines.append(f"  Witnesses Added: {summary['total_witnesses_added']}")
        lines.append("")

        # Update runs
        if data['update_runs']:
            lines.append("RECENT UPDATE RUNS")
            lines.append("-" * 80)
            for update in data['update_runs']:
                start = datetime.fromisoformat(update['start_time'])
                status = "✅ SUCCESS" if update['success'] else "❌ FAILED"
                lines.append(f"  {start.strftime('%Y-%m-%d %H:%M:%S')} | {status}")
                duration = f"{update['duration_seconds']:.1f}s" if update['duration_seconds'] is not None else "N/A"
                lines.append(f"    Duration: {duration}")
                lines.append(f"    Checked: {update['hearings_checked']} | "
                           f"Updated: {update['hearings_updated']} | "
                           f"Added: {update['hearings_added']}")
                if update['error_count'] > 0:
                    lines.append(f"    ⚠️  Errors: {update['error_count']}")
                lines.append("")

        # Recent hearings
        if data['recent_hearings']:
            lines.append("RECENTLY MODIFIED HEARINGS (Last 50)")
            lines.append("-" * 80)
            for hearing in data['recent_hearings'][:20]:  # Show first 20
                updated = datetime.fromisoformat(hearing['updated_at'])
                lines.append(f"  [{hearing['chamber']}] {hearing['hearing_date'] or 'TBD'}")
                title = hearing['title'][:70] + "..." if len(hearing['title']) > 70 else hearing['title']
                lines.append(f"    {title}")
                lines.append(f"    Committees: {hearing['committees']}")
                lines.append(f"    Updated: {updated.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")

            if len(data['recent_hearings']) > 20:
                lines.append(f"  ... and {len(data['recent_hearings']) - 20} more")
                lines.append("")

        # Recent witnesses
        if data['recent_witnesses']:
            lines.append("RECENTLY ADDED WITNESSES (Last 50)")
            lines.append("-" * 80)
            for witness in data['recent_witnesses'][:20]:  # Show first 20
                created = datetime.fromisoformat(witness['created_at'])
                lines.append(f"  {witness['name']}")
                lines.append(f"    Organization: {witness['organization']}")
                lines.append(f"    Title: {witness['title']}")
                lines.append(f"    Appearances: {witness['appearance_count']}")
                lines.append(f"    Added: {created.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")

            if len(data['recent_witnesses']) > 20:
                lines.append(f"  ... and {len(data['recent_witnesses']) - 20} more")
                lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def format_as_markdown(self, data: Dict[str, Any]) -> str:
        """Format update summary as Markdown"""
        lines = []
        lines.append("# Recent Updates Summary")
        lines.append("")
        lines.append(f"**Generated**: {data['generated_at']}")
        lines.append(f"**Lookback Period**: {data['days_lookback']} days")
        lines.append("")

        # Summary
        summary = data['summary']
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Update Runs**: {summary['total_update_runs']}")
        lines.append(f"- **Hearings Checked**: {summary['total_hearings_checked']}")
        lines.append(f"- **Hearings Updated**: {summary['total_hearings_updated']}")
        lines.append(f"- **Hearings Added**: {summary['total_hearings_added']}")
        lines.append(f"- **Witnesses Added**: {summary['total_witnesses_added']}")
        lines.append("")

        # Update runs
        if data['update_runs']:
            lines.append("## Recent Update Runs")
            lines.append("")
            lines.append("| Date/Time | Status | Duration | Checked | Updated | Added | Errors |")
            lines.append("|-----------|--------|----------|---------|---------|-------|--------|")
            for update in data['update_runs']:
                start = datetime.fromisoformat(update['start_time'])
                status = "✅" if update['success'] else "❌"
                duration = f"{update['duration_seconds']:.1f}s" if update['duration_seconds'] is not None else "N/A"
                lines.append(
                    f"| {start.strftime('%Y-%m-%d %H:%M')} | {status} | "
                    f"{duration} | "
                    f"{update['hearings_checked']} | "
                    f"{update['hearings_updated']} | "
                    f"{update['hearings_added']} | "
                    f"{update['error_count']} |"
                )
            lines.append("")

        # Recent hearings
        if data['recent_hearings']:
            lines.append("## Recently Modified Hearings")
            lines.append("")
            for hearing in data['recent_hearings'][:20]:
                updated = datetime.fromisoformat(hearing['updated_at'])
                lines.append(f"### [{hearing['chamber']}] {hearing['hearing_date'] or 'TBD'}")
                lines.append(f"**Title**: {hearing['title']}")
                lines.append(f"**Committees**: {hearing['committees']}")
                lines.append(f"**Updated**: {updated.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")

        # Recent witnesses
        if data['recent_witnesses']:
            lines.append("## Recently Added Witnesses")
            lines.append("")
            for witness in data['recent_witnesses'][:20]:
                created = datetime.fromisoformat(witness['created_at'])
                lines.append(f"### {witness['name']}")
                lines.append(f"- **Organization**: {witness['organization']}")
                lines.append(f"- **Title**: {witness['title']}")
                lines.append(f"- **Appearances**: {witness['appearance_count']}")
                lines.append(f"- **Added**: {created.strftime('%Y-%m-%d %H:%M:%S')}")
                lines.append("")

        return "\n".join(lines)

    def generate_report(self, days: int = 7, format: str = 'text', output_file: str = None) -> str:
        """
        Generate a recent updates report

        Args:
            days: Number of days to look back
            format: Output format (text, json, markdown)
            output_file: Optional file path to write report to

        Returns:
            Report as string
        """
        logger.info(f"Generating recent updates report (last {days} days, format={format})")

        data = self.get_recent_updates(days)

        if format == 'json':
            report = json.dumps(data, indent=2)
        elif format == 'markdown':
            report = self.format_as_markdown(data)
        else:  # text
            report = self.format_as_text(data)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            logger.info(f"Report written to {output_file}")

        return report


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(description='Generate recent updates report')
    parser.add_argument('--days', type=int, default=7, help='Days to look back (default: 7)')
    parser.add_argument('--format', choices=['text', 'json', 'markdown'], default='text',
                       help='Output format (default: text)')
    parser.add_argument('--output', '-o', type=str, help='Output file path')
    parser.add_argument('--db', type=str, help='Database path (default: database.db)')

    args = parser.parse_args()

    reporter = RecentUpdatesReporter(db_path=args.db)
    report = reporter.generate_report(days=args.days, format=args.format, output_file=args.output)

    if not args.output:
        print(report)


if __name__ == '__main__':
    main()
