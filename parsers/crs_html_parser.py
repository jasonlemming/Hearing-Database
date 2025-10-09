"""
CRS HTML Parser - Extracts and structures content from CRS report HTML pages
"""
import hashlib
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag, NavigableString
from config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ParsedContent:
    """Container for parsed CRS content"""
    html_content: str          # Cleaned HTML for display
    text_content: str          # Plain text for search
    structure_json: Dict       # Table of contents and sections
    content_hash: str          # SHA256 hash of text content
    word_count: int            # Word count

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            'html_content': self.html_content,
            'text_content': self.text_content,
            'structure_json': self.structure_json,
            'content_hash': self.content_hash,
            'word_count': self.word_count
        }


class CRSHTMLParser:
    """
    Parses HTML content from congress.gov CRS report pages

    Extracts:
    - Clean HTML (removes navigation, headers, footers)
    - Plain text (for full-text search)
    - Document structure (TOC, sections, headings)
    """

    # Selectors for content extraction (adjust based on actual HTML structure)
    CONTENT_SELECTORS = [
        'main',
        'article',
        'div.report-content',
        'div.crs-report',
        'div#report-content',
        'div.main-content',
        'div[role="main"]'
    ]

    # Elements to remove from HTML
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        '.breadcrumb',
        '.breadcrumbs',
        '.skip-nav',
        '.navigation',
        '.site-header',
        '.site-footer',
        '.banner',
        'script',
        'style',
        'noscript',
        '.advertisement',
        '.ad',
        '#sidebar',
        '.sidebar'
    ]

    # Heading tags that indicate document structure
    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def __init__(self):
        """Initialize parser"""
        pass

    def parse(self, html: str, product_id: str) -> Optional[ParsedContent]:
        """
        Parse CRS HTML content

        Args:
            html: Raw HTML string
            product_id: CRS product ID (for logging)

        Returns:
            ParsedContent object or None if parsing failed
        """
        try:
            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Extract content area
            content_soup = self.extract_content_area(soup)
            if not content_soup:
                logger.error(f"Could not extract content area for {product_id}")
                return None

            # Build structure (TOC, sections, headings)
            structure = self.build_structure(content_soup)

            # Don't add our own section anchors - reports have their own native anchors
            # content_soup = self.add_section_anchors(content_soup, structure)

            # Get cleaned HTML
            clean_html = self.clean_html(content_soup)

            # Extract plain text
            text_content = self.extract_text(content_soup)

            # Calculate metrics
            content_hash = hashlib.sha256(text_content.encode('utf-8')).hexdigest()
            word_count = len(text_content.split())

            logger.info(f"✓ Parsed {product_id}: {word_count} words, {len(structure['headings'])} headings")

            return ParsedContent(
                html_content=clean_html,
                text_content=text_content,
                structure_json=structure,
                content_hash=content_hash,
                word_count=word_count
            )

        except Exception as e:
            logger.error(f"Error parsing HTML for {product_id}: {e}")
            return None

    def extract_content_area(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Extract main content area from page, removing chrome/navigation

        Args:
            soup: BeautifulSoup object

        Returns:
            BeautifulSoup object with just content, or None if not found
        """
        # First remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Try to find main content area using selectors
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                logger.debug(f"Found content using selector: {selector}")
                return BeautifulSoup(str(content), 'html.parser')

        # Fallback: If no specific content area found, use body
        body = soup.find('body')
        if body:
            logger.warning("Using full body as content (no specific content selector matched)")
            return BeautifulSoup(str(body), 'html.parser')

        # Last resort: use entire soup
        logger.warning("Could not find body tag, using entire document")
        return soup

    def build_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Build document structure from headings

        Returns:
            {
                'toc': [{'level': 1, 'title': 'Introduction', 'anchor': 'intro', 'order': 0}],
                'sections': [{'heading': 'Background', 'level': 2, 'order': 1, 'anchor': 'background'}],
                'headings': ['Introduction', 'Background', 'Analysis']  # For FTS
            }
        """
        toc = []
        sections = []
        headings_text = []

        for order, heading in enumerate(soup.find_all(self.HEADING_TAGS)):
            if not heading.get_text(strip=True):
                continue

            heading_text = heading.get_text(strip=True)
            heading_level = int(heading.name[1])  # h1 -> 1, h2 -> 2, etc.

            # Create anchor from heading text
            anchor = self._create_anchor(heading_text, order)

            # Add to TOC and sections
            entry = {
                'level': heading_level,
                'title': heading_text,
                'anchor': anchor,
                'order': order
            }

            toc.append(entry)
            sections.append(entry)
            headings_text.append(heading_text)

        return {
            'toc': toc,
            'sections': sections,
            'headings': headings_text
        }

    def add_section_anchors(self, soup: BeautifulSoup, structure: Dict) -> BeautifulSoup:
        """
        Add id attributes to headings for in-page navigation

        Args:
            soup: BeautifulSoup content
            structure: Structure dict from build_structure()

        Returns:
            Modified BeautifulSoup
        """
        headings = soup.find_all(self.HEADING_TAGS)

        for i, heading in enumerate(headings):
            if i < len(structure['sections']):
                anchor = structure['sections'][i]['anchor']
                heading['id'] = anchor

        return soup

    def clean_html(self, soup: BeautifulSoup) -> str:
        """
        Clean and format HTML for display

        Args:
            soup: BeautifulSoup object

        Returns:
            Cleaned HTML string
        """
        # Remove empty paragraphs and divs
        for tag in soup.find_all(['p', 'div']):
            if not tag.get_text(strip=True):
                tag.decompose()

        # Fix image paths - convert relative paths to absolute congress.gov URLs
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith(('http://', 'https://', 'data:')):
                # Remove the relative path and point to congress.gov
                # Images won't load, but at least the path won't be broken
                img['data-original-src'] = src
                img['src'] = f"https://www.congress.gov/crs_external_products/{src}"
                img['title'] = "Image from original CRS report (may not load due to access restrictions)"

        # Get HTML string
        html = str(soup)

        # Remove ASP.NET server tags and other server-side code
        html = re.sub(r'<%@?\s*.*?%>', '', html, flags=re.DOTALL)  # Remove <%...%> tags
        html = re.sub(r'<\?.*?\?>', '', html, flags=re.DOTALL)      # Remove <?...?> tags

        # Remove HTML-escaped server tags (e.g., &lt;%@ ... %&gt;)
        html = re.sub(r'&lt;%@?\s*.*?%&gt;', '', html, flags=re.DOTALL)

        # Remove excessive whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)  # Multiple newlines -> double newline
        html = re.sub(r'[ \t]+', ' ', html)      # Multiple spaces/tabs -> single space

        return html.strip()

    def extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract plain text from HTML for search

        Args:
            soup: BeautifulSoup object

        Returns:
            Plain text string
        """
        # Get text, preserving some structure
        text = soup.get_text(separator='\n', strip=True)

        # Clean up excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Multiple newlines -> double newline
        text = re.sub(r'[ \t]+', ' ', text)      # Multiple spaces/tabs -> single space

        return text.strip()

    def _create_anchor(self, text: str, order: int) -> str:
        """
        Create URL-safe anchor from heading text

        Args:
            text: Heading text
            order: Heading order number (for uniqueness)

        Returns:
            URL-safe anchor string
        """
        # Convert to lowercase
        anchor = text.lower()

        # Replace spaces and special chars with hyphens
        anchor = re.sub(r'[^\w\s-]', '', anchor)  # Remove punctuation
        anchor = re.sub(r'[\s_]+', '-', anchor)   # Spaces to hyphens
        anchor = re.sub(r'-+', '-', anchor)       # Multiple hyphens to single
        anchor = anchor.strip('-')                # Remove leading/trailing hyphens

        # Limit length
        if len(anchor) > 50:
            anchor = anchor[:50].rstrip('-')

        # Add order number for uniqueness
        anchor = f"{anchor}-{order}"

        return anchor

    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract additional metadata from HTML if available

        Args:
            soup: BeautifulSoup object

        Returns:
            Dictionary with metadata (publication date, authors, etc.)
        """
        metadata = {}

        # Try to extract publication date
        date_meta = soup.find('meta', attrs={'name': 'publication-date'}) or \
                   soup.find('meta', attrs={'property': 'article:published_time'})
        if date_meta:
            metadata['publication_date'] = date_meta.get('content')

        # Try to extract authors
        authors = []
        author_meta = soup.find_all('meta', attrs={'name': 'author'})
        for author in author_meta:
            if author.get('content'):
                authors.append(author.get('content'))
        if authors:
            metadata['authors'] = authors

        # Try to extract description/summary
        desc_meta = soup.find('meta', attrs={'name': 'description'}) or \
                   soup.find('meta', attrs={'property': 'og:description'})
        if desc_meta:
            metadata['description'] = desc_meta.get('content')

        return metadata if metadata else None
