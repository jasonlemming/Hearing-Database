"""
Document data fetcher for Congress.gov API
"""
from typing import List, Dict, Any, Optional
from fetchers.base_fetcher import BaseFetcher
from config.logging_config import get_logger

logger = get_logger(__name__)


class DocumentFetcher(BaseFetcher):
    """Fetches document data from Congress.gov API"""

    def fetch_hearing_transcript(self, congress: int, chamber: str, jacket_number: str) -> Optional[Dict[str, Any]]:
        """
        Fetch hearing transcript information

        Args:
            congress: Congress number
            chamber: Chamber name
            jacket_number: 5-digit hearing jacket number

        Returns:
            Hearing transcript information
        """
        try:
            return self.api_client.get_hearing_transcript(congress, chamber.lower(), jacket_number)
        except Exception as e:
            logger.error(f"Error fetching transcript {jacket_number}: {e}")
            return None

    def extract_hearing_documents(self, hearing_details: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract all document information from hearing details.

        Accurately parses transcripts, witness statements, and supporting materials
        from the real Congress.gov response structure, capturing title, witness name
        (where applicable), description, file/format type, and URLs.

        Args:
            hearing_details: Detailed hearing data from Congress.gov API

        Returns:
            Dictionary with categorized documents:
            {
                'transcripts': List of transcript documents,
                'witness_documents': List of witness-related documents,
                'supporting_documents': List of supporting materials
            }
        """
        documents = {
            'transcripts': [],
            'witness_documents': [],
            'supporting_documents': []
        }

        # Extract transcript information
        transcripts = self._extract_transcripts(hearing_details)
        documents['transcripts'] = transcripts

        # Extract witness documents with full metadata
        witness_docs = self._extract_witness_documents(hearing_details)
        documents['witness_documents'] = witness_docs

        # Extract supporting documents with descriptions
        supporting_docs = self._extract_supporting_documents(hearing_details)
        documents['supporting_documents'] = supporting_docs

        return documents

    def _extract_transcripts(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract transcript documents from hearing details.

        In the real Congress.gov API, transcripts appear in the meetingDocuments
        array with documentType "Hearing: Transcript". This method extracts those
        transcript URLs directly.
        """
        transcripts = []

        # Check meetingDocuments for transcript entries
        meeting_docs = self.safe_get(hearing_details, 'meetingDocuments', [])
        for doc in meeting_docs:
            doc_type = self.safe_get(doc, 'documentType', '').lower()

            # Look for transcript document types
            if 'transcript' in doc_type:
                transcript = {
                    'jacket_number': None,  # Usually not in meetingDocuments
                    'title': self.safe_get(doc, 'name') or 'Hearing Transcript',
                    'document_url': self.safe_get(doc, 'url'),
                    'pdf_url': self.safe_get(doc, 'url') if self.safe_get(doc, 'format', '').upper() == 'PDF' else None,
                    'html_url': self.safe_get(doc, 'url') if self.safe_get(doc, 'format', '').upper() == 'HTML' else None,
                    'format_type': self.safe_get(doc, 'format', 'PDF')
                }
                transcripts.append(transcript)

        return transcripts

    def _extract_witness_documents(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract witness-related documents from hearing details.

        In the real Congress.gov API, witness documents are in a separate
        'witnessDocuments' array (not nested under each witness). Each document
        has documentType, format, and url, but no explicit witness name - we
        must infer it from the URL filename.
        """
        witness_docs = []

        # Get the list of witnesses to match documents to
        witnesses = self.safe_get(hearing_details, 'witnesses', [])
        witness_map = {}  # Map surname -> full witness info
        for witness in witnesses:
            full_name = self.safe_get(witness, 'name', '')
            if full_name:
                # Extract last name (assumes format like "Mr. Christopher Urben")
                surname = self._extract_surname(full_name)
                if surname:
                    witness_map[surname.lower()] = {
                        'name': full_name,
                        'title': self.safe_get(witness, 'position') or self.safe_get(witness, 'title'),
                        'organization': self.safe_get(witness, 'organization') or self.safe_get(witness, 'organisationName')
                    }

        # Extract documents from witnessDocuments array
        witness_document_array = self.safe_get(hearing_details, 'witnessDocuments', [])
        for doc in witness_document_array:
            # Extract witness surname from URL filename
            url = self.safe_get(doc, 'url', '')
            witness_surname = self._extract_witness_from_url(url)

            # Match to actual witness
            witness_info = witness_map.get(witness_surname.lower()) if witness_surname else None

            # Build witness document record
            witness_doc = {
                'witness_name': witness_info['name'] if witness_info else None,
                'witness_title': witness_info['title'] if witness_info else None,
                'witness_organization': witness_info['organization'] if witness_info else None,
                'document_type': self._normalize_document_type(self.safe_get(doc, 'documentType')),
                'title': self.safe_get(doc, 'name') or self.safe_get(doc, 'documentType'),
                'description': None,
                'document_url': url,
                'format_type': self.safe_get(doc, 'format', 'PDF')
            }

            # Only add if we successfully matched to a witness
            if witness_doc['witness_name']:
                witness_docs.append(witness_doc)

        return witness_docs

    def _extract_supporting_documents(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract supporting documents from hearing details.

        Captures committee documents, activity reports, member statements,
        and other materials not directly associated with witnesses.
        Includes descriptions for all document types where available.
        """
        supporting_docs = []

        # Check for supporting document information in various locations
        doc_sources = [
            'meetingDocuments',       # Congress.gov committee-meeting response
            'documents',              # General documents array
            'supportingDocuments',    # Explicitly labeled supporting docs
            'relatedDocuments',       # Related materials
            'materials',              # Alternative naming
            'attachments'             # Alternative naming
        ]

        for source in doc_sources:
            doc_data = self.safe_get(hearing_details, source, [])
            if doc_data and isinstance(doc_data, list):
                for doc in doc_data:
                    # Get document type to check if we should skip it
                    doc_type_raw = self.safe_get(doc, 'documentType') or self.safe_get(doc, 'type') or self.safe_get(doc, 'docType') or 'Document'

                    # Skip transcripts (handled separately) and witness-specific documents
                    if 'transcript' in doc_type_raw.lower() or self._is_witness_document(doc):
                        continue

                    # Normalize document type
                    doc_type = self._normalize_supporting_document_type(doc_type_raw)

                    # Build supporting document record with all available fields
                    supporting_doc = {
                        'document_type': doc_type,
                        'title': self.safe_get(doc, 'title') or self.safe_get(doc, 'name'),
                        'description': self.safe_get(doc, 'description') or self.safe_get(doc, 'summary'),
                        'document_url': self.safe_get(doc, 'url') or self.safe_get(doc, 'link'),
                        'format_type': self.safe_get(doc, 'format') or self._guess_format_from_url(
                            self.safe_get(doc, 'url', ''))
                    }
                    supporting_docs.append(supporting_doc)

        return supporting_docs

    def _normalize_transcript(self, transcript: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize transcript information"""
        return {
            'jacket_number': self.safe_get(transcript, 'jacketNumber'),
            'title': self.safe_get(transcript, 'title'),
            'document_url': self.safe_get(transcript, 'url'),
            'pdf_url': self.safe_get(transcript, 'pdfUrl'),
            'html_url': self.safe_get(transcript, 'htmlUrl'),
            'format_type': self.safe_get(transcript, 'format', 'PDF')
        }

    def _normalize_transcript_with_urls(self, transcript: Dict[str, Any],
                                       congress: int, chamber: str) -> Dict[str, Any]:
        """
        Normalize transcript and fetch actual document URLs from hearing endpoint.

        Args:
            transcript: Transcript data from committee-meeting response
            congress: Congress number
            chamber: Chamber name

        Returns:
            Normalized transcript with actual document URLs
        """
        jacket_number = self.safe_get(transcript, 'jacketNumber')

        # Start with basic normalization
        normalized = {
            'jacket_number': jacket_number,
            'title': self.safe_get(transcript, 'title'),
            'format_type': 'PDF'
        }

        # Fetch actual document URLs if we have jacket number
        if jacket_number and congress and chamber:
            url_data = self._fetch_transcript_urls(jacket_number, congress, chamber)
            if url_data:
                # Merge URL data
                normalized.update(url_data)

        return normalized

    def _fetch_transcript_urls(self, jacket_number: str, congress: int,
                              chamber: str) -> Optional[Dict[str, Any]]:
        """
        Fetch actual document URLs from hearing endpoint.

        Args:
            jacket_number: 5-digit hearing jacket number
            congress: Congress number
            chamber: Chamber name

        Returns:
            Dictionary with document_url, pdf_url, html_url, and format_type
        """
        try:
            # Call hearing endpoint to get formats array
            hearing_data = self.api_client.get_hearing_transcript(congress, chamber, jacket_number)

            if hearing_data and 'hearing' in hearing_data:
                hearing = hearing_data['hearing']
                formats = self.safe_get(hearing, 'formats', [])

                urls = {
                    'jacket_number': jacket_number,
                    'document_url': None,
                    'pdf_url': None,
                    'html_url': None,
                    'format_type': 'PDF'
                }

                # Extract URLs from formats array
                for fmt in formats:
                    fmt_type = self.safe_get(fmt, 'type', '').lower()
                    url = self.safe_get(fmt, 'url')

                    if url:
                        if 'pdf' in fmt_type:
                            urls['pdf_url'] = url
                            urls['document_url'] = url  # Primary URL
                        elif 'text' in fmt_type or 'html' in fmt_type:
                            urls['html_url'] = url
                            if not urls['document_url']:
                                urls['document_url'] = url

                # Set format type based on what we found
                if urls['pdf_url']:
                    urls['format_type'] = 'PDF'
                elif urls['html_url']:
                    urls['format_type'] = 'HTML'

                return urls

        except Exception as e:
            logger.warning(f"Failed to fetch transcript URLs for jacket {jacket_number}: {e}")

        return None

    def _normalize_document_type(self, doc_type: str) -> str:
        """
        Normalize document type to standard categories.

        Must map to allowed witness_documents table values:
        - Statement
        - Biography
        - Truth Statement
        - Questions for Record
        - Supplemental
        """
        if not doc_type:
            return 'Statement'  # Default

        doc_type_lower = doc_type.lower()

        # Map to standard document types (matching CHECK constraint)
        type_mapping = {
            'statement': 'Statement',
            'prepared statement': 'Statement',
            'written statement': 'Statement',
            'witness statement': 'Statement',
            'testimony': 'Statement',
            'biography': 'Biography',
            'bio': 'Biography',
            'witness biography': 'Biography',
            'biographical information': 'Biography',
            'truth statement': 'Truth Statement',
            'witness truth in testimony': 'Truth Statement',
            'truth in testimony': 'Truth Statement',
            'financial disclosure': 'Truth Statement',
            'questions for record': 'Questions for Record',
            'qfr': 'Questions for Record',
            'questions for the record': 'Questions for Record',
            'supplemental': 'Supplemental',
            'supplemental material': 'Supplemental',
            'additional material': 'Supplemental'
        }

        normalized = type_mapping.get(doc_type_lower)
        if normalized:
            return normalized

        # If not in map, try to infer from keywords
        if 'statement' in doc_type_lower or 'testimony' in doc_type_lower:
            return 'Statement'
        elif 'bio' in doc_type_lower:
            return 'Biography'
        elif 'truth' in doc_type_lower:
            return 'Truth Statement'
        elif 'question' in doc_type_lower:
            return 'Questions for Record'
        else:
            return 'Supplemental'

    def _is_witness_document(self, document: Dict[str, Any]) -> bool:
        """Check if document is witness-specific"""
        doc_type = self.safe_get(document, 'type', '').lower()
        witness_types = [
            'statement', 'testimony', 'biography', 'bio',
            'truth statement', 'financial disclosure',
            'prepared statement', 'written statement'
        ]

        return any(wtype in doc_type for wtype in witness_types)

    def _normalize_supporting_document_type(self, doc_type: str) -> str:
        """
        Normalize supporting document type to standard categories.

        Common supporting document types:
        - Activity Report
        - Committee Rules
        - Member Statements
        - Committee Reports
        - Background Materials
        """
        if not doc_type:
            return 'Document'

        doc_type_lower = doc_type.lower()

        # Map to standard supporting document types
        type_mapping = {
            'activity report': 'Activity Report',
            'committee activity report': 'Activity Report',
            'committee rules': 'Committee Rules',
            'rules': 'Committee Rules',
            'member statement': 'Member Statements',
            'member statements': 'Member Statements',
            'opening statement': 'Member Statements',
            'committee report': 'Committee Reports',
            'report': 'Committee Reports',
            'background material': 'Background Materials',
            'background': 'Background Materials',
            'fact sheet': 'Background Materials',
            'briefing': 'Background Materials',
            'memorandum': 'Memorandum',
            'memo': 'Memorandum',
            'correspondence': 'Correspondence',
            'letter': 'Correspondence'
        }

        return type_mapping.get(doc_type_lower, doc_type)

    def _guess_format_from_url(self, url: str) -> str:
        """Guess document format from URL if not explicitly provided"""
        if not url:
            return 'PDF'  # Default assumption

        url_lower = url.lower()
        if '.pdf' in url_lower:
            return 'PDF'
        elif '.html' in url_lower or '.htm' in url_lower:
            return 'HTML'
        elif '.txt' in url_lower:
            return 'Text'
        elif '.doc' in url_lower or '.docx' in url_lower:
            return 'Word'
        else:
            return 'PDF'  # Default assumption

    def _extract_surname(self, full_name: str) -> str:
        """
        Extract surname from full witness name.

        Examples:
        - "Mr. Christopher Urben" -> "Urben"
        - "Dr. Jane Smith-Jones" -> "Smith-Jones"
        - "The Honorable John Doe" -> "Doe"
        - "Rear Admiral Upper Half Mark Montgomery" -> "Montgomery"
        """
        if not full_name:
            return ''

        # Remove common titles/honorifics and military ranks
        name = full_name
        titles = [
            'Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Professor', 'The Honorable', 'Hon.',
            'Rear Admiral', 'Admiral', 'Vice Admiral',
            'General', 'Lieutenant General', 'Major General', 'Brigadier General',
            'Colonel', 'Lieutenant Colonel', 'Major', 'Captain', 'Lieutenant',
            'Upper Half', 'Lower Half'
        ]
        for title in titles:
            name = name.replace(title, '').strip()

        # Split and get last word (surname)
        parts = name.split()
        if parts:
            return parts[-1]

        return ''

    def _extract_witness_from_url(self, url: str) -> str:
        """
        Extract witness surname from document URL filename.

        Handles both 6-part and 7-part URL formats:
        - 6-part: "HHRG-119-HM09-Wstate-UrbenC-20250918.pdf" -> "Urben"
        - 7-part: "HHRG-119-JU13-TTF-KingD-20250929-U15.pdf" -> "King"

        The witness name is ALWAYS at position 4 (index 4) in both formats.
        """
        if not url:
            return ''

        # Get filename from URL
        filename = url.split('/')[-1]

        # Remove extension
        filename = filename.rsplit('.', 1)[0]

        # Split by hyphens
        parts = filename.split('-')

        # The witness name is ALWAYS at position 4 (index 4)
        # 6-part: HHRG-119-HM09-Wstate-UrbenC-20250918
        #         [0]  [1] [2]  [3]    [4]    [5]
        # 7-part: HHRG-119-JU13-TTF-KingD-20250929-U15
        #         [0]  [1] [2]  [3]  [4]  [5]     [6]
        if len(parts) >= 5:
            witness_part = parts[4]  # e.g., "UrbenC" or "KingD"

            # Remove trailing single capital letter (initial)
            if len(witness_part) > 1 and witness_part[-1].isupper():
                return witness_part[:-1]  # "Urben" or "King"

            return witness_part

        return ''

    def fetch_documents_for_hearings(self, hearing_list: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Fetch documents for a list of hearings

        Args:
            hearing_list: List of hearing records

        Returns:
            Dictionary mapping hearing IDs to document collections
        """
        all_documents = {}

        for hearing in hearing_list:
            hearing_id = self.safe_get(hearing, 'eventId') or self.safe_get(hearing, 'hearing_id')
            if hearing_id:
                documents = self.extract_hearing_documents(hearing)
                all_documents[hearing_id] = documents

        return all_documents

    def fetch_all(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Implementation of abstract method from BaseFetcher
        Note: Documents are typically fetched in context of hearings
        """
        # Documents are usually fetched as part of hearing details
        # This method is implemented for interface compliance
        logger.warning("fetch_all called on DocumentFetcher - documents are typically fetched via hearings")
        return []