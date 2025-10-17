#!/usr/bin/env python3
"""
Generate ingester scaffold from source analysis

Usage:
    python brookings_ingester/scripts/generate_ingester.py <source_name>

Example:
    python brookings_ingester/scripts/generate_ingester.py aei

This generates:
    - brookings_ingester/ingesters/aei.py (main ingester class)
    - brookings_ingester/ingesters/utils/aei_parser.py (HTML parser)

Based on patterns from Brookings and Heritage ingesters.
"""
import sys
import os
from pathlib import Path
from datetime import datetime

# Template for main ingester file (following Brookings/Heritage pattern)
INGESTER_TEMPLATE = '''"""
{full_name} Ingester

Fetches content from {full_name} using:
1. {discovery_method}
2. Playwright browser for fetching
3. Custom HTML parser

Generated: {date}
Based on: brookings_ingester/docs/sources/{source_name}_analysis.md
"""
import logging
import time
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

from .base import BaseIngester
from .utils.{source_name}_parser import {class_name}HTMLParser
from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class {class_name}Ingester(BaseIngester):
    """
    {full_name} content ingester

    Discovers documents, fetches content, extracts metadata,
    and stores in database with full-text search support.
    """

    # TODO: Update these constants from your analysis document
    BASE_URL = "{base_url}"
    LISTING_URL = "{listing_url}"

    def __init__(self, rate_limit_delay: float = None):
        """
        Initialize {class_name} ingester

        Args:
            rate_limit_delay: Delay between requests (default: 1.5s)
        """
        super().__init__(source_code='{source_code}', rate_limit_delay=rate_limit_delay or 1.5)

        # {class_name}-specific components
        self.html_parser = {class_name}HTMLParser()

        # Content filters
        self.start_date = config.START_DATE  # or define specific start date

    def discover(self, limit: int = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Discover {full_name} documents

        Args:
            limit: Maximum number of documents to discover
            **kwargs: Additional parameters:
                - since_date: Override start date (YYYY-MM-DD)
                - max_pages: Maximum pagination pages (default: 5)

        Returns:
            List of document metadata dictionaries
        """
        since_date = kwargs.get('since_date', self.start_date)
        max_pages = kwargs.get('max_pages', 5)

        # TODO: Implement discovery method based on your analysis:
        # - Pagination: Iterate through pages
        # - Sitemap: Parse sitemap.xml
        # - API: Use REST API
        # - RSS: Parse RSS feed

        documents = self._discover_via_{discovery_strategy}(since_date, limit, max_pages)

        logger.info(f"Discovered {{len(documents)}} {full_name} documents")
        return documents

    def _discover_via_{discovery_strategy}(self, since_date: str, limit: Optional[int], max_pages: int) -> List[Dict[str, Any]]:
        """
        Discover documents via {discovery_method}

        TODO: Implement this based on your source analysis:
        - Parse listing pages or sitemap
        - Extract article URLs
        - Filter by date
        - Return list of dicts with: document_identifier, url, title (optional)

        Args:
            since_date: Start date (YYYY-MM-DD)
            limit: Maximum documents
            max_pages: Maximum pages to crawl

        Returns:
            List of document metadata
        """
        documents = []

        # TODO: Implement discovery logic here
        # Example for pagination:
        # page = 1
        # while page <= max_pages:
        #     listing_url = f"{{self.LISTING_URL}}page/{{page}}/"
        #     html = self._fetch_with_browser(listing_url)
        #
        #     from bs4 import BeautifulSoup
        #     soup = BeautifulSoup(html, 'lxml')
        #
        #     links = soup.select('YOUR_ARTICLE_LINK_SELECTOR')
        #     if not links:
        #         break
        #
        #     for link in links:
        #         doc = {{
        #             'document_identifier': self._extract_slug(link['href']),
        #             'url': link['href'],
        #             'title': link.get_text(strip=True)
        #         }}
        #         documents.append(doc)
        #
        #         if limit and len(documents) >= limit:
        #             return documents
        #
        #     page += 1

        logger.warning("TODO: Implement _discover_via_{discovery_strategy}()")
        return documents

    def fetch(self, document_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch document content using Playwright

        Args:
            document_meta: Metadata from discover()

        Returns:
            Dictionary with:
            {{
                'html_content': str
            }}
        """
        url = document_meta['url']

        try:
            # Fetch HTML with Playwright (same pattern as Brookings/Heritage)
            html_content = self._fetch_with_browser(url)

            if not html_content:
                logger.error(f"Failed to fetch HTML content from {{url}}")
                return None

            return {{
                'html_content': html_content
            }}

        except Exception as e:
            logger.error(f"Error fetching {{url}}: {{e}}")
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
            logger.debug(f"Fetching with browser: {{url}}")

            with sync_playwright() as playwright:
                # Launch browser
                browser = playwright.chromium.launch(headless=headless)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    viewport={{'width': 1920, 'height': 1080}}
                )
                page = context.new_page()

                # Navigate to page
                # TODO: Adjust wait_until based on your site needs
                # Options: 'domcontentloaded', 'load', 'networkidle'
                page.goto(url, wait_until='domcontentloaded', timeout=60000)

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

            logger.info(f"✓ Fetched: {{url}} ({{size_bytes:,}} bytes, {{fetch_time:.0f}}ms)")
            return html_content

        except Exception as e:
            logger.error(f"✗ Browser fetch failed for {{url}}: {{e}}")
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
                logger.error(f"Parser returned None for {{document_meta['url']}}")
                return None

            # Determine document type (heuristic based on URL or metadata)
            document_type = self._determine_document_type(parsed.title, document_meta['url'])

            # Return standardized format (matches Brookings/Heritage pattern)
            return {{
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
            }}

        except Exception as e:
            logger.error(f"Error parsing content for {{document_meta['document_identifier']}}: {{e}}")
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
        Heuristically determine document type from URL/title

        TODO: Customize based on your source's content types

        Args:
            title: Document title
            url: Document URL

        Returns:
            Document type string
        """
        url_lower = url.lower()
        title_lower = title.lower()

        # TODO: Customize these patterns
        if '/report/' in url_lower or 'report' in title_lower:
            return 'Report'
        elif '/commentary/' in url_lower or '/op-ed/' in url_lower:
            return 'Commentary'
        elif '/research/' in url_lower:
            return 'Research'
        else:
            return 'Article'
'''

# Template for HTML parser file (following BrookingsHTMLParser pattern)
PARSER_TEMPLATE = '''"""
HTML Parser for {full_name}

Extracts structured content and metadata from {full_name} pages

Generated: {date}
Based on: brookings_ingester/docs/sources/{source_name}_analysis.md
"""
import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedContent:
    """Container for parsed content"""
    html_content: str
    text_content: str
    structure: Dict[str, Any]
    title: str
    authors: List[Dict[str, str]]  # List of author dicts
    publication_date: Optional[str]
    summary: str
    subjects: List[str]
    metadata: Dict[str, Any]
    word_count: int


class {class_name}HTMLParser:
    """
    Parse HTML content from {full_name} pages

    TODO: Update selectors from your source analysis document

    Extracts:
    - Metadata (title, authors, date, topics)
    - Main content (cleaned HTML)
    - Plain text (for search)
    - Document structure (headings, sections)
    """

    # TODO: Update these selectors from your analysis document
    # Priority order: most specific first
    CONTENT_SELECTORS = [
        'div.entry-content',
        'article .post-content',
        'main',
        'article',
    ]

    METADATA_SELECTORS = {{
        'title': [
            'h1.entry-title',
            'article h1',
            'h1',
            'meta[property="og:title"]',
        ],
        'authors': [
            'span.author-name a',
            '.byline a',
            'a[rel="author"]',
            '.article-author',
        ],
        'date': [
            'time[datetime]',
            '.post-date',
            'meta[property="article:published_time"]',
        ],
        'summary': [
            '.article-summary',
            'meta[name="description"]',
            'meta[property="og:description"]',
        ],
        'topics': [
            'a[rel="category"]',
            '.post-tag',
        ],
    }}

    # TODO: Elements to remove from content
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        'aside.related-content',
        'div.related-posts',
        'div.newsletter-signup',
        'div.social-sharing',
        '.share-buttons',
        'div.advertisement',
        '.ad-container',
        'div.comments',
        'section#comments',
        'script',
        'style',
        'noscript',
    ]

    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def parse(self, html: str, url: str) -> Optional[ParsedContent]:
        """
        Parse {full_name} HTML content

        Args:
            html: Raw HTML string
            url: Page URL (for metadata)

        Returns:
            ParsedContent object or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract title
            title = self._extract_title(soup)
            if not title:
                logger.warning(f"No title found for {{url}}")
                return None

            # Extract metadata
            authors = self._extract_authors(soup)
            publication_date = self._extract_date(soup)
            summary = self._extract_summary(soup)
            subjects = self._extract_topics(soup)

            # Build metadata dict
            metadata = {{
                '{source_name}_url': url,
                '{source_name}_topics': subjects,
            }}

            # Extract main content
            content_soup = self._extract_content_area(soup)
            if not content_soup:
                logger.error(f"Could not extract content area from {{url}}")
                return None

            # Build structure
            structure = self._build_structure(content_soup)

            # Get cleaned HTML
            clean_html = self._clean_html(content_soup)

            # Extract plain text
            text_content = self._extract_text(content_soup)
            word_count = len(text_content.split())

            # Basic validation
            if word_count < 50:
                logger.warning(f"Content too short ({{word_count}} words) for {{url}}")
                return None

            logger.info(f"✓ Parsed {full_name} content: {{word_count:,}} words, {{len(authors)}} authors")

            return ParsedContent(
                html_content=clean_html,
                text_content=text_content,
                structure=structure,
                title=title,
                authors=authors,
                publication_date=publication_date,
                summary=summary,
                subjects=subjects,
                metadata=metadata,
                word_count=word_count
            )

        except Exception as e:
            logger.error(f"Error parsing {full_name} HTML: {{e}}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title"""
        for selector in self.METADATA_SELECTORS['title']:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    title = element.get('content', '').strip()
                else:
                    title = element.get_text(strip=True)

                if title:
                    return self._clean_title(title)

        return "Untitled"

    def _clean_title(self, title: str) -> str:
        """
        Clean title by removing site name suffixes

        TODO: Customize patterns for your source
        """
        # Remove common site name patterns
        patterns = [
            r'\\s*[|\\-–—]\\s*{full_name}\\s*$',
        ]

        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        return title.strip()

    def _extract_authors(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract author information

        Returns:
            List of author dictionaries with 'name' key (and optionally others)
        """
        authors = []
        seen_names = set()

        for selector in self.METADATA_SELECTORS['authors']:
            elements = soup.select(selector)
            for elem in elements:
                name = elem.get_text(strip=True)

                # Basic validation
                if not name or len(name) < 3 or len(name) > 100:
                    continue
                if name in seen_names:
                    continue

                # TODO: Add filters for your source (skip "by", social links, etc.)

                author_data = {{'name': name}}

                # TODO: Extract additional metadata if available:
                # - title/position
                # - affiliation
                # - profile URL
                # - etc.

                authors.append(author_data)
                seen_names.add(name)

        return authors[:20]  # Limit to prevent errors

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract and parse publication date

        Returns:
            Date string in YYYY-MM-DD format or None
        """
        for selector in self.METADATA_SELECTORS['date']:
            element = soup.select_one(selector)
            if element:
                # Try datetime attribute first (ISO format)
                date_str = element.get('datetime')
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        return parsed_date

                # Try content attribute (meta tags)
                date_str = element.get('content')
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        return parsed_date

                # Try text content
                date_str = element.get_text(strip=True)
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        return parsed_date

        logger.warning("Could not extract publication date")
        return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """
        Parse date string to YYYY-MM-DD format

        TODO: Customize for your source's date formats
        """
        try:
            # Handle ISO format (most common)
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')

            # Handle common formats
            # TODO: Add formats specific to your source from analysis doc
            formats = [
                '%Y-%m-%d',
                '%B %d, %Y',
                '%b %d, %Y',
                '%m/%d/%Y',
                '%d %B %Y',
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            # Fallback: use dateparser if available
            try:
                import dateparser
                dt = dateparser.parse(date_str)
                if dt:
                    return dt.strftime('%Y-%m-%d')
            except:
                pass

            return None
        except Exception as e:
            logger.debug(f"Failed to parse date '{{date_str}}': {{e}}")
            return None

    def _extract_summary(self, soup: BeautifulSoup) -> str:
        """Extract article summary/description"""
        for selector in self.METADATA_SELECTORS['summary']:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    summary = element.get('content', '').strip()
                else:
                    summary = element.get_text(strip=True)

                if summary:
                    return summary[:500]  # Limit length

        # Fallback: First paragraph of content
        content = self._extract_content_area(soup)
        if content:
            first_p = content.find('p')
            if first_p:
                return first_p.get_text(strip=True)[:500]

        return ""

    def _extract_topics(self, soup: BeautifulSoup) -> List[str]:
        """Extract topic/category tags"""
        topics = []

        for selector in self.METADATA_SELECTORS['topics']:
            elements = soup.select(selector)
            for elem in elements:
                topic = elem.get_text(strip=True)
                if topic and topic not in topics:
                    topics.append(topic)

        return topics

    def _extract_content_area(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Extract main content area, removing navigation/chrome"""
        # Make a copy to avoid modifying original
        soup = BeautifulSoup(str(soup), 'lxml')

        # Remove unwanted elements first
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Find main content
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                # Validate we found substantial content
                word_count = len(content.get_text().split())

                if word_count > 50:  # Require at least 50 words
                    logger.debug(f"Found content using selector: {{selector}} ({{word_count}} words)")
                    return content
                else:
                    logger.debug(f"Selector {{selector}} only found {{word_count}} words, trying next...")

        # Fallback: use body
        body = soup.find('body')
        if body:
            word_count = len(body.get_text().split())
            logger.warning(f"Using full body as content ({{word_count}} words)")
            return body

        return soup

    def _build_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Build document structure from headings"""
        toc = []
        headings = []

        for order, heading in enumerate(soup.find_all(self.HEADING_TAGS)):
            heading_text = heading.get_text(strip=True)
            if not heading_text:
                continue

            heading_level = int(heading.name[1])  # h1 -> 1, h2 -> 2

            entry = {{
                'level': heading_level,
                'title': heading_text,
                'order': order
            }}

            toc.append(entry)
            headings.append(heading_text)

        return {{
            'toc': toc,
            'headings': headings
        }}

    def _clean_html(self, soup: BeautifulSoup) -> str:
        """Clean and format HTML for display"""
        # Remove empty paragraphs
        for tag in soup.find_all(['p', 'div']):
            if not tag.get_text(strip=True):
                tag.decompose()

        # Fix image paths (convert relative to absolute)
        # TODO: Implement if needed for your source
        # for img in soup.find_all('img'):
        #     src = img.get('src', '')
        #     if src and not src.startswith(('http://', 'https://', 'data:')):
        #         img['src'] = f"{{base_url}}{{src if src.startswith('/') else '/' + src}}"

        html = str(soup)

        # Remove excessive whitespace
        html = re.sub(r'\\n\\s*\\n', '\\n\\n', html)
        html = re.sub(r'[ \\t]+', ' ', html)

        return html.strip()

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract plain text for search"""
        # Make a copy
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Get text with space separator
        text = soup_copy.get_text(separator=' ')

        # Fix spacing issues
        text = re.sub(r'[ \\t]+', ' ', text)
        text = re.sub(r' *\\n *', '\\n', text)
        text = re.sub(r'\\s+([.,;:!?])', r'\\1', text)
        text = re.sub(r'([.,;:!?])([A-Za-z])', r'\\1 \\2', text)

        # Clean up excessive whitespace
        text = re.sub(r'\\n\\s*\\n\\s*\\n+', '\\n\\n', text)

        return text.strip()
'''


def generate_ingester(source_name: str):
    """Generate ingester scaffold from source name"""

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    # Paths
    analysis_file = project_root / "brookings_ingester" / "docs" / "sources" / f"{source_name}_analysis.md"
    ingester_output = project_root / "brookings_ingester" / "ingesters" / f"{source_name}.py"
    parser_output = project_root / "brookings_ingester" / "ingesters" / "utils" / f"{source_name}_parser.py"

    # Check if analysis exists
    if not analysis_file.exists():
        print(f"❌ Analysis file not found: {analysis_file}")
        print(f"\nPlease create the analysis document first:")
        print(f"  1. Copy template: cp brookings_ingester/docs/source_analysis_template.md {analysis_file}")
        print(f"  2. Fill out all sections")
        print(f"  3. Run this script again")
        return 1

    # Generate class name (capitalize, remove underscores)
    class_name = ''.join(word.capitalize() for word in source_name.split('_'))
    source_code = source_name.upper()

    # TODO: In future, parse analysis doc to extract these
    # For now, use defaults and let developer customize
    context = {
        'source_name': source_name,
        'class_name': class_name,
        'source_code': source_code,
        'full_name': f"{class_name}",  # Will be customized by developer
        'base_url': "https://www.example.org",  # TODO from analysis
        'listing_url': "https://www.example.org/articles/",  # TODO from analysis
        'discovery_method': "pagination / sitemap / API",  # TODO from analysis
        'discovery_strategy': "pagination",  # TODO from analysis (pagination/sitemap/api)
        'date': datetime.now().strftime('%Y-%m-%d'),
    }

    # Generate ingester file
    ingester_code = INGESTER_TEMPLATE.format(**context)
    ingester_output.write_text(ingester_code)
    print(f"✅ Generated: {ingester_output}")

    # Generate parser file
    parser_code = PARSER_TEMPLATE.format(**context)
    parser_output.write_text(parser_code)
    print(f"✅ Generated: {parser_output}")

    # Print next steps
    print(f"\n{'='*60}")
    print(f"Next steps:")
    print(f"{'='*60}")
    print(f"1. Review generated files:")
    print(f"   - {ingester_output}")
    print(f"   - {parser_output}")
    print(f"\n2. Customize TODOs based on your analysis document:")
    print(f"   - Update selectors in {source_name}_parser.py")
    print(f"   - Implement discovery logic in {source_name}.py")
    print(f"   - Test incrementally as you implement")
    print(f"\n3. Test the ingester:")
    print(f"   python brookings_ingester/scripts/test_ingester.py {source_name} --limit 10")
    print(f"\n4. Save HTML fixtures for testing:")
    print(f"   python brookings_ingester/scripts/save_html_fixture.py {source_name} <article_url>")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python brookings_ingester/scripts/generate_ingester.py <source_name>")
        print("\nExample:")
        print("  python brookings_ingester/scripts/generate_ingester.py aei")
        sys.exit(1)

    source_name = sys.argv[1].lower()
    sys.exit(generate_ingester(source_name))
