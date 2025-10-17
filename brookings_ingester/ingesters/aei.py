"""
American Enterprise Institute (AEI) Ingester

Fetches content from AEI using:
1. Pagination discovery (/articles/page/N/)
2. Playwright browser for fetching
3. Custom HTML parser

Generated: 2025-10-17
Based on: brookings_ingester/docs/sources/aei_analysis.md
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

from .base import BaseIngester
from .utils.aei_parser import AeiHTMLParser
from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class AeiIngester(BaseIngester):
    """
    American Enterprise Institute (AEI) content ingester

    Discovers documents via pagination, fetches content, extracts metadata,
    and stores in database with full-text search support.
    """

    # AEI URLs
    BASE_URL = "https://www.aei.org"

    # Research products listing pages (more specific than general articles)
    LISTING_URLS = [
        "https://www.aei.org/research-products/reports/",
        "https://www.aei.org/research-products/journal-publications/",
        "https://www.aei.org/research-products/one-pagers/",
        "https://www.aei.org/research-products/testimonies/",
        "https://www.aei.org/research-products/working-papers/",
        "https://www.aei.org/research-products/speeches/",
    ]

    def __init__(self, rate_limit_delay: float = None):
        """
        Initialize AEI ingester

        Args:
            rate_limit_delay: Delay between requests (default: 1.5s)
        """
        super().__init__(source_code='AEI', rate_limit_delay=rate_limit_delay or 1.5)

        # AEI-specific components
        self.html_parser = AeiHTMLParser()

        # Content filters
        self.start_date = config.START_DATE

    def discover(self, limit: int = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Discover AEI documents via pagination

        Args:
            limit: Maximum number of documents to discover
            **kwargs: Additional parameters:
                - since_date: Override start date (YYYY-MM-DD)
                - max_pages: Maximum pagination pages (default: 20)

        Returns:
            List of document metadata dictionaries
        """
        since_date = kwargs.get('since_date', self.start_date)
        max_pages = kwargs.get('max_pages', 20)

        documents = self._discover_via_pagination(since_date, limit, max_pages)

        logger.info(f"Discovered {len(documents)} AEI documents")
        return documents

    def _discover_via_pagination(self, since_date: str, limit: Optional[int], max_pages: int) -> List[Dict[str, Any]]:
        """
        Discover documents via pagination across multiple research product categories

        Iterates through AEI research-products listing pages (reports, testimonies, etc.),
        extracting article URLs. Stops when limit reached or no more articles found.

        Args:
            since_date: Start date (YYYY-MM-DD)
            limit: Maximum documents
            max_pages: Maximum pages to crawl per category

        Returns:
            List of document metadata
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        documents = []

        logger.info(f"Starting pagination discovery across {len(self.LISTING_URLS)} categories")
        logger.info(f"Max {max_pages} pages per category, since {since_date}")

        # Iterate through each category
        for category_url in self.LISTING_URLS:
            if limit and len(documents) >= limit:
                break

            category_name = category_url.split('/')[-2]
            logger.info(f"Discovering from category: {category_name}")

            page = 1
            while page <= max_pages:
                if limit and len(documents) >= limit:
                    break

                # Construct pagination URL
                if page == 1:
                    listing_url = category_url
                else:
                    listing_url = f"{category_url}page/{page}/"

                logger.debug(f"Fetching listing page {page}: {listing_url}")

                try:
                    # Fetch listing page with browser
                    html = self._fetch_with_browser(listing_url)
                    if not html:
                        logger.warning(f"Failed to fetch {category_name} page {page}, moving to next category")
                        break

                    # Parse HTML
                    soup = BeautifulSoup(html, 'lxml')

                    # Extract article links using selector from analysis
                    # Selector: article.post-item h3.post-title a
                    article_links = soup.select('article.post-item h3.post-title a')

                    # Fallback selectors
                    if not article_links:
                        article_links = soup.select('div.article-card h2 a')
                    if not article_links:
                        article_links = soup.select('h2.entry-title a')
                    if not article_links:
                        article_links = soup.select('article h3 a')

                    if not article_links:
                        logger.info(f"No articles found on {category_name} page {page}, moving to next category")
                        break

                    logger.info(f"Found {len(article_links)} articles on {category_name} page {page}")

                    # Process each article link
                    for link in article_links:
                        # Extract URL
                        href = link.get('href', '')
                        if not href:
                            continue

                        # Make absolute URL
                        url = urljoin(self.BASE_URL, href)

                        # Include URLs from research-products
                        if '/research-products/' not in url:
                            continue

                        # Extract title
                        title = link.get_text(strip=True)

                        # Create document metadata
                        doc = {
                            'document_identifier': self._extract_slug(url),
                            'url': url,
                            'title': title if title else None
                        }

                        documents.append(doc)
                        logger.debug(f"  Added: {title[:60] if title else url}")

                        # Check limit
                        if limit and len(documents) >= limit:
                            logger.info(f"Reached limit of {limit} documents")
                            return documents

                    # Move to next page
                    page += 1

                except Exception as e:
                    logger.error(f"Error processing {category_name} page {page}: {e}")
                    break

        logger.info(f"Discovery complete: found {len(documents)} documents across {len(self.LISTING_URLS)} categories")
        return documents

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
            # Fetch HTML with Playwright (same pattern as Brookings/Heritage)
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
        Fetch HTML content using Playwright browser (sync pattern)

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
                # Launch browser with stealth mode to bypass Cloudflare
                browser = playwright.chromium.launch(
                    headless=headless,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox'
                    ]
                )
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    viewport={'width': 1920, 'height': 1080},
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                page = context.new_page()

                # Navigate to page with longer timeout for Cloudflare
                # Options: 'domcontentloaded', 'load', 'networkidle'
                page.goto(url, wait_until='networkidle', timeout=90000)

                # TODO: Adjust wait strategy based on analysis
                # If site uses JavaScript to render content:
                # page.wait_for_selector('article, main p', timeout=15000)

                # Additional wait if needed
                time.sleep(2)

                # Get HTML content
                html_content = page.content()

                # Close browser
                browser.close()

            fetch_time = (time.time() - start_time) * 1000
            size_bytes = len(html_content.encode('utf-8'))

            logger.info(f"✓ Fetched: {url} ({size_bytes:,} bytes, {fetch_time:.0f}ms)")
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
            Complete document data for storage (standardized dict format)
        """
        try:
            # Parse HTML
            parsed = self.html_parser.parse(
                fetched_content['html_content'],
                document_meta['url']
            )

            if not parsed:
                logger.error(f"Parser returned None for {document_meta['url']}")
                return None

            # Determine document type (heuristic based on URL or metadata)
            document_type = self._determine_document_type(parsed.title, document_meta['url'])

            # Return standardized format (matches Brookings/Heritage pattern)
            return {
                'document_identifier': document_meta['document_identifier'],
                'title': parsed.title,
                'document_type': document_type,
                'publication_date': parsed.publication_date or document_meta.get('publication_date'),
                'summary': parsed.summary,
                'full_text': parsed.text_content,
                'url': document_meta['url'],
                'pdf_url': None,  # TODO: Extract if PDFs available
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
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _extract_slug(self, url: str) -> str:
        """
        Extract document identifier from URL

        Example:
        https://www.example.org/articles/sample-title/ -> sample-title

        Args:
            url: Full article URL

        Returns:
            Document identifier (slug)
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
        Heuristically determine document type from URL

        AEI uses URL patterns to indicate content type:
        - /articles/ → Article
        - /op-eds/ → Op-Ed
        - /research-products/report/ → Report
        - /research-products/working-paper/ → Working Paper

        Args:
            title: Document title
            url: Document URL

        Returns:
            Document type string
        """
        url_lower = url.lower()

        # Check URL patterns
        if '/op-eds/' in url_lower:
            return 'Op-Ed'
        elif '/research-products/report/' in url_lower:
            return 'Report'
        elif '/research-products/working-paper/' in url_lower:
            return 'Working Paper'
        elif '/articles/' in url_lower:
            return 'Article'
        else:
            return 'Article'  # Default
