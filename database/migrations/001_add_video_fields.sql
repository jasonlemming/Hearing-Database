-- Migration: Add video fields to hearings table
-- Date: 2025-10-07
-- Description: Adds video_url and youtube_video_id fields to support YouTube video embeds

-- Add video_url field to store full Congress.gov video URL
ALTER TABLE hearings ADD COLUMN video_url TEXT;

-- Add youtube_video_id field to store extracted YouTube video ID
ALTER TABLE hearings ADD COLUMN youtube_video_id TEXT;

-- Create index for video queries (optional but helpful for filtering)
CREATE INDEX idx_hearings_video ON hearings(youtube_video_id) WHERE youtube_video_id IS NOT NULL;
