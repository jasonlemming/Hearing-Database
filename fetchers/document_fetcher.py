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
        Extract all document information from hearing details

        Args:
            hearing_details: Detailed hearing data

        Returns:
            Dictionary with categorized documents
        """
        documents = {
            'transcripts': [],
            'witness_documents': [],
            'supporting_documents': []
        }

        # Extract transcript information
        transcripts = self._extract_transcripts(hearing_details)
        documents['transcripts'] = transcripts

        # Extract witness documents
        witness_docs = self._extract_witness_documents(hearing_details)
        documents['witness_documents'] = witness_docs

        # Extract supporting documents
        supporting_docs = self._extract_supporting_documents(hearing_details)
        documents['supporting_documents'] = supporting_docs

        return documents

    def _extract_transcripts(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract transcript documents"""
        transcripts = []

        # Check for transcript information
        transcript_sources = [
            'transcripts',
            'transcript',
            'hearingTranscript'
        ]

        for source in transcript_sources:
            transcript_data = self.safe_get(hearing_details, source)
            if transcript_data:
                if isinstance(transcript_data, list):
                    for transcript in transcript_data:
                        transcripts.append(self._normalize_transcript(transcript))
                elif isinstance(transcript_data, dict):
                    transcripts.append(self._normalize_transcript(transcript_data))
                break

        # Check for jacket number in main hearing data
        jacket_number = self.safe_get(hearing_details, 'jacketNumber')
        if jacket_number and not transcripts:
            # Create placeholder transcript record
            transcripts.append({
                'jacket_number': jacket_number,
                'title': self.safe_get(hearing_details, 'title'),
                'format_type': 'Unknown'
            })

        return transcripts

    def _extract_witness_documents(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract witness-related documents"""
        witness_docs = []

        # Check for witness document information
        witnesses = self.safe_get(hearing_details, 'witnesses', [])
        for witness in witnesses:
            documents = self.safe_get(witness, 'documents', [])
            for doc in documents:
                witness_doc = {
                    'witness_name': self.safe_get(witness, 'name'),
                    'document_type': self._normalize_document_type(self.safe_get(doc, 'type')),
                    'title': self.safe_get(doc, 'title'),
                    'document_url': self.safe_get(doc, 'url'),
                    'format_type': self.safe_get(doc, 'format', 'PDF')
                }
                witness_docs.append(witness_doc)

        return witness_docs

    def _extract_supporting_documents(self, hearing_details: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract supporting documents"""
        supporting_docs = []

        # Check for supporting document information
        doc_sources = [
            'documents',
            'supportingDocuments',
            'relatedDocuments'
        ]

        for source in doc_sources:
            doc_data = self.safe_get(hearing_details, source, [])
            if doc_data:
                for doc in doc_data:
                    # Skip witness-specific documents
                    if not self._is_witness_document(doc):
                        supporting_doc = {
                            'document_type': self._normalize_document_type(self.safe_get(doc, 'type')),
                            'title': self.safe_get(doc, 'title'),
                            'description': self.safe_get(doc, 'description'),
                            'document_url': self.safe_get(doc, 'url'),
                            'format_type': self.safe_get(doc, 'format', 'PDF')
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

    def _normalize_document_type(self, doc_type: str) -> str:
        """Normalize document type to standard categories"""
        if not doc_type:
            return 'Unknown'

        doc_type_lower = doc_type.lower()

        # Map to standard document types
        type_mapping = {
            'statement': 'Statement',
            'prepared statement': 'Statement',
            'written statement': 'Statement',
            'testimony': 'Statement',
            'biography': 'Biography',
            'bio': 'Biography',
            'biographical information': 'Biography',
            'truth statement': 'Truth Statement',
            'financial disclosure': 'Truth Statement',
            'questions for record': 'Questions for Record',
            'qfr': 'Questions for Record',
            'questions for the record': 'Questions for Record',
            'supplemental': 'Supplemental',
            'supplemental material': 'Supplemental',
            'additional material': 'Supplemental'
        }

        return type_mapping.get(doc_type_lower, doc_type)

    def _is_witness_document(self, document: Dict[str, Any]) -> bool:
        """Check if document is witness-specific"""
        doc_type = self.safe_get(document, 'type', '').lower()
        witness_types = ['statement', 'testimony', 'biography', 'truth statement']

        return any(wtype in doc_type for wtype in witness_types)

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