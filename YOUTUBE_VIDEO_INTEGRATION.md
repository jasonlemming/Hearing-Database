# YouTube Video Integration - Implementation Summary

## Overview
This branch adds comprehensive YouTube video support to the Congressional Hearing Database, allowing users to watch hearing videos directly from the hearing detail pages when available from Congress.gov.

## Features Implemented

### 1. Database Schema Updates
- **New Fields**: Added `video_url` (TEXT) and `youtube_video_id` (TEXT) to the `hearings` table
- **Migration Script**: Created `database/migrations/001_add_video_fields.sql` for existing databases
- **Indexing**: Added conditional index on `youtube_video_id` for efficient queries

### 2. Data Collection & Parsing
- **Video Extraction**: `HearingFetcher.extract_videos()` pulls video data from Congress.gov API
  - Handles multiple API response formats (array or dict with 'item' key)
  - Extracts primary video URL from videos array

- **YouTube ID Parsing**: `HearingParser.parse_video_url()` with defensive validation
  - Extracts YouTube video ID from Congress.gov video URLs
  - Validates 11-character alphanumeric pattern (with `-` and `_`)
  - Logs warnings for unexpected formats
  - Returns both full URL and extracted YouTube ID

- **Import Integration**: Updated `ImportOrchestrator._process_hearing_batch()`
  - Video extraction runs during both initial import and daily updates
  - Stores both video_url and youtube_video_id in database

### 3. Web Interface
- **Video Player Section**: Added "Video of Proceedings" card on hearing detail pages
  - Positioned prominently at top, right after hearing header
  - Medium-sized responsive player (2/3 width on large screens, col-lg-8)
  - YouTube embed with 16:9 aspect ratio
  - Rounded corners and subtle shadow for polish

- **Fallback UI**: When no video is available
  - Shows icon and message: "Data will display when it becomes available."
  - Sets clear expectations for users

- **Congress.gov Link**: When video_url exists, includes link to view on Congress.gov

### 4. Testing
- **Test Suite**: `test_video_extraction.py`
  - Tests video URL parsing with various formats
  - Tests video extraction from API responses
  - Validates edge cases (empty, invalid, missing data)
  - **All tests passing** ✅

## Technical Details

### API Response Format
Congress.gov API returns video data in this structure:
```json
{
  "videos": {
    "item": [
      {
        "name": "Video Title",
        "url": "https://www.congress.gov/committees/video/house-appropriations/hshm12/yv8VUIRAm7k"
      }
    ]
  }
}
```

### URL Pattern
- **Format**: `https://www.congress.gov/committees/video/{chamber-committee}/{code}/{youtube-id}`
- **Example**: `https://www.congress.gov/committees/video/house-appropriations/hshm12/yv8VUIRAm7k`
- **YouTube ID**: Last segment (`yv8VUIRAm7k` - 11 characters)

### Database Schema
```sql
ALTER TABLE hearings ADD COLUMN video_url TEXT;
ALTER TABLE hearings ADD COLUMN youtube_video_id TEXT;
CREATE INDEX idx_hearings_video ON hearings(youtube_video_id)
  WHERE youtube_video_id IS NOT NULL;
```

## Files Modified

### Database Layer
- `database/schema.sql` - Added video fields to hearings table
- `database/manager.py` - Updated upsert_hearing() to handle video fields
- `database/migrations/001_add_video_fields.sql` - Migration script

### Data Collection
- `fetchers/hearing_fetcher.py` - Added extract_videos() method
- `parsers/hearing_parser.py` - Added parse_video_url() method
- `importers/orchestrator.py` - Integrated video extraction into import flow

### Web Interface
- `web/templates/hearing_detail.html` - Added video player section
- `web/templates/base.html` - Added video player CSS styling
- `web/blueprints/hearings.py` - Already queries video fields (SELECT * FROM hearings)

### Testing
- `test_video_extraction.py` - Comprehensive test suite

## Usage Instructions

### For New Databases
The schema already includes the video fields. Just run the normal database initialization.

### For Existing Databases
Run the migration script:
```bash
sqlite3 data/congressional_hearings.db < database/migrations/001_add_video_fields.sql
```

### To Populate Video Data
Run import or update operations as normal:
```bash
# Initial import (will fetch videos for all hearings)
python3 import_hearings.py

# Daily updates (will fetch videos for new/updated hearings)
python3 daily_update.py
```

### Testing
Run the test suite:
```bash
python3 test_video_extraction.py
```

## UI/UX Design Decisions

1. **Prominent Placement**: Video at top after hearing header
   - Users expect video to be highly visible
   - More important than committees/witnesses for engagement

2. **Medium Size (2/3 width)**: Balanced approach
   - Not overwhelming the page
   - Leaves room for text content
   - Responsive on mobile (full width on small screens)

3. **Fallback Message**: Clear expectation setting
   - "Data will display when it becomes available"
   - Implies videos may be added later
   - Professional, not apologetic

4. **Defensive Validation**: Robust parsing
   - Validates YouTube ID format
   - Logs warnings for unexpected patterns
   - Gracefully handles missing/invalid data

## Next Steps

### Before Merging to Main
1. ✅ Test video extraction logic (COMPLETE - all tests passing)
2. ⏳ Test video display in browser (start Flask app, navigate to hearing with video)
3. ⏳ Run migration on production database
4. ⏳ Import/update to populate video data

### Future Enhancements (Optional)
- Add video thumbnail previews to hearing list pages
- Support multiple videos per hearing (if API provides multiple)
- Add video download links
- Track video view analytics
- Add "Share Video" button
- Lazy-load videos for performance

## Branch Information
- **Branch**: `feature/youtube-video-integration`
- **Status**: Ready for testing
- **Tests**: ✅ All passing

## Questions for Review
1. Should we add video thumbnails to the hearings list page?
2. Do we want analytics on video views?
3. Should videos autoplay (currently set to not autoplay)?
