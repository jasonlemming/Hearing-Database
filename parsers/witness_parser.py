"""
Witness data parser
"""
from typing import Dict, Any, Optional, List
from parsers.base_parser import BaseParser
from parsers.models import WitnessModel, WitnessAppearanceModel
from config.logging_config import get_logger

logger = get_logger(__name__)


class WitnessParser(BaseParser):
    """Parser for witness data from Congress.gov API"""

    def parse(self, raw_data: Dict[str, Any]) -> Optional[WitnessModel]:
        """
        Parse raw witness data into validated model

        Args:
            raw_data: Raw witness data from API

        Returns:
            Validated WitnessModel or None
        """
        # Extract name components
        name_data = self._parse_name(raw_data)

        # Check if we have enough data for a witness
        if not name_data['full_name']:
            self.collect_error('validation', 'No witness name found', 'warning')
            if self.strict_mode:
                return None

        # Extract and normalize data
        witness_data = {
            'first_name': name_data['first_name'],
            'last_name': name_data['last_name'],
            'full_name': name_data['full_name'],
            'title': self._extract_title(raw_data),
            'organization': self._extract_organization(raw_data)
        }

        return self.validate_model(WitnessModel, witness_data)

    def parse_appearance(self, raw_data: Dict[str, Any], witness_id: int, hearing_id: int, order: int = None) -> Optional[WitnessAppearanceModel]:
        """
        Parse witness appearance data

        Args:
            raw_data: Raw witness appearance data
            witness_id: Witness ID
            hearing_id: Hearing ID
            order: Appearance order

        Returns:
            Validated WitnessAppearanceModel or None
        """
        appearance_data = {
            'witness_id': witness_id,
            'hearing_id': hearing_id,
            'position': self._extract_position(raw_data),
            'witness_type': self._extract_witness_type(raw_data),
            'appearance_order': order
        }

        return self.validate_model(WitnessAppearanceModel, appearance_data)

    def _parse_name(self, raw_data: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """
        Parse witness name components

        Args:
            raw_data: Raw witness data

        Returns:
            Dictionary with name components
        """
        # Try to get individual name components
        first_name = self.safe_get(raw_data, 'firstName')
        last_name = self.safe_get(raw_data, 'lastName')
        full_name = self.safe_get(raw_data, 'name') or self.safe_get(raw_data, 'fullName')

        # If we have full name but missing components, try to parse
        if full_name and not (first_name and last_name):
            parsed = self._parse_full_name(full_name)
            first_name = first_name or parsed['first_name']
            last_name = last_name or parsed['last_name']

        # Build full name if not provided
        if not full_name and (first_name or last_name):
            name_parts = [first_name, last_name]
            full_name = ' '.join(part for part in name_parts if part)

        return {
            'first_name': self.normalize_text(first_name) if first_name else None,
            'last_name': self.normalize_text(last_name) if last_name else None,
            'full_name': self.normalize_text(full_name) if full_name else ''
        }

    def _parse_full_name(self, full_name: str) -> Dict[str, Optional[str]]:
        """
        Parse full name into first and last name

        Args:
            full_name: Full name string

        Returns:
            Dictionary with first_name and last_name
        """
        if not full_name:
            return {'first_name': None, 'last_name': None}

        parts = full_name.strip().split()

        if len(parts) == 0:
            return {'first_name': None, 'last_name': None}
        elif len(parts) == 1:
            return {'first_name': parts[0], 'last_name': None}
        else:
            # Take first word as first name, rest as last name
            return {
                'first_name': parts[0],
                'last_name': ' '.join(parts[1:])
            }

    def _extract_title(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract witness professional title"""
        title_fields = [
            'title',
            'professionalTitle',
            'jobTitle',
            'position'
        ]

        for field in title_fields:
            title = self.safe_get(raw_data, field)
            if title:
                return self.normalize_text(title)

        return None

    def _extract_organization(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract witness organization"""
        org_fields = [
            'organization',
            'org',
            'company',
            'institution',
            'agency',
            'affiliation'
        ]

        for field in org_fields:
            org = self.safe_get(raw_data, field)
            if org:
                return self.normalize_text(org)

        return None

    def _extract_position(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract witness position at time of testimony"""
        position_fields = [
            'position',
            'currentPosition',
            'jobTitle',
            'role'
        ]

        for field in position_fields:
            position = self.safe_get(raw_data, field)
            if position:
                return self.normalize_text(position)

        return None

    def _extract_witness_type(self, raw_data: Dict[str, Any]) -> Optional[str]:
        """Extract witness type classification"""
        witness_type = self.safe_get(raw_data, 'type') or self.safe_get(raw_data, 'witnessType')

        if witness_type:
            return self._normalize_witness_type(witness_type)

        # Try to infer from organization
        organization = self._extract_organization(raw_data)
        if organization:
            return self._infer_witness_type_from_org(organization)

        return None

    def _normalize_witness_type(self, witness_type: str) -> str:
        """Normalize witness type to standard categories"""
        type_mapping = {
            'government': 'Government',
            'federal': 'Government',
            'private': 'Private',
            'industry': 'Private',
            'business': 'Private',
            'academic': 'Academic',
            'university': 'Academic',
            'research': 'Academic',
            'nonprofit': 'Nonprofit',
            'ngo': 'Nonprofit',
            'advocacy': 'Advocacy',
            'expert': 'Expert',
            'professional': 'Professional'
        }

        normalized = type_mapping.get(witness_type.lower(), witness_type)
        return normalized

    def _infer_witness_type_from_org(self, organization: str) -> str:
        """Infer witness type from organization name"""
        org_lower = organization.lower()

        # Government indicators
        gov_indicators = [
            'department of', 'agency', 'bureau', 'office of',
            'administration', 'commission', 'federal', 'u.s.',
            'united states', 'government'
        ]
        if any(indicator in org_lower for indicator in gov_indicators):
            return 'Government'

        # Academic indicators
        academic_indicators = [
            'university', 'college', 'institute', 'school',
            'research', 'academic'
        ]
        if any(indicator in org_lower for indicator in academic_indicators):
            return 'Academic'

        # Nonprofit indicators
        nonprofit_indicators = [
            'foundation', 'association', 'society', 'council',
            'coalition', 'alliance', 'nonprofit', 'non-profit'
        ]
        if any(indicator in org_lower for indicator in nonprofit_indicators):
            return 'Nonprofit'

        # Default to private sector
        return 'Private'

    def extract_witness_documents(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract witness document information

        Args:
            raw_data: Raw witness data

        Returns:
            List of document data
        """
        documents = []

        # Check for document information
        doc_sources = [
            'documents',
            'testimony',
            'statements',
            'materials'
        ]

        for source in doc_sources:
            doc_data = self.safe_get(raw_data, source, [])
            if doc_data:
                for doc in doc_data:
                    document = {
                        'document_type': self._normalize_document_type(self.safe_get(doc, 'type')),
                        'title': self.normalize_text(self.safe_get(doc, 'title')),
                        'document_url': self.safe_get(doc, 'url'),
                        'format_type': self.safe_get(doc, 'format', 'PDF')
                    }
                    documents.append(document)
                break

        return documents

    def _normalize_document_type(self, doc_type: str) -> str:
        """Normalize document type"""
        if not doc_type:
            return 'Statement'

        type_mapping = {
            'statement': 'Statement',
            'prepared statement': 'Statement',
            'written statement': 'Statement',
            'testimony': 'Statement',
            'biography': 'Biography',
            'bio': 'Biography',
            'truth statement': 'Truth Statement',
            'financial disclosure': 'Truth Statement',
            'questions for record': 'Questions for Record',
            'qfr': 'Questions for Record',
            'supplemental': 'Supplemental'
        }

        return type_mapping.get(doc_type.lower(), doc_type)

    def deduplicate_witness(self, witness_data: Dict[str, Any], existing_witnesses: List[Dict[str, Any]]) -> Optional[int]:
        """
        Check if witness already exists and return ID if found

        Args:
            witness_data: New witness data
            existing_witnesses: List of existing witness records

        Returns:
            Existing witness ID if found, None otherwise
        """
        full_name = (witness_data.get('full_name') or '').strip().lower()
        organization = (witness_data.get('organization') or '').strip().lower()

        for existing in existing_witnesses:
            existing_name = (existing.get('full_name') or '').strip().lower()
            existing_org = (existing.get('organization') or '').strip().lower()

            # Match on name and organization
            if full_name == existing_name and organization == existing_org:
                return existing.get('witness_id')

            # Match on name only if organizations are both empty
            if full_name == existing_name and not organization and not existing_org:
                return existing.get('witness_id')

        return None