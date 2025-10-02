"""
Member data parser
"""
from typing import Dict, Any, Optional, List
from parsers.base_parser import BaseParser
from parsers.models import MemberModel
from config.logging_config import get_logger

logger = get_logger(__name__)


class MemberParser(BaseParser):
    """Parser for member data from Congress.gov API"""

    def parse(self, raw_data: Dict[str, Any]) -> Optional[MemberModel]:
        """
        Parse raw member data into validated model

        Args:
            raw_data: Raw member data from API

        Returns:
            Validated MemberModel or None
        """
        # Required fields for members
        required_fields = ['bioguideId', 'name']
        if not self.validate_required_fields(raw_data, required_fields):
            if self.strict_mode:
                return None

        # Extract name components
        name_data = self._parse_name(raw_data)

        # Extract and normalize data
        member_data = {
            'bioguide_id': self.safe_get(raw_data, 'bioguideId'),
            'first_name': name_data['first_name'],
            'middle_name': name_data['middle_name'],
            'last_name': name_data['last_name'],
            'full_name': name_data['full_name'],
            'party': self._normalize_party(self.safe_get(raw_data, 'partyName')),
            'state': self._normalize_state(self.safe_get(raw_data, 'state')),
            'district': self._extract_district(raw_data),
            'birth_year': self._extract_birth_year(raw_data),
            'current_member': self.safe_get(raw_data, 'currentMember', True),
            'honorific_prefix': self._extract_honorific(raw_data),
            'official_url': self.safe_get(raw_data, 'officialWebsiteUrl'),
            'office_address': self._extract_office_address(raw_data),
            'phone': self._extract_phone(raw_data),
            'terms_served': self._extract_terms_served(raw_data),
            'congress': 119  # Set default congress, will be overridden by orchestrator
        }

        return self.validate_model(MemberModel, member_data)

    def _parse_name(self, raw_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Parse name components from member data

        Args:
            raw_data: Raw member data

        Returns:
            Dictionary with name components
        """
        # Try to get individual name components first
        first_name = self.safe_get(raw_data, 'firstName')
        middle_name = self.safe_get(raw_data, 'middleName')
        last_name = self.safe_get(raw_data, 'lastName')
        full_name = self.safe_get(raw_data, 'name')

        # If we have full name but missing components, try to parse
        if full_name and not (first_name and last_name):
            parsed = self._parse_full_name(full_name)
            first_name = first_name or parsed['first_name']
            middle_name = middle_name or parsed['middle_name']
            last_name = last_name or parsed['last_name']

        # Build full name if not provided
        if not full_name:
            name_parts = [first_name, middle_name, last_name]
            full_name = ' '.join(part for part in name_parts if part)

        return {
            'first_name': self.normalize_text(first_name or ''),
            'middle_name': self.normalize_text(middle_name) if middle_name else None,
            'last_name': self.normalize_text(last_name or ''),
            'full_name': self.normalize_text(full_name or '')
        }

    def _parse_full_name(self, full_name: str) -> Dict[str, Optional[str]]:
        """
        Parse full name into components

        Args:
            full_name: Full name string

        Returns:
            Dictionary with name components
        """
        parts = full_name.strip().split()

        if len(parts) == 0:
            return {'first_name': '', 'middle_name': None, 'last_name': ''}
        elif len(parts) == 1:
            return {'first_name': parts[0], 'middle_name': None, 'last_name': ''}
        elif len(parts) == 2:
            return {'first_name': parts[0], 'middle_name': None, 'last_name': parts[1]}
        else:
            # More than 2 parts - first, middle(s), last
            return {
                'first_name': parts[0],
                'middle_name': ' '.join(parts[1:-1]),
                'last_name': parts[-1]
            }

    def _normalize_party(self, party_data: Any) -> str:
        """
        Normalize party information

        Args:
            party_data: Party data from API

        Returns:
            Normalized party code
        """
        if not party_data:
            return 'Unknown'

        # Extract party name
        if isinstance(party_data, dict):
            party_name = party_data.get('name', party_data.get('abbreviation', ''))
        else:
            party_name = str(party_data)

        # Normalize to standard codes
        party_mapping = {
            'democratic': 'D',
            'democrat': 'D',
            'republican': 'R',
            'independent': 'I',
            'libertarian': 'L',
            'd': 'D',
            'r': 'R',
            'i': 'I',
            'l': 'L'
        }

        normalized = party_mapping.get(party_name.lower().strip(), party_name[:1].upper() if party_name else 'Unknown')
        return normalized

    def _normalize_state(self, state: str) -> str:
        """
        Normalize state to 2-letter code

        Args:
            state: State name or code

        Returns:
            2-letter state code
        """
        if not state:
            return 'XX'  # Unknown state

        state = state.strip().upper()

        # If already 2 letters, return as-is
        if len(state) == 2:
            return state

        # Map full state names to codes (partial list)
        state_mapping = {
            'ALABAMA': 'AL',
            'ALASKA': 'AK',
            'ARIZONA': 'AZ',
            'ARKANSAS': 'AR',
            'CALIFORNIA': 'CA',
            'COLORADO': 'CO',
            'CONNECTICUT': 'CT',
            'DELAWARE': 'DE',
            'FLORIDA': 'FL',
            'GEORGIA': 'GA',
            # Add more as needed
        }

        return state_mapping.get(state, state[:2] if len(state) >= 2 else 'XX')

    def _extract_district(self, raw_data: Dict[str, Any]) -> Optional[int]:
        """Extract district number for House members"""
        district = self.safe_get(raw_data, 'district')
        if district:
            return self.normalize_integer(district)

        # Try alternative field names
        district_num = self.safe_get(raw_data, 'districtNumber')
        if district_num:
            return self.normalize_integer(district_num)

        # Check if this is a Senator (no district)
        # This would be determined by chamber or other indicators
        return None

    def _extract_birth_year(self, raw_data: Dict[str, Any]) -> Optional[int]:
        """Extract birth year from member data"""
        birth_year = self.safe_get(raw_data, 'birthYear')
        if birth_year:
            return self.normalize_integer(birth_year)

        # Try to extract from birth date
        birth_date = self.safe_get(raw_data, 'birthDate')
        if birth_date:
            parsed_date = self.normalize_date(birth_date)
            if parsed_date:
                return parsed_date.year

        return None

    def _extract_honorific(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract honorific prefix"""
        honorific = self.safe_get(raw_data, 'honorificPrefix')
        if honorific:
            return self.normalize_text(honorific)

        # Check other possible fields
        title = self.safe_get(raw_data, 'title')
        if title and title.lower() in ['mr.', 'mrs.', 'ms.', 'dr.']:
            return title

        return None

    def _extract_office_address(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract office address"""
        # Check various possible fields
        address_fields = [
            'officeAddress',
            'office.address',
            'address',
            'contactInformation.address'
        ]

        for field in address_fields:
            address = self.safe_get(raw_data, field)
            if address:
                return self.normalize_text(address)

        return None

    def _extract_phone(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract phone number"""
        # Check various possible fields
        phone_fields = [
            'phone',
            'phoneNumber',
            'office.phone',
            'contactInformation.phone'
        ]

        for field in phone_fields:
            phone = self.safe_get(raw_data, field)
            if phone:
                return self.normalize_text(phone)

        return None

    def _extract_terms_served(self, raw_data: Dict[str, Any]) -> Optional[int]:
        """Extract number of terms served"""
        terms = self.safe_get(raw_data, 'termsServed')
        if terms:
            return self.normalize_integer(terms)

        # Try to count from terms array
        terms_array = self.safe_get(raw_data, 'terms', [])
        if terms_array:
            return len(terms_array)

        return None

    def extract_leadership_positions(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract leadership positions from member data

        Args:
            raw_data: Raw member data

        Returns:
            List of leadership position data
        """
        positions = []

        # Check for leadership information
        leadership_sources = [
            'leadershipRoles',
            'leadership',
            'positions'
        ]

        for source in leadership_sources:
            leadership_data = self.safe_get(raw_data, source, [])
            if leadership_data:
                for position in leadership_data:
                    position_data = {
                        'title': self.normalize_text(self.safe_get(position, 'title')),
                        'congress': self.normalize_integer(self.safe_get(position, 'congress')),
                        'is_current': self.safe_get(position, 'isCurrent', True)
                    }
                    positions.append(position_data)
                break

        return positions