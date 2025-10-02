"""
Import orchestrator for managing the overall import process
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from database.manager import DatabaseManager
from api.client import CongressAPIClient
from fetchers.committee_fetcher import CommitteeFetcher
from fetchers.member_fetcher import MemberFetcher
from fetchers.hearing_fetcher import HearingFetcher
from fetchers.bill_fetcher import BillFetcher
from fetchers.document_fetcher import DocumentFetcher
from parsers.committee_parser import CommitteeParser
from parsers.member_parser import MemberParser
from parsers.hearing_parser import HearingParser
from parsers.witness_parser import WitnessParser
from config.logging_config import get_logger

logger = get_logger(__name__)


class ImportOrchestrator:
    """Manages the overall import process with checkpointing and progress tracking"""

    def __init__(self, db_manager: DatabaseManager, api_client: CongressAPIClient):
        """
        Initialize import orchestrator

        Args:
            db_manager: Database manager instance
            api_client: API client instance
        """
        self.db_manager = db_manager
        self.api_client = api_client

        # Initialize fetchers
        self.committee_fetcher = CommitteeFetcher(api_client)
        self.member_fetcher = MemberFetcher(api_client)
        self.hearing_fetcher = HearingFetcher(api_client)
        self.bill_fetcher = BillFetcher(api_client)
        self.document_fetcher = DocumentFetcher(api_client)

        # Initialize parsers (use lenient mode for better data capture)
        self.committee_parser = CommitteeParser(strict_mode=False)
        self.member_parser = MemberParser(strict_mode=False)
        self.hearing_parser = HearingParser(strict_mode=False)
        self.witness_parser = WitnessParser(strict_mode=False)

    def run_full_import(self, congress: int, validation_mode: bool = False, batch_size: int = 50) -> Dict[str, Any]:
        """
        Run complete import process

        Args:
            congress: Congress number
            validation_mode: If True, validate but don't write to database
            batch_size: Batch size for processing

        Returns:
            Dictionary with import statistics
        """
        results = {}

        try:
            # Phase 1: Import committees
            logger.info("Phase 1: Importing committees...")
            results['committees'] = self.import_committees(congress, validation_mode)
            if not validation_mode:
                self.create_checkpoint('committees', 'success')

            # Phase 2: Import members
            logger.info("Phase 2: Importing members...")
            results['members'] = self.import_members(congress, validation_mode)
            if not validation_mode:
                self.create_checkpoint('members', 'success')

            # Phase 3: Import hearings
            logger.info("Phase 3: Importing hearings...")
            results['hearings'] = self.import_hearings(congress, validation_mode, batch_size)
            if not validation_mode:
                self.create_checkpoint('hearings', 'success')

            # Phase 4: Import bills (from hearing references)
            logger.info("Phase 4: Importing bills...")
            results['bills'] = self.import_bills_from_hearings(congress, validation_mode)
            if not validation_mode:
                self.create_checkpoint('bills', 'success')

            # Phase 5: Import documents and witnesses
            logger.info("Phase 5: Importing documents and witnesses...")
            hearing_ids = self._get_all_hearing_ids()
            results['documents'] = self.import_documents(hearing_ids[:100], validation_mode)  # Limit for initial run
            if not validation_mode:
                self.create_checkpoint('documents', 'success')

            logger.info("Full import completed successfully")
            return results

        except Exception as e:
            logger.error(f"Import failed during full import: {e}")
            raise

    def import_committees(self, congress: int, validation_mode: bool = False) -> Dict[str, int]:
        """
        Import committees for specified congress

        Args:
            congress: Congress number
            validation_mode: If True, validate but don't write

        Returns:
            Import statistics
        """
        stats = {'processed': 0, 'imported': 0, 'errors': 0}

        try:
            # Fetch all committees
            committees = self.committee_fetcher.fetch_all_committees(congress)
            stats['processed'] = len(committees)

            for committee_data in committees:
                try:
                    # Parse committee data
                    committee = self.committee_parser.parse(committee_data)
                    if committee:
                        if not validation_mode:
                            # Import to database
                            committee_dict = committee.dict()
                            committee_dict['congress'] = congress
                            committee_id = self.db_manager.upsert_committee(committee_dict)

                            # Handle roster if available
                            roster = self.committee_fetcher.extract_committee_roster(committee_data)
                            if roster:
                                self._import_committee_roster(roster, committee_id, congress)

                        stats['imported'] += 1
                    else:
                        stats['errors'] += 1

                except Exception as e:
                    logger.error(f"Error importing committee {committee_data.get('systemCode', 'unknown')}: {e}")
                    stats['errors'] += 1

            logger.info(f"Committee import: {stats['imported']}/{stats['processed']} successful")
            return stats

        except Exception as e:
            logger.error(f"Committee import failed: {e}")
            raise

    def import_members(self, congress: int, validation_mode: bool = False) -> Dict[str, int]:
        """
        Import members for specified congress

        Args:
            congress: Congress number
            validation_mode: If True, validate but don't write

        Returns:
            Import statistics
        """
        stats = {'processed': 0, 'imported': 0, 'errors': 0}

        try:
            # Fetch all current members
            members = self.member_fetcher.fetch_current_members(congress)
            stats['processed'] = len(members)

            for member_data in members:
                try:
                    # Parse member data
                    member = self.member_parser.parse(member_data)
                    if member:
                        if not validation_mode:
                            # Import to database
                            member_dict = member.dict()
                            # Ensure congress is set correctly
                            member_dict['congress'] = congress
                            member_id = self.db_manager.upsert_member(member_dict)

                            # Handle leadership positions
                            leadership = self.member_parser.extract_leadership_positions(member_data)
                            for position in leadership:
                                self.db_manager.execute(
                                    "INSERT OR REPLACE INTO member_leadership_positions (member_id, title, congress, is_current) VALUES (?, ?, ?, ?)",
                                    (member_id, position['title'], position['congress'], position['is_current'])
                                )

                        stats['imported'] += 1
                    else:
                        stats['errors'] += 1

                except Exception as e:
                    logger.error(f"Error importing member {member_data.get('bioguideId', 'unknown')}: {e}")
                    stats['errors'] += 1

            logger.info(f"Member import: {stats['imported']}/{stats['processed']} successful")
            return stats

        except Exception as e:
            logger.error(f"Member import failed: {e}")
            raise

    def import_hearings(self, congress: int, validation_mode: bool = False, batch_size: int = 50) -> Dict[str, int]:
        """
        Import hearings for specified congress

        Args:
            congress: Congress number
            validation_mode: If True, validate but don't write
            batch_size: Batch size for processing

        Returns:
            Import statistics
        """
        stats = {'processed': 0, 'imported': 0, 'errors': 0}

        try:
            # Fetch all hearings
            hearings = self.hearing_fetcher.fetch_hearings(congress)
            stats['processed'] = len(hearings)

            # Process in batches
            for i in range(0, len(hearings), batch_size):
                batch = hearings[i:i + batch_size]
                batch_stats = self._process_hearing_batch(batch, congress, validation_mode)

                stats['imported'] += batch_stats['imported']
                stats['errors'] += batch_stats['errors']

                logger.info(f"Processed hearing batch {i//batch_size + 1}: {batch_stats['imported']}/{len(batch)} successful")

            logger.info(f"Hearing import: {stats['imported']}/{stats['processed']} successful")
            return stats

        except Exception as e:
            logger.error(f"Hearing import failed: {e}")
            raise

    def import_bills_from_hearings(self, congress: int, validation_mode: bool = False) -> Dict[str, int]:
        """
        Import bills referenced in hearings

        Args:
            congress: Congress number
            validation_mode: If True, validate but don't write

        Returns:
            Import statistics
        """
        stats = {'processed': 0, 'imported': 0, 'errors': 0}

        try:
            # Get all hearing-bill relationships that need bill details
            if not validation_mode:
                with self.db_manager.transaction() as conn:
                    cursor = conn.execute(
                        "SELECT DISTINCT hb.bill_id, b.congress, b.bill_type, b.bill_number "
                        "FROM hearing_bills hb "
                        "JOIN bills b ON hb.bill_id = b.bill_id "
                        "WHERE b.title IS NULL OR b.title = ''"
                    )
                    hearing_bills = cursor.fetchall()

                for hb in hearing_bills:
                    try:
                        # Fetch bill details
                        bill_details = self.bill_fetcher.fetch_bill_details(
                            hb[1], hb[2], hb[3]  # congress, bill_type, bill_number
                        )

                        if bill_details and 'bill' in bill_details:
                            bill_data = bill_details['bill']
                            # Update bill record with details
                            self.db_manager.execute(
                                "UPDATE bills SET title = ?, url = ?, introduced_date = ?, updated_at = CURRENT_TIMESTAMP "
                                "WHERE bill_id = ?",
                                (
                                    bill_data.get('title'),
                                    bill_data.get('url'),
                                    self.hearing_parser.normalize_date(bill_data.get('introducedDate')),
                                    hb[0]  # bill_id
                                )
                            )
                            stats['imported'] += 1

                        stats['processed'] += 1

                    except Exception as e:
                        logger.error(f"Error importing bill {hb[2]} {hb[3]}: {e}")
                        stats['errors'] += 1

            logger.info(f"Bill import: {stats['imported']}/{stats['processed']} successful")
            return stats

        except Exception as e:
            logger.error(f"Bill import failed: {e}")
            raise

    def import_documents(self, hearing_ids: List[int], validation_mode: bool = False) -> Dict[str, int]:
        """
        Import documents for specified hearings

        Args:
            hearing_ids: List of hearing IDs to process
            validation_mode: If True, validate but don't write

        Returns:
            Import statistics
        """
        stats = {'processed': 0, 'imported': 0, 'errors': 0}

        try:
            for hearing_id in hearing_ids:
                try:
                    # Get hearing details
                    if not validation_mode:
                        hearing = self.db_manager.fetch_one(
                            "SELECT * FROM hearings WHERE hearing_id = ?",
                            (hearing_id,)
                        )

                        if hearing:
                            # Fetch detailed hearing information (which includes documents)
                            detailed_hearing = self.hearing_fetcher.fetch_hearing_details(
                                hearing['congress'], hearing['chamber'].lower(), hearing['event_id']
                            )

                            if detailed_hearing and 'committeeMeeting' in detailed_hearing:
                                event_data = detailed_hearing['committeeMeeting']
                            elif detailed_hearing and 'committeeEvent' in detailed_hearing:
                                event_data = detailed_hearing['committeeEvent']

                                # Extract and import witnesses
                                witnesses = self.hearing_parser.extract_witnesses(event_data)
                                for witness_data in witnesses:
                                    witness = self.witness_parser.parse(witness_data)
                                    if witness:
                                        witness_id = self.db_manager.get_or_create_witness(witness.dict())
                                        self.db_manager.create_witness_appearance(
                                            witness_id, hearing_id, witness_data
                                        )

                                # Extract documents
                                documents = self.document_fetcher.extract_hearing_documents(event_data)

                                # Import transcripts
                                for transcript in documents['transcripts']:
                                    self.db_manager.execute(
                                        "INSERT OR REPLACE INTO hearing_transcripts "
                                        "(hearing_id, jacket_number, title, document_url, pdf_url, html_url, format_type) "
                                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                        (hearing_id, transcript.get('jacket_number'), transcript.get('title'),
                                         transcript.get('document_url'), transcript.get('pdf_url'),
                                         transcript.get('html_url'), transcript.get('format_type'))
                                    )

                                stats['imported'] += 1

                    stats['processed'] += 1

                except Exception as e:
                    logger.error(f"Error importing documents for hearing {hearing_id}: {e}")
                    stats['errors'] += 1

            logger.info(f"Document import: {stats['imported']}/{stats['processed']} successful")
            return stats

        except Exception as e:
            logger.error(f"Document import failed: {e}")
            raise

    def _process_hearing_batch(self, hearings: List[Dict[str, Any]], congress: int, validation_mode: bool) -> Dict[str, int]:
        """Process a batch of hearings"""
        batch_stats = {'imported': 0, 'errors': 0}

        for hearing_data in hearings:
            try:
                # Parse hearing data
                hearing = self.hearing_parser.parse(hearing_data)
                if hearing:
                    if not validation_mode:
                        # Import hearing
                        hearing_dict = hearing.dict()
                        hearing_dict['congress'] = congress
                        hearing_id = self.db_manager.upsert_hearing(hearing_dict)

                        # Link to committees
                        committees = self.hearing_parser.extract_committee_references(hearing_data)
                        for committee_ref in committees:
                            committee = self.db_manager.get_committee_by_system_code(committee_ref['system_code'])
                            if committee:
                                self.db_manager.link_hearing_committee(
                                    hearing_id, committee['committee_id'], committee_ref['is_primary']
                                )

                        # Link to bills
                        bills = self.hearing_parser.extract_bill_references(hearing_data)
                        for bill_ref in bills:
                            if bill_ref.get('congress') and bill_ref.get('bill_type') and bill_ref.get('bill_number'):
                                # Create or get bill
                                bill_id = self.db_manager.upsert_bill(bill_ref)
                                self.db_manager.link_hearing_bill(
                                    hearing_id, bill_id, bill_ref.get('relationship_type', 'mentioned')
                                )

                    batch_stats['imported'] += 1
                else:
                    batch_stats['errors'] += 1

            except Exception as e:
                logger.error(f"Error processing hearing {hearing_data.get('eventId', 'unknown')}: {e}")
                batch_stats['errors'] += 1

        return batch_stats

    def _import_committee_roster(self, roster: List[Dict[str, Any]], committee_id: int, congress: int):
        """Import committee roster memberships"""
        for member_info in roster:
            bioguide_id = member_info.get('bioguide_id')
            if bioguide_id:
                member = self.db_manager.get_member_by_bioguide_id(bioguide_id)
                if member:
                    self.db_manager.create_committee_membership(
                        member['member_id'], committee_id, member_info.get('role', 'Member'), congress
                    )

    def _get_all_hearing_ids(self) -> List[int]:
        """Get all hearing IDs from database"""
        try:
            with self.db_manager.transaction() as conn:
                cursor = conn.execute("SELECT hearing_id FROM hearings")
                hearings = cursor.fetchall()
                return [h[0] for h in hearings]
        except Exception as e:
            logger.warning(f"Could not fetch hearing IDs: {e}")
            return []

    def create_checkpoint(self, phase: str, status: str):
        """Create checkpoint for resumability"""
        # Map phase names to valid entity types
        entity_type_mapping = {
            'committees': 'committees',
            'members': 'members',
            'hearings': 'hearings',
            'bills': 'bills',
            'documents': 'documents'
        }

        entity_type = entity_type_mapping.get(phase, phase)
        self.db_manager.execute(
            "INSERT INTO sync_tracking (entity_type, last_sync_timestamp, status, notes) "
            "VALUES (?, CURRENT_TIMESTAMP, ?, ?)",
            (entity_type, status, f"Import phase {phase} {status}")
        )

    def resume_from_checkpoint(self) -> Optional[str]:
        """Resume from last checkpoint"""
        last_checkpoint = self.db_manager.fetch_one(
            "SELECT * FROM sync_tracking "
            "WHERE status = 'success' AND notes LIKE 'Import phase %' "
            "ORDER BY last_sync_timestamp DESC LIMIT 1"
        )

        if last_checkpoint:
            # Extract phase from notes
            notes = last_checkpoint['notes']
            if 'Import phase' in notes:
                return notes.split('Import phase ')[1].split(' ')[0]
        return None