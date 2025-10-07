#!/usr/bin/env python3
"""
Database migration: Add video_type column to hearings table

This migration adds the video_type column to track the type of video source:
- youtube: Direct YouTube embeds
- senate_isvp: Senate ISVP player videos
- house_video: House video player videos
- committee_video: Congress.gov committee video pages
- event_page: Congress.gov event pages (fallback)
"""
import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.logging_config import get_logger

logger = get_logger(__name__)


def migrate_up(db_path: str = 'database.db'):
    """
    Apply migration: Add video_type column

    Args:
        db_path: Path to database file
    """
    logger.info("Starting migration: add_video_type_column")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(hearings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'video_type' in columns:
            logger.info("Column 'video_type' already exists - skipping migration")
            return

        # Add video_type column
        logger.info("Adding video_type column to hearings table")
        cursor.execute("""
            ALTER TABLE hearings
            ADD COLUMN video_type TEXT
        """)

        # Add check constraint for valid video types
        # Note: SQLite doesn't support adding constraints to existing tables,
        # so we'll validate in the application layer via Pydantic model

        # Backfill video_type for existing records with YouTube videos
        logger.info("Backfilling video_type='youtube' for existing YouTube videos")
        cursor.execute("""
            UPDATE hearings
            SET video_type = 'youtube'
            WHERE youtube_video_id IS NOT NULL
        """)
        updated_youtube = cursor.rowcount
        logger.info(f"Updated {updated_youtube} records with video_type='youtube'")

        # Backfill video_type for existing records with event page URLs
        # These are Senate hearings that have video_url but no youtube_video_id
        logger.info("Backfilling video_type='event_page' for records with video_url but no youtube_video_id")
        cursor.execute("""
            UPDATE hearings
            SET video_type = 'event_page'
            WHERE video_url IS NOT NULL
              AND youtube_video_id IS NULL
              AND video_url LIKE '%congress.gov/event%'
        """)
        updated_event_page = cursor.rowcount
        logger.info(f"Updated {updated_event_page} records with video_type='event_page'")

        conn.commit()
        logger.info("Migration completed successfully")

        # Display summary statistics
        cursor.execute("""
            SELECT
                video_type,
                COUNT(*) as count
            FROM hearings
            WHERE video_type IS NOT NULL
            GROUP BY video_type
            ORDER BY count DESC
        """)

        logger.info("Video type distribution after migration:")
        for row in cursor.fetchall():
            logger.info(f"  {row[0]}: {row[1]} hearings")

    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


def migrate_down(db_path: str = 'database.db'):
    """
    Rollback migration: Remove video_type column

    Note: SQLite doesn't support DROP COLUMN directly.
    This would require recreating the table.

    Args:
        db_path: Path to database file
    """
    logger.warning("Rollback not implemented - SQLite doesn't support DROP COLUMN")
    logger.warning("To rollback, you would need to recreate the hearings table without video_type")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Add video_type column to hearings table')
    parser.add_argument('--db', default='database.db', help='Database file path')
    parser.add_argument('--rollback', action='store_true', help='Rollback migration')

    args = parser.parse_args()

    if args.rollback:
        migrate_down(args.db)
    else:
        migrate_up(args.db)
