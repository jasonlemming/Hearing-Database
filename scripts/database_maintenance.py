#!/usr/bin/env python3
"""
Database Maintenance Script for Congressional Hearing Database

Performs routine maintenance tasks:
- VACUUM (reclaim space from deleted records)
- ANALYZE (update query planner statistics)
- Integrity check
- Index optimization
- Old log cleanup

Usage:
    python scripts/database_maintenance.py [--vacuum] [--analyze] [--cleanup-logs]
"""

import sys
import os
from datetime import datetime, timedelta
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class DatabaseMaintenance:
    """Handles database maintenance operations"""

    def __init__(self, db_path: str = None):
        self.db = DatabaseManager(db_path) if db_path else DatabaseManager()

    def vacuum(self):
        """
        VACUUM database to reclaim space and defragment

        This rebuilds the database file, repacking it into a minimal amount of disk space.
        Should be run periodically (monthly recommended).
        """
        logger.info("Running VACUUM...")
        start_time = datetime.now()

        # Get size before
        size_before = self._get_database_size()

        try:
            with self.db.get_connection() as conn:
                conn.execute('VACUUM')

            # Get size after
            size_after = self._get_database_size()
            savings = size_before - size_after

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"VACUUM completed in {duration:.2f}s")
            logger.info(f"Size before: {size_before:.2f} MB, after: {size_after:.2f} MB, saved: {savings:.2f} MB")

            return {
                'success': True,
                'duration_seconds': duration,
                'size_before_mb': size_before,
                'size_after_mb': size_after,
                'space_saved_mb': savings
            }

        except Exception as e:
            logger.error(f"VACUUM failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def analyze(self):
        """
        ANALYZE database to update query planner statistics

        This gathers statistics about the content of tables to help SQLite
        choose better query plans. Should be run after significant data changes.
        """
        logger.info("Running ANALYZE...")
        start_time = datetime.now()

        try:
            with self.db.get_connection() as conn:
                conn.execute('ANALYZE')

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"ANALYZE completed in {duration:.2f}s")

            return {
                'success': True,
                'duration_seconds': duration
            }

        except Exception as e:
            logger.error(f"ANALYZE failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def integrity_check(self):
        """
        Check database integrity

        Verifies the database file is not corrupted and foreign keys are valid.
        """
        logger.info("Running integrity check...")

        issues = []

        try:
            # Check database integrity
            with self.db.get_connection() as conn:
                cursor = conn.execute('PRAGMA integrity_check')
                result = cursor.fetchone()

                if result and result[0] == 'ok':
                    logger.info("Database integrity: OK")
                else:
                    issues.append(f"Integrity check failed: {result}")

            # Check foreign keys
            with self.db.get_connection() as conn:
                conn.execute('PRAGMA foreign_keys = ON')
                cursor = conn.execute('PRAGMA foreign_key_check')
                violations = cursor.fetchall()

                if violations:
                    for violation in violations:
                        issues.append(f"Foreign key violation: {violation}")
                    logger.warning(f"Found {len(violations)} foreign key violations")
                else:
                    logger.info("Foreign key integrity: OK")

            return {
                'success': len(issues) == 0,
                'issues': issues
            }

        except Exception as e:
            logger.error(f"Integrity check failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def cleanup_old_logs(self, days_to_keep: int = 90):
        """
        Delete old update logs to prevent table bloat

        Args:
            days_to_keep: Keep logs from last N days (default: 90)
        """
        logger.info(f"Cleaning up logs older than {days_to_keep} days...")

        try:
            cutoff_date = (datetime.now() - timedelta(days=days_to_keep)).date()

            with self.db.transaction() as conn:
                # Count logs to delete
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM update_logs
                    WHERE update_date < ?
                ''', (cutoff_date,))
                count_to_delete = cursor.fetchone()[0]

                if count_to_delete > 0:
                    # Delete old logs
                    conn.execute('''
                        DELETE FROM update_logs
                        WHERE update_date < ?
                    ''', (cutoff_date,))

                    logger.info(f"Deleted {count_to_delete} old log entries")

                    return {
                        'success': True,
                        'deleted_count': count_to_delete,
                        'cutoff_date': str(cutoff_date)
                    }
                else:
                    logger.info("No old logs to delete")
                    return {
                        'success': True,
                        'deleted_count': 0
                    }

        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def optimize_indexes(self):
        """
        Check and optimize database indexes

        Reindexes all indexes to improve query performance.
        """
        logger.info("Optimizing indexes...")
        start_time = datetime.now()

        try:
            with self.db.get_connection() as conn:
                conn.execute('REINDEX')

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Index optimization completed in {duration:.2f}s")

            return {
                'success': True,
                'duration_seconds': duration
            }

        except Exception as e:
            logger.error(f"Index optimization failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def get_table_stats(self):
        """Get statistics about all tables"""
        logger.info("Gathering table statistics...")

        stats = {}

        try:
            counts = self.db.get_table_counts()

            # Get more detailed stats
            with self.db.transaction() as conn:
                for table in counts.keys():
                    # Get row count and average row size
                    cursor = conn.execute(f'''
                        SELECT
                            COUNT(*) as row_count,
                            SUM(LENGTH(CAST({table} AS TEXT))) / COUNT(*) as avg_row_size
                        FROM {table}
                    ''')
                    row_count, avg_size = cursor.fetchone()

                    stats[table] = {
                        'row_count': row_count,
                        'avg_row_bytes': int(avg_size) if avg_size else 0
                    }

            return {
                'success': True,
                'stats': stats
            }

        except Exception as e:
            logger.error(f"Failed to get table stats: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _get_database_size(self):
        """Get database size in MB"""
        try:
            with self.db.transaction() as conn:
                cursor = conn.execute('''
                    SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
                    FROM pragma_page_count('main'), pragma_page_size()
                ''')
                return cursor.fetchone()[0]
        except:
            return 0.0

    def run_full_maintenance(self, cleanup_days: int = 90):
        """
        Run complete maintenance routine

        Args:
            cleanup_days: Days to keep in update_logs

        Returns:
            Dict with results of all operations
        """
        logger.info("=" * 80)
        logger.info("STARTING FULL DATABASE MAINTENANCE")
        logger.info("=" * 80)

        results = {
            'timestamp': datetime.now().isoformat(),
            'operations': {}
        }

        # 1. Integrity check
        logger.info("\n1. Integrity Check")
        results['operations']['integrity_check'] = self.integrity_check()

        # 2. Cleanup old logs
        logger.info("\n2. Cleanup Old Logs")
        results['operations']['cleanup_logs'] = self.cleanup_old_logs(cleanup_days)

        # 3. VACUUM
        logger.info("\n3. VACUUM")
        results['operations']['vacuum'] = self.vacuum()

        # 4. ANALYZE
        logger.info("\n4. ANALYZE")
        results['operations']['analyze'] = self.analyze()

        # 5. Optimize indexes
        logger.info("\n5. Optimize Indexes")
        results['operations']['optimize_indexes'] = self.optimize_indexes()

        # 6. Table stats
        logger.info("\n6. Table Statistics")
        results['operations']['table_stats'] = self.get_table_stats()

        logger.info("\n" + "=" * 80)
        logger.info("MAINTENANCE COMPLETED")
        logger.info("=" * 80)

        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Database maintenance tool')
    parser.add_argument('--vacuum', action='store_true', help='Run VACUUM')
    parser.add_argument('--analyze', action='store_true', help='Run ANALYZE')
    parser.add_argument('--integrity', action='store_true', help='Check integrity')
    parser.add_argument('--cleanup-logs', type=int, metavar='DAYS', help='Delete logs older than N days')
    parser.add_argument('--optimize-indexes', action='store_true', help='Optimize indexes')
    parser.add_argument('--stats', action='store_true', help='Show table statistics')
    parser.add_argument('--full', action='store_true', help='Run full maintenance (all operations)')
    parser.add_argument('--db', type=str, help='Database path (default: database.db)')

    args = parser.parse_args()

    # If no specific operation selected, show help
    if not any([args.vacuum, args.analyze, args.integrity, args.cleanup_logs,
                args.optimize_indexes, args.stats, args.full]):
        parser.print_help()
        sys.exit(0)

    # Create maintenance instance
    maintenance = DatabaseMaintenance(db_path=args.db)

    # Run full maintenance if requested
    if args.full:
        results = maintenance.run_full_maintenance(cleanup_days=args.cleanup_logs or 90)
        import json
        print(json.dumps(results, indent=2))
        sys.exit(0 if all(r.get('success', False) for r in results['operations'].values()) else 1)

    # Run individual operations
    if args.integrity:
        result = maintenance.integrity_check()
        if not result['success']:
            print(f"Integrity check failed: {result.get('error', 'Unknown error')}")
            if result.get('issues'):
                for issue in result['issues']:
                    print(f"  - {issue}")
            sys.exit(1)
        else:
            print("✓ Integrity check passed")

    if args.vacuum:
        result = maintenance.vacuum()
        if result['success']:
            print(f"✓ VACUUM completed: saved {result['space_saved_mb']:.2f} MB")
        else:
            print(f"✗ VACUUM failed: {result.get('error')}")
            sys.exit(1)

    if args.analyze:
        result = maintenance.analyze()
        if result['success']:
            print(f"✓ ANALYZE completed in {result['duration_seconds']:.2f}s")
        else:
            print(f"✗ ANALYZE failed: {result.get('error')}")
            sys.exit(1)

    if args.cleanup_logs:
        result = maintenance.cleanup_old_logs(args.cleanup_logs)
        if result['success']:
            print(f"✓ Cleaned up {result['deleted_count']} old log entries")
        else:
            print(f"✗ Cleanup failed: {result.get('error')}")
            sys.exit(1)

    if args.optimize_indexes:
        result = maintenance.optimize_indexes()
        if result['success']:
            print(f"✓ Indexes optimized in {result['duration_seconds']:.2f}s")
        else:
            print(f"✗ Index optimization failed: {result.get('error')}")
            sys.exit(1)

    if args.stats:
        result = maintenance.get_table_stats()
        if result['success']:
            print("\nTable Statistics:")
            print("-" * 60)
            for table, stats in result['stats'].items():
                print(f"{table:30s}: {stats['row_count']:>8,} rows, {stats['avg_row_bytes']:>6} bytes/row")
        else:
            print(f"✗ Failed to get stats: {result.get('error')}")
            sys.exit(1)


if __name__ == '__main__':
    main()
