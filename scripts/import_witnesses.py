#!/usr/bin/env python3
"""
Import witness data from Congress.gov API for existing hearings
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
from typing import Dict, List, Any, Optional
from fetchers.witness_fetcher import WitnessFetcher
from parsers.witness_parser import WitnessParser
from database.manager import DatabaseManager
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class WitnessImporter:
    """Import witness data from Congress.gov API"""

    def __init__(self):
        self.db = DatabaseManager()
        self.witness_fetcher = WitnessFetcher()
        self.witness_parser = WitnessParser()

    def import_witnesses_for_congress(self, congress: int, limit: Optional[int] = None, batch_size: int = 10) -> Dict[str, Any]:
        """
        Import witnesses for all hearings in a specific congress

        Args:
            congress: Congress number to process
            limit: Maximum number of hearings to process
            batch_size: Number of hearings to process per batch

        Returns:
            Import statistics
        """
        logger.info(f"Starting witness import for Congress {congress}")

        stats = {
            'hearings_processed': 0,
            'hearings_with_witnesses': 0,
            'witnesses_imported': 0,
            'witness_appearances_created': 0,
            'duplicate_witnesses_found': 0,
            'errors': 0
        }

        try:
            # Get hearings from database
            hearings = self._get_hearings_for_import(congress, limit)

            if not hearings:
                logger.warning(f"No hearings found for Congress {congress}")
                return stats

            logger.info(f"Found {len(hearings)} hearings to process")

            # Process in batches to respect rate limits
            for i in range(0, len(hearings), batch_size):
                batch = hearings[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}: hearings {i+1}-{min(i+batch_size, len(hearings))}")

                batch_stats = self._process_hearing_batch(batch)

                # Update overall stats
                for key in stats:
                    if key in batch_stats:
                        stats[key] += batch_stats[key]

                logger.info(f"Batch completed. Total progress: {stats['hearings_processed']}/{len(hearings)} hearings")

        except Exception as e:
            logger.error(f"Error during witness import: {e}")
            stats['errors'] += 1

        logger.info(f"Witness import completed. Statistics: {stats}")
        return stats

    def _get_hearings_for_import(self, congress: int, limit: Optional[int] = None) -> List[tuple]:
        """Get hearings that need witness data import"""

        try:
            with self.db.transaction() as conn:
                query = '''
                    SELECT h.hearing_id, h.event_id, h.congress, h.chamber, h.title
                    FROM hearings h
                    WHERE h.congress = ?
                    AND h.event_id IS NOT NULL
                    AND h.event_id != ''
                    AND NOT EXISTS (
                        SELECT 1 FROM witness_appearances wa
                        WHERE wa.hearing_id = h.hearing_id
                    )
                    ORDER BY h.hearing_date_only DESC
                '''
                params = [congress]

                if limit:
                    query += ' LIMIT ?'
                    params.append(limit)

                cursor = conn.execute(query, params)
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error querying hearings for import: {e}")
            return []

    def _process_hearing_batch(self, hearings: List[tuple]) -> Dict[str, int]:
        """Process a batch of hearings for witness import"""

        batch_stats = {
            'hearings_processed': 0,
            'hearings_with_witnesses': 0,
            'witnesses_imported': 0,
            'witness_appearances_created': 0,
            'duplicate_witnesses_found': 0,
            'errors': 0
        }

        # Prepare hearing specs for fetcher
        hearing_specs = [(int(h[2]), h[3].lower(), h[1]) for h in hearings]

        try:
            # Fetch witness data for all hearings in batch
            witnesses_data = self.witness_fetcher.fetch_witnesses_for_multiple_hearings(hearing_specs)

            # Process each hearing
            for hearing in hearings:
                hearing_id, event_id, congress, chamber, title = hearing

                try:
                    # Get witness data for this hearing
                    if event_id in witnesses_data:
                        witnesses, witness_docs = witnesses_data[event_id]

                        if witnesses:
                            batch_stats['hearings_with_witnesses'] += 1

                            # Import witnesses for this hearing
                            hearing_stats = self._import_witnesses_for_hearing(
                                hearing_id, event_id, witnesses
                            )

                            batch_stats['witnesses_imported'] += hearing_stats['witnesses_imported']
                            batch_stats['witness_appearances_created'] += hearing_stats['appearances_created']
                            batch_stats['duplicate_witnesses_found'] += hearing_stats['duplicates_found']

                            logger.debug(f"Imported {len(witnesses)} witnesses for hearing {event_id}")

                    batch_stats['hearings_processed'] += 1

                except Exception as e:
                    logger.error(f"Error processing hearing {event_id}: {e}")
                    batch_stats['errors'] += 1

        except Exception as e:
            logger.error(f"Error processing hearing batch: {e}")
            batch_stats['errors'] += 1

        return batch_stats

    def _import_witnesses_for_hearing(self, hearing_id: int, event_id: str, witnesses: List[Dict[str, Any]]) -> Dict[str, int]:
        """Import witnesses for a specific hearing"""

        stats = {
            'witnesses_imported': 0,
            'appearances_created': 0,
            'duplicates_found': 0
        }

        try:
            with self.db.transaction() as conn:
                # Get existing witnesses for deduplication
                cursor = conn.execute('SELECT witness_id, full_name, organization FROM witnesses')
                existing_witnesses = cursor.fetchall()

                for order, witness_data in enumerate(witnesses, 1):
                    try:
                        # Extract and normalize witness information
                        normalized_witness = self.witness_fetcher.extract_witness_info(witness_data)

                        # Create raw data dict for parser (parser expects different field names)
                        raw_witness_data = {
                            'name': normalized_witness.get('full_name'),
                            'firstName': normalized_witness.get('first_name'),
                            'lastName': normalized_witness.get('last_name'),
                            'position': normalized_witness.get('title'),
                            'organization': normalized_witness.get('organization')
                        }

                        # Parse witness data using the parser
                        witness_model = self.witness_parser.parse(raw_witness_data)

                        if not witness_model:
                            logger.warning(f"Failed to parse witness data for hearing {event_id}")
                            continue

                        # Check for duplicate witness
                        witness_dict = witness_model.model_dump()
                        existing_witness_id = self.witness_parser.deduplicate_witness(
                            witness_dict,
                            [{'witness_id': w[0], 'full_name': w[1], 'organization': w[2]} for w in existing_witnesses]
                        )

                        if existing_witness_id:
                            witness_id = existing_witness_id
                            stats['duplicates_found'] += 1
                            logger.debug(f"Found duplicate witness: {witness_dict['full_name']}")
                        else:
                            # Insert new witness
                            witness_insert = '''
                                INSERT INTO witnesses (full_name, first_name, last_name, title, organization)
                                VALUES (?, ?, ?, ?, ?)
                            '''
                            cursor = conn.execute(witness_insert, (
                                witness_dict['full_name'],
                                witness_dict['first_name'],
                                witness_dict['last_name'],
                                witness_dict['title'],
                                witness_dict['organization']
                            ))
                            witness_id = cursor.lastrowid
                            stats['witnesses_imported'] += 1

                            # Add to existing list for future deduplication in this batch
                            existing_witnesses.append((witness_id, witness_dict['full_name'], witness_dict['organization']))

                        # Create witness appearance
                        witness_type = self.witness_fetcher.infer_witness_type(witness_data)

                        appearance_insert = '''
                            INSERT INTO witness_appearances
                            (witness_id, hearing_id, position, witness_type, appearance_order)
                            VALUES (?, ?, ?, ?, ?)
                        '''
                        conn.execute(appearance_insert, (
                            witness_id,
                            hearing_id,
                            normalized_witness.get('title'),
                            witness_type,
                            order
                        ))
                        stats['appearances_created'] += 1

                    except Exception as e:
                        logger.error(f"Error importing witness for hearing {event_id}: {e}")

        except Exception as e:
            logger.error(f"Error in database transaction for hearing {event_id}: {e}")

        return stats

    def get_import_status(self, congress: Optional[int] = None) -> Dict[str, Any]:
        """Get current import status for witness data"""

        try:
            with self.db.transaction() as conn:
                status = {}

                # Total hearings
                query = 'SELECT COUNT(*) FROM hearings'
                params = []
                if congress:
                    query += ' WHERE congress = ?'
                    params.append(congress)

                cursor = conn.execute(query, params)
                status['total_hearings'] = cursor.fetchone()[0]

                # Hearings with event IDs
                query = 'SELECT COUNT(*) FROM hearings WHERE event_id IS NOT NULL AND event_id != ""'
                if congress:
                    query += ' AND congress = ?'

                cursor = conn.execute(query, params)
                status['hearings_with_event_ids'] = cursor.fetchone()[0]

                # Hearings with witnesses
                query = '''
                    SELECT COUNT(DISTINCT h.hearing_id)
                    FROM hearings h
                    JOIN witness_appearances wa ON h.hearing_id = wa.hearing_id
                '''
                if congress:
                    query += ' WHERE h.congress = ?'

                cursor = conn.execute(query, params)
                status['hearings_with_witnesses'] = cursor.fetchone()[0]

                # Total witnesses and appearances
                cursor = conn.execute('SELECT COUNT(*) FROM witnesses')
                status['total_witnesses'] = cursor.fetchone()[0]

                cursor = conn.execute('SELECT COUNT(*) FROM witness_appearances')
                status['total_witness_appearances'] = cursor.fetchone()[0]

                # Witness types breakdown
                cursor = conn.execute('''
                    SELECT witness_type, COUNT(*)
                    FROM witness_appearances
                    WHERE witness_type IS NOT NULL
                    GROUP BY witness_type
                    ORDER BY COUNT(*) DESC
                ''')
                status['witness_types'] = dict(cursor.fetchall())

                return status

        except Exception as e:
            logger.error(f"Error getting import status: {e}")
            return {}

def main():
    """Main import function"""
    parser = argparse.ArgumentParser(description='Import witness data from Congress.gov API')
    parser.add_argument('--congress', type=int, default=119, help='Congress number (default: 119)')
    parser.add_argument('--limit', type=int, help='Limit number of hearings to process')
    parser.add_argument('--batch-size', type=int, default=10, help='Batch size for processing (default: 10)')
    parser.add_argument('--status', action='store_true', help='Show current import status only')

    args = parser.parse_args()

    # Initialize importer
    importer = WitnessImporter()

    if args.status:
        # Show status only
        status = importer.get_import_status(args.congress)
        print(f"\n=== Witness Import Status (Congress {args.congress if args.congress else 'All'}) ===")
        print(f"Total hearings: {status.get('total_hearings', 0)}")
        print(f"Hearings with event IDs: {status.get('hearings_with_event_ids', 0)}")
        print(f"Hearings with witnesses: {status.get('hearings_with_witnesses', 0)}")
        print(f"Total witnesses: {status.get('total_witnesses', 0)}")
        print(f"Total witness appearances: {status.get('total_witness_appearances', 0)}")

        if status.get('witness_types'):
            print(f"\nWitness types:")
            for witness_type, count in status['witness_types'].items():
                print(f"  {witness_type}: {count}")
    else:
        # Run import
        print(f"Starting witness import for Congress {args.congress}")
        if args.limit:
            print(f"Processing limit: {args.limit} hearings")
        print(f"Batch size: {args.batch_size}")
        print()

        stats = importer.import_witnesses_for_congress(
            congress=args.congress,
            limit=args.limit,
            batch_size=args.batch_size
        )

        print(f"\n=== Import Complete ===")
        print(f"Hearings processed: {stats['hearings_processed']}")
        print(f"Hearings with witnesses: {stats['hearings_with_witnesses']}")
        print(f"New witnesses imported: {stats['witnesses_imported']}")
        print(f"Witness appearances created: {stats['witness_appearances_created']}")
        print(f"Duplicate witnesses found: {stats['duplicate_witnesses_found']}")
        if stats['errors']:
            print(f"Errors encountered: {stats['errors']}")

if __name__ == '__main__':
    main()