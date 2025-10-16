#!/usr/bin/env python3
"""
Post-Update Validation Script for Congressional Hearing Database

This script validates data quality and consistency after daily updates.
It checks for:
- Data integrity violations
- Anomalous data patterns
- Missing relationships
- Date range validity
- Duplicate records

Usage:
    python scripts/verify_updates.py [--verbose] [--fix] [--alert]
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class UpdateValidator:
    """Validates database after updates"""

    def __init__(self, db_path: str = None):
        self.db = DatabaseManager(db_path) if db_path else DatabaseManager()
        self.issues = []
        self.warnings = []
        self.stats = {}

    def run_all_checks(self, fix_issues: bool = False) -> Dict[str, Any]:
        """
        Run all validation checks

        Args:
            fix_issues: If True, attempt to fix issues automatically

        Returns:
            Dict with validation results
        """
        logger.info("Starting post-update validation")

        # Run all check methods
        self.check_data_counts()
        self.check_date_ranges()
        self.check_foreign_keys()
        self.check_duplicates()
        self.check_missing_relationships()
        self.check_anomalies()
        self.check_recent_update()

        # Attempt fixes if requested
        if fix_issues and self.issues:
            self.fix_issues()

        return {
            'timestamp': datetime.now().isoformat(),
            'passed': len(self.issues) == 0,
            'issues': self.issues,
            'warnings': self.warnings,
            'stats': self.stats
        }

    def check_data_counts(self):
        """Check if record counts are reasonable"""
        logger.info("Checking data counts...")

        try:
            counts = self.db.get_table_counts()
            self.stats['counts'] = counts

            # Check for suspicious counts
            if counts.get('hearings', 0) < 1000:
                self.warnings.append(f"Low hearing count: {counts['hearings']} (expected >= 1000)")

            if counts.get('committees', 0) < 200:
                self.warnings.append(f"Low committee count: {counts['committees']} (expected >= 200)")

            if counts.get('witnesses', 0) < 1500:
                self.warnings.append(f"Low witness count: {counts['witnesses']} (expected >= 1500)")

            # Check for zero counts (critical)
            # Note: bills and hearing_bills are out of scope, so ignore those
            excluded_tables = {'bills', 'hearing_bills'}
            for table, count in counts.items():
                if count == 0 and table not in excluded_tables:
                    self.issues.append(f"CRITICAL: Table '{table}' is empty")

            logger.info(f"Data counts: {counts}")

        except Exception as e:
            self.issues.append(f"Failed to check data counts: {e}")

    def check_date_ranges(self):
        """Validate date ranges are reasonable"""
        logger.info("Checking date ranges...")

        try:
            with self.db.transaction() as conn:
                # Check hearing dates
                cursor = conn.execute('''
                    SELECT MIN(hearing_date_only), MAX(hearing_date_only), COUNT(*)
                    FROM hearings
                    WHERE hearing_date_only IS NOT NULL
                ''')
                row = cursor.fetchone()
                min_date, max_date, count = row[0], row[1], row[2]

                if min_date and max_date:
                    # Convert dates to string if they're datetime objects (PostgreSQL)
                    min_date_str = min_date.isoformat() if hasattr(min_date, 'isoformat') else min_date
                    max_date_str = max_date.isoformat() if hasattr(max_date, 'isoformat') else max_date

                    self.stats['hearing_date_range'] = {
                        'min': min_date_str,
                        'max': max_date_str,
                        'count': count
                    }

                    # Warn if dates are in future (more than 1 year)
                    future_cutoff = (datetime.now() + timedelta(days=365)).date()
                    max_date_obj = max_date if hasattr(max_date, 'year') else datetime.fromisoformat(max_date).date()
                    if max_date_obj > future_cutoff:
                        self.warnings.append(f"Latest hearing date is far in future: {max_date_str}")

                    # Warn if dates are too old (more than 2 years ago)
                    old_cutoff = (datetime.now() - timedelta(days=730)).date()
                    min_date_obj = min_date if hasattr(min_date, 'year') else datetime.fromisoformat(min_date).date()
                    if min_date_obj < old_cutoff:
                        self.warnings.append(f"Earliest hearing date is very old: {min_date_str}")

                # Check for hearings with missing dates
                cursor = conn.execute('SELECT COUNT(*) FROM hearings WHERE hearing_date_only IS NULL')
                missing_dates = cursor.fetchone()[0]
                if missing_dates > 0:
                    self.warnings.append(f"{missing_dates} hearings missing dates")
                    self.stats['missing_dates'] = missing_dates

        except Exception as e:
            self.issues.append(f"Failed to check date ranges: {e}")

    def check_foreign_keys(self):
        """Check for foreign key violations"""
        logger.info("Checking foreign key integrity...")

        try:
            # Detect if we're using PostgreSQL or SQLite
            is_postgres = os.environ.get('POSTGRES_URL') or os.environ.get('DATABASE_URL', '').startswith('postgres')

            with self.db.transaction() as conn:
                if not is_postgres:
                    # SQLite: Use PRAGMA
                    conn.execute('PRAGMA foreign_keys = ON')
                    cursor = conn.execute('PRAGMA foreign_key_check')
                    violations = cursor.fetchall()

                    if violations:
                        for violation in violations:
                            self.issues.append(f"Foreign key violation: {violation}")
                        self.stats['fk_violations'] = len(violations)
                    else:
                        logger.info("No foreign key violations found")
                        self.stats['fk_violations'] = 0
                else:
                    # PostgreSQL: Foreign keys are always enforced, just note that
                    logger.info("PostgreSQL enforces foreign key constraints automatically")
                    self.stats['fk_violations'] = 0

        except Exception as e:
            self.issues.append(f"Failed to check foreign keys: {e}")

    def check_duplicates(self):
        """Check for duplicate records"""
        logger.info("Checking for duplicates...")

        try:
            with self.db.transaction() as conn:
                # Check duplicate hearings
                cursor = conn.execute('''
                    SELECT event_id, COUNT(*) as count
                    FROM hearings
                    GROUP BY event_id
                    HAVING count > 1
                ''')
                dup_hearings = cursor.fetchall()
                if dup_hearings:
                    self.issues.append(f"Found {len(dup_hearings)} duplicate hearings (by event_id)")
                    self.stats['duplicate_hearings'] = len(dup_hearings)

                # Check duplicate witnesses (same name + org)
                cursor = conn.execute('''
                    SELECT full_name, organization, COUNT(*) as count
                    FROM witnesses
                    WHERE organization IS NOT NULL
                    GROUP BY full_name, organization
                    HAVING count > 1
                ''')
                dup_witnesses = cursor.fetchall()
                if dup_witnesses:
                    self.warnings.append(f"Found {len(dup_witnesses)} potential duplicate witnesses")
                    self.stats['duplicate_witnesses'] = len(dup_witnesses)

                # Check duplicate committee system_codes
                cursor = conn.execute('''
                    SELECT system_code, COUNT(*) as count
                    FROM committees
                    GROUP BY system_code
                    HAVING count > 1
                ''')
                dup_committees = cursor.fetchall()
                if dup_committees:
                    self.issues.append(f"Found {len(dup_committees)} duplicate committees (by system_code)")
                    self.stats['duplicate_committees'] = len(dup_committees)

        except Exception as e:
            self.issues.append(f"Failed to check duplicates: {e}")

    def check_missing_relationships(self):
        """Check for hearings missing critical relationships"""
        logger.info("Checking for missing relationships...")

        try:
            with self.db.transaction() as conn:
                # Hearings without committees
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM hearings h
                    WHERE NOT EXISTS (
                        SELECT 1 FROM hearing_committees hc WHERE hc.hearing_id = h.hearing_id
                    )
                ''')
                no_committees = cursor.fetchone()[0]
                if no_committees > 0:
                    self.warnings.append(f"{no_committees} hearings have no committee associations")
                    self.stats['hearings_no_committees'] = no_committees

                # Hearings without witnesses (not always an issue)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM hearings h
                    WHERE hearing_date_only < DATE('now', '-30 days')
                    AND NOT EXISTS (
                        SELECT 1 FROM witness_appearances wa WHERE wa.hearing_id = h.hearing_id
                    )
                ''')
                no_witnesses = cursor.fetchone()[0]
                if no_witnesses > 100:
                    self.warnings.append(f"{no_witnesses} past hearings have no witnesses")
                    self.stats['hearings_no_witnesses'] = no_witnesses

                # Committees without members (for current congress)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM committees c
                    WHERE c.is_current = 1
                    AND c.parent_committee_id IS NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM committee_memberships cm
                        WHERE cm.committee_id = c.committee_id AND cm.is_active = 1
                    )
                ''')
                no_members = cursor.fetchone()[0]
                if no_members > 0:
                    self.warnings.append(f"{no_members} active committees have no members")
                    self.stats['committees_no_members'] = no_members

        except Exception as e:
            self.issues.append(f"Failed to check missing relationships: {e}")

    def check_anomalies(self):
        """Check for anomalous data patterns"""
        logger.info("Checking for anomalies...")

        try:
            with self.db.transaction() as conn:
                # Check for sudden drops in hearing counts
                cursor = conn.execute('''
                    SELECT
                        DATE(hearing_date_only) as date,
                        COUNT(*) as count
                    FROM hearings
                    WHERE hearing_date_only >= DATE('now', '-90 days')
                    GROUP BY DATE(hearing_date_only)
                    ORDER BY date DESC
                    LIMIT 30
                ''')
                daily_counts = cursor.fetchall()

                if daily_counts:
                    counts = [row[1] for row in daily_counts]
                    avg_count = sum(counts) / len(counts) if counts else 0

                    # Check if recent count is significantly lower
                    if counts and counts[0] < avg_count * 0.3:
                        self.warnings.append(
                            f"Recent hearing count ({counts[0]}) much lower than average ({avg_count:.1f})"
                        )

                # Check for hearings with extremely long titles (> 500 chars)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM hearings WHERE LENGTH(title) > 500
                ''')
                long_titles = cursor.fetchone()[0]
                if long_titles > 50:
                    self.warnings.append(f"{long_titles} hearings have unusually long titles")

                # Check for hearings missing video URLs (recent hearings)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM hearings
                    WHERE hearing_date_only >= DATE('now', '-30 days')
                    AND (video_url IS NULL OR video_url = '')
                ''')
                no_video = cursor.fetchone()[0]
                total_recent = conn.execute('''
                    SELECT COUNT(*) FROM hearings
                    WHERE hearing_date_only >= DATE('now', '-30 days')
                ''').fetchone()[0]

                if total_recent > 0:
                    video_rate = (total_recent - no_video) / total_recent * 100
                    self.stats['recent_video_rate_pct'] = round(video_rate, 1)
                    if video_rate < 50:
                        self.warnings.append(f"Low video extraction rate: {video_rate:.1f}%")

                # NEW: Check for sudden spike in hearing additions (potential duplicate imports)
                cursor = conn.execute('''
                    SELECT hearings_added FROM update_logs
                    WHERE hearings_added > 0
                    ORDER BY start_time DESC
                    LIMIT 10
                ''')
                recent_additions = [row[0] for row in cursor.fetchall()]

                if len(recent_additions) >= 2:
                    latest = recent_additions[0]
                    avg_additions = sum(recent_additions[1:]) / len(recent_additions[1:])

                    if latest > avg_additions * 3 and latest > 50:
                        self.warnings.append(
                            f"Unusually high hearing additions: {latest} (avg: {avg_additions:.1f}) - check for duplicates"
                        )

                # NEW: Check for witnesses with missing organizations (data quality)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM witnesses
                    WHERE organization IS NULL OR organization = ''
                ''')
                missing_org = cursor.fetchone()[0]
                total_witnesses = conn.execute('SELECT COUNT(*) FROM witnesses').fetchone()[0]

                if total_witnesses > 0:
                    missing_org_rate = (missing_org / total_witnesses) * 100
                    self.stats['witnesses_missing_org_pct'] = round(missing_org_rate, 1)
                    if missing_org_rate > 30:
                        self.warnings.append(f"High rate of witnesses missing organization: {missing_org_rate:.1f}%")

                # NEW: Check for hearings with duplicate titles (potential data quality issue)
                cursor = conn.execute('''
                    SELECT title, COUNT(*) as count
                    FROM hearings
                    GROUP BY title
                    HAVING count > 5
                ''')
                duplicate_titles = cursor.fetchall()

                if duplicate_titles:
                    self.warnings.append(f"Found {len(duplicate_titles)} titles used more than 5 times")
                    self.stats['duplicate_titles'] = len(duplicate_titles)

                # NEW: Check for sudden increase in error rate
                cursor = conn.execute('''
                    SELECT error_count, hearings_checked FROM update_logs
                    WHERE hearings_checked > 0
                    ORDER BY start_time DESC
                    LIMIT 5
                ''')
                recent_error_rates = []
                for error_count, checked in cursor.fetchall():
                    if checked > 0:
                        recent_error_rates.append((error_count / checked) * 100)

                if len(recent_error_rates) >= 2:
                    latest_error_rate = recent_error_rates[0]
                    avg_error_rate = sum(recent_error_rates[1:]) / len(recent_error_rates[1:])

                    if latest_error_rate > avg_error_rate * 2 and latest_error_rate > 5:
                        self.warnings.append(
                            f"Error rate spike: {latest_error_rate:.1f}% (avg: {avg_error_rate:.1f}%)"
                        )

                # NEW: Check for hearing dates far in the future (> 2 years)
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM hearings
                    WHERE hearing_date_only > DATE('now', '+730 days')
                ''')
                far_future = cursor.fetchone()[0]
                if far_future > 0:
                    self.warnings.append(f"{far_future} hearings scheduled more than 2 years in future")

        except Exception as e:
            self.issues.append(f"Failed to check anomalies: {e}")

    def check_recent_update(self):
        """Check if recent update was successful"""
        logger.info("Checking recent update status...")

        try:
            with self.db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT start_time, end_time, duration_seconds,
                           hearings_updated, hearings_added, error_count, success
                    FROM update_logs
                    ORDER BY start_time DESC
                    LIMIT 1
                ''')
                last_update = cursor.fetchone()

                if last_update:
                    start_time, end_time, duration, updated, added, errors, success = last_update

                    # Handle both PostgreSQL (returns datetime objects) and SQLite (returns strings)
                    start_time_str = start_time.isoformat() if hasattr(start_time, 'isoformat') else start_time
                    end_time_str = end_time.isoformat() if hasattr(end_time, 'isoformat') else end_time

                    self.stats['last_update'] = {
                        'start_time': start_time_str,
                        'end_time': end_time_str,
                        'duration_seconds': duration,
                        'hearings_updated': updated,
                        'hearings_added': added,
                        'error_count': errors,
                        'success': bool(success)
                    }

                    if not success:
                        self.issues.append("Last update failed")

                    if errors and errors > 10:
                        self.warnings.append(f"Last update had {errors} errors")

                    # Check if update was recent (within 48 hours)
                    if start_time:
                        # Convert to datetime if it's a string
                        if isinstance(start_time, str):
                            start_dt = datetime.fromisoformat(start_time)
                        else:
                            start_dt = start_time
                        hours_ago = (datetime.now() - start_dt).total_seconds() / 3600
                        if hours_ago > 48:
                            self.warnings.append(f"Last update was {hours_ago:.1f} hours ago (> 48h)")
                else:
                    self.warnings.append("No update logs found")

        except Exception as e:
            self.issues.append(f"Failed to check recent update: {e}")

    def fix_issues(self):
        """Attempt to automatically fix common issues"""
        logger.info("Attempting to fix issues...")

        # For now, log that fixes would be applied
        # Future: implement specific fixes for each issue type
        logger.info(f"Found {len(self.issues)} issues that could be fixed automatically")
        for issue in self.issues:
            logger.info(f"  - {issue}")

    def print_report(self):
        """Print validation report to console"""
        print("\n" + "="*80)
        print("UPDATE VALIDATION REPORT")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Stats
        print("DATABASE STATISTICS:")
        print("-" * 80)
        if 'counts' in self.stats:
            for table, count in self.stats['counts'].items():
                print(f"  {table:30s}: {count:>8,}")
        print()

        if 'hearing_date_range' in self.stats:
            dr = self.stats['hearing_date_range']
            print(f"  Hearing Date Range: {dr['min']} to {dr['max']} ({dr['count']} hearings)")
            print()

        # Issues
        if self.issues:
            print("ISSUES FOUND:")
            print("-" * 80)
            for i, issue in enumerate(self.issues, 1):
                print(f"  {i}. {issue}")
            print()
        else:
            print("✓ NO ISSUES FOUND")
            print()

        # Warnings
        if self.warnings:
            print("WARNINGS:")
            print("-" * 80)
            for i, warning in enumerate(self.warnings, 1):
                print(f"  {i}. {warning}")
            print()
        else:
            print("✓ NO WARNINGS")
            print()

        # Overall status
        print("="*80)
        if not self.issues:
            print("✓ VALIDATION PASSED")
        else:
            print(f"✗ VALIDATION FAILED - {len(self.issues)} issue(s) found")
        print("="*80)
        print()

        return len(self.issues) == 0


# ============================================================================
# Phase 2.3.2: Historical Pattern Validation
# ============================================================================

from dataclasses import dataclass
import statistics


@dataclass
class HistoricalStats:
    """Statistical summary of a metric from historical data"""
    metric_name: str
    mean: float
    std_dev: float
    p5: float          # 5th percentile
    p95: float         # 95th percentile
    sample_size: int
    last_updated: datetime


@dataclass
class Anomaly:
    """Represents a detected anomaly in current metrics"""
    metric_name: str
    current_value: float
    expected_value: float  # mean or baseline
    z_score: float
    severity: str  # "warning", "critical"
    explanation: str
    confidence: float  # 0.0 to 1.0


class HistoricalValidator:
    """
    Validates current update metrics against historical patterns

    Uses statistical analysis (z-score, percentiles) to detect anomalies
    that static thresholds would miss.
    """

    def __init__(self, db: DatabaseManager, min_history_days: int = 17):
        """
        Initialize validator

        Args:
            db: Database manager instance
            min_history_days: Minimum days of history required (default: 17)
        """
        self.db = db
        self.min_history_days = min_history_days
        self._stats_cache = {}
        self._cache_timestamp = None

    def get_historical_data(self, days: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch historical update logs for analysis

        Args:
            days: Number of days to look back

        Returns:
            List of update log records
        """
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        with self.db.transaction() as conn:
            cursor = conn.execute('''
                SELECT
                    start_time,
                    hearings_checked,
                    hearings_updated,
                    hearings_added,
                    committees_updated,
                    witnesses_updated,
                    error_count,
                    duration_seconds
                FROM update_logs
                WHERE start_time >= ?
                AND hearings_checked > 0
                ORDER BY start_time ASC
            ''', (cutoff_str,))

            records = []
            for row in cursor.fetchall():
                records.append({
                    'start_time': row[0],
                    'hearings_checked': row[1],
                    'hearings_updated': row[2],
                    'hearings_added': row[3],
                    'committees_updated': row[4],
                    'witnesses_updated': row[5],
                    'error_count': row[6],
                    'duration_seconds': row[7] or 0
                })

            return records

    def calculate_stats(self, metric_name: str, values: List[float]) -> HistoricalStats:
        """
        Calculate statistical summary for a metric

        Args:
            metric_name: Name of the metric
            values: List of historical values

        Returns:
            HistoricalStats object with calculated statistics
        """
        if len(values) < 2:
            # Not enough data for statistics
            return None

        mean_val = statistics.mean(values)

        # Calculate standard deviation (need at least 2 points)
        if len(values) >= 2:
            std_dev = statistics.stdev(values)
        else:
            std_dev = 0.0

        # Calculate percentiles
        sorted_vals = sorted(values)
        p5_idx = max(0, int(len(sorted_vals) * 0.05))
        p95_idx = min(len(sorted_vals) - 1, int(len(sorted_vals) * 0.95))

        p5 = sorted_vals[p5_idx]
        p95 = sorted_vals[p95_idx]

        return HistoricalStats(
            metric_name=metric_name,
            mean=mean_val,
            std_dev=std_dev,
            p5=p5,
            p95=p95,
            sample_size=len(values),
            last_updated=datetime.now()
        )

    def calculate_all_stats(self, days: int = 30) -> Dict[str, HistoricalStats]:
        """
        Calculate statistics for all tracked metrics

        Args:
            days: Number of days of history to analyze

        Returns:
            Dict mapping metric names to HistoricalStats objects
        """
        # Check cache (valid for 24 hours)
        if self._cache_timestamp and self._stats_cache:
            cache_age = (datetime.now() - self._cache_timestamp).total_seconds() / 3600
            if cache_age < 24:
                logger.info(f"Using cached historical stats (age: {cache_age:.1f}h)")
                return self._stats_cache

        logger.info(f"Calculating historical statistics (last {days} days)")

        records = self.get_historical_data(days)

        if len(records) < self.min_history_days:
            logger.warning(f"Insufficient historical data: {len(records)} records (need >= {self.min_history_days})")
            return {}

        # Extract values for each metric
        metrics = {
            'hearings_checked': [r['hearings_checked'] for r in records],
            'hearings_updated': [r['hearings_updated'] for r in records],
            'hearings_added': [r['hearings_added'] for r in records],
            'committees_updated': [r['committees_updated'] for r in records],
            'witnesses_updated': [r['witnesses_updated'] for r in records],
            'error_count': [r['error_count'] for r in records],
        }

        # Calculate stats for each metric
        stats = {}
        for metric_name, values in metrics.items():
            stat = self.calculate_stats(metric_name, values)
            if stat:
                stats[metric_name] = stat
                logger.debug(f"{metric_name}: mean={stat.mean:.1f}, std={stat.std_dev:.1f}, "
                           f"p5={stat.p5:.1f}, p95={stat.p95:.1f}")

        # Cache results
        self._stats_cache = stats
        self._cache_timestamp = datetime.now()

        return stats

    def detect_anomalies(self, current_metrics: Dict[str, float],
                        z_threshold: float = 3.0) -> List[Anomaly]:
        """
        Detect anomalies in current metrics compared to historical patterns

        Args:
            current_metrics: Dict of current metric values
            z_threshold: Z-score threshold for anomaly detection (default: 3.0)

        Returns:
            List of detected Anomaly objects
        """
        stats = self.calculate_all_stats()

        if not stats:
            logger.info("No historical statistics available, skipping historical validation")
            return []

        anomalies = []

        for metric_name, current_value in current_metrics.items():
            if metric_name not in stats:
                continue

            stat = stats[metric_name]

            # Skip if no variation in historical data
            if stat.std_dev == 0:
                logger.debug(f"{metric_name}: No variation in historical data, skipping")
                continue

            # Calculate z-score
            z_score = (current_value - stat.mean) / stat.std_dev

            # Check for anomaly using z-score (3σ rule)
            if abs(z_score) > z_threshold:
                severity = "critical" if abs(z_score) > 4 else "warning"

                # Generate explanation
                direction = "higher" if z_score > 0 else "lower"
                explanation = (
                    f"{metric_name} is {abs(z_score):.1f} standard deviations {direction} "
                    f"than historical mean ({current_value:.0f} vs {stat.mean:.0f})"
                )

                anomaly = Anomaly(
                    metric_name=metric_name,
                    current_value=current_value,
                    expected_value=stat.mean,
                    z_score=z_score,
                    severity=severity,
                    explanation=explanation,
                    confidence=min(abs(z_score) / 5.0, 1.0)  # Confidence 0-1
                )

                anomalies.append(anomaly)
                logger.info(f"Anomaly detected: {explanation}")

            # Also check percentile method
            elif current_value < stat.p5 or current_value > stat.p95:
                severity = "warning"
                direction = "below 5th percentile" if current_value < stat.p5 else "above 95th percentile"
                explanation = f"{metric_name} is {direction} ({current_value:.0f} vs {stat.p5:.0f}-{stat.p95:.0f})"

                anomaly = Anomaly(
                    metric_name=metric_name,
                    current_value=current_value,
                    expected_value=stat.mean,
                    z_score=z_score,
                    severity=severity,
                    explanation=explanation,
                    confidence=0.7  # Lower confidence for percentile method
                )

                anomalies.append(anomaly)
                logger.info(f"Anomaly detected: {explanation}")

        return anomalies

    def should_alert(self, anomalies: List[Anomaly]) -> bool:
        """
        Determine if anomalies warrant an alert

        Uses multi-signal approach: requires 2+ anomalies OR 1 critical anomaly

        Args:
            anomalies: List of detected anomalies

        Returns:
            True if alert should be sent
        """
        if not anomalies:
            return False

        critical = [a for a in anomalies if a.severity == "critical"]

        # Alert if 2+ anomalies OR 1+ critical anomalies
        return len(anomalies) >= 2 or len(critical) >= 1


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Validate database after updates')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--fix', action='store_true', help='Attempt to fix issues')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of text')
    parser.add_argument('--alert', action='store_true', help='Send alerts on failure (future)')
    parser.add_argument('--db', type=str, help='Database path (default: database.db)')

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    else:
        import logging
        logging.basicConfig(level=logging.INFO)

    # Run validation
    validator = UpdateValidator(db_path=args.db)
    results = validator.run_all_checks(fix_issues=args.fix)

    # Output results
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        passed = validator.print_report()
        sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
