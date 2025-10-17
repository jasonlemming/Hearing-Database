"""
HTML Parser for Heritage Foundation content

Extracts structured content and metadata from Heritage research pages
"""
import re
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedContent:
    """Container for parsed Heritage content"""
    html_content: str
    text_content: str
    structure: Dict[str, Any]
    title: str
    authors: List[Dict[str, str]]  # List of author dicts with name, title, affiliation, etc.
    publication_date: Optional[str]
    summary: str
    subjects: List[str]
    metadata: Dict[str, Any]
    word_count: int


class HeritageHTMLParser:
    """
    Parse HTML content from Heritage Foundation research pages

    Extracts:
    - Metadata (title, authors, date, topics)
    - Main content (cleaned HTML)
    - Plain text (for search)
    - Document structure (headings, sections)
    """

    # CSS selectors for Heritage pages (Drupal-based)
    CONTENT_SELECTORS = [
        'div.article-body',
        'div.field--name-body',
        'div.field--name-field-body',
        'article.node--type-article',
        'main',
        'article',
        'div.content',
        '[role="main"]',
    ]

    METADATA_SELECTORS = {
        'title': [
            'h1.page-title',
            'h1.article-title',
            'h1.node-title',
            'meta[property="og:title"]',
            'title'
        ],
        'authors': [
            'div.author-card__author-info-wrapper',
            'div.field--name-field-authors',
            'div.author-info',
            '.byline',
            '.author-name',
            'span[itemprop="author"]',
        ],
        'date': [
            'div.article-general-info',  # Heritage specific: "Nov 21, 2016 4 min read"
            'time[datetime]',
            'meta[property="article:published_time"]',
            'div.field--name-post-date',
            '.published-date',
            '.post-date',
        ],
        'summary': [
            'div.commentary__intro-wrapper',  # Heritage specific intro
            'div.field--name-field-summary',
            'div.article-summary',
            '.lead',
            'meta[name="description"]',
            'meta[property="og:description"]'
        ],
        'topics': [
            'div.field--name-field-topics a',
            'a[rel="tag"]',
            '.topic-tag',
            '.category',
        ]
    }

    # Elements to remove
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        '.breadcrumb',
        '.navigation',
        'script',
        'style',
        'noscript',
        '.advertisement',
        '.ad',
        '#sidebar',
        '.sidebar',
        '.related-content',
        '.related-posts',
        '.share-buttons',
        '.social-share',
        '.comments',
        '.author-bio',  # Author bios in content area
        '.newsletter-signup',
        '.cta',
        'button',
        '.social-media-links',
        '.share-links',
        'svg:not(svg[class*="chart"])',  # SVG icons (but not charts)
    ]

    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def parse(self, html: str, url: str) -> Optional[ParsedContent]:
        """
        Parse Heritage HTML content

        Args:
            html: Raw HTML string
            url: Page URL (for metadata)

        Returns:
            ParsedContent object or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract metadata FIRST before removing anything
            title = self._extract_title(soup)
            publication_date = self._extract_date(soup)  # Extract date before removing scripts
            subjects = self._extract_topics(soup)
            summary = self._extract_summary(soup)

            # Extract authors (this removes scripts internally)
            authors = self._extract_authors(soup)

            # Build metadata dict
            metadata = {
                'heritage_url': url,
                'heritage_topics': subjects
            }

            # Extract main content
            content_soup = self._extract_content_area(soup)
            if not content_soup:
                logger.error(f"Could not extract content area from {url}")
                return None

            # Build structure
            structure = self._build_structure(content_soup)

            # Get cleaned HTML
            clean_html = self._clean_html(content_soup)

            # Extract plain text
            text_content = self._extract_text(content_soup)
            word_count = len(text_content.split())

            logger.info(f"✓ Parsed Heritage content: {word_count:,} words, {len(authors)} authors")

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
            logger.error(f"Error parsing Heritage HTML: {e}")
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

                # Clean the title to remove site name suffixes
                return self._clean_title(title)
        return "Untitled"

    def _clean_title(self, title: str) -> str:
        """
        Clean title by removing site name suffixes

        Examples:
        "Article Title | The Heritage Foundation" -> "Article Title"
        """
        patterns = [
            r'\s*[|\-–—]\s*The\s+Heritage\s+Foundation\s*$',
            r'\s*[|\-–—]\s*Heritage\s+Foundation\s*$',
            r'\s*[|\-–—]\s*Heritage\s*$',
        ]

        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        return title.strip()

    def _extract_authors(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extract author information from Heritage pages with metadata

        Extracts:
        - name: Author's full name
        - title: Job title/position (e.g., "Former Senior Research Fellow")
        - affiliation: Description (e.g., "specialized in Korean and Japanese affairs...")
        - profile_url: Heritage profile page URL
        - twitter_url: Twitter profile URL (if available)

        Heritage uses author-card structure with specific CSS classes

        Returns:
            List of author dictionaries with metadata
        """
        authors = []
        seen_names = set()

        # Remove scripts first to avoid extracting JavaScript
        soup = BeautifulSoup(str(soup), 'lxml')
        for tag in soup.find_all(['script', 'style', 'noscript']):
            tag.decompose()

        # STRATEGY 1: Look for author-card__author-info-wrapper (most reliable for Heritage)
        author_cards = soup.find_all('div', class_='author-card__author-info-wrapper')

        for card in author_cards:
            author_data = {}

            # Extract name from author-card__name
            name_elem = card.select_one('p.author-card__name, .author-card__name')
            if name_elem:
                # Get the span inside or the text directly
                name_span = name_elem.find('span')
                name = name_span.get_text(strip=True) if name_span else name_elem.get_text(strip=True)

                # Clean up name (remove extra whitespace)
                name = ' '.join(name.split())

                if not name or len(name) < 3 or len(name) > 100:
                    continue
                if name in seen_names:
                    continue

                author_data['name'] = name
                seen_names.add(name)

                # Extract title from author-card__title
                title_elem = card.select_one('p.author-card__title, .author-card__title')
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:
                        author_data['title'] = title

                # Extract affiliation/description from author-card__info
                info_elem = card.select_one('div.author-card__info, .author-card__info')
                if info_elem:
                    affiliation = info_elem.get_text(strip=True)
                    if affiliation:
                        author_data['affiliation'] = affiliation

                # Extract Twitter handle
                twitter_elem = card.select_one('a.author-card__twitter-handle')
                if twitter_elem:
                    twitter_url = twitter_elem.get('href', '')
                    if twitter_url and twitter_url != 'https://twitter.com/':
                        author_data['twitter_url'] = twitter_url

                authors.append(author_data)
                logger.debug(f"✓ Found author via author-card: {name}")

        # STRATEGY 2: Fallback - look for author bio in article body (last paragraph pattern)
        # Heritage often includes "- AuthorName is Title at Heritage..." at end of article
        if not authors:
            # Look for paragraphs starting with "- " (author bio signature)
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if text.startswith('- ') and ' is ' in text and 'Heritage' in text:
                    # Extract name (between "- " and " is ")
                    match = re.match(r'^-\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+is\s+(.+?)(?:\s+at\s+The\s+Heritage\s+Foundation)?\.', text)
                    if match:
                        name = match.group(1).strip()
                        title_desc = match.group(2).strip()

                        if name and name not in seen_names:
                            author_data = {'name': name}
                            seen_names.add(name)

                            # Try to split title from description
                            # E.g., "Senior Research Fellow for Northeast Asia"
                            if title_desc:
                                author_data['title'] = title_desc

                            authors.append(author_data)
                            logger.debug(f"✓ Found author via bio signature: {name}")


        if authors:
            logger.info(f"Extracted {len(authors)} authors: {[a.get('name') for a in authors]}")
        else:
            logger.warning("No authors extracted from page")

        return authors[:20]  # Limit to 20 authors max

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract publication date

        Priority order:
        1. HTML meta tags and time elements
        2. Visible date text (Heritage format: "Nov 21, 2016 4 min read")
        """
        for selector in self.METADATA_SELECTORS['date']:
            element = soup.select_one(selector)
            if element:
                # Try datetime attribute first
                date_str = element.get('datetime')
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        logger.debug(f"✓ Found date via selector {selector}: {parsed_date}")
                        return parsed_date

                # Try content attribute (meta tags)
                date_str = element.get('content')
                if date_str:
                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        logger.debug(f"✓ Found date via meta tag: {parsed_date}")
                        return parsed_date

                # Try text content
                date_str = element.get_text(strip=True)
                if date_str:
                    # Heritage specific: extract just the date part before "min read"
                    # Example: "Nov 21, 2016 4 min read" or "Nov 21, 20164 min read" -> "Nov 21, 2016"
                    # Pattern: Month Day, Year + digits + "min read"
                    # The year might be stuck to the next digit (20164 instead of 2016 4)
                    match = re.match(r'([A-Za-z]+\s+\d+,\s+\d{4})\s*\d+\s+min\s+read', date_str, re.I)
                    if match:
                        date_str = match.group(1).strip()
                    else:
                        # Fallback: just remove min read part
                        date_str = re.sub(r'\s*\d+\s+min\s+read.*$', '', date_str, flags=re.I).strip()

                    parsed_date = self._parse_date(date_str)
                    if parsed_date:
                        logger.debug(f"✓ Found date via text content: {parsed_date}")
                        return parsed_date

        logger.warning("Could not extract publication date from any source")
        return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Parse date string to YYYY-MM-DD format"""
        try:
            # Handle ISO format
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')

            # Handle common formats
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y', '%b %d, %Y %H min read']:
                try:
                    # Remove "min read" suffix if present
                    clean_date = re.sub(r'\s+\d+\s+min\s+read$', '', date_str, flags=re.I)
                    dt = datetime.strptime(clean_date.strip(), fmt)
                    return dt.strftime('%Y-%m-%d')
                except ValueError:
                    continue

            return None
        except Exception:
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
                    return summary

        # Fallback: First paragraph of content
        content = self._extract_content_area(soup)
        if content:
            first_p = content.find('p')
            if first_p:
                return first_p.get_text(strip=True)[:500]

        return ""

    def _extract_topics(self, soup: BeautifulSoup) -> List[str]:
        """Extract topic tags"""
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

        # Remove scripts and styles FIRST (before any parsing)
        for tag in soup.find_all(['script', 'style', 'noscript']):
            tag.decompose()

        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Find main content
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                # Get word count to validate we found real content
                word_count = len(content.get_text().split())

                # If this selector gives us substantial content, use it
                if word_count > 50:  # Require at least 50 words
                    # Clean Heritage-specific elements from content
                    self._clean_heritage_content(content)

                    logger.debug(f"Found content using selector: {selector} ({word_count} words)")
                    return content
                else:
                    logger.debug(f"Selector {selector} only found {word_count} words, trying next...")

        # Fallback: use body
        body = soup.find('body')
        if body:
            self._clean_heritage_content(body)
            word_count = len(body.get_text().split())
            logger.warning(f"Using full body as content ({word_count} words)")
            return body

        return soup

    def _clean_heritage_content(self, content_soup: BeautifulSoup):
        """
        Remove Heritage-specific content elements

        - Author bio signatures (paragraphs starting with "- AuthorName is...")
        - Reference paragraphs ("This piece originally appeared in...")
        - Author card elements
        """
        # Remove author cards (already extracted for metadata)
        for card in content_soup.find_all('div', class_='author-card__author-info-wrapper'):
            if card.parent:
                card.parent.decompose()

        # Remove author bio signatures at end of article
        for p in content_soup.find_all('p'):
            text = p.get_text(strip=True)
            # Remove paragraphs like "- Bruce Klingner is Senior Research Fellow..."
            if text.startswith('- ') and ' is ' in text and 'Heritage' in text:
                p.decompose()

        # Remove reference paragraphs
        for p in content_soup.find_all('p', class_='article-body__reference'):
            p.decompose()

        # Remove "COMMENTARY BY" figcaptions
        for fig in content_soup.find_all('figcaption'):
            if 'COMMENTARY BY' in fig.get_text().upper():
                if fig.parent and fig.parent.name == 'figure':
                    fig.parent.decompose()
                else:
                    fig.decompose()

    def _build_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Build document structure from headings"""
        toc = []
        headings = []

        for order, heading in enumerate(soup.find_all(self.HEADING_TAGS)):
            if not heading.get_text(strip=True):
                continue

            heading_text = heading.get_text(strip=True)
            heading_level = int(heading.name[1])  # h1 -> 1, h2 -> 2

            entry = {
                'level': heading_level,
                'title': heading_text,
                'order': order
            }

            toc.append(entry)
            headings.append(heading_text)

        return {
            'toc': toc,
            'headings': headings
        }

    def _clean_html(self, soup: BeautifulSoup) -> str:
        """Clean and format HTML for display"""
        # Remove empty paragraphs
        for tag in soup.find_all(['p', 'div']):
            if not tag.get_text(strip=True):
                tag.decompose()

        # Fix image paths (convert relative to absolute)
        for img in soup.find_all('img'):
            src = img.get('src', '')
            if src and not src.startswith(('http://', 'https://', 'data:')):
                img['src'] = f"https://www.heritage.org{src if src.startswith('/') else '/' + src}"

        html = str(soup)

        # Remove excessive whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = re.sub(r'[ \t]+', ' ', html)

        return html.strip()

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract plain text for search with improved spacing and heading preservation
        """
        # Make a copy to avoid modifying original
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Process headings: mark them with special markers before text extraction
        for heading in soup_copy.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = heading.name  # h2, h3, etc.
            heading_text = heading.get_text(strip=True)
            if heading_text:
                # Add markers: [H2], [H3], etc.
                heading.string = f'\n\n[{level.upper()}]{heading_text}\n\n'

        # Get text with space separator to ensure words don't run together
        text = soup_copy.get_text(separator=' ')

        # Fix common spacing issues
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space
        text = re.sub(r' *\n *', '\n', text)  # Clean up spaces around newlines
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)  # Add space after punctuation

        # Fix common abbreviations with spaces (U. S. -> U.S.)
        text = re.sub(r'U\.\s+S\.', 'U.S.', text)
        text = re.sub(r'U\.\s+K\.', 'U.K.', text)

        # Clean up spacing around heading markers
        text = re.sub(r'\s+(\[H[0-9]\])', r'\n\n\1', text)
        text = re.sub(r'(\[H[0-9]\][^\n]+)\s+', r'\1\n\n', text)

        # Create proper paragraphs
        text = re.sub(r'([.!?])\s+(?!\[H[0-9]\])([A-Z])', r'\1\n\n\2', text)

        # Clean up excessive whitespace
        text = re.sub(r' +', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        return text.strip()
