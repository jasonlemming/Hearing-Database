"""
Committee data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class CommitteeFetcher(BaseFetcher):
    """Fetches committee data from Congress.gov API"""

    def fetch_all_committees(self, congress: int) -> List[Dict[str, Any]]:
        """
        Fetch all committees for a specific congress

        Args:
            congress: Congress number (e.g., 119)

        Returns:
            List of all committees (House, Senate, Joint)
        """
        all_committees = []

        # Fetch from each chamber
        chambers = ['house', 'senate', 'joint']

        for chamber in chambers:
            try:
                endpoint = f"committee/{congress}/{chamber}"
                logger.info(f"Fetching {chamber} committees for Congress {congress}")

                for committee in self.api_client.paginate(endpoint):
                    committee['chamber'] = chamber.title()
                    all_committees.append(committee)

                logger.info(f"Fetched {len([c for c in all_committees if c['chamber'] == chamber.title()])} {chamber} committees")

            except Exception as e:
                logger.error(f"Error fetching {chamber} committees: {e}")

        logger.info(f"Total committees fetched: {len(all_committees)}")
        return all_committees

    def fetch_committee_details(self, chamber: str, committee_code: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed committee information including roster

        Args:
            chamber: Chamber name (house, senate, joint)
            committee_code: Committee system code

        Returns:
            Detailed committee information
        """
        try:
            return self.api_client.get_committee_details(chamber.lower(), committee_code)
        except Exception as e:
            logger.error(f"Error fetching details for committee {committee_code}: {e}")
            return None

    def fetch_all_with_details(self, congress: int) -> List[Dict[str, Any]]:
        """
        Fetch all committees with detailed information

        Args:
            congress: Congress number

        Returns:
            List of committees with detailed information
        """
        basic_committees = self.fetch_all_committees(congress)
        detailed_committees = []

        for committee in basic_committees:
            system_code = self.safe_get(committee, 'systemCode')
            chamber = self.safe_get(committee, 'chamber', '').lower()

            if system_code and chamber:
                detailed = self.fetch_committee_details(chamber, system_code)
                if detailed and 'committee' in detailed:
                    # Merge basic info with detailed info
                    detailed_committee = detailed['committee']
                    detailed_committee['chamber'] = chamber.title()
                    detailed_committees.append(detailed_committee)
                else:
                    # Fall back to basic info
                    detailed_committees.append(committee)
            else:
                detailed_committees.append(committee)

        return detailed_committees

    def extract_committee_roster(self, committee_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract committee roster from detailed committee information

        Args:
            committee_details: Detailed committee data

        Returns:
            List of committee members with roles
        """
        roster = []

        # Check for membership information in various possible locations
        membership_sources = [
            'members',
            'committeeMembers',
            'roster.members'
        ]

        for source in membership_sources:
            members = self.safe_get(committee_details, source, [])
            if members:
                for member in members:
                    roster_entry = {
                        'bioguide_id': self.safe_get(member, 'bioguideId'),
                        'name': self.safe_get(member, 'name'),
                        'party': self.safe_get(member, 'party'),
                        'state': self.safe_get(member, 'state'),
                        'role': self.safe_get(member, 'role', 'Member'),
                        'rank': self.safe_get(member, 'rank')
                    }
                    roster.append(roster_entry)
                break

        return roster

    def fetch_all(self, congress: int, include_details: bool = False) -> List[Dict[str, Any]]:
        """
        Implementation of abstract method from BaseFetcher

        Args:
            congress: Congress number
            include_details: Whether to fetch detailed information

        Returns:
            List of committee records
        """
        if include_details:
            return self.fetch_all_with_details(congress)
        else:
            return self.fetch_all_committees(congress)