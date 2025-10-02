"""
Bill data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class BillFetcher(BaseFetcher):
    """Fetches bill data from Congress.gov API"""

    def fetch_bill_details(self, congress: int, bill_type: str, bill_number: int) -> Optional[Dict[str, Any]]:
        """
        Fetch detailed bill information

        Args:
            congress: Congress number
            bill_type: Bill type (HR, S, HJRES, etc.)
            bill_number: Bill number

        Returns:
            Detailed bill information
        """
        try:
            return self.api_client.get_bill_details(congress, bill_type.lower(), bill_number)
        except Exception as e:
            logger.error(f"Error fetching bill {bill_type} {bill_number}: {e}")
            return None

    def fetch_bills_by_references(self, bill_references: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for a list of bill references

        Args:
            bill_references: List of bill references with congress, type, number

        Returns:
            List of detailed bill records
        """
        bills = []

        for ref in bill_references:
            congress = ref.get('congress')
            bill_type = ref.get('bill_type')
            bill_number = ref.get('bill_number')

            if congress and bill_type and bill_number:
                bill_details = self.fetch_bill_details(congress, bill_type, bill_number)
                if bill_details and 'bill' in bill_details:
                    bill_record = bill_details['bill']
                    # Add relationship context from reference
                    bill_record['relationship_type'] = ref.get('relationship_type', 'mentioned')
                    bills.append(bill_record)
                else:
                    # Create minimal record from reference
                    minimal_bill = {
                        'congress': congress,
                        'bill_type': bill_type,
                        'bill_number': bill_number,
                        'title': ref.get('title', ''),
                        'relationship_type': ref.get('relationship_type', 'mentioned')
                    }
                    bills.append(minimal_bill)

        return bills

    def normalize_bill_type(self, bill_type: str) -> str:
        """
        Normalize bill type to standard format

        Args:
            bill_type: Raw bill type from API

        Returns:
            Normalized bill type
        """
        # Map variations to standard types
        type_mapping = {
            'hr': 'HR',
            'house-bill': 'HR',
            's': 'S',
            'senate-bill': 'S',
            'hjres': 'HJRES',
            'house-joint-resolution': 'HJRES',
            'sjres': 'SJRES',
            'senate-joint-resolution': 'SJRES',
            'hconres': 'HCONRES',
            'house-concurrent-resolution': 'HCONRES',
            'sconres': 'SCONRES',
            'senate-concurrent-resolution': 'SCONRES',
            'hres': 'HRES',
            'house-resolution': 'HRES',
            'sres': 'SRES',
            'senate-resolution': 'SRES'
        }

        normalized = type_mapping.get(bill_type.lower(), bill_type.upper())
        return normalized

    def extract_bill_number(self, bill_identifier: str) -> tuple[Optional[str], Optional[int]]:
        """
        Extract bill type and number from identifier string

        Args:
            bill_identifier: Bill identifier (e.g., "HR 123", "S.456")

        Returns:
            Tuple of (bill_type, bill_number)
        """
        import re

        # Pattern to match various bill formats
        pattern = r'([HS])\.?([JCR]+)?\.?\s*(\d+)'
        match = re.match(pattern, bill_identifier.strip(), re.IGNORECASE)

        if match:
            chamber = match.group(1).upper()
            resolution_type = match.group(2)
            number = int(match.group(3))

            # Determine bill type
            if resolution_type:
                if resolution_type.upper() == 'J':
                    bill_type = f"{chamber}JRES"
                elif resolution_type.upper() == 'CON':
                    bill_type = f"{chamber}CONRES"
                else:
                    bill_type = f"{chamber}RES"
            else:
                bill_type = chamber + ('R' if chamber == 'H' else '')

            return bill_type, number

        return None, None

    def search_bills(self, congress: int, query: str) -> List[Dict[str, Any]]:
        """
        Search for bills by query string

        Args:
            congress: Congress number
            query: Search query

        Returns:
            List of matching bills
        """
        try:
            endpoint = f"bill/{congress}"
            params = {'q': query}

            bills = []
            for bill in self.api_client.paginate(endpoint, params):
                bills.append(bill)

            logger.info(f"Found {len(bills)} bills matching query: {query}")
            return bills

        except Exception as e:
            logger.error(f"Error searching bills: {e}")
            return []

    def fetch_bills_by_type(self, congress: int, bill_type: str) -> List[Dict[str, Any]]:
        """
        Fetch all bills of a specific type

        Args:
            congress: Congress number
            bill_type: Type of bills to fetch

        Returns:
            List of bills
        """
        try:
            endpoint = f"bill/{congress}/{bill_type.lower()}"

            bills = []
            for bill in self.api_client.paginate(endpoint):
                bills.append(bill)

            logger.info(f"Fetched {len(bills)} {bill_type} bills for Congress {congress}")
            return bills

        except Exception as e:
            logger.error(f"Error fetching {bill_type} bills: {e}")
            return []

    def fetch_all(self, congress: int, bill_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Implementation of abstract method from BaseFetcher

        Args:
            congress: Congress number
            bill_type: Specific bill type to fetch, or None for all

        Returns:
            List of bill records
        """
        if bill_type:
            return self.fetch_bills_by_type(congress, bill_type)
        else:
            # Fetch all bill types
            all_bills = []
            bill_types = ['HR', 'S', 'HJRES', 'SJRES', 'HCONRES', 'SCONRES', 'HRES', 'SRES']

            for bt in bill_types:
                bills = self.fetch_bills_by_type(congress, bt)
                all_bills.extend(bills)

            return all_bills