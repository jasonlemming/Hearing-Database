"""
Member data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class MemberFetcher(BaseFetcher):
    """Fetches member data from Congress.gov API"""

    def fetch_current_members(self, congress: int) -> List[Dict[str, Any]]:
        """
        Fetch all current members for a specific congress

        Args:
            congress: Congress number (e.g., 119)

        Returns:
            List of current members
        """
        try:
            endpoint = f"member/congress/{congress}"
            params = {
                'currentMember': 'true'
            }

            members = []
            logger.info(f"Fetching current members for Congress {congress}")

            for member in self.api_client.paginate(endpoint, params):
                members.append(member)

            logger.info(f"Fetched {len(members)} current members")
            return members

        except Exception as e:
            logger.error(f"Error fetching current members: {e}")
            return []

    def fetch_member_details(self, bioguide_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed member information

        Args:
            bioguide_id: Member's bioguide identifier

        Returns:
            Detailed member information
        """
        try:
            return self.api_client.get_member_details(bioguide_id)
        except Exception as e:
            logger.error(f"Error fetching details for member {bioguide_id}: {e}")
            return None

    def fetch_all_with_details(self, congress: int) -> List[Dict[str, Any]]:
        """
        Fetch all current members with detailed information

        Args:
            congress: Congress number

        Returns:
            List of members with detailed information
        """
        basic_members = self.fetch_current_members(congress)
        detailed_members = []

        for member in basic_members:
            bioguide_id = self.safe_get(member, 'bioguideId')

            if bioguide_id:
                detailed = self.fetch_member_details(bioguide_id)
                if detailed and 'member' in detailed:
                    # Merge basic info with detailed info
                    detailed_member = detailed['member']
                    # Add congress info from basic record
                    detailed_member['congress'] = congress
                    detailed_members.append(detailed_member)
                else:
                    # Fall back to basic info
                    member['congress'] = congress
                    detailed_members.append(member)
            else:
                member['congress'] = congress
                detailed_members.append(member)

        return detailed_members

    def extract_leadership_positions(self, member_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract leadership positions from detailed member information

        Args:
            member_details: Detailed member data

        Returns:
            List of leadership positions
        """
        positions = []

        # Check for leadership information
        leadership_sources = [
            'leadershipRoles',
            'leadership',
            'positions'
        ]

        for source in leadership_sources:
            leadership_data = self.safe_get(member_details, source, [])
            if leadership_data:
                for position in leadership_data:
                    position_entry = {
                        'title': self.safe_get(position, 'title'),
                        'congress': self.safe_get(position, 'congress'),
                        'is_current': self.safe_get(position, 'isCurrent', True)
                    }
                    positions.append(position_entry)
                break

        return positions

    def extract_terms_served(self, member_details: Dict[str, Any]) -> int:
        """
        Extract number of terms served

        Args:
            member_details: Detailed member data

        Returns:
            Number of terms served
        """
        terms = self.safe_get(member_details, 'terms', [])
        if isinstance(terms, list):
            return len(terms)

        # Try alternative field names
        terms_served = self.safe_get(member_details, 'termsServed')
        if terms_served is not None:
            return int(terms_served)

        return 0

    def normalize_party(self, party_data: Any) -> str:
        """
        Normalize party information to standard codes

        Args:
            party_data: Party information from API

        Returns:
            Normalized party code
        """
        if isinstance(party_data, dict):
            party_name = party_data.get('name', '').upper()
        else:
            party_name = str(party_data).upper()

        # Map to standard codes
        party_mapping = {
            'DEMOCRATIC': 'D',
            'DEMOCRAT': 'D',
            'REPUBLICAN': 'R',
            'INDEPENDENT': 'I',
            'LIBERTARIAN': 'L'
        }

        return party_mapping.get(party_name, party_name[:1] if party_name else 'Unknown')

    def extract_district_number(self, member_details: Dict[str, Any]) -> Optional[int]:
        """
        Extract district number for House members

        Args:
            member_details: Member data

        Returns:
            District number or None for Senators
        """
        district = self.safe_get(member_details, 'district')
        if district and str(district).isdigit():
            return int(district)

        # Check alternative field names
        district_num = self.safe_get(member_details, 'districtNumber')
        if district_num and str(district_num).isdigit():
            return int(district_num)

        return None

    def fetch_all(self, congress: int, include_details: bool = False) -> List[Dict[str, Any]]:
        """
        Implementation of abstract method from BaseFetcher

        Args:
            congress: Congress number
            include_details: Whether to fetch detailed information

        Returns:
            List of member records
        """
        if include_details:
            return self.fetch_all_with_details(congress)
        else:
            return self.fetch_current_members(congress)