"""
HTML Parser for Brookings Institution content

Extracts structured content and metadata from Brookings research pages
"""
import re
import hashlib
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ParsedContent:
    """Container for parsed Brookings content"""
    html_content: str
    text_content: str
    structure: Dict[str, Any]
    title: str
    authors: List[str]
    publication_date: Optional[str]
    summary: str
    subjects: List[str]
    metadata: Dict[str, Any]
    word_count: int


class BrookingsHTMLParser:
    """
    Parse HTML content from Brookings Institution research pages

    Extracts:
    - Metadata (title, authors, date, topics, programs)
    - Main content (cleaned HTML)
    - Plain text (for search)
    - Document structure (headings, sections)
    """

    # CSS selectors for Brookings pages (React/WordPress-based)
    # Priority order: most specific first
    CONTENT_SELECTORS = [
        'div.article-content',  # Primary: Brookings React component (most reliable)
        'div.byo-blocks',       # Same as article-content
        'main',                 # Fallback: includes header/footer noise
        'article',
        'div.post-body',
        '.post-content',
        '[role="main"]',
        '.entry-content'
    ]

    METADATA_SELECTORS = {
        'title': [
            'h1.entry-title',
            'h1.post-title',
            'h1.article-title',
            'meta[property="og:title"]',
            'title'
        ],
        'authors': [
            'div.byo-block.authors',   # Brookings React component for authors
            'div.authors',
            '.author-name',
            '.byline a',
            'span[itemprop="author"]',
            '.article-author'
        ],
        'date': [
            'time[datetime]',
            '.post-date',
            '.published-date',
            'meta[property="article:published_time"]'
        ],
        'summary': [
            '.article-summary',
            '.post-excerpt',
            'meta[name="description"]',
            'meta[property="og:description"]'
        ],
        'topics': [
            '.topic-tag',
            '.post-tag',
            'a[rel="tag"]'
        ],
        'programs': [
            '.program-tag',
            '.research-program'
        ]
    }

    # Elements to remove
    REMOVE_SELECTORS = [
        'nav',
        'header',
        'footer',
        '.breadcrumb',
        '.navigation',
        '.site-header',
        '.site-footer',
        'script',
        'style',
        'noscript',
        '.advertisement',
        '.ad',
        '#sidebar',
        'aside.sidebar',              # Brookings: sidebars contain TOC/nav
        'aside.sidebar-left',         # Brookings: left sidebar
        'aside.sidebar-right',        # Brookings: right sidebar (TOC)
        '.sidebar',
        'div.byo-block.related-content',  # Brookings: related articles
        'div.related-content',
        '.related-posts',
        '.share-buttons',
        '.comments',
        'div.byo-block.authors',      # Author cards (extract separately for metadata)
        'div.article-meta',           # Article metadata
        'div.social-share',           # Social sharing buttons
        'div.podcast-links',          # Podcast platform links
        'div.listen-on',              # "Listen on" navigation
        'div.byo-block.cta',          # Call-to-action blocks
        'div.newsletter-signup',      # Newsletter forms
        'div.related-content',        # Related content boxes
        '.social-media-links',        # Social media link lists
        '.share-links',               # Share button containers (NOT embed-shareable!)
        '.social-icons',              # Social icon groups
        'button',                     # Interactive buttons
        'a[href*="apple.com"]',       # Apple Podcasts links
        'a[href*="spotify"]',         # Spotify links
        'a[href*="youtube"]',         # YouTube links
        'a[href*="pod.link"]',        # Podcast aggregator links
        '.drop-cap',                  # Decorative drop caps
        'svg:not(svg[class*="chart"])',  # SVG icons (but not charts)
    ]

    HEADING_TAGS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

    def _is_404_page(self, soup: BeautifulSoup) -> bool:
        """
        Detect if page is a 404 error page

        Multiple detection strategies:
        1. Check for Brookings-specific 404 class
        2. Check title for 404 or "Page not found"
        3. Check h1 for 404 error messages
        4. Check for very short content (< 100 words)

        Returns:
            True if page is a 404 error page
        """
        # Strategy 1: Check for Brookings 404 class
        if soup.select_one('.block-404, div.block-404, .error-404'):
            logger.debug("Detected 404 via block-404 class")
            return True

        # Strategy 2: Check title
        title = self._extract_title(soup)
        if title and ("404" in title or "page not found" in title.lower() or "not found" in title.lower()):
            logger.debug(f"Detected 404 via title: {title}")
            return True

        # Strategy 3: Check h1 for common 404 messages
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            h1_text = h1.get_text(strip=True).lower()
            if any(phrase in h1_text for phrase in [
                "couldn't find the page",
                "page not found",
                "404",
                "page you are looking for",
                "page doesn't exist"
            ]):
                logger.debug(f"Detected 404 via h1: {h1_text[:50]}")
                return True

        # Strategy 4: Check for suspiciously short content
        # Extract potential content area
        content = soup.select_one('div.article-content, main, article')
        if content:
            text = content.get_text(strip=True)
            word_count = len(text.split())
            # Real articles have at least 100 words; 404 pages are much shorter
            if word_count < 100:
                # Double-check it's not just a short intro (check for search form or "try these links")
                if 'try these links' in text.lower() or 'search' in text.lower():
                    logger.debug(f"Detected 404 via short content: {word_count} words")
                    return True

        return False

    def parse(self, html: str, url: str) -> Optional[ParsedContent]:
        """
        Parse Brookings HTML content

        Args:
            html: Raw HTML string
            url: Page URL (for metadata)

        Returns:
            ParsedContent object or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Check for 404 pages - reject early
            if self._is_404_page(soup):
                logger.warning(f"Detected 404 page, skipping: {url}")
                return None

            title = self._extract_title(soup)

            # Extract metadata
            authors = self._extract_authors(soup)
            publication_date = self._extract_date(soup)
            summary = self._extract_summary(soup)
            subjects = self._extract_topics(soup)
            programs = self._extract_programs(soup)

            # Build metadata dict
            metadata = {
                'brookings_programs': programs,
                'brookings_url': url,
                'brookings_topics': subjects
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

            logger.info(f"✓ Parsed Brookings content: {word_count:,} words, {len(authors)} authors")

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
            logger.error(f"Error parsing Brookings HTML: {e}")
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
        "Article Title | Brookings" -> "Article Title"
        "Article Title - Brookings Institution" -> "Article Title"
        """
        # Common patterns for site name suffixes
        patterns = [
            r'\s*[|\-–—]\s*Brookings\s*Institution\s*$',  # " | Brookings Institution"
            r'\s*[|\-–—]\s*Brookings\s*$',                 # " | Brookings"
            r'\s*[|\-–—]\s*The\s+Brookings\s+Institution\s*$'  # " | The Brookings Institution"
        ]

        for pattern in patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        return title.strip()

    def _extract_jsonld(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract JSON-LD structured data from page

        Returns:
            Dictionary with extracted structured data or None
        """
        try:
            # Find all JSON-LD script tags
            jsonld_scripts = soup.find_all('script', type='application/ld+json')

            # First pass: look for objects with datePublished
            for script in jsonld_scripts:
                try:
                    data = json.loads(script.string)

                    # Handle arrays of JSON-LD objects
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'datePublished' in item:
                                return item
                    elif isinstance(data, dict):
                        # Check if this dict has datePublished
                        if 'datePublished' in data:
                            return data

                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse JSON-LD: {e}")
                    continue

            # Second pass: return first valid dict if no datePublished found
            for script in jsonld_scripts:
                try:
                    data = json.loads(script.string)

                    if isinstance(data, list):
                        if data and isinstance(data[0], dict):
                            return data[0]
                    elif isinstance(data, dict):
                        return data

                except json.JSONDecodeError as e:
                    continue

            return None

        except Exception as e:
            logger.debug(f"Error extracting JSON-LD: {e}")
            return None

    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """Extract author names from Brookings pages"""
        authors = []

        # Special handling for Brookings byo-block.authors format
        authors_div = soup.select_one('div.byo-block.authors')
        if authors_div:
            # Look for author names in nested elements
            # Authors are often in links or specific class elements
            author_links = authors_div.select('a[href*="/experts/"]')
            if author_links:
                for link in author_links:
                    name = link.get_text(strip=True)
                    if name and name not in authors and not name.startswith('@'):
                        authors.append(name)
            else:
                # Fallback: try to parse structured text
                # Look for patterns like "Name\nTitle\nAffiliation"
                text = authors_div.get_text('\n', strip=True)
                lines = [l.strip() for l in text.split('\n') if l.strip()]

                # Filter out common non-name patterns
                for line in lines:
                    # Skip if line contains common metadata patterns
                    if any(x in line.lower() for x in ['fellow', 'director', 'professor', 'center', '@', 'bluesky', 'authors', 'http', '.com', 'senior', 'nonresident']):
                        continue
                    # Skip very short or very long strings
                    if len(line) < 5 or len(line) > 50:
                        continue
                    # Skip if all caps or contains mostly punctuation
                    if line.isupper() or line.count('.') > 2:
                        continue
                    # Likely an author name
                    if line and line not in authors:
                        authors.append(line)

        # Try other selectors if no authors found yet
        if not authors:
            for selector in self.METADATA_SELECTORS['authors'][1:]:  # Skip first (already tried)
                elements = soup.select(selector)
                for elem in elements:
                    author = elem.get_text(strip=True)
                    if author and author not in authors and len(author) < 100:
                        authors.append(author)

        return authors[:10]  # Limit to 10 authors max

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract publication date

        Priority order:
        1. JSON-LD structured data (most reliable)
        2. HTML meta tags and time elements
        3. Visible date text
        """
        # Try JSON-LD first (most reliable)
        jsonld = self._extract_jsonld(soup)
        if jsonld:
            # Try datePublished first
            date_published = jsonld.get('datePublished')
            if date_published:
                parsed_date = self._parse_date(date_published)
                if parsed_date:
                    logger.debug(f"✓ Found date via JSON-LD datePublished: {parsed_date}")
                    return parsed_date

            # Fall back to dateModified
            date_modified = jsonld.get('dateModified')
            if date_modified:
                parsed_date = self._parse_date(date_modified)
                if parsed_date:
                    logger.debug(f"✓ Found date via JSON-LD dateModified: {parsed_date}")
                    return parsed_date

        # Fall back to traditional selectors
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
            for fmt in ['%Y-%m-%d', '%B %d, %Y', '%b %d, %Y', '%m/%d/%Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
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

    def _extract_programs(self, soup: BeautifulSoup) -> List[str]:
        """Extract Brookings program/center tags"""
        programs = []
        for selector in self.METADATA_SELECTORS['programs']:
            elements = soup.select(selector)
            for elem in elements:
                program = elem.get_text(strip=True)
                if program and program not in programs:
                    programs.append(program)
        return programs

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
                # Get word count to validate we found real content
                word_count = len(content.get_text().split())

                # If this selector gives us substantial content, use it
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
                img['src'] = f"https://www.brookings.edu{src if src.startswith('/') else '/' + src}"

        html = str(soup)

        # Remove excessive whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = re.sub(r'[ \t]+', ' ', html)

        return html.strip()

    def _table_to_text(self, table) -> str:
        """Convert HTML table to pipe-delimited text format"""
        rows = []

        # Extract headers
        headers = []
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    headers.append(th.get_text(strip=True))

        # If no thead, check first row
        if not headers:
            first_row = table.find('tr')
            if first_row:
                # Check if first row is all th elements
                ths = first_row.find_all('th')
                if ths:
                    headers = [th.get_text(strip=True) for th in ths]

        # Extract data rows
        tbody = table.find('tbody')
        if tbody:
            data_rows = tbody.find_all('tr')
            # If no headers found yet, check if first row might be headers
            # (heuristic: first row with shorter text or different styling)
            if not headers and data_rows:
                first_row = data_rows[0]
                first_cells = first_row.find_all(['td', 'th'])
                # Check if first row looks like headers (shorter text, all caps, or bold)
                is_header = all(len(cell.get_text(strip=True)) < 30 for cell in first_cells)
                if is_header and len(first_cells) > 0:
                    headers = [cell.get_text(strip=True) for cell in first_cells]
                    data_rows = data_rows[1:]  # Skip first row
        else:
            # No tbody, get all rows (skip first if it was headers)
            all_rows = table.find_all('tr')
            data_rows = all_rows[1:] if headers else all_rows

        # Build table text with [TABLE] markers
        table_lines = ['\n[TABLE]']

        # Add headers if we have them
        if headers:
            table_lines.append('| ' + ' | '.join(headers) + ' |')
            # Add separator line to mark as header row
            table_lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')

        # Add data rows
        for row in data_rows:
            cells = row.find_all(['td', 'th'])
            if cells:
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                table_lines.append('| ' + ' | '.join(cell_texts) + ' |')

        table_lines.append('[/TABLE]\n')
        return '\n'.join(table_lines)

    def _figure_to_text(self, figure, figure_num: int) -> str:
        """
        Convert HTML figure (image/iframe + caption) to descriptive text format

        Handles:
        - Images with alt text
        - Iframes (embedded charts/maps)
        - Captions (figcaption)
        - Multiple items in one figure

        Args:
            figure: BeautifulSoup figure element
            figure_num: Sequential figure number

        Returns:
            Formatted text with [FIGURE] marker(s)
        """
        parts = []
        current_fig_num = figure_num

        # Extract all iframes first (charts, maps, etc.)
        iframes = figure.find_all('iframe')
        for iframe in iframes:
            title = iframe.get('title', '').strip()
            src = iframe.get('src', '').strip()

            if title and src:
                # Make absolute URL if needed
                if not src.startswith(('http://', 'https://')):
                    src = f"https://www.brookings.edu{src if src.startswith('/') else '/' + src}"

                fig_text = f'\n[FIGURE {current_fig_num}: {title}]'
                fig_text += f'\n[Interactive chart: {src}]'
                parts.append(fig_text)
                current_fig_num += 1

        # Extract images (if not already covered by iframes)
        if not iframes:
            img = figure.find('img')
            if img:
                img_alt = img.get('alt', '').strip()
                img_src = img.get('src', '').strip()

                # Make absolute URL
                if img_src and not img_src.startswith(('http://', 'https://', 'data:')):
                    img_src = f"https://www.brookings.edu{img_src if img_src.startswith('/') else '/' + img_src}"

                # Extract caption
                caption = ''
                figcaption = figure.find('figcaption')
                if figcaption:
                    caption = figcaption.get_text(strip=True)

                # Build description
                description = caption or img_alt or 'Image'

                fig_text = f'\n[FIGURE {current_fig_num}: {description}]'
                if img_src:
                    fig_text += f'\n[Image source: {img_src}]'
                parts.append(fig_text)

        # Join all parts
        result = '\n'.join(parts) + '\n' if parts else ''
        return result

    def _extract_text(self, soup: BeautifulSoup) -> str:
        """
        Extract plain text for search with improved spacing and heading preservation

        Handles:
        - Tables converted to pipe-delimited format
        - Figures/images with captions
        - Headings marked with special syntax for later formatting
        - Proper spacing between elements
        - Drop caps and decorative elements
        - Removal of excessive whitespace
        - Common abbreviations and formatting
        """
        # Make a copy to avoid modifying original
        soup_copy = BeautifulSoup(str(soup), 'lxml')

        # Process tables: convert to text format before extraction
        for table in soup_copy.find_all('table'):
            table_text = self._table_to_text(table)
            # Replace table with formatted text (use plain string, not BeautifulSoup)
            table.replace_with(table_text)

        # Process figures: convert to descriptive text with markers
        # Note: figures may contain iframes, images, or both
        figure_num = 1
        for figure in soup_copy.find_all('figure'):
            figure_text = self._figure_to_text(figure, figure_num)
            # Figure may contain multiple items (e.g., multiple iframes)
            # Count how many FIGURE markers were created
            num_figures = figure_text.count('[FIGURE')
            figure_num += num_figures if num_figures > 0 else 1
            # Replace figure with formatted text (use plain string, not BeautifulSoup)
            figure.replace_with(figure_text)

        # Process headings: mark them with special markers before text extraction
        for heading in soup_copy.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = heading.name  # h2, h3, etc.
            heading_text = heading.get_text(strip=True)
            if heading_text:
                # Add markers: [H2], [H3], etc.
                heading.string = f'\n\n[{level.upper()}]{heading_text}\n\n'

        # Get text with space separator to ensure words don't run together
        # Note: Don't use strip=True as it removes the newlines we embedded in headings
        text = soup_copy.get_text(separator=' ')

        # Fix common spacing issues - but preserve newlines around heading markers
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces/tabs to single space (preserve newlines)
        text = re.sub(r' *\n *', '\n', text)  # Clean up spaces around newlines

        text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.,;:!?])([A-Za-z])', r'\1 \2', text)  # Add space after punctuation if missing

        # Fix broken words (e.g., "R oughly" -> "Roughly")
        # This handles cases where decorative elements split words
        text = re.sub(r'\b([A-Z])\s+([a-z]{2,})\b', r'\1\2', text)

        # Fix common abbreviations with spaces (U. S. -> U.S.)
        text = re.sub(r'U\.\s+S\.', 'U.S.', text)
        text = re.sub(r'U\.\s+K\.', 'U.K.', text)

        # Fix possessive spacing (word ' s -> word's)
        text = re.sub(r"(\w+)\s+'\s+s\b", r"\1's", text)

        # Remove sequences of commas and spaces (from removed links) - but preserve newlines
        text = re.sub(r'[, \t]{3,}', ' ', text)

        # Clean up spacing around heading markers
        text = re.sub(r'\s+(\[H[0-9]\])', r'\n\n\1', text)
        text = re.sub(r'(\[H[0-9]\][^\n]+)\s+', r'\1\n\n', text)

        # Create proper paragraphs - split on common sentence endings
        # But preserve heading markers
        text = re.sub(r'([.!?])\s+(?!\[H[0-9]\])([A-Z])', r'\1\n\n\2', text)

        # Clean up remaining excessive whitespace
        text = re.sub(r' +', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple newlines to double newline

        # Fix URLs that got spaces inserted during text processing
        # This must be done LAST, after all other text cleanup
        # The regex at line 721 (add space after punctuation) adds spaces to URLs like "datawrapper.dwcdn.net"
        def fix_url_spaces(match):
            """Remove all spaces from URLs in markers"""
            marker = match.group(1)  # "Interactive chart" or "Image source"
            url = match.group(2).replace(' ', '')  # Remove all spaces from URL
            return f'[{marker}: {url}]'

        text = re.sub(r'\[(Interactive chart|Image source): ([^\]]+)\]', fix_url_spaces, text)

        return text.strip()
