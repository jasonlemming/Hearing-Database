"""
Witness data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional, Tuple
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class WitnessFetcher(BaseFetcher):
    """Fetches witness data from Congress.gov API hearing details"""

    def __init__(self, api_client=None):
        """Initialize with API client"""
        if api_client is None:
            from api.client import CongressAPIClient
            api_client = CongressAPIClient()
        super().__init__(api_client)

    def fetch_all(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch all witnesses from database hearings (required abstract method)

        Returns:
            List of all witness records
        """
        congress = kwargs.get('congress', 119)
        limit = kwargs.get('limit', None)

        witnesses_data = self.fetch_witnesses_from_database_hearings(congress, limit)

        # Flatten all witnesses into a single list
        all_witnesses = []
        for event_id, (witnesses, docs) in witnesses_data.items():
            all_witnesses.extend(witnesses)

        return all_witnesses

    def fetch_witnesses_for_hearing(self, congress: int, chamber: str, event_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetch witnesses and their documents for a specific hearing

        Args:
            congress: Congress number
            chamber: Chamber name (house/senate)
            event_id: Hearing event ID

        Returns:
            Tuple of (witnesses_list, witness_documents_list)
        """
        try:
            logger.info(f"Fetching witnesses for hearing {event_id} in {chamber} congress {congress}")

            # Get hearing details using existing API client method
            hearing_details = self.api_client.get_hearing_details(congress, chamber, event_id)

            if not hearing_details or 'committeeMeeting' not in hearing_details:
                logger.warning(f"No hearing details found for event {event_id}")
                return [], []

            committee_meeting = hearing_details['committeeMeeting']

            # Extract witnesses
            witnesses = committee_meeting.get('witnesses', [])
            witness_documents = committee_meeting.get('witnessDocuments', [])

            logger.info(f"Found {len(witnesses)} witnesses and {len(witness_documents)} witness documents for event {event_id}")

            # Add metadata to witnesses
            for i, witness in enumerate(witnesses):
                witness['hearing_event_id'] = event_id
                witness['hearing_congress'] = congress
                witness['hearing_chamber'] = chamber
                witness['appearance_order'] = i + 1  # 1-based ordering

            # Add metadata to witness documents
            for doc in witness_documents:
                doc['hearing_event_id'] = event_id
                doc['hearing_congress'] = congress
                doc['hearing_chamber'] = chamber

            return witnesses, witness_documents

        except Exception as e:
            logger.error(f"Error fetching witnesses for hearing {event_id}: {e}")
            return [], []

    def fetch_witnesses_for_multiple_hearings(self, hearing_specs: List[Tuple[int, str, str]]) -> Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """
        Fetch witnesses for multiple hearings

        Args:
            hearing_specs: List of (congress, chamber, event_id) tuples

        Returns:
            Dictionary mapping event_id to (witnesses, witness_documents) tuple
        """
        results = {}

        for congress, chamber, event_id in hearing_specs:
            try:
                witnesses, documents = self.fetch_witnesses_for_hearing(congress, chamber, event_id)
                results[event_id] = (witnesses, documents)

                # Rate limiting - respect API limits
                self.api_client.rate_limiter.wait_if_needed()

            except Exception as e:
                logger.error(f"Error fetching witnesses for hearing {event_id}: {e}")
                results[event_id] = ([], [])

        return results

    def fetch_witnesses_from_database_hearings(self, congress: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]:
        """
        Fetch witnesses for hearings that exist in the database

        Args:
            congress: Optional congress filter
            limit: Optional limit on number of hearings to process

        Returns:
            Dictionary mapping event_id to (witnesses, witness_documents) tuple
        """
        from database.manager import DatabaseManager

        db = DatabaseManager()

        try:
            with db.transaction() as conn:
                # Get hearings with event IDs from database
                query = '''
                    SELECT DISTINCT h.event_id, h.congress, h.chamber
                    FROM hearings h
                    WHERE h.event_id IS NOT NULL
                    AND h.event_id != ''
                '''
                params = []

                if congress:
                    query += ' AND h.congress = ?'
                    params.append(congress)

                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)

                cursor = conn.execute(query, params)
                hearings = cursor.fetchall()

                logger.info(f"Found {len(hearings)} hearings with event IDs to process for witness data")

        except Exception as e:
            logger.error(f"Error querying database for hearings: {e}")
            return {}

        # Convert to required format and fetch witnesses
        hearing_specs = [(int(h[1]), h[2].lower(), h[0]) for h in hearings if h[0]]
        return self.fetch_witnesses_for_multiple_hearings(hearing_specs)

    def extract_witness_info(self, witness_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize witness information from API data

        Args:
            witness_data: Raw witness data from API

        Returns:
            Normalized witness data
        """
        # Parse name - Congress.gov typically provides formal names
        name = witness_data.get('name', '').strip()

        # Extract title/honorific and clean name
        cleaned_name = self._clean_witness_name(name)
        first_name, last_name = self._parse_witness_name(cleaned_name)

        return {
            'full_name': cleaned_name or name,
            'first_name': first_name,
            'last_name': last_name,
            'title': witness_data.get('position', '').strip() or None,
            'organization': witness_data.get('organization', '').strip() or None,
            'hearing_event_id': witness_data.get('hearing_event_id'),
            'hearing_congress': witness_data.get('hearing_congress'),
            'hearing_chamber': witness_data.get('hearing_chamber'),
            'appearance_order': witness_data.get('appearance_order', 1)
        }

    def _clean_witness_name(self, name: str) -> str:
        """
        Clean witness name by removing titles and honorifics

        Args:
            name: Raw name string

        Returns:
            Cleaned name
        """
        if not name:
            return name

        # Common honorifics and titles to remove
        titles_to_remove = [
            'The Honorable ', 'Hon. ', 'Mr. ', 'Ms. ', 'Mrs. ', 'Dr. ', 'Prof. ',
            'Senator ', 'Representative ', 'Rep. ', 'Sen. ', 'Admiral ', 'General ',
            'Colonel ', 'Major ', 'Captain ', 'Lieutenant ', 'Sergeant '
        ]

        cleaned = name
        for title in titles_to_remove:
            if cleaned.startswith(title):
                cleaned = cleaned[len(title):]
                break

        return cleaned.strip()

    def _parse_witness_name(self, name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse witness name into first and last name components

        Args:
            name: Full name string

        Returns:
            Tuple of (first_name, last_name)
        """
        if not name:
            return None, None

        parts = name.strip().split()

        if len(parts) == 0:
            return None, None
        elif len(parts) == 1:
            return parts[0], None
        else:
            # Take first part as first name, rest as last name
            first_name = parts[0]
            last_name = ' '.join(parts[1:])
            return first_name, last_name

    def infer_witness_type(self, witness_data: Dict[str, Any]) -> str:
        """
        Infer witness type from organization and position information

        Args:
            witness_data: Witness data

        Returns:
            Witness type category
        """
        organization = witness_data.get('organization', '').lower()
        position = witness_data.get('title', '').lower()

        # Government indicators
        gov_indicators = [
            'department of', 'agency', 'bureau', 'office of', 'administration',
            'commission', 'federal', 'u.s.', 'united states', 'government',
            'secretary', 'administrator', 'director', 'commissioner'
        ]

        if any(indicator in organization for indicator in gov_indicators):
            return 'Government'

        if any(indicator in position for indicator in ['secretary', 'administrator', 'commissioner']):
            return 'Government'

        # Academic indicators
        academic_indicators = [
            'university', 'college', 'institute', 'school', 'research',
            'academic', 'professor', 'dr.', 'phd'
        ]

        if any(indicator in organization for indicator in academic_indicators):
            return 'Academic'

        if any(indicator in position for indicator in ['professor', 'researcher']):
            return 'Academic'

        # Nonprofit indicators
        nonprofit_indicators = [
            'foundation', 'association', 'society', 'council', 'coalition',
            'alliance', 'nonprofit', 'non-profit', 'center for', 'institute for'
        ]

        if any(indicator in organization for indicator in nonprofit_indicators):
            return 'Nonprofit'

        # Default to private sector
        return 'Private'

    def get_witness_statistics(self, witnesses_data: Dict[str, Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]]) -> Dict[str, Any]:
        """
        Generate statistics about collected witness data

        Args:
            witnesses_data: Dictionary of event_id -> (witnesses, documents)

        Returns:
            Statistics dictionary
        """
        total_hearings = len(witnesses_data)
        total_witnesses = 0
        total_documents = 0
        hearings_with_witnesses = 0
        witness_types = {}
        organizations = {}

        for event_id, (witnesses, documents) in witnesses_data.items():
            if witnesses:
                hearings_with_witnesses += 1
                total_witnesses += len(witnesses)

                for witness in witnesses:
                    # Count witness types
                    witness_type = self.infer_witness_type(witness)
                    witness_types[witness_type] = witness_types.get(witness_type, 0) + 1

                    # Count organizations
                    org = witness.get('organization', 'Unknown')
                    organizations[org] = organizations.get(org, 0) + 1

            total_documents += len(documents)

        return {
            'total_hearings_processed': total_hearings,
            'hearings_with_witnesses': hearings_with_witnesses,
            'total_witnesses': total_witnesses,
            'total_witness_documents': total_documents,
            'average_witnesses_per_hearing': total_witnesses / max(hearings_with_witnesses, 1),
            'witness_types': witness_types,
            'top_organizations': dict(sorted(organizations.items(), key=lambda x: x[1], reverse=True)[:10])
        }