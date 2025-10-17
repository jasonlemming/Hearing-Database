"""
HTML Parser for American Enterprise Institute (AEI)

Extracts structured content and metadata from AEI pages

Generated: 2025-10-17
Based on: brookings_ingester/docs/sources/aei_analysis.md
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


class AeiHTMLParser:
    """
    Parse HTML content from AEI pages

    Based on selectors identified in aei_analysis.md

    Extracts:
    - Metadata (title, authors, date, topics)
    - Main content (cleaned HTML)
    - Plain text (for search)
    - Document structure (headings, sections)
    """

    # Content selectors from analysis document
    CONTENT_SELECTORS = [
        'div.entry-content',
        'article .post-content',
        'main',
        'article',
    ]

    # Metadata selectors from analysis document
    METADATA_SELECTORS = {
        'title': [
            'h1.entry-title',
            'article h1',
            'h1',
            'meta[property="og:title"]',
        ],
        'authors': [
            'span.author-name a',
            '.entry-meta a[href*="/scholars/"]',
            '.byline a',
            'a[rel="author"]',
        ],
        'date': [
            'time[datetime]',
            'time.published',
            '.post-date',
            'meta[property="article:published_time"]',
        ],
        'summary': [
            'div.entry-summary',
            'meta[name="description"]',
            'meta[property="og:description"]',
        ],
        'topics': [
            'a[rel="category"]',
            '.entry-categories a',
            '.post-tag',
        ],
    }

    # Cleanup selectors from analysis document
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        'aside.related-content',
        'div.related-posts',
        'div.newsletter-signup',
        'form.newsletter-form',
        'div.social-sharing',
        '.share-buttons',
        'div.advertisement',
        '.ad-container',
        'div.comments',
        'section#comments',
        'aside.author-bio',
        'div.author-info-box',
        'section.recommended-reading',
        'div.event-details',
        '.breadcrumb',
        'script',
        'style',
        'noscript',
    ]

    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def parse(self, html: str, url: str) -> Optional[ParsedContent]:
        """
        Parse Aei HTML content

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
                logger.warning(f"No title found for {url}")
                return None

            # Extract metadata
            authors = self._extract_authors(soup)
            publication_date = self._extract_date(soup)
            summary = self._extract_summary(soup)
            subjects = self._extract_topics(soup)

            # Build metadata dict
            metadata = {
                'aei_url': url,
                'aei_topics': subjects,
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

            # Basic validation
            if word_count < 50:
                logger.warning(f"Content too short ({word_count} words) for {url}")
                return None

            logger.info(f"✓ Parsed Aei content: {word_count:,} words, {len(authors)} authors")

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
            logger.error(f"Error parsing Aei HTML: {e}")
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
        """
        # Remove AEI site name patterns
        patterns = [
            r'\s*[|\-–—]\s*AEI\s*$',
            r'\s*[|\-–—]\s*American Enterprise Institute\s*$',
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

                author_data = {'name': name}

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
            logger.debug(f"Failed to parse date '{date_str}': {e}")
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
                    logger.debug(f"Found content using selector: {selector} ({word_count} words)")
                    return content
                else:
                    logger.debug(f"Selector {selector} only found {word_count} words, trying next...")

        # Fallback: use body
        body = soup.find('body')
        if body:
            word_count = len(body.get_text().split())
            logger.warning(f"Using full body as content ({word_count} words)")
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
        # TODO: Implement if needed for your source
        # for img in soup.find_all('img'):
        #     src = img.get('src', '')
        #     if src and not src.startswith(('http://', 'https://', 'data:')):
        #         img['src'] = f"{base_url}{src if src.startswith('/') else '/' + src}"

        html = str(soup)

        # Remove excessive whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = re.sub(r'[ \t]+', ' ', html)

        return html.strip()

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """Extract plain text for search"""
        # Make a copy
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Get text with space separator
        text = soup_copy.get_text(separator=' ')

        # Fix spacing issues
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r' *\n *', '\n', text)
        text = re.sub(r'\s+([.,;:!?])', r'\1', text)
        text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)

        # Clean up excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        return text.strip()
