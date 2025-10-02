"""
Committee data parser
"""
from typing import Dict, Any, Optional, List
from parsers.base_parser import BaseParser
from parsers.models import CommitteeModel, CommitteeMembershipModel
from config.logging_config import get_logger

logger = get_logger(__name__)


class CommitteeParser(BaseParser):
    """Parser for committee data from Congress.gov API"""

    def parse(self, raw_data: Dict[str, Any]) -> Optional[CommitteeModel]:
        """
        Parse raw committee data into validated model

        Args:
            raw_data: Raw committee data from API

        Returns:
            Validated CommitteeModel or None
        """
        # Required fields for committees
        required_fields = ['systemCode', 'name', 'chamber']
        if not self.validate_required_fields(raw_data, required_fields):
            if self.strict_mode:
                return None

        # Extract and normalize data
        committee_data = {
            'system_code': self.safe_get(raw_data, 'systemCode'),
            'name': self.normalize_text(self.safe_get(raw_data, 'name')),
            'chamber': self._normalize_chamber(self.safe_get(raw_data, 'chamber')),
            'type': self._normalize_committee_type(self.safe_get(raw_data, 'type')),
            'is_current': self.safe_get(raw_data, 'isCurrent', True),
            'url': self.safe_get(raw_data, 'url'),
            'congress': self._extract_congress(raw_data)
        }

        # Handle parent committee relationship
        parent_code = self.safe_get(raw_data, 'parent.systemCode')
        if parent_code:
            # Note: parent_committee_id will need to be resolved during import
            # Store parent system code for now
            committee_data['parent_system_code'] = parent_code

        return self.validate_model(CommitteeModel, committee_data)

    def parse_roster(self, raw_roster: List[Dict[str, Any]], committee_id: int, congress: int) -> List[CommitteeMembershipModel]:
        """
        Parse committee roster data

        Args:
            raw_roster: Raw roster data from API
            committee_id: Committee ID for memberships
            congress: Congress number

        Returns:
            List of validated CommitteeMembershipModel instances
        """
        memberships = []

        for raw_member in raw_roster:
            # Extract membership data
            membership_data = {
                'committee_id': committee_id,
                'member_id': None,  # Will be resolved during import
                'bioguide_id': self.safe_get(raw_member, 'bioguideId'),
                'role': self._normalize_role(self.safe_get(raw_member, 'role', 'Member')),
                'congress': congress,
                'is_active': True
            }

            # Validate membership
            membership = self.validate_model(CommitteeMembershipModel, membership_data)
            if membership:
                memberships.append(membership)

        return memberships

    def _normalize_chamber(self, chamber: str) -> str:
        """Normalize chamber name"""
        if not chamber:
            return 'NoChamber'

        chamber_mapping = {
            'house': 'House',
            'senate': 'Senate',
            'joint': 'Joint',
            'nochamber': 'NoChamber'
        }

        normalized = chamber_mapping.get(chamber.lower(), chamber)
        return normalized

    def _normalize_committee_type(self, committee_type: str) -> str:
        """Normalize committee type"""
        if not committee_type:
            return 'Other'

        type_mapping = {
            'standing': 'Standing',
            'select': 'Select',
            'special': 'Special',
            'joint': 'Joint',
            'task force': 'Task Force',
            'subcommittee': 'Subcommittee',
            'commission': 'Commission or Caucus',
            'caucus': 'Commission or Caucus'
        }

        normalized = type_mapping.get(committee_type.lower(), committee_type)
        return normalized

    def _normalize_role(self, role: str) -> str:
        """Normalize committee member role"""
        if not role:
            return 'Member'

        role_mapping = {
            'chair': 'Chair',
            'chairman': 'Chair',
            'chairwoman': 'Chair',
            'chairperson': 'Chair',
            'ranking member': 'Ranking Member',
            'ranking': 'Ranking Member',
            'vice chair': 'Vice Chair',
            'vice chairman': 'Vice Chair',
            'vice chairwoman': 'Vice Chair',
            'member': 'Member'
        }

        normalized = role_mapping.get(role.lower(), role)
        return normalized

    def _extract_congress(self, raw_data: Dict[str, Any]) -> int:
        """Extract congress number from committee data"""
        congress = self.safe_get(raw_data, 'congress')
        if congress and str(congress).isdigit():
            return self.normalize_integer(congress)

        # Try to extract from URL
        url = self.safe_get(raw_data, 'url', '')
        if '/committee/' in url:
            parts = url.split('/committee/')
            if len(parts) > 1:
                congress_part = parts[1].split('/')[0]
                if congress_part.isdigit():
                    return self.normalize_integer(congress_part)

        # Default to current congress if not found
        from config.settings import settings
        return settings.target_congress

    def extract_subcommittees(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract subcommittee information from committee data

        Args:
            raw_data: Raw committee data

        Returns:
            List of subcommittee data dictionaries
        """
        subcommittees = []

        # Check for subcommittee information
        subcommittee_sources = [
            'subcommittees',
            'subCommittees',
            'children'
        ]

        for source in subcommittee_sources:
            subcommittee_data = self.safe_get(raw_data, source, [])
            if subcommittee_data:
                for subcommittee in subcommittee_data:
                    # Add parent reference
                    subcommittee['parent'] = {
                        'systemCode': self.safe_get(raw_data, 'systemCode')
                    }
                    subcommittees.append(subcommittee)
                break

        return subcommittees

    def is_subcommittee(self, raw_data: Dict[str, Any]) -> bool:
        """
        Check if committee data represents a subcommittee

        Args:
            raw_data: Raw committee data

        Returns:
            True if this is a subcommittee
        """
        # Check for parent reference
        if self.safe_get(raw_data, 'parent.systemCode'):
            return True

        # Check committee type
        committee_type = self.safe_get(raw_data, 'type', '').lower()
        if 'subcommittee' in committee_type:
            return True

        return False