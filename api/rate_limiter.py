"""
Rate limiter for Congress.gov API
"""
import time
from typing import List
from config.logging_config import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter to respect API limits (5,000 requests per hour)"""

    def __init__(self, max_requests: int = 5000, time_window: int = 3600):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds (default 1 hour)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests: List[float] = []

    def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded"""
        now = time.time()

        # Remove requests older than time_window
        self.requests = [req for req in self.requests
                        if now - req < self.time_window]

        if len(self.requests) >= self.max_requests:
            # Calculate wait time
            oldest = self.requests[0]
            wait_time = self.time_window - (now - oldest) + 1
            logger.warning(f"Rate limit reached. Waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
            self.requests = []

        self.requests.append(now)

    def get_remaining_requests(self) -> int:
        """Get number of requests remaining in current window"""
        now = time.time()
        self.requests = [req for req in self.requests
                        if now - req < self.time_window]
        return max(0, self.max_requests - len(self.requests))

    def get_reset_time(self) -> float:
        """Get time when rate limit resets (Unix timestamp)"""
        if not self.requests:
            return time.time()
        return self.requests[0] + self.time_window