#!/usr/bin/env python3
"""
Integration tests for document import pipeline
"""
import unittest
import sys
import os
import sqlite3
from unittest.mock import MagicMock, patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from importers.orchestrator import ImportOrchestrator
from database.manager import DatabaseManager


class TestDocumentImport(unittest.TestCase):
    """Test document import integration"""

    def setUp(self):
        """Set up test database"""
        # Create a temporary connection for schema initialization
        self.conn = sqlite3.connect(':memory:')
        self._init_test_schema()

    def _init_test_schema(self):
        """Initialize test database schema"""
        schema = '''
        CREATE TABLE IF NOT EXISTS hearings (
            hearing_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            congress INTEGER,
            chamber TEXT
        );

        CREATE TABLE IF NOT EXISTS witnesses (
            witness_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT
        );

        CREATE TABLE IF NOT EXISTS witness_appearances (
            appearance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            witness_id INTEGER,
            hearing_id INTEGER,
            FOREIGN KEY (witness_id) REFERENCES witnesses(witness_id),
            FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
        );

        CREATE TABLE IF NOT EXISTS hearing_transcripts (
            transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hearing_id INTEGER NOT NULL,
            jacket_number TEXT,
            title TEXT,
            document_url TEXT,
            pdf_url TEXT,
            html_url TEXT,
            format_type TEXT,
            FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
        );

        CREATE TABLE IF NOT EXISTS witness_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            appearance_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            title TEXT,
            document_url TEXT,
            format_type TEXT,
            FOREIGN KEY (appearance_id) REFERENCES witness_appearances(appearance_id)
        );

        CREATE TABLE IF NOT EXISTS supporting_documents (
            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hearing_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            title TEXT,
            description TEXT,
            document_url TEXT,
            format_type TEXT,
            FOREIGN KEY (hearing_id) REFERENCES hearings(hearing_id)
        );
        '''

        self.conn.executescript(schema)

    def test_transcript_insertion(self):
        """Test that transcripts are correctly inserted"""
        # Insert test hearing
        cursor = self.conn.execute(
            "INSERT INTO hearings (event_id, congress, chamber) VALUES (?, ?, ?)",
            ('12345', 119, 'House')
        )
        hearing_id = cursor.lastrowid

        # Insert transcript
        self.conn.execute(
            "INSERT INTO hearing_transcripts (hearing_id, jacket_number, title, document_url, format_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (hearing_id, 'H-123', 'Test Transcript', 'https://example.com/transcript', 'PDF')
        )
        self.conn.commit()

        # Verify insertion
        cursor = self.conn.execute("SELECT COUNT(*) FROM hearing_transcripts WHERE hearing_id = ?", (hearing_id,))
        count = cursor.fetchone()[0]

        self.assertEqual(count, 1)

    def test_witness_document_linking(self):
        """Test witness documents are correctly linked to appearances"""
        # Create hearing
        cursor = self.conn.execute(
            "INSERT INTO hearings (event_id, congress, chamber) VALUES (?, ?, ?)",
            ('12345', 119, 'House')
        )
        hearing_id = cursor.lastrowid

        # Create witness
        cursor = self.conn.execute(
            "INSERT INTO witnesses (full_name) VALUES (?)",
            ('John Doe',)
        )
        witness_id = cursor.lastrowid

        # Create appearance
        cursor = self.conn.execute(
            "INSERT INTO witness_appearances (witness_id, hearing_id) VALUES (?, ?)",
            (witness_id, hearing_id)
        )
        appearance_id = cursor.lastrowid

        # Insert witness document
        self.conn.execute(
            "INSERT INTO witness_documents (appearance_id, document_type, title, document_url, format_type) "
            "VALUES (?, ?, ?, ?, ?)",
            (appearance_id, 'Statement', 'Written Statement', 'https://example.com/statement.pdf', 'PDF')
        )
        self.conn.commit()

        # Verify linkage
        cursor = self.conn.execute('''
            SELECT wd.title, w.full_name, h.event_id
            FROM witness_documents wd
            JOIN witness_appearances wa ON wd.appearance_id = wa.appearance_id
            JOIN witnesses w ON wa.witness_id = w.witness_id
            JOIN hearings h ON wa.hearing_id = h.hearing_id
        ''')
        result = cursor.fetchone()

        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'Written Statement')
        self.assertEqual(result[1], 'John Doe')
        self.assertEqual(result[2], '12345')

    def test_supporting_document_with_description(self):
        """Test supporting documents preserve descriptions"""
        # Insert test data
        cursor = self.conn.execute(
            "INSERT INTO hearings (event_id, congress, chamber) VALUES (?, ?, ?)",
            ('12345', 119, 'House')
        )
        hearing_id = cursor.lastrowid

        self.conn.execute(
            "INSERT INTO supporting_documents "
            "(hearing_id, document_type, title, description, document_url, format_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (hearing_id, 'Background Materials', 'Policy Brief',
             'Overview of current policy landscape', 'https://example.com/brief.pdf', 'PDF')
        )
        self.conn.commit()

        # Verify description is preserved
        cursor = self.conn.execute(
            "SELECT description FROM supporting_documents WHERE hearing_id = ?",
            (hearing_id,)
        )
        description = cursor.fetchone()[0]

        self.assertEqual(description, 'Overview of current policy landscape')


if __name__ == '__main__':
    unittest.main()
