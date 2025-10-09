"""
CRS Content Fetcher - Fetches HTML content from congress.gov CRS report pages
"""
import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, Browser
from config.logging_config import get_logger

logger = get_logger(__name__)


class CRSContentFetcher:
    """
    Fetches HTML content for CRS reports from congress.gov

    Note: This fetcher downloads HTML pages directly, not API JSON.
    It implements rate limiting to be respectful to congress.gov servers.
    """

    def __init__(self, rate_limit_delay: float = 0.5, timeout: int = 30, max_retries: int = 3):
        """
        Initialize CRS content fetcher

        Args:
            rate_limit_delay: Delay between requests in seconds (default: 0.5s = 2 req/sec)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.last_request_time = 0
        self.session = requests.Session()

        # Set user agent to identify our scraper
        self.session.headers.update({
            'User-Agent': 'Congressional-Hearing-Database-Bot/1.0 (Educational/Research)',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9'
        })

        # Statistics
        self.stats = {
            'requests_made': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'total_bytes': 0,
            'total_time': 0.0
        }

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        time_since_last = time.time() - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()

    def fetch_html(self, url: str) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Fetch HTML content from a URL with retries and error handling

        Args:
            url: URL to fetch

        Returns:
            Tuple of (html_content, metadata) or None if fetch failed
            metadata includes: status_code, size_bytes, fetch_time_ms
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                # Rate limiting
                self._rate_limit()

                # Make request
                start_time = time.time()
                logger.debug(f"Fetching {url} (attempt {attempt}/{self.max_retries})")

                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()  # Raise exception for 4xx/5xx status codes

                # Calculate metrics
                fetch_time = (time.time() - start_time) * 1000  # Convert to ms
                size_bytes = len(response.content)

                # Update statistics
                self.stats['requests_made'] += 1
                self.stats['successful_fetches'] += 1
                self.stats['total_bytes'] += size_bytes
                self.stats['total_time'] += fetch_time

                metadata = {
                    'status_code': response.status_code,
                    'size_bytes': size_bytes,
                    'fetch_time_ms': round(fetch_time, 2),
                    'content_type': response.headers.get('Content-Type', ''),
                    'fetched_at': datetime.now().isoformat()
                }

                logger.info(f"✓ Fetched {url} ({size_bytes:,} bytes, {fetch_time:.0f}ms)")
                return response.text, metadata

            except requests.exceptions.HTTPError as e:
                self.stats['requests_made'] += 1
                self.stats['failed_fetches'] += 1

                if e.response.status_code == 403:
                    logger.error(f"✗ 403 Forbidden: {url} - May need authentication or different headers")
                    return None  # Don't retry 403s
                elif e.response.status_code == 404:
                    logger.warning(f"✗ 404 Not Found: {url}")
                    return None  # Don't retry 404s
                elif attempt < self.max_retries:
                    wait_time = attempt * 2  # Exponential backoff: 2s, 4s, 6s
                    logger.warning(f"✗ HTTP {e.response.status_code}: {url}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"✗ Failed after {self.max_retries} attempts: {url} ({e})")

            except requests.exceptions.Timeout:
                self.stats['requests_made'] += 1
                self.stats['failed_fetches'] += 1

                if attempt < self.max_retries:
                    logger.warning(f"✗ Timeout fetching {url}, retrying...")
                    time.sleep(attempt * 2)
                else:
                    logger.error(f"✗ Timeout after {self.max_retries} attempts: {url}")

            except requests.exceptions.RequestException as e:
                self.stats['requests_made'] += 1
                self.stats['failed_fetches'] += 1

                if attempt < self.max_retries:
                    logger.warning(f"✗ Request error fetching {url}: {e}, retrying...")
                    time.sleep(attempt * 2)
                else:
                    logger.error(f"✗ Request failed after {self.max_retries} attempts: {url} ({e})")

        return None

    def fetch_html_with_browser(self, url: str, headless: bool = True, wait_for_selector: str = 'body') -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Fetch HTML content using Playwright headless browser (bypasses Cloudflare)

        Args:
            url: URL to fetch
            headless: Run browser in headless mode
            wait_for_selector: CSS selector to wait for before extracting HTML

        Returns:
            Tuple of (html_content, metadata) or None if fetch failed
        """
        try:
            # Rate limiting
            self._rate_limit()

            start_time = time.time()
            logger.debug(f"Fetching with browser: {url}")

            with sync_playwright() as playwright:
                # Launch browser
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080}
                )
                page = context.new_page()

                # Navigate to page
                page.goto(url, wait_until='networkidle', timeout=self.timeout * 1000)

                # Wait for content to load
                page.wait_for_selector(wait_for_selector, timeout=10000)

                # Additional wait for any dynamic content (Cloudflare challenge)
                time.sleep(2)

                # Get HTML content
                html_content = page.content()
                size_bytes = len(html_content.encode('utf-8'))

                # Close browser
                browser.close()

            # Calculate metrics
            fetch_time = (time.time() - start_time) * 1000  # Convert to ms

            # Update statistics
            self.stats['requests_made'] += 1
            self.stats['successful_fetches'] += 1
            self.stats['total_bytes'] += size_bytes
            self.stats['total_time'] += fetch_time

            metadata = {
                'status_code': 200,  # Browser fetch doesn't have HTTP status
                'size_bytes': size_bytes,
                'fetch_time_ms': round(fetch_time, 2),
                'content_type': 'text/html',
                'fetched_at': datetime.now().isoformat(),
                'method': 'browser'
            }

            logger.info(f"✓ Fetched with browser: {url} ({size_bytes:,} bytes, {fetch_time:.0f}ms)")
            return html_content, metadata

        except Exception as e:
            self.stats['requests_made'] += 1
            self.stats['failed_fetches'] += 1
            logger.error(f"✗ Browser fetch failed for {url}: {e}")
            return None

    def fetch_batch(self, urls: List[str], progress_callback: Optional[callable] = None, use_browser: bool = False) -> Dict[str, Optional[Tuple[str, Dict]]]:
        """
        Fetch multiple URLs with progress tracking

        Args:
            urls: List of URLs to fetch
            progress_callback: Optional callback function called after each fetch
                              Signature: callback(current, total, url, success)
            use_browser: Use browser fetch instead of HTTP

        Returns:
            Dictionary mapping URL to (html_content, metadata) or None
        """
        results = {}
        total = len(urls)

        logger.info(f"Fetching batch of {total} URLs (method: {'browser' if use_browser else 'HTTP'})")

        for i, url in enumerate(urls, 1):
            # Try HTTP first, fallback to browser if it fails with 403
            if use_browser:
                result = self.fetch_html_with_browser(url)
            else:
                result = self.fetch_html(url)
                # If HTTP failed with 403, try browser
                if result is None:
                    logger.info(f"HTTP fetch failed for {url}, trying browser...")
                    result = self.fetch_html_with_browser(url)

            results[url] = result

            # Call progress callback
            if progress_callback:
                progress_callback(i, total, url, result is not None)

        return results

    def get_fetch_priority(self, products: List[Dict[str, Any]],
                          existing_versions: Dict[str, int]) -> List[Tuple[str, int]]:
        """
        Prioritize which products to fetch first

        Priority order:
        1. New products (no version in database)
        2. Updated products (version_number > stored version)
        3. Recently published products (within last 30 days)
        4. Oldest unfetched products

        Args:
            products: List of product records from database
            existing_versions: Dict mapping product_id to current version_number in DB

        Returns:
            List of (product_id, version_number) tuples in priority order
        """
        priority_list = []
        new_products = []
        updated_products = []
        recent_products = []
        old_products = []

        thirty_days_ago = datetime.now().timestamp() - (30 * 24 * 60 * 60)

        for product in products:
            product_id = product.get('product_id')
            version_number = product.get('version', 1)  # Default to version 1 if not in API
            publication_date = product.get('publication_date')

            # Parse publication date
            try:
                pub_timestamp = datetime.fromisoformat(publication_date.replace('Z', '+00:00')).timestamp() if publication_date else 0
            except:
                pub_timestamp = 0

            # Categorize product
            if product_id not in existing_versions:
                # New product
                new_products.append((product_id, version_number, pub_timestamp))
            elif version_number > existing_versions[product_id]:
                # Updated version
                updated_products.append((product_id, version_number, pub_timestamp))
            elif pub_timestamp > thirty_days_ago:
                # Recent product
                recent_products.append((product_id, version_number, pub_timestamp))
            else:
                # Old product
                old_products.append((product_id, version_number, pub_timestamp))

        # Sort each category by publication date (newest first)
        new_products.sort(key=lambda x: x[2], reverse=True)
        updated_products.sort(key=lambda x: x[2], reverse=True)
        recent_products.sort(key=lambda x: x[2], reverse=True)
        old_products.sort(key=lambda x: x[2])  # Oldest first for backfill

        # Combine in priority order
        for category in [new_products, updated_products, recent_products, old_products]:
            priority_list.extend([(pid, ver) for pid, ver, _ in category])

        logger.info(f"Fetch priority: {len(new_products)} new, {len(updated_products)} updated, "
                   f"{len(recent_products)} recent, {len(old_products)} old")

        return priority_list

    def get_stats(self) -> Dict[str, Any]:
        """
        Get fetcher statistics

        Returns:
            Dictionary with fetch statistics
        """
        avg_time = self.stats['total_time'] / self.stats['requests_made'] if self.stats['requests_made'] > 0 else 0
        avg_size = self.stats['total_bytes'] / self.stats['successful_fetches'] if self.stats['successful_fetches'] > 0 else 0
        success_rate = (self.stats['successful_fetches'] / self.stats['requests_made'] * 100) if self.stats['requests_made'] > 0 else 0

        return {
            **self.stats,
            'avg_fetch_time_ms': round(avg_time, 2),
            'avg_size_bytes': round(avg_size, 0),
            'success_rate_percent': round(success_rate, 1)
        }

    def reset_stats(self):
        """Reset statistics counters"""
        self.stats = {
            'requests_made': 0,
            'successful_fetches': 0,
            'failed_fetches': 0,
            'total_bytes': 0,
            'total_time': 0.0
        }

    def close(self):
        """Close the session and cleanup"""
        self.session.close()
