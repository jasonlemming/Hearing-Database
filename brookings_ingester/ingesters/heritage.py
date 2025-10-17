"""
Heritage Foundation Ingester

Fetches research content from Heritage Foundation using:
1. Sitemap crawling (primary)
2. Direct page scraping (HTML)
3. Playwright browser for JS-rendered content
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

from .base import BaseIngester
from .utils.heritage_parser import HeritageHTMLParser
from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class HeritageIngester(BaseIngester):
    """
    Heritage Foundation content ingester

    Discovers documents via sitemap, fetches content, extracts metadata,
    and stores in database with full-text search support.
    """

    # Heritage Foundation URLs
    HERITAGE_BASE = "https://www.heritage.org"
    HERITAGE_SITEMAP = "https://www.heritage.org/sitemap.xml"

    def __init__(self, rate_limit_delay: float = None):
        """
        Initialize Heritage ingester

        Args:
            rate_limit_delay: Delay between requests (default: 1.5s)
        """
        super().__init__(source_code='HERITAGE', rate_limit_delay=rate_limit_delay)

        # Heritage-specific components
        self.html_parser = HeritageHTMLParser()

        # Content filters - focus on research/commentary
        self.start_date = config.START_DATE
        self.include_patterns = ['/commentary/', '/report/', '/article/']

    def discover(self, limit: int = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Discover Heritage documents via sitemap

        Args:
            limit: Maximum number of documents to discover
            **kwargs: Additional parameters:
                - since_date: Override start date (YYYY-MM-DD)

        Returns:
            List of document metadata dictionaries
        """
        # Override defaults if provided
        since_date = kwargs.get('since_date', self.start_date)

        documents = self._discover_via_sitemap(since_date, limit)

        logger.info(f"Discovered {len(documents)} Heritage documents")
        return documents

    def _discover_via_sitemap(self, since_date: str, limit: Optional[int]) -> List[Dict[str, Any]]:
        """
        Discover documents via sitemap.xml

        Heritage uses a sitemap index with 21 paginated sitemaps.
        This method parses the index and follows sitemap links.

        Args:
            since_date: Start date (YYYY-MM-DD)
            limit: Maximum documents

        Returns:
            List of document metadata
        """
        documents = []

        try:
            logger.info("Discovering via sitemap index...")

            self._rate_limit()
            response = self.session.get(self.HERITAGE_SITEMAP, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse sitemap index XML
            root = ET.fromstring(response.content)

            # Namespace for sitemap
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Check if this is a sitemap index (contains <sitemap> elements)
            sitemap_elements = root.findall('ns:sitemap', ns)

            if sitemap_elements:
                # This is a sitemap index - parse each sub-sitemap
                logger.info(f"Found sitemap index with {len(sitemap_elements)} sub-sitemaps")

                for sitemap_elem in sitemap_elements:
                    if limit and len(documents) >= limit:
                        break

                    loc = sitemap_elem.find('ns:loc', ns)
                    if loc is None:
                        continue

                    sitemap_url = loc.text
                    logger.info(f"Parsing {sitemap_url}")

                    self._rate_limit()

                    sitemap_response = self.session.get(sitemap_url, timeout=config.REQUEST_TIMEOUT)
                    sitemap_response.raise_for_status()

                    sitemap_root = ET.fromstring(sitemap_response.content)

                    # Extract URLs from sitemap
                    for url_elem in sitemap_root.findall('ns:url', ns):
                        loc = url_elem.find('ns:loc', ns)
                        lastmod = url_elem.find('ns:lastmod', ns)

                        if loc is not None:
                            url = loc.text

                            # Filter by content type (URL pattern)
                            if not self._is_research_content(url):
                                continue

                            # Filter by date
                            if lastmod is not None:
                                mod_date = lastmod.text[:10]  # YYYY-MM-DD
                                if mod_date < since_date:
                                    continue

                            doc = {
                                'document_identifier': self._extract_slug(url),
                                'url': url,
                                'title': None,  # Will be extracted from HTML
                                'publication_date': lastmod.text[:10] if lastmod is not None else None
                            }
                            documents.append(doc)

                            if limit and len(documents) >= limit:
                                break

            else:
                # Regular sitemap (single file)
                for url_elem in root.findall('ns:url', ns):
                    loc = url_elem.find('ns:loc', ns)
                    lastmod = url_elem.find('ns:lastmod', ns)

                    if loc is not None:
                        url = loc.text

                        # Filter by content type
                        if not self._is_research_content(url):
                            continue

                        # Filter by date
                        if lastmod is not None:
                            mod_date = lastmod.text[:10]  # YYYY-MM-DD
                            if mod_date < since_date:
                                continue

                        doc = {
                            'document_identifier': self._extract_slug(url),
                            'url': url,
                            'title': None,  # Will be extracted from HTML
                            'publication_date': lastmod.text[:10] if lastmod is not None else None
                        }
                        documents.append(doc)

                        if limit and len(documents) >= limit:
                            break

            logger.info(f"Found {len(documents)} documents via sitemap")

        except Exception as e:
            logger.error(f"Error parsing sitemap: {e}")

        return documents

    def _is_research_content(self, url: str) -> bool:
        """
        Check if URL is research/commentary content

        Args:
            url: URL to check

        Returns:
            True if URL matches research patterns
        """
        # Extract path from URL
        path = url.replace('https://www.heritage.org/', '')
        parts = path.split('/')

        # Exclude generic /article/ pages (copyright-notice, heritage-academy-speakers, etc.)
        # These start with /article/ directly, unlike research articles which are /{topic}/article/
        if len(parts) >= 1 and parts[0] == 'article':
            logger.debug(f"Excluding generic article page: {url}")
            return False

        # Exclude model legislation
        if '/model-legislation/' in url:
            logger.debug(f"Excluding model legislation: {url}")
            return False

        # Exclude other non-content pages
        excluded_patterns = ['/search/', '/about/', '/donate/', '/press/', '/staff/']
        if any(pattern in url for pattern in excluded_patterns):
            logger.debug(f"Excluding non-content page: {url}")
            return False

        # Include research content patterns
        # Must have a topic category (first part) and content type (second part)
        if len(parts) >= 2:
            content_type = parts[1]
            research_types = ['commentary', 'report', 'backgrounder', 'issue-brief',
                            'legal-memorandum', 'testimony', 'article']

            if content_type in research_types:
                logger.debug(f"Including research content: {url}")
                return True

        logger.debug(f"No match for URL: {url}")
        return False

    def fetch(self, document_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch document content using Playwright

        Args:
            document_meta: Metadata from discover()

        Returns:
            Dictionary with:
            {
                'html_content': str
            }
        """
        url = document_meta['url']

        try:
            # Fetch HTML with Playwright
            html_content = self._fetch_with_browser(url)

            if not html_content:
                logger.error(f"Failed to fetch HTML content from {url}")
                return None

            return {
                'html_content': html_content
            }

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _fetch_with_browser(self, url: str, headless: bool = True) -> Optional[str]:
        """
        Fetch HTML content using Playwright browser

        Args:
            url: URL to fetch
            headless: Run browser in headless mode

        Returns:
            HTML content as string or None if fetch failed
        """
        try:
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
                page.goto(url, wait_until='networkidle', timeout=60000)

                # Wait for main content to load
                try:
                    # Wait for article content
                    page.wait_for_selector('article, main p, .article-body, .node-title', timeout=15000)
                except:
                    logger.warning("Timeout waiting for content selectors, proceeding anyway")

                # Additional wait for dynamic content
                time.sleep(2)

                # Scroll to load lazy-loaded content
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)

                # Get HTML content
                html_content = page.content()

                # Close browser
                browser.close()

            fetch_time = (time.time() - start_time) * 1000
            size_bytes = len(html_content.encode('utf-8'))

            logger.info(f"✓ Fetched with browser: {url} ({size_bytes:,} bytes, {fetch_time:.0f}ms)")
            return html_content

        except Exception as e:
            logger.error(f"✗ Browser fetch failed for {url}: {e}")
            return None

    def parse(self, document_meta: Dict[str, Any], fetched_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse document content and extract metadata

        Args:
            document_meta: Metadata from discover()
            fetched_content: Content from fetch()

        Returns:
            Complete document data for storage
        """
        try:
            # Parse HTML
            parsed = self.html_parser.parse(
                fetched_content['html_content'],
                document_meta['url']
            )

            if not parsed:
                return None

            # Determine document type (heuristic)
            document_type = self._determine_document_type(parsed.title, document_meta['url'])

            return {
                'document_identifier': document_meta['document_identifier'],
                'title': parsed.title,
                'document_type': document_type,
                'publication_date': parsed.publication_date or document_meta.get('publication_date'),
                'summary': parsed.summary,
                'full_text': parsed.text_content,
                'url': document_meta['url'],
                'pdf_url': None,  # Heritage typically doesn't have PDFs
                'authors': parsed.authors,
                'subjects': parsed.subjects,
                'metadata': parsed.metadata,
                'html_content': parsed.html_content,
                'text_content': parsed.text_content,
                'structure': parsed.structure,
                'page_count': None,
                'word_count': parsed.word_count,
                'pdf_bytes': None
            }

        except Exception as e:
            logger.error(f"Error parsing content for {document_meta['document_identifier']}: {e}")
            return None

    def _extract_slug(self, url: str) -> str:
        """
        Extract document identifier from URL

        Example:
        https://www.heritage.org/immigration/commentary/why-trumps-reforms -> why-trumps-reforms
        """
        path = urlparse(url).path.strip('/')
        parts = path.split('/')

        # Get last part as slug
        slug = parts[-1] if parts else 'unknown'

        # Clean slug
        slug = slug.replace('.html', '').replace('.php', '')

        return slug

    def _determine_document_type(self, title: str, url: str) -> str:
        """
        Heuristically determine document type

        Args:
            title: Document title
            url: Document URL

        Returns:
            Document type string
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # Check URL patterns
        if '/report/' in url_lower or 'report' in title_lower:
            return 'Report'
        elif '/commentary/' in url_lower or 'commentary' in title_lower:
            return 'Commentary'
        elif '/backgrounder/' in url_lower or 'backgrounder' in title_lower:
            return 'Backgrounder'
        elif '/issue-brief/' in url_lower or 'issue brief' in title_lower:
            return 'Issue Brief'
        elif '/legal-memorandum/' in url_lower:
            return 'Legal Memorandum'
        elif '/testimony/' in url_lower:
            return 'Testimony'
        else:
            return 'Article'

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get comprehensive ingestion statistics"""
        stats = self.get_stats()

        # Add component stats
        stats['file_manager'] = self.file_manager.get_stats()

        return stats
