"""
Brookings Institution Ingester

Fetches research content from Brookings Institution using:
1. WordPress REST API (primary)
2. Sitemap crawling (fallback/supplement)
3. Direct page scraping (HTML + PDF)
4. Playwright browser for Cloudflare bypass
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

from .base import BaseIngester
from .utils.html_parser import BrookingsHTMLParser
from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class BrookingsIngester(BaseIngester):
    """
    Brookings Institution content ingester

    Discovers documents via WordPress API, fetches content, extracts metadata,
    and stores in database with full-text search support.
    """

    def __init__(self, rate_limit_delay: float = None):
        """
        Initialize Brookings ingester

        Args:
            rate_limit_delay: Delay between requests (default: 1.5s)
        """
        super().__init__(source_code='BROOKINGS', rate_limit_delay=rate_limit_delay)

        # Brookings-specific components
        self.html_parser = BrookingsHTMLParser()
        self.wp_api_base = config.BROOKINGS_WP_API
        self.brookings_base = config.BROOKINGS_BASE_URL

        # Content filters
        self.start_date = config.START_DATE
        self.include_types = config.INCLUDE_CONTENT_TYPES
        self.exclude_types = config.EXCLUDE_CONTENT_TYPES

    def discover(self, limit: int = None, method: str = 'api', **kwargs) -> List[Dict[str, Any]]:
        """
        Discover Brookings documents

        Args:
            limit: Maximum number of documents to discover
            method: Discovery method ('api', 'sitemap', or 'both')
            **kwargs: Additional parameters:
                - since_date: Override start date (YYYY-MM-DD)
                - content_types: Override content type filters

        Returns:
            List of document metadata dictionaries
        """
        # Override defaults if provided
        since_date = kwargs.get('since_date', self.start_date)
        content_types = kwargs.get('content_types', self.include_types)

        if method == 'api':
            documents = self._discover_via_api(since_date, limit)
        elif method == 'sitemap':
            documents = self._discover_via_sitemap(since_date, limit)
        elif method == 'both':
            # Try API first, supplement with sitemap
            documents = self._discover_via_api(since_date, limit)
            api_urls = {doc['url'] for doc in documents}

            sitemap_docs = self._discover_via_sitemap(since_date, limit)
            for doc in sitemap_docs:
                if doc['url'] not in api_urls:
                    documents.append(doc)

            if limit:
                documents = documents[:limit]
        else:
            raise ValueError(f"Unknown discovery method: {method}")

        # Filter by content type
        filtered = self._filter_by_content_type(documents, content_types)

        logger.info(f"Discovered {len(filtered)} Brookings documents (method: {method})")
        return filtered

    def _discover_via_api(self, since_date: str, limit: Optional[int]) -> List[Dict[str, Any]]:
        """
        Discover documents via WordPress REST API

        Args:
            since_date: Start date (YYYY-MM-DD)
            limit: Maximum documents

        Returns:
            List of document metadata
        """
        documents = []
        page = 1
        per_page = 100

        logger.info(f"Discovering via WordPress API (since {since_date})")

        while True:
            try:
                self._rate_limit()

                # Build API URL
                params = {
                    'per_page': per_page,
                    'page': page,
                    'after': f"{since_date}T00:00:00",  # ISO 8601 format
                    'orderby': 'date',
                    'order': 'desc',
                    '_fields': 'id,title,link,date,excerpt,content,categories,tags'
                }

                # Use posts endpoint (WordPress default)
                url = f"{self.wp_api_base}/posts"

                logger.debug(f"Fetching API page {page}: {url}")
                response = self.session.get(url, params=params, timeout=config.REQUEST_TIMEOUT)
                response.raise_for_status()

                posts = response.json()

                if not posts:
                    logger.debug("No more posts, stopping pagination")
                    break

                # Convert to our format
                for post in posts:
                    doc = {
                        'document_identifier': self._extract_slug(post['link']),
                        'url': post['link'],
                        'title': self._clean_html_text(post['title'].get('rendered', '')),
                        'publication_date': post['date'][:10] if post.get('date') else None,
                        'summary': self._clean_html_text(post['excerpt'].get('rendered', ''))[:500],
                        'api_id': post['id']
                    }
                    documents.append(doc)

                logger.debug(f"Found {len(posts)} posts on page {page}")

                # Check limit
                if limit and len(documents) >= limit:
                    documents = documents[:limit]
                    break

                # Check if there are more pages
                total_pages = int(response.headers.get('X-WP-TotalPages', 0))
                if page >= total_pages:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error fetching API page {page}: {e}")
                break

        logger.info(f"Found {len(documents)} documents via API")
        return documents

    def _discover_via_sitemap(self, since_date: str, limit: Optional[int]) -> List[Dict[str, Any]]:
        """
        Discover documents via sitemap.xml

        Brookings uses a sitemap index with multiple article sitemaps.
        This method parses the index and follows article sitemap links.

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
            response = self.session.get(config.BROOKINGS_SITEMAP, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse sitemap index XML
            root = ET.fromstring(response.content)

            # Namespace for sitemap
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            # Check if this is a sitemap index (contains <sitemap> elements)
            sitemap_elements = root.findall('ns:sitemap', ns)

            if sitemap_elements:
                # This is a sitemap index - find article sitemaps
                logger.info(f"Found sitemap index with {len(sitemap_elements)} sub-sitemaps")

                article_sitemaps = []
                for sitemap_elem in sitemap_elements:
                    loc = sitemap_elem.find('ns:loc', ns)
                    if loc is not None and 'article-sitemap' in loc.text:
                        article_sitemaps.append(loc.text)

                logger.info(f"Found {len(article_sitemaps)} article sitemaps")

                # Parse each article sitemap
                for article_sitemap_url in article_sitemaps:
                    if limit and len(documents) >= limit:
                        break

                    logger.info(f"Parsing {article_sitemap_url}")
                    self._rate_limit()

                    sitemap_response = self.session.get(article_sitemap_url, timeout=config.REQUEST_TIMEOUT)
                    sitemap_response.raise_for_status()

                    sitemap_root = ET.fromstring(sitemap_response.content)

                    # Extract URLs from article sitemap
                    for url_elem in sitemap_root.findall('ns:url', ns):
                        loc = url_elem.find('ns:loc', ns)
                        lastmod = url_elem.find('ns:lastmod', ns)

                        if loc is not None:
                            url = loc.text

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

    def _filter_by_content_type(self, documents: List[Dict], allowed_types: List[str]) -> List[Dict]:
        """
        Filter documents by content type

        Note: Content type determination is heuristic-based since WordPress API
        doesn't always expose content type clearly. We use URL patterns and
        will refine during HTML parsing.
        """
        # For now, accept all discovered documents
        # Full filtering happens during parse() when we examine the actual content
        return documents

    def fetch(self, document_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch document content (HTML and PDF if available) using Playwright

        Args:
            document_meta: Metadata from discover()

        Returns:
            Dictionary with:
            {
                'html_content': str,
                'pdf_bytes': bytes (optional),
                'pdf_url': str (optional)
            }
        """
        url = document_meta['url']

        try:
            # Fetch HTML with Playwright (bypasses Cloudflare)
            html_content = self._fetch_with_browser(url)

            if not html_content:
                logger.error(f"Failed to fetch HTML content from {url}")
                return None

            # Look for PDF link in HTML
            pdf_url = self._find_pdf_link(html_content, url)
            pdf_bytes = None

            if pdf_url:
                try:
                    self._rate_limit()

                    logger.debug(f"Downloading PDF: {pdf_url}")
                    pdf_response = self.session.get(pdf_url, timeout=config.REQUEST_TIMEOUT)
                    pdf_response.raise_for_status()

                    if pdf_response.headers.get('content-type', '').startswith('application/pdf'):
                        pdf_bytes = pdf_response.content
                        logger.info(f"✓ Downloaded PDF ({len(pdf_bytes):,} bytes)")
                    else:
                        logger.warning(f"URL {pdf_url} is not a PDF (Content-Type: {pdf_response.headers.get('content-type')})")

                except Exception as e:
                    logger.warning(f"Failed to download PDF from {pdf_url}: {e}")

            return {
                'html_content': html_content,
                'pdf_bytes': pdf_bytes,
                'pdf_url': pdf_url
            }

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _fetch_with_browser(self, url: str, headless: bool = True) -> Optional[str]:
        """
        Fetch HTML content using Playwright browser (bypasses Cloudflare)

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

                # Wait for main content to load (Brookings uses React/JS rendering)
                try:
                    # Wait for article content or main paragraph
                    page.wait_for_selector('article, main p, .article-content, .post-content', timeout=15000)
                except:
                    logger.warning("Timeout waiting for content selectors, proceeding anyway")

                # Additional wait for dynamic content and Cloudflare
                time.sleep(3)

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

            # Extract PDF text if available
            pdf_text = None
            page_count = None

            if fetched_content.get('pdf_bytes'):
                pdf_result = self.pdf_extractor.extract_from_bytes(fetched_content['pdf_bytes'])
                if pdf_result:
                    pdf_text = pdf_result['text']
                    page_count = pdf_result['page_count']
                    logger.debug(f"Extracted {pdf_result['word_count']:,} words from PDF")

            # Use PDF text if available and longer than HTML text
            if pdf_text and len(pdf_text) > len(parsed.text_content):
                full_text = pdf_text
                word_count = len(pdf_text.split())
                logger.debug("Using PDF text (longer than HTML)")
            else:
                full_text = parsed.text_content
                word_count = parsed.word_count
                logger.debug("Using HTML text")

            # Determine document type (heuristic)
            document_type = self._determine_document_type(parsed.title, parsed.metadata, document_meta['url'])

            return {
                'document_identifier': document_meta['document_identifier'],
                'title': parsed.title,
                'document_type': document_type,
                'publication_date': parsed.publication_date or document_meta.get('publication_date'),
                'summary': parsed.summary,
                'full_text': full_text,
                'url': document_meta['url'],
                'pdf_url': fetched_content.get('pdf_url'),
                'authors': parsed.authors,
                'subjects': parsed.subjects,
                'metadata': parsed.metadata,
                'html_content': parsed.html_content,
                'text_content': parsed.text_content,
                'structure': parsed.structure,
                'page_count': page_count,
                'word_count': word_count,
                'pdf_bytes': fetched_content.get('pdf_bytes')
            }

        except Exception as e:
            logger.error(f"Error parsing content for {document_meta['document_identifier']}: {e}")
            return None

    def _extract_slug(self, url: str) -> str:
        """
        Extract document identifier from URL

        Example:
        https://www.brookings.edu/research/economic-mobility/ -> economic-mobility
        """
        path = urlparse(url).path.strip('/')
        parts = path.split('/')

        # Get last part as slug
        slug = parts[-1] if parts else 'unknown'

        # Clean slug
        slug = slug.replace('.html', '').replace('.php', '')

        return slug

    def _clean_html_text(self, html_text: str) -> str:
        """Remove HTML tags from text"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'lxml')
        return soup.get_text(strip=True)

    def _find_pdf_link(self, html: str, base_url: str) -> Optional[str]:
        """
        Find PDF download link in HTML

        Args:
            html: HTML content
            base_url: Base URL for resolving relative links

        Returns:
            Absolute PDF URL or None
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, 'lxml')

        # Look for PDF links
        pdf_patterns = [
            'a[href*=".pdf"]',
            'a:contains("Download PDF")',
            'a:contains("Read the full paper")',
            'a.download-pdf',
            'a[href*="/wp-content/uploads/"]'
        ]

        for pattern in pdf_patterns:
            link = soup.select_one(pattern)
            if link:
                href = link.get('href')
                if href and '.pdf' in href.lower():
                    # Make absolute URL
                    return urljoin(base_url, href)

        return None

    def _determine_document_type(self, title: str, metadata: Dict, url: str) -> str:
        """
        Heuristically determine document type

        Args:
            title: Document title
            metadata: Extracted metadata
            url: Document URL

        Returns:
            Document type string
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # Check URL patterns
        if '/report/' in url_lower or 'report' in title_lower:
            return 'Report'
        elif '/essay/' in url_lower or 'essay' in title_lower:
            return 'Essay'
        elif '/policy-brief/' in url_lower or 'policy brief' in title_lower:
            return 'Policy Brief'
        elif '/working-paper/' in url_lower or 'working paper' in title_lower:
            return 'Working Paper'
        elif '/book-chapter/' in url_lower or 'chapter' in title_lower:
            return 'Book Chapter'
        elif '/research/' in url_lower:
            return 'Research'
        else:
            return 'Article'

    def get_ingestion_stats(self) -> Dict[str, Any]:
        """Get comprehensive ingestion statistics"""
        stats = self.get_stats()

        # Add component stats
        stats['pdf_extractor'] = self.pdf_extractor.get_stats()
        stats['file_manager'] = self.file_manager.get_stats()

        return stats
