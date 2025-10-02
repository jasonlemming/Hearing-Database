"""
Congress.gov API client with rate limiting and error handling
"""
import time
from typing import Dict, Any, Optional, Generator, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.rate_limiter import RateLimiter
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class CongressAPIClient:
    """Client for Congress.gov API v3 with rate limiting"""

    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 5000):
        """
        Initialize API client

        Args:
            api_key: API key for Congress.gov (defaults to settings)
            rate_limit: Requests per hour limit
        """
        self.api_key = api_key or settings.api_key
        self.base_url = settings.api_base_url
        self.rate_limiter = RateLimiter(max_requests=rate_limit)

        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'Congressional-Hearing-Database/1.0',
            'Accept': 'application/json'
        })

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to API endpoint

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            requests.RequestException: On API error
        """
        # Apply rate limiting
        self.rate_limiter.wait_if_needed()

        # Prepare request
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        params = params or {}
        params['api_key'] = self.api_key
        params['format'] = 'json'

        logger.debug(f"GET {url} with params: {params}")

        try:
            response = self.session.get(
                url,
                params=params,
                timeout=settings.request_timeout
            )
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Response: {len(data)} bytes")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def paginate(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Paginate through all results for an endpoint

        Args:
            endpoint: API endpoint
            params: Query parameters

        Yields:
            Individual items from paginated response
        """
        params = params or {}
        params['limit'] = 250  # Maximum allowed by API
        offset = 0

        while True:
            params['offset'] = offset
            response = self.get(endpoint, params)

            # Extract items based on common response patterns
            items = []
            if 'committees' in response:
                items = response['committees']
            elif 'members' in response:
                items = response['members']
            elif 'committeeMeetings' in response:
                items = response['committeeMeetings']
            elif 'committee_meetings' in response:
                items = response['committee_meetings']
            elif 'bills' in response:
                items = response['bills']
            elif 'hearings' in response:
                items = response['hearings']
            else:
                # Try to find the main data array
                for key in response:
                    if isinstance(response[key], list) and key != 'request':
                        items = response[key]
                        break

            if not items:
                break

            yield from items

            # Check if we got fewer results than requested (last page)
            if len(items) < params['limit']:
                break

            offset += params['limit']
            logger.debug(f"Fetched {offset} items from {endpoint}")

    def check_rate_limit(self) -> tuple[int, float]:
        """
        Check current rate limit status

        Returns:
            Tuple of (remaining_requests, reset_time)
        """
        remaining = self.rate_limiter.get_remaining_requests()
        reset_time = self.rate_limiter.get_reset_time()
        return remaining, reset_time

    def get_committee_details(self, chamber: str, committee_code: str) -> Dict[str, Any]:
        """Get detailed committee information including roster"""
        endpoint = f"committee/{chamber}/{committee_code}"
        return self.get(endpoint)

    def get_member_details(self, bioguide_id: str) -> Dict[str, Any]:
        """Get detailed member information"""
        endpoint = f"member/{bioguide_id}"
        return self.get(endpoint)

    def get_hearing_details(self, congress: int, chamber: str, event_id: str) -> Dict[str, Any]:
        """Get detailed hearing information"""
        endpoint = f"committee-meeting/{congress}/{chamber}/{event_id}"
        return self.get(endpoint)

    def get_bill_details(self, congress: int, bill_type: str, bill_number: int) -> Dict[str, Any]:
        """Get detailed bill information"""
        endpoint = f"bill/{congress}/{bill_type}/{bill_number}"
        return self.get(endpoint)

    def get_hearing_transcript(self, congress: int, chamber: str, jacket_number: str) -> Dict[str, Any]:
        """Get hearing transcript information"""
        endpoint = f"hearing/{congress}/{chamber}/{jacket_number}"
        return self.get(endpoint)