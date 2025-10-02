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
            'congressGovUrl',
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