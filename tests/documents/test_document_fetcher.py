#!/usr/bin/env python3
"""
Unit tests for DocumentFetcher parsing logic
"""
import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fetchers.document_fetcher import DocumentFetcher
from api.client import CongressAPIClient


class TestDocumentFetcher(unittest.TestCase):
    """Test DocumentFetcher parsing methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.api_client = CongressAPIClient()
        self.fetcher = DocumentFetcher(self.api_client)

    def test_extract_transcripts_from_list(self):
        """Test extracting transcripts from list format"""
        hearing_details = {
            'transcripts': [
                {
                    'jacketNumber': '12345',
                    'title': 'Hearing Transcript',
                    'url': 'https://example.com/transcript',
                    'pdfUrl': 'https://example.com/transcript.pdf',
                    'format': 'PDF'
                }
            ]
        }

        documents = self.fetcher.extract_hearing_documents(hearing_details)
        self.assertEqual(len(documents['transcripts']), 1)
        self.assertEqual(documents['transcripts'][0]['jacket_number'], '12345')
        self.assertEqual(documents['transcripts'][0]['title'], 'Hearing Transcript')

    def test_extract_witness_documents(self):
        """Test extracting witness documents with metadata"""
        hearing_details = {
            'witnesses': [
                {
                    'name': 'John Doe',
                    'position': 'Director',
                    'organization': 'Test Organization',
                    'documents': [
                        {
                            'type': 'Statement',
                            'title': 'Written Statement',
                            'url': 'https://example.com/statement.pdf',
                            'format': 'PDF'
                        },
                        {
                            'type': 'Biography',
                            'title': 'Biographical Information',
                            'url': 'https://example.com/bio.pdf'
                        }
                    ]
                }
            ]
        }

        documents = self.fetcher.extract_hearing_documents(hearing_details)
        self.assertEqual(len(documents['witness_documents']), 2)

        # Check first document
        doc1 = documents['witness_documents'][0]
        self.assertEqual(doc1['witness_name'], 'John Doe')
        self.assertEqual(doc1['witness_title'], 'Director')
        self.assertEqual(doc1['witness_organization'], 'Test Organization')
        self.assertEqual(doc1['document_type'], 'Statement')
        self.assertEqual(doc1['title'], 'Written Statement')

    def test_extract_supporting_documents_with_descriptions(self):
        """Test extracting supporting documents including descriptions"""
        hearing_details = {
            'supportingDocuments': [
                {
                    'type': 'Committee Rules',
                    'title': 'Committee Operating Rules',
                    'description': 'Rules for committee operation',
                    'url': 'https://example.com/rules.pdf',
                    'format': 'PDF'
                }
            ]
        }

        documents = self.fetcher.extract_hearing_documents(hearing_details)
        self.assertEqual(len(documents['supporting_documents']), 1)

        doc = documents['supporting_documents'][0]
        self.assertEqual(doc['document_type'], 'Committee Rules')
        self.assertEqual(doc['title'], 'Committee Operating Rules')
        self.assertEqual(doc['description'], 'Rules for committee operation')

    def test_normalize_document_types(self):
        """Test document type normalization"""
        test_cases = [
            ('prepared statement', 'Statement'),
            ('written statement', 'Statement'),
            ('testimony', 'Statement'),
            ('bio', 'Biography'),
            ('qfr', 'Questions for Record'),
            ('supplemental material', 'Supplemental'),
        ]

        for input_type, expected_output in test_cases:
            result = self.fetcher._normalize_document_type(input_type)
            self.assertEqual(result, expected_output,
                           f"Failed to normalize '{input_type}' to '{expected_output}'")

    def test_normalize_supporting_document_types(self):
        """Test supporting document type normalization"""
        test_cases = [
            ('committee rules', 'Committee Rules'),
            ('member statement', 'Member Statements'),
            ('background material', 'Background Materials'),
            ('memorandum', 'Memorandum'),
        ]

        for input_type, expected_output in test_cases:
            result = self.fetcher._normalize_supporting_document_type(input_type)
            self.assertEqual(result, expected_output,
                           f"Failed to normalize '{input_type}' to '{expected_output}'")

    def test_guess_format_from_url(self):
        """Test format guessing from URLs"""
        test_cases = [
            ('https://example.com/doc.pdf', 'PDF'),
            ('https://example.com/page.html', 'HTML'),
            ('https://example.com/file.txt', 'Text'),
            ('https://example.com/doc.docx', 'Word'),
            ('https://example.com/unknown', 'PDF'),  # Default
        ]

        for url, expected_format in test_cases:
            result = self.fetcher._guess_format_from_url(url)
            self.assertEqual(result, expected_format,
                           f"Failed to guess format for '{url}'")

    def test_empty_hearing_details(self):
        """Test handling empty hearing details"""
        hearing_details = {}
        documents = self.fetcher.extract_hearing_documents(hearing_details)

        self.assertEqual(len(documents['transcripts']), 0)
        self.assertEqual(len(documents['witness_documents']), 0)
        self.assertEqual(len(documents['supporting_documents']), 0)

    def test_fallback_jacket_number(self):
        """Test jacket number fallback when no transcripts array"""
        hearing_details = {
            'jacketNumber': '54321',
            'title': 'Test Hearing',
            'url': 'https://example.com/hearing'
        }

        documents = self.fetcher.extract_hearing_documents(hearing_details)
        self.assertEqual(len(documents['transcripts']), 1)
        self.assertEqual(documents['transcripts'][0]['jacket_number'], '54321')


if __name__ == '__main__':
    unittest.main()
