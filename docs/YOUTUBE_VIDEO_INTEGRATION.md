# YouTube Video Integration

This document describes how YouTube videos from congressional hearings are integrated into the Hearing Database system.

## Overview

The system automatically extracts and stores YouTube video information from congressional hearing data provided by the Congress.gov API. Video data includes the full video URL and the extracted YouTube video ID for embedding.

## Database Schema

### Video Fields in Hearings Table

```sql
video_url TEXT          -- Full YouTube or Congress.gov video URL
youtube_video_id TEXT   -- Extracted YouTube video ID (11 characters)
```

## Data Flow

### 1. Fetching Video Data

Video data is fetched from the Congress.gov API as part of detailed hearing information:

```python
# fetchers/hearing_fetcher.py
def fetch_hearing_details(congress, chamber, event_id):
    # Returns detailed hearing data including 'videos' field
```

The API returns videos in this format:
```json
{
  "committeeMeeting": {
    "eventId": "118642",
    "videos": {
      "item": [
        {
          "url": "https://www.youtube.com/watch?v=-FpXFc4UzH8U"
        }
      ]
    }
  }
}
```

### 2. Parsing Video Data

The `HearingParser` automatically extracts video data during parsing:

```python
# parsers/hearing_parser.py
def parse(raw_data):
    # Extract video data
    video_data = self._extract_video_data(raw_data)
    hearing_data['video_url'] = video_data['video_url']
    hearing_data['youtube_video_id'] = video_data['youtube_video_id']
```

The `_extract_video_data()` method:
- Checks for videos in the API response
- Handles both list and dict video formats
- Prefers YouTube URLs over other video sources
- Extracts YouTube video ID from the URL

The `parse_video_url()` method handles two URL formats:

**Direct YouTube URLs:**
```
https://www.youtube.com/watch?v={VIDEO_ID}
```

**Congress.gov Committee Video URLs:**
```
https://www.congress.gov/committees/video/{chamber-committee}/{code}/{youtube-id}
```

YouTube IDs are validated using the pattern: `[A-Za-z0-9_-]{10,12}`

### 3. Storing Video Data

Video data is automatically stored via the `DatabaseManager`:

```python
# database/manager.py
def upsert_hearing(hearing_data):
    # Inserts or updates hearing with video_url and youtube_video_id
```

## Implementation Details

### HearingModel (parsers/models.py)

```python
class HearingModel(BaseModel):
    # ... other fields ...
    video_url: Optional[str] = None
    youtube_video_id: Optional[str] = None
```

### Video Extraction Logic (parsers/hearing_parser.py)

The parser handles various video data structures from the API:

- **List format**: `videos: [{"url": "..."}]`
- **Dict format**: `videos: {"item": [{"url": "..."}]}`
- **Single video**: `videos: {"item": {"url": "..."}}`

Priority order for video URLs:
1. Direct YouTube URLs (`youtube.com`)
2. Congress.gov committee video URLs (`committees/video`)
3. First available video URL (fallback)

### YouTube ID Extraction

The system extracts YouTube IDs using two methods:

**Method 1: Query Parameter Extraction**
```python
if 'youtube.com' in video_url:
    parsed = urlparse(video_url)
    query_params = parse_qs(parsed.query)
    video_id = query_params['v'][0]
```

**Method 2: Path Extraction (Congress.gov URLs)**
```python
url_parts = video_url.rstrip('/').split('/')
potential_id = url_parts[-1]  # Last path component
```

## Import Process

### Full Import

During a full import, video data is automatically extracted for all hearings:

```bash
python3 cli.py import full --congress 119 --phase hearings
```

The orchestrator processes each hearing through the parser pipeline, which includes video extraction.

### Incremental Updates

The `DailyUpdater` also extracts video data when adding or updating hearings:

```bash
python3 cli.py update incremental --congress 119
```

Both `_update_hearing_record()` and `_add_new_hearing()` methods use the `HearingParser`, ensuring video data is always extracted consistently.

## Web Display

Videos are displayed on hearing detail pages using the YouTube video ID:

```html
<!-- web/templates/hearing.html -->
{% if hearing.youtube_video_id %}
<div class="video-container">
    <iframe
        src="https://www.youtube.com/embed/{{ hearing.youtube_video_id }}"
        frameborder="0"
        allowfullscreen>
    </iframe>
</div>
{% endif %}
```

## Testing

### Test Script

Use the test script to verify video extraction for a specific hearing:

```bash
python3 test_single_video.py
```

This tests hearing 118642 which is known to have video data.

### Database Query

Check video data in the database:

```sql
-- Count hearings with videos
SELECT COUNT(*) FROM hearings WHERE video_url IS NOT NULL;

-- View sample video data
SELECT event_id, title, video_url, youtube_video_id
FROM hearings
WHERE video_url IS NOT NULL
LIMIT 10;
```

## Troubleshooting

### No Videos in Database

If videos are not appearing after import:

1. **Check API Response**: Verify the API returns video data
   ```python
   hearing_fetcher.fetch_hearing_details(119, 'house', '118642')
   ```

2. **Verify Parser**: Test video extraction
   ```python
   video_data = parser._extract_video_data(hearing_data)
   ```

3. **Check Model**: Ensure HearingModel has video fields
   ```python
   hearing.dict()  # Should include video_url and youtube_video_id
   ```

### Invalid YouTube IDs

If YouTube IDs are not extracted:

- Check ID format matches pattern: `[A-Za-z0-9_-]{10,12}`
- Verify URL format is supported
- Check logs for parsing warnings

## Architecture Changes (October 2025)

The video integration was refactored to use the parser pipeline:

**Before:**
- Orchestrator manually extracted videos after parsing
- Video data added to dict after `.dict()` call
- DailyUpdater wrote raw API data directly

**After:**
- Parser extracts videos during `parse()` method
- Video fields included in HearingModel schema
- All import paths use consistent parser pipeline
- DailyUpdater uses HearingParser for updates

This ensures video data is extracted consistently across all import and update operations.
