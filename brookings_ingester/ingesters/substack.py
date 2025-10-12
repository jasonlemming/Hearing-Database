"""
Substack Newsletter Ingester

Fetches newsletter content from Substack publications using:
1. RSS feed discovery (primary)
2. Direct HTML page scraping
3. Clean HTML parsing (no browser automation needed)
"""
import logging
import time
import feedparser
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import re

from .base import BaseIngester
from .utils.html_parser import BrookingsHTMLParser
from brookings_ingester.config import config

logger = logging.getLogger(__name__)


class SubstackIngester(BaseIngester):
    """
    Substack newsletter content ingester

    Discovers posts via RSS feeds, fetches HTML content, extracts metadata,
    and stores in database with full-text search support.
    """

    def __init__(self, rate_limit_delay: float = None):
        """
        Initialize Substack ingester

        Args:
            rate_limit_delay: Delay between requests (default: 1.0s)
        """
        super().__init__(source_code='SUBSTACK', rate_limit_delay=rate_limit_delay or 1.0)

        # Reuse Brookings HTML parser (Substack has similar clean HTML)
        self.html_parser = SubstackHTMLParser()

        # Content filters
        self.start_date = config.START_DATE
        self.publications = config.SUBSTACK_PUBLICATIONS if hasattr(config, 'SUBSTACK_PUBLICATIONS') else []

    def discover(self, limit: int = None, publications: List[str] = None,
                 since_date: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Discover Substack posts via RSS feeds

        Args:
            limit: Maximum number of documents to discover
            publications: List of Substack publication URLs (e.g., ['author.substack.com'])
            since_date: Override start date (YYYY-MM-DD)
            **kwargs: Additional parameters

        Returns:
            List of document metadata dictionaries
        """
        publications = publications or self.publications
        since_date = since_date or self.start_date

        if not publications:
            logger.warning("No publications specified for Substack ingestion")
            return []

        # Parse since_date for filtering
        if since_date:
            try:
                cutoff_date = datetime.strptime(since_date, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date format: {since_date}")
                cutoff_date = None
        else:
            cutoff_date = None

        all_documents = []

        for publication in publications:
            logger.info(f"Discovering posts from {publication}")

            # Build RSS feed URL
            feed_url = self._build_feed_url(publication)

            try:
                self._rate_limit()

                # Parse RSS feed
                logger.debug(f"Fetching RSS feed: {feed_url}")
                feed = feedparser.parse(feed_url)

                if feed.bozo:
                    # Feed has parse errors
                    logger.warning(f"RSS feed has parse errors for {publication}: {feed.bozo_exception}")

                if not feed.entries:
                    logger.warning(f"No entries found in RSS feed for {publication}")
                    continue

                logger.info(f"Found {len(feed.entries)} posts in {publication} RSS feed")

                # Process each entry
                for entry in feed.entries:
                    # Filter by date
                    if cutoff_date:
                        pub_date = self._parse_feed_date(entry)
                        if pub_date and pub_date < cutoff_date:
                            logger.debug(f"Skipping post older than {since_date}: {entry.title}")
                            continue

                    # Extract metadata
                    doc = self._parse_feed_entry(entry, publication)
                    if doc:
                        all_documents.append(doc)

                        # Check limit
                        if limit and len(all_documents) >= limit:
                            logger.info(f"Reached limit of {limit} documents")
                            return all_documents

            except Exception as e:
                logger.error(f"Error fetching RSS feed for {publication}: {e}")
                continue

        logger.info(f"Discovered {len(all_documents)} Substack posts total")
        return all_documents

    def _build_feed_url(self, publication: str) -> str:
        """
        Build RSS feed URL for a Substack publication

        Args:
            publication: Publication domain (e.g., 'author.substack.com' or 'https://author.substack.com')

        Returns:
            Full RSS feed URL
        """
        # Clean publication URL
        publication = publication.strip()

        # Remove protocol if present
        if publication.startswith('http://') or publication.startswith('https://'):
            parsed = urlparse(publication)
            publication = parsed.netloc

        # Build feed URL
        return f"https://{publication}/feed"

    def _parse_feed_date(self, entry: Dict) -> Optional[datetime]:
        """
        Parse publication date from RSS feed entry

        Args:
            entry: feedparser entry dict

        Returns:
            datetime object or None
        """
        # Try published_parsed first (most reliable)
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                return datetime(*entry.published_parsed[:6])
            except:
                pass

        # Try updated_parsed
        if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            try:
                return datetime(*entry.updated_parsed[:6])
            except:
                pass

        # Try parsing date strings
        for date_field in ['published', 'updated']:
            if hasattr(entry, date_field):
                date_str = getattr(entry, date_field)
                if date_str:
                    try:
                        # Try ISO format
                        if 'T' in date_str:
                            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        pass

        return None

    def _parse_feed_entry(self, entry: Dict, publication: str) -> Optional[Dict[str, Any]]:
        """
        Parse RSS feed entry into document metadata

        Args:
            entry: feedparser entry dict
            publication: Publication domain

        Returns:
            Document metadata dict
        """
        try:
            # Extract URL
            url = entry.get('link', '')
            if not url:
                logger.warning("RSS entry missing link")
                return None

            # Extract document identifier from URL
            document_identifier = self._extract_slug(url)

            # Extract title
            title = entry.get('title', 'Untitled')
            if hasattr(title, 'rendered'):
                title = title.rendered
            title = self._clean_html_text(title)

            # Extract publication date
            pub_date = self._parse_feed_date(entry)
            publication_date = pub_date.strftime('%Y-%m-%d') if pub_date else None

            # Extract summary
            summary = ''
            if hasattr(entry, 'summary'):
                summary = self._clean_html_text(entry.summary)[:500]
            elif hasattr(entry, 'description'):
                summary = self._clean_html_text(entry.description)[:500]

            # Extract author
            author = None
            if hasattr(entry, 'author'):
                author = entry.author
            elif hasattr(entry, 'dc_creator'):
                author = entry.dc_creator

            return {
                'document_identifier': document_identifier,
                'url': url,
                'title': title,
                'publication_date': publication_date,
                'summary': summary,
                'author': author,
                'publication': publication,
                'rss_id': entry.get('id', '')
            }

        except Exception as e:
            logger.error(f"Error parsing RSS entry: {e}")
            return None

    def fetch(self, document_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Fetch Substack post content (HTML)

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
            self._rate_limit()

            logger.debug(f"Fetching HTML: {url}")
            response = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
            response.raise_for_status()

            html_content = response.text

            if not html_content:
                logger.error(f"Empty HTML content from {url}")
                return None

            logger.info(f"✓ Fetched HTML: {url} ({len(html_content):,} bytes)")

            return {
                'html_content': html_content
            }

        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def parse(self, document_meta: Dict[str, Any], fetched_content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse Substack post content and extract metadata

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

            # Merge RSS metadata with parsed data
            # RSS data is more reliable for dates and authors
            title = parsed.title or document_meta.get('title', 'Untitled')
            publication_date = document_meta.get('publication_date') or parsed.publication_date

            # Authors: prefer RSS if available
            authors = parsed.authors
            if document_meta.get('author') and document_meta['author'] not in authors:
                authors.insert(0, document_meta['author'])

            # Summary: prefer RSS if available and longer
            summary = document_meta.get('summary', '') or parsed.summary

            # Add publication as a subject
            subjects = parsed.subjects.copy()
            publication_name = self._extract_publication_name(document_meta.get('publication', ''))
            if publication_name and publication_name not in subjects:
                subjects.append(publication_name)

            return {
                'document_identifier': document_meta['document_identifier'],
                'title': title,
                'document_type': 'Newsletter Article',
                'publication_date': publication_date,
                'summary': summary,
                'full_text': parsed.text_content,
                'url': document_meta['url'],
                'pdf_url': None,  # Substack doesn't provide PDFs
                'authors': authors,
                'subjects': subjects,
                'metadata': {
                    'substack_publication': document_meta.get('publication'),
                    'rss_id': document_meta.get('rss_id'),
                    **parsed.metadata
                },
                'html_content': parsed.html_content,
                'text_content': parsed.text_content,
                'structure': parsed.structure,
                'page_count': None,
                'word_count': parsed.word_count
            }

        except Exception as e:
            logger.error(f"Error parsing content for {document_meta['document_identifier']}: {e}")
            return None

    def _extract_slug(self, url: str) -> str:
        """
        Extract document identifier from Substack URL

        Examples:
        https://author.substack.com/p/article-title -> article-title
        https://custom.com/p/article-title -> article-title
        """
        path = urlparse(url).path.strip('/')
        parts = path.split('/')

        # Substack URLs typically: /p/{slug}
        if 'p' in parts:
            idx = parts.index('p')
            if idx + 1 < len(parts):
                return parts[idx + 1]

        # Fallback: use last part
        slug = parts[-1] if parts else 'unknown'

        # Clean slug
        slug = slug.replace('.html', '')

        return slug

    def _extract_publication_name(self, publication: str) -> str:
        """
        Extract clean publication name from domain

        Examples:
        author.substack.com -> Author
        my-newsletter.substack.com -> My Newsletter
        """
        if not publication:
            return ''

        # Remove protocol
        publication = re.sub(r'^https?://', '', publication)

        # Get domain part before .substack.com
        publication = publication.split('.substack.com')[0]
        publication = publication.split('.')[0]  # Handle custom domains

        # Convert hyphens to spaces and title case
        publication = publication.replace('-', ' ').replace('_', ' ')
        publication = publication.title()

        return publication

    def _clean_html_text(self, html_text: str) -> str:
        """Remove HTML tags from text"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_text, 'lxml')
        return soup.get_text(strip=True)


class SubstackHTMLParser:
    """
    Parse HTML content from Substack newsletter posts

    Substack has cleaner HTML than Brookings, with consistent structure:
    - Content in .post-content or .body
    - Metadata in structured areas
    - Clean heading hierarchy
    """

    # Substack-specific selectors
    CONTENT_SELECTORS = [
        'div.post-content',
        'div.body',
        'div.available-content',
        'article.post',
        'div.post'
    ]

    METADATA_SELECTORS = {
        'title': [
            'h1.post-title',
            'h1.entry-title',
            'meta[property="og:title"]',
            'title'
        ],
        'authors': [
            'a.frontend-pencraft-Text-module__decoration-hover-underline',
            'span.author-name',
            'a.pencraft',
            'meta[property="article:author"]'
        ],
        'date': [
            'time[datetime]',
            'meta[property="article:published_time"]'
        ],
        'summary': [
            'meta[name="description"]',
            'meta[property="og:description"]'
        ]
    }

    REMOVE_SELECTORS = [
        'nav',
        'header.header',
        'footer',
        'div.paywall',
        'div.subscribe-widget',
        'div.subscription-widget-wrap',
        'button',
        'div.captioned-button-wrap',
        'div.share-dialog',
        'script',
        'style',
        'noscript'
    ]

    def parse(self, html: str, url: str):
        """
        Parse Substack HTML content

        Uses same pattern as BrookingsHTMLParser for consistency
        """
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract metadata
            title = self._extract_title(soup)
            authors = self._extract_authors(soup)
            publication_date = self._extract_date(soup)
            summary = self._extract_summary(soup)

            # Extract main content
            content_soup = self._extract_content_area(soup)
            if not content_soup:
                logger.error(f"Could not extract content area from {url}")
                return None

            # Build structure
            structure = self._build_structure(content_soup)

            # Get cleaned HTML
            clean_html = str(content_soup)

            # Extract plain text
            text_content = content_soup.get_text('\n', strip=True)
            word_count = len(text_content.split())

            logger.info(f"✓ Parsed Substack content: {word_count:,} words, {len(authors)} authors")

            # Create ParsedContent-like object
            from dataclasses import dataclass
            from typing import Dict, Any, List, Optional

            @dataclass
            class ParsedContent:
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

            return ParsedContent(
                html_content=clean_html,
                text_content=text_content,
                structure=structure,
                title=title,
                authors=authors,
                publication_date=publication_date,
                summary=summary,
                subjects=[],
                metadata={'substack_url': url},
                word_count=word_count
            )

        except Exception as e:
            logger.error(f"Error parsing Substack HTML: {e}")
            return None

    def _extract_title(self, soup) -> str:
        """Extract post title"""
        from bs4 import BeautifulSoup

        for selector in self.METADATA_SELECTORS['title']:
            element = soup.select_one(selector)
            if element:
                if element.name == 'meta':
                    return element.get('content', '').strip()
                else:
                    return element.get_text(strip=True)
        return "Untitled"

    def _extract_authors(self, soup) -> List[str]:
        """Extract author names"""
        authors = []

        # Common non-author text to filter out
        skip_patterns = ['reply', 'share', 'subscribe', 'read more', 'comments',
                        'like', 'restacks', 'restack', 'ago', 'min read',
                        '2d', '3d', '4d', '1w', '2w', 'privacy', 'terms',
                        'collection notice', 'by', 'order', 'regular']  # Footer/UI text

        for selector in self.METADATA_SELECTORS['authors']:
            elements = soup.select(selector)
            for elem in elements:
                author = elem.get_text(strip=True)

                # Skip if empty, too long, or matches skip patterns
                if not author or len(author) > 50:  # Tighter limit
                    continue

                # Skip if matches common UI text
                if any(pattern in author.lower() for pattern in skip_patterns):
                    continue

                # Skip if too short (likely UI element)
                if len(author) < 3:
                    continue

                # Skip if starts with common prefixes
                if author.lower().startswith(('regular order', 'collection')):
                    continue

                if author not in authors:
                    authors.append(author)

        # If we have exactly one author that looks good, use it
        # Otherwise, prefer RSS author data (handled in parse())
        return authors[:2]  # Limit to 2 to avoid UI text

    def _extract_date(self, soup) -> Optional[str]:
        """Extract publication date"""
        for selector in self.METADATA_SELECTORS['date']:
            element = soup.select_one(selector)
            if element:
                date_str = element.get('datetime') or element.get('content')
                if date_str:
                    try:
                        if 'T' in date_str:
                            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                            return dt.strftime('%Y-%m-%d')
                    except:
                        pass
        return None

    def _extract_summary(self, soup) -> str:
        """Extract post summary"""
        for selector in self.METADATA_SELECTORS['summary']:
            element = soup.select_one(selector)
            if element:
                return element.get('content', '').strip()
        return ""

    def _extract_content_area(self, soup):
        """Extract main content area"""
        from bs4 import BeautifulSoup

        # Make a copy
        soup = BeautifulSoup(str(soup), 'lxml')

        # Remove unwanted elements
        for selector in self.REMOVE_SELECTORS:
            for element in soup.select(selector):
                element.decompose()

        # Find main content
        for selector in self.CONTENT_SELECTORS:
            content = soup.select_one(selector)
            if content:
                word_count = len(content.get_text().split())
                if word_count > 50:
                    logger.debug(f"Found content using selector: {selector} ({word_count} words)")
                    return content

        # Fallback
        return soup.find('body') or soup

    def _build_structure(self, soup) -> Dict[str, Any]:
        """Build document structure from headings"""
        toc = []
        headings = []

        for order, heading in enumerate(soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])):
            heading_text = heading.get_text(strip=True)
            if not heading_text:
                continue

            heading_level = int(heading.name[1])

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
