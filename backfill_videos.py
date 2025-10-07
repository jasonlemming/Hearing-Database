#!/usr/bin/env python3
"""
Video Backfill Script

Fetches and updates video data for hearings that don't have videos.
Uses UPDATE instead of INSERT OR REPLACE to avoid FK constraint issues.

Usage:
    python3 backfill_videos.py --limit 5      # Test on 5 hearings
    python3 backfill_videos.py --limit 50     # Scale to 50
    python3 backfill_videos.py                # Backfill all hearings
"""

import argparse
import re
import sqlite3
from typing import Optional, Dict, Any
from api.client import CongressAPIClient
from fetchers.hearing_fetcher import HearingFetcher
from parsers.hearing_parser import HearingParser
from config.settings import Settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class VideoBackfiller:
    """Backfills video data for existing hearings"""

    def __init__(self, db_path: str = "database.db"):
        """Initialize backfiller with database connection"""
        self.db_path = db_path
        self.settings = Settings()
        self.api_client = CongressAPIClient(api_key=self.settings.api_key)
        self.hearing_fetcher = HearingFetcher(self.api_client)
        self.hearing_parser = HearingParser()

    def get_hearings_without_videos(self, limit: Optional[int] = None) -> list:
        """Query hearings that don't have video data"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        query = """
        SELECT hearing_id, event_id, congress, chamber, title
        FROM hearings
        WHERE video_url IS NULL OR youtube_video_id IS NULL
        ORDER BY hearing_id
        """

        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query)
        hearings = cursor.fetchall()
        conn.close()

        return [dict(h) for h in hearings]

    def update_hearing_video(self, hearing_id: int, video_url: Optional[str],
                            youtube_video_id: Optional[str], video_type: Optional[str] = None) -> bool:
        """Update video data for a hearing using direct UPDATE"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
            UPDATE hearings
            SET video_url = ?, youtube_video_id = ?, video_type = ?, updated_at = CURRENT_TIMESTAMP
            WHERE hearing_id = ?
            """
            conn.execute(query, (video_url, youtube_video_id, video_type, hearing_id))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error updating hearing {hearing_id}: {e}")
            return False

    def validate_youtube_id(self, youtube_id: Optional[str]) -> bool:
        """Validate YouTube ID format"""
        if not youtube_id:
            return False

        # YouTube IDs are 10-12 characters: alphanumeric, hyphens, underscores
        pattern = r'^[A-Za-z0-9_-]{10,12}$'
        return bool(re.match(pattern, youtube_id))

    def backfill(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run the backfill process"""
        logger.info(f"Starting video backfill (limit: {limit or 'all'})")

        # Get hearings without videos
        hearings = self.get_hearings_without_videos(limit)
        total = len(hearings)

        logger.info(f"Found {total} hearings without video data")

        stats = {
            'total': total,
            'success': 0,
            'no_video': 0,
            'errors': 0,
            'invalid_id': 0
        }

        for i, hearing in enumerate(hearings, 1):
            event_id = hearing['event_id']
            congress = hearing['congress']
            chamber = hearing['chamber'].lower()
            hearing_id = hearing['hearing_id']

            logger.info(f"[{i}/{total}] Processing hearing {event_id} ({chamber}, Congress {congress})")

            try:
                # Fetch detailed hearing data from API
                detailed_hearing = self.hearing_fetcher.fetch_hearing_details(
                    congress, chamber, event_id
                )

                if not detailed_hearing:
                    logger.warning(f"Could not fetch details for hearing {event_id}")
                    stats['errors'] += 1
                    continue

                # Extract event data from response (same as orchestrator)
                event_data = None
                if 'committeeMeeting' in detailed_hearing:
                    event_data = detailed_hearing['committeeMeeting']
                elif 'committeeEvent' in detailed_hearing:
                    event_data = detailed_hearing['committeeEvent']

                if not event_data:
                    logger.warning(f"No event data in API response for hearing {event_id}")
                    stats['errors'] += 1
                    continue

                # Extract video data using parser
                video_data = self.hearing_parser._extract_video_data(event_data)
                video_url = video_data.get('video_url')
                youtube_id = video_data.get('youtube_video_id')
                video_type = video_data.get('video_type')

                if not video_url:
                    logger.info(f"  No video data available for hearing {event_id}")
                    stats['no_video'] += 1
                    # Update with NULL to mark as checked
                    self.update_hearing_video(hearing_id, None, None, None)
                    continue

                # Validate YouTube ID format
                if youtube_id and not self.validate_youtube_id(youtube_id):
                    logger.warning(f"  Invalid YouTube ID format: {youtube_id}")
                    stats['invalid_id'] += 1

                # Update database
                success = self.update_hearing_video(hearing_id, video_url, youtube_id, video_type)

                if success:
                    logger.info(f"  ✓ Updated with video: {video_url}")
                    logger.info(f"    YouTube ID: {youtube_id}")
                    logger.info(f"    Video type: {video_type}")
                    stats['success'] += 1
                else:
                    stats['errors'] += 1

            except Exception as e:
                logger.error(f"Error processing hearing {event_id}: {e}")
                stats['errors'] += 1

        # Print summary
        logger.info("\n" + "="*60)
        logger.info("BACKFILL SUMMARY")
        logger.info("="*60)
        logger.info(f"Total hearings processed: {stats['total']}")
        logger.info(f"Successfully updated:     {stats['success']}")
        logger.info(f"No video available:       {stats['no_video']}")
        logger.info(f"Invalid YouTube IDs:      {stats['invalid_id']}")
        logger.info(f"Errors:                   {stats['errors']}")
        logger.info("="*60)

        return stats


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Backfill video data for hearings')
    parser.add_argument('--limit', type=int, help='Limit number of hearings to process')

    args = parser.parse_args()

    backfiller = VideoBackfiller()
    stats = backfiller.backfill(limit=args.limit)

    # Return exit code based on success
    if stats['errors'] > 0:
        return 1
    return 0


if __name__ == '__main__':
    exit(main())
