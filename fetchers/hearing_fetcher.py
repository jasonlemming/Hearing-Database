"""
Hearing data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class HearingFetcher(BaseFetcher):
    """Fetches hearing/committee meeting data from Congress.gov API"""

    def fetch_hearings(self, congress: int, chamber: Optional[str] = None,
                      from_date: Optional[str] = None, to_date: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch committee meetings/hearings

        Args:
            congress: Congress number
            chamber: Specific chamber (house, senate) or None for all
            from_date: Start date filter (YYYY-MM-DD)
            to_date: End date filter (YYYY-MM-DD)

        Returns:
            List of hearing records
        """
        all_hearings = []

        # Determine chambers to fetch
        chambers = [chamber.lower()] if chamber else ['house', 'senate']

        for chamber_name in chambers:
            try:
                endpoint = f"committee-meeting/{congress}/{chamber_name}"
                params = {}

                if from_date:
                    params['fromDateTime'] = from_date
                if to_date:
                    params['toDateTime'] = to_date

                logger.info(f"Fetching {chamber_name} hearings for Congress {congress}")

                for hearing in self.api_client.paginate(endpoint, params):
                    hearing['chamber'] = chamber_name.title()
                    all_hearings.append(hearing)

                logger.info(f"Fetched {len([h for h in all_hearings if h['chamber'] == chamber_name.title()])} {chamber_name} hearings")

            except Exception as e:
                logger.error(f"Error fetching {chamber_name} hearings: {e}")

        logger.info(f"Total hearings fetched: {len(all_hearings)}")
        return all_hearings

    def fetch_recent_hearings(self, congress: int, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Fetch recent hearings within specified number of days

        Args:
            congress: Congress number
            days_back: Number of days to look back

        Returns:
            List of recent hearing records
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        from_date = start_date.strftime('%Y-%m-%d')
        to_date = end_date.strftime('%Y-%m-%d')

        return self.fetch_hearings(congress, from_date=from_date, to_date=to_date)

    def fetch_hearing_details(self, congress: int, chamber: str, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed hearing information

        Args:
            congress: Congress number
            chamber: Chamber name
            event_id: Hearing event ID

        Returns:
            Detailed hearing information
        """
        try:
            return self.api_client.get_hearing_details(congress, chamber.lower(), event_id)
        except Exception as e:
            logger.error(f"Error fetching details for hearing {event_id}: {e}")
            return None

    def fetch_all_with_details(self, congress: int) -> List[Dict[str, Any]]:
        """
        Fetch all hearings with detailed information

        Args:
            congress: Congress number

        Returns:
            List of hearings with detailed information
        """
        basic_hearings = self.fetch_hearings(congress)
        detailed_hearings = []

        for hearing in basic_hearings:
            event_id = self.safe_get(hearing, 'eventId')
            chamber = self.safe_get(hearing, 'chamber', '').lower()

            if event_id and chamber:
                detailed = self.fetch_hearing_details(congress, chamber, event_id)
                if detailed and 'committeeEvent' in detailed:
                    # Merge basic info with detailed info
                    detailed_hearing = detailed['committeeEvent']
                    detailed_hearing['chamber'] = chamber.title()
                    detailed_hearings.append(detailed_hearing)
                else:
                    # Fall back to basic info
                    detailed_hearings.append(hearing)
            else:
                detailed_hearings.append(hearing)

        return detailed_hearings

    def extract_committee_references(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract committee references from hearing details

        Args:
            hearing_details: Detailed hearing data

        Returns:
            List of committee references
        """
        committees = []

        # Check various possible locations for committee info
        committee_sources = [
            'committees',
            'committee',
            'committeeInfo'
        ]

        for source in committee_sources:
            committee_data = self.safe_get(hearing_details, source)
            if committee_data:
                if isinstance(committee_data, list):
                    for committee in committee_data:
                        committees.append({
                            'system_code': self.safe_get(committee, 'systemCode'),
                            'name': self.safe_get(committee, 'name'),
                            'is_primary': committees == []  # First committee is primary
                        })
                elif isinstance(committee_data, dict):
                    committees.append({
                        'system_code': self.safe_get(committee_data, 'systemCode'),
                        'name': self.safe_get(committee_data, 'name'),
                        'is_primary': True
                    })
                break

        return committees

    def extract_bill_references(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract bill references from hearing details

        Args:
            hearing_details: Detailed hearing data

        Returns:
            List of bill references
        """
        bills = []

        # Check for related items
        related_items = self.safe_get(hearing_details, 'relatedItems', [])
        for item in related_items:
            if self.safe_get(item, 'type') == 'bill':
                bill_info = {
                    'congress': self.safe_get(item, 'congress'),
                    'bill_type': self.safe_get(item, 'type'),
                    'bill_number': self.safe_get(item, 'number'),
                    'title': self.safe_get(item, 'title'),
                    'relationship_type': 'mentioned'  # Default relationship
                }
                bills.append(bill_info)

        # Also check hearing title for bill references
        title = self.safe_get(hearing_details, 'title', '')
        bill_patterns = self._extract_bills_from_text(title)
        bills.extend(bill_patterns)

        return bills

    def extract_witnesses(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract witness information from hearing details

        Args:
            hearing_details: Detailed hearing data

        Returns:
            List of witness records
        """
        witnesses = []

        # Check for witness information
        witness_sources = [
            'witnesses',
            'testimony',
            'participants'
        ]

        for source in witness_sources:
            witness_data = self.safe_get(hearing_details, source, [])
            if witness_data:
                for i, witness in enumerate(witness_data):
                    witness_record = {
                        'first_name': self.safe_get(witness, 'firstName'),
                        'last_name': self.safe_get(witness, 'lastName'),
                        'full_name': self.safe_get(witness, 'name') or self._build_full_name(witness),
                        'title': self.safe_get(witness, 'title'),
                        'organization': self.safe_get(witness, 'organization'),
                        'position': self.safe_get(witness, 'position'),
                        'witness_type': self.safe_get(witness, 'type'),
                        'appearance_order': i + 1
                    }
                    witnesses.append(witness_record)
                break

        return witnesses

    def _build_full_name(self, witness: Dict[str, Any]) -> str:
        """Build full name from first and last name"""
        first = self.safe_get(witness, 'firstName', '')
        last = self.safe_get(witness, 'lastName', '')
        return f"{first} {last}".strip()

    def _extract_bills_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract bill references from text using pattern matching

        Args:
            text: Text to search

        Returns:
            List of bill references found
        """
        import re
        bills = []

        # Pattern for bills: H.R. 123, S. 456, etc.
        bill_pattern = r'\b([HS])\.?R?\.?\s*(\d+)\b'
        matches = re.finditer(bill_pattern, text, re.IGNORECASE)

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

    def fetch_all(self, congress: int, include_details: bool = False) -> List[Dict[str, Any]]:
        """
        Implementation of abstract method from BaseFetcher

        Args:
            congress: Congress number
            include_details: Whether to fetch detailed information

        Returns:
            List of hearing records
        """
        if include_details:
            return self.fetch_all_with_details(congress)
        else:
            return self.fetch_hearings(congress)