"""
Congress.gov API client with rate limiting and error handling
"""
import time
import socket
from typing import Dict, Any, Optional, Generator, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from api.rate_limiter import RateLimiter
from utils.circuit_breaker import CircuitBreaker, CircuitBreakerError
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

# Set global socket timeout at module import time
# This ensures ALL threads (including ThreadPoolExecutor workers) have timeout
_SOCKET_TIMEOUT = settings.read_timeout + 5  # 20 seconds (15s read + 5s buffer)
socket.setdefaulttimeout(_SOCKET_TIMEOUT)
logger.info(f"Set global socket timeout to {_SOCKET_TIMEOUT} seconds")


class CongressAPIClient:
    """Client for Congress.gov API v3 with rate limiting"""

    def __init__(self, api_key: Optional[str] = None, rate_limit: int = 5000):
        """
        Initialize API client

        Args:
            api_key: API key for Congress.gov (defaults to settings)
            rate_limit: Requests per hour limit
        """
        # EMERGENCY BYPASS: Read directly from environment if not provided
        import os
        if not api_key:
            api_key = os.environ.get('CONGRESS_API_KEY') or os.environ.get('API_KEY')
            logger.info(f"[BYPASS] Reading API key directly from environment: {bool(api_key)}")

        self.api_key = api_key or settings.api_key
        self.base_url = settings.api_base_url
        self.rate_limiter = RateLimiter(max_requests=rate_limit)

        # Validate API key
        if self.api_key:
            # Strip any surrounding quotes that might have been included
            self.api_key = self.api_key.strip('"').strip("'")
            logger.info(f"API client initialized with key: {self.api_key[:8]}... (length: {len(self.api_key)})")
            if len(self.api_key) != 40:
                logger.warning(f"API key length is {len(self.api_key)}, expected 40. This may cause authentication failures.")
        else:
            logger.error("API client initialized WITHOUT an API key! All requests will fail.")
            logger.error(f"[DEBUG] settings.api_key = {settings.api_key}")
            logger.error(f"[DEBUG] CONGRESS_API_KEY env = {os.environ.get('CONGRESS_API_KEY', 'NOT SET')[:20]}...")
            logger.error(f"[DEBUG] API_KEY env = {os.environ.get('API_KEY', 'NOT SET')[:20]}...")

        # Initialize circuit breaker if enabled
        self.circuit_breaker = None
        if settings.circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=settings.circuit_breaker_threshold,
                recovery_timeout=settings.circuit_breaker_timeout,
                success_threshold=2,
                name="congress_api"
            )

        # Configure session with enhanced retry strategy
        # Uses exponential backoff: 2s → 4s → 8s
        self.session = requests.Session()

        retry_strategy = Retry(
            total=settings.retry_attempts,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=settings.retry_backoff_factor,
            raise_on_status=False  # Don't raise exception on retry exhaustion
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.session.headers.update({
            'User-Agent': 'Congressional-Hearing-Database/1.0',
            'Accept': 'application/json'
        })

        # Track retry statistics
        self.retry_count = 0
        self.last_retry_time = None

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make GET request to API endpoint with circuit breaker protection

        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            JSON response as dictionary

        Raises:
            CircuitBreakerError: If circuit breaker is open
            requests.RequestException: On API error
        """
        # Define the actual request logic
        def _make_request():
            # Apply rate limiting
            self.rate_limiter.wait_if_needed()

            # Prepare request
            url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
            request_params = params or {}
            request_params['api_key'] = self.api_key
            request_params['format'] = 'json'

            logger.debug(f"GET {url} with params: {request_params}")

            # DIAGNOSTIC: Log request start with timestamp
            start_time = time.time()
            logger.debug(f"[TIMEOUT DEBUG] Starting request to {endpoint} at {start_time:.3f}")

            try:
                # Use tuple timeout: (connect_timeout, read_timeout)
                # This prevents hanging on unresponsive servers
                timeout = (settings.connect_timeout, settings.read_timeout)
                response = self.session.get(
                    url,
                    params=request_params,
                    timeout=timeout
                )

                # DIAGNOSTIC: Log request completion
                elapsed = time.time() - start_time
                logger.debug(f"[TIMEOUT DEBUG] Completed request to {endpoint} in {elapsed:.3f}s")

                # Track retry statistics if request was retried
                if hasattr(response.raw, 'retries') and response.raw.retries:
                    retry_count = response.raw.retries.total
                    if retry_count > 0:
                        self.retry_count += retry_count
                        self.last_retry_time = time.time()
                        logger.warning(f"Request to {endpoint} required {retry_count} retries")

                response.raise_for_status()

                data = response.json()
                logger.debug(f"Response: {len(data)} bytes")
                return data

            except socket.timeout as e:
                elapsed = time.time() - start_time
                logger.error(f"[TIMEOUT DEBUG] Socket timeout after {elapsed:.3f}s on {endpoint}: {e}")
                raise
            except requests.exceptions.Timeout as e:
                elapsed = time.time() - start_time
                logger.error(f"[TIMEOUT DEBUG] Requests timeout after {elapsed:.3f}s on {endpoint}: {e}")
                raise
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[TIMEOUT DEBUG] Request failed after {elapsed:.3f}s on {endpoint}: {type(e).__name__}: {e}")
                raise

        # Execute with circuit breaker if enabled
        try:
            if self.circuit_breaker:
                return self.circuit_breaker.call(_make_request)
            else:
                return _make_request()

        except CircuitBreakerError:
            # Re-raise circuit breaker errors for visibility
            raise

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed after retries: {e}")
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

    def get_retry_stats(self) -> Dict[str, Any]:
        """
        Get retry statistics

        Returns:
            Dictionary with retry_count and last_retry_time
        """
        return {
            'total_retries': self.retry_count,
            'last_retry_time': self.last_retry_time
        }

    def get_circuit_breaker_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get circuit breaker statistics

        Returns:
            Circuit breaker stats dict or None if disabled
        """
        if self.circuit_breaker:
            return self.circuit_breaker.get_stats()
        return None

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