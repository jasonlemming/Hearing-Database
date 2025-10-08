"""
Hearing data parser
"""
from typing import Dict, Any, Optional, List
from parsers.base_parser import BaseParser
from parsers.models import HearingModel
from config.logging_config import get_logger

logger = get_logger(__name__)


class HearingParser(BaseParser):
    """Parser for hearing data from Congress.gov API"""

    def parse(self, raw_data: Dict[str, Any]) -> Optional[HearingModel]:
        """
        Parse raw hearing data into validated model

        Args:
            raw_data: Raw hearing data from API

        Returns:
            Validated HearingModel or None
        """
        # Required fields for hearings
        required_fields = ['eventId', 'title']
        if not self.validate_required_fields(raw_data, required_fields):
            if self.strict_mode:
                return None

        # Extract and normalize data
        hearing_data = {
            'event_id': self.safe_get(raw_data, 'eventId'),
            'congress': self._extract_congress(raw_data),
            'chamber': self._normalize_chamber(self.safe_get(raw_data, 'chamber')),
            'title': self.normalize_text(self.safe_get(raw_data, 'title')),
            'hearing_type': self._normalize_hearing_type(self.safe_get(raw_data, 'type')),
            'status': self._normalize_status(self.safe_get(raw_data, 'status')),
            'hearing_date': self._extract_hearing_date(raw_data),
            'location': self._extract_location(raw_data),
            'jacket_number': self._extract_jacket_number(raw_data),
            'url': self.safe_get(raw_data, 'url'),
            'congress_gov_url': self._extract_congress_gov_url(raw_data),
            'update_date': self._extract_update_date(raw_data)
        }

        # Extract video data
        video_data = self._extract_video_data(raw_data)
        hearing_data['video_url'] = video_data['video_url']
        hearing_data['youtube_video_id'] = video_data['youtube_video_id']
        hearing_data['video_type'] = video_data['video_type']

        return self.validate_model(HearingModel, hearing_data)

    def _normalize_chamber(self, chamber: str) -> str:
        """Normalize chamber name"""
        if not chamber:
            return 'NoChamber'

        chamber_mapping = {
            'house': 'House',
            'senate': 'Senate',
            'nochamber': 'NoChamber'
        }

        return chamber_mapping.get(chamber.lower(), chamber.title())

    def _normalize_hearing_type(self, hearing_type: str) -> str:
        """Normalize hearing type"""
        if not hearing_type:
            return 'Hearing'

        type_mapping = {
            'hearing': 'Hearing',
            'meeting': 'Meeting',
            'markup': 'Markup',
            'committee meeting': 'Meeting',
            'business meeting': 'Meeting'
        }

        return type_mapping.get(hearing_type.lower(), hearing_type)

    def _normalize_status(self, status: str) -> str:
        """Normalize hearing status"""
        if not status:
            return 'Scheduled'

        status_mapping = {
            'scheduled': 'Scheduled',
            'canceled': 'Canceled',
            'cancelled': 'Canceled',
            'postponed': 'Postponed',
            'rescheduled': 'Rescheduled'
        }

        return status_mapping.get(status.lower(), status)

    def _extract_congress(self, raw_data: Dict[str, Any]) -> int:
        """Extract congress number"""
        congress = self.safe_get(raw_data, 'congress')
        if congress:
            return self.normalize_integer(congress)

        # Try to extract from URL
        url = self.safe_get(raw_data, 'url', '')
        if '/committee-meeting/' in url:
            parts = url.split('/committee-meeting/')
            if len(parts) > 1:
                congress_part = parts[1].split('/')[0]
                return self.normalize_integer(congress_part)

        # Default to current congress
        from config.settings import settings
        return settings.target_congress

    def _extract_hearing_date(self, raw_data: Dict[str, Any]) -> Optional:
        """Extract hearing date"""
        # Check various possible date fields
        date_fields = [
            'meetingDate',
            'date',
            'hearingDate',
            'eventDate'
        ]

        for field in date_fields:
            date_value = self.safe_get(raw_data, field)
            if date_value:
                return self.normalize_date(date_value)

        return None

    def _extract_location(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract hearing location"""
        location_fields = [
            'location',
            'room',
            'venue',
            'meetingLocation'
        ]

        for field in location_fields:
            location = self.safe_get(raw_data, field)
            if location:
                return self.normalize_text(location)

        return None

    def _extract_jacket_number(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract hearing jacket number"""
        jacket_fields = [
            'jacketNumber',
            'jacket',
            'hearingNumber'
        ]

        for field in jacket_fields:
            jacket = self.safe_get(raw_data, field)
            if jacket:
                # Normalize to 5-digit format if needed
                jacket_str = str(jacket).zfill(5)
                return jacket_str

        return None

    def _extract_congress_gov_url(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract Congress.gov public URL"""
        # Check for public URL
        public_url_fields = [
            'congressDotGovUrl',  # Correct API field name
            'congressGovUrl',      # Legacy fallback
            'publicUrl',
            'webUrl'
        ]

        for field in public_url_fields:
            url = self.safe_get(raw_data, field)
            if url and 'congress.gov' in url:
                return url

        return None

    def _extract_update_date(self, raw_data: Dict[str, Any]) -> Optional:
        """Extract last update date"""
        update_fields = [
            'updateDate',
            'lastModified',
            'modified'
        ]

        for field in update_fields:
            update_date = self.safe_get(raw_data, field)
            if update_date:
                return self.normalize_datetime(update_date)

        return None

    def _extract_video_data(self, raw_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Extract and parse video data from hearing raw data

        Scans ALL videos in the API response and selects the best one based on priority:
        1. YouTube URLs (for embeddable video)
        2. Senate ISVP URLs (senate.gov/isvp)
        3. House video URLs (house.gov)
        4. Congress.gov committee video URLs
        5. Congress.gov event page URLs (fallback)

        Args:
            raw_data: Raw hearing data

        Returns:
            Dictionary with video_url, youtube_video_id, and video_type
        """
        result = {
            'video_url': None,
            'youtube_video_id': None,
            'video_type': None
        }

        # Check for videos in the API response
        videos = self.safe_get(raw_data, 'videos')

        if not videos:
            return result

        # Videos can be an array or dict with 'item' key
        video_items = []
        if isinstance(videos, list):
            video_items = videos
        elif isinstance(videos, dict):
            items = self.safe_get(videos, 'item', [])
            video_items = items if isinstance(items, list) else [items]

        # Scan ALL videos and categorize them
        youtube_urls = []
        senate_isvp_urls = []
        house_video_urls = []
        committee_video_urls = []
        event_page_urls = []

        for video in video_items:
            if not isinstance(video, dict):
                continue
            url = self.safe_get(video, 'url')
            if not url:
                continue

            # Categorize by URL pattern
            if 'youtube.com' in url or 'youtu.be' in url:
                youtube_urls.append(url)
            elif 'senate.gov/isvp' in url:
                senate_isvp_urls.append(url)
            elif 'house.gov' in url and 'video' in url.lower():
                house_video_urls.append(url)
            elif 'congress.gov/committees/video' in url:
                committee_video_urls.append(url)
            elif 'congress.gov/event' in url:
                event_page_urls.append(url)

        # Select best video based on priority
        video_url = None
        video_type = None

        if youtube_urls:
            video_url = youtube_urls[0]
            video_type = 'youtube'
            logger.debug(f"Selected YouTube video: {video_url}")
        elif senate_isvp_urls:
            video_url = senate_isvp_urls[0]
            video_type = 'senate_isvp'
            logger.debug(f"Selected Senate ISVP video: {video_url}")
        elif house_video_urls:
            video_url = house_video_urls[0]
            video_type = 'house_video'
            logger.debug(f"Selected House video: {video_url}")
        elif committee_video_urls:
            video_url = committee_video_urls[0]
            video_type = 'committee_video'
            logger.debug(f"Selected committee video: {video_url}")
        elif event_page_urls:
            video_url = event_page_urls[0]
            video_type = 'event_page'
            logger.debug(f"Selected event page (fallback): {video_url}")

        # Parse the video URL to extract YouTube ID if applicable
        if video_url:
            parsed = self.parse_video_url(video_url)
            result['video_url'] = parsed['video_url']
            result['youtube_video_id'] = parsed['youtube_video_id']
            result['video_type'] = video_type

        return result

    def extract_committee_references(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract committee references from hearing data

        Args:
            raw_data: Raw hearing data

        Returns:
            List of committee reference data
        """
        committees = []

        # Check various committee reference sources
        committee_sources = [
            'committees',
            'committee',
            'committeeInfo'
        ]

        for source in committee_sources:
            committee_data = self.safe_get(raw_data, source)
            if committee_data:
                if isinstance(committee_data, list):
                    for i, committee in enumerate(committee_data):
                        committees.append({
                            'system_code': self.safe_get(committee, 'systemCode'),
                            'name': self.safe_get(committee, 'name'),
                            'is_primary': i == 0  # First committee is primary
                        })
                elif isinstance(committee_data, dict):
                    committees.append({
                        'system_code': self.safe_get(committee_data, 'systemCode'),
                        'name': self.safe_get(committee_data, 'name'),
                        'is_primary': True
                    })
                break

        return committees

    def extract_bill_references(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract bill references from hearing data

        Args:
            raw_data: Raw hearing data

        Returns:
            List of bill reference data
        """
        bills = []

        # Check for related items
        related_items = self.safe_get(raw_data, 'relatedItems', [])
        for item in related_items:
            if self.safe_get(item, 'type') == 'bill':
                bills.append({
                    'congress': self.normalize_integer(self.safe_get(item, 'congress')),
                    'bill_type': self._normalize_bill_type(self.safe_get(item, 'type')),
                    'bill_number': self.normalize_integer(self.safe_get(item, 'number')),
                    'title': self.safe_get(item, 'title'),
                    'relationship_type': 'mentioned'
                })

        # Extract from title using pattern matching
        title_bills = self._extract_bills_from_title(self.safe_get(raw_data, 'title', ''))
        bills.extend(title_bills)

        return bills

    def _normalize_bill_type(self, bill_type: str) -> str:
        """Normalize bill type"""
        if not bill_type:
            return 'HR'

        type_mapping = {
            'hr': 'HR',
            'house-bill': 'HR',
            's': 'S',
            'senate-bill': 'S',
            'hjres': 'HJRES',
            'sjres': 'SJRES',
            'hconres': 'HCONRES',
            'sconres': 'SCONRES',
            'hres': 'HRES',
            'sres': 'SRES'
        }

        return type_mapping.get(bill_type.lower(), bill_type.upper())

    def _extract_bills_from_title(self, title: str) -> List[Dict[str, Any]]:
        """Extract bill references from hearing title"""
        import re
        bills = []

        if not title:
            return bills

        # Pattern for bills: H.R. 123, S. 456, etc.
        patterns = [
            r'\b([HS])\.?R?\.?\s*(\d+)\b',  # H.R. 123, S. 456
            r'\b(HR|SR)\s*(\d+)\b',         # HR 123, SR 456
            r'\b([HS])\s*(\d+)\b'           # H 123, S 456
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, title, re.IGNORECASE)
            for match in matches:
                chamber = match.group(1).upper()
                number = int(match.group(2))

                bill_type = 'HR' if chamber == 'H' else 'S'

                bills.append({
                    'bill_type': bill_type,
                    'bill_number': number,
                    'relationship_type': 'mentioned'
                })

        return bills

    def parse_video_url(self, video_url: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Parse and validate video URL, extracting YouTube video ID

        Args:
            video_url: YouTube URL (direct or congress.gov committee video URL)

        Returns:
            Dictionary with validated video_url and extracted youtube_video_id
        """
        import re
        from urllib.parse import urlparse, parse_qs

        result = {
            'video_url': None,
            'youtube_video_id': None
        }

        if not video_url:
            return result

        # Store the full URL
        result['video_url'] = video_url

        # Extract YouTube video ID from URL
        # Supported formats:
        # 1. Direct YouTube: https://www.youtube.com/watch?v={VIDEO_ID}
        # 2. Congress.gov committee: https://www.congress.gov/committees/video/{chamber-committee}/{code}/{youtube-id}
        # YouTube IDs are typically 11 characters: alphanumeric, hyphens, underscores

        try:
            # Check if it's a direct YouTube URL
            if 'youtube.com' in video_url:
                parsed = urlparse(video_url)
                query_params = parse_qs(parsed.query)

                # Look for 'v' parameter in query string
                if 'v' in query_params and query_params['v']:
                    potential_id = query_params['v'][0]

                    # Strip erroneous leading hyphen from Congress.gov API bug
                    # API returns IDs like "-cuneRXGeLaQ" (12 chars) instead of "cuneRXGeLaQ" (11 chars)
                    if potential_id.startswith('-') and len(potential_id) == 12:
                        potential_id = potential_id[1:]

                    # Validate it looks like a YouTube video ID
                    # YouTube IDs are exactly 11 characters: alphanumeric, hyphens, underscores
                    youtube_id_pattern = r'^[A-Za-z0-9_-]{11}$'

                    if re.match(youtube_id_pattern, potential_id):
                        result['youtube_video_id'] = potential_id
                        logger.debug(f"Extracted YouTube ID from direct URL: {potential_id}")
                    else:
                        logger.warning(f"YouTube ID '{potential_id}' from query parameter does not match expected pattern")
            else:
                # Try congress.gov committee video URL format
                # Expected format: https://www.congress.gov/committees/video/{chamber-committee}/{code}/{youtube-id}
                url_parts = video_url.rstrip('/').split('/')
                if url_parts:
                    potential_id = url_parts[-1]

                    # Strip erroneous leading hyphen from Congress.gov API bug
                    # API returns IDs like "-cuneRXGeLaQ" (12 chars) instead of "cuneRXGeLaQ" (11 chars)
                    if potential_id.startswith('-') and len(potential_id) == 12:
                        potential_id = potential_id[1:]

                    # Validate it looks like a YouTube video ID
                    # YouTube IDs are exactly 11 characters: alphanumeric, hyphens, underscores
                    youtube_id_pattern = r'^[A-Za-z0-9_-]{11}$'

                    if re.match(youtube_id_pattern, potential_id):
                        result['youtube_video_id'] = potential_id
                        logger.debug(f"Extracted YouTube ID from path: {potential_id}")
                    else:
                        logger.warning(f"Potential YouTube ID '{potential_id}' from path does not match expected pattern")

        except Exception as e:
            logger.error(f"Error parsing video URL '{video_url}': {e}")

        return result