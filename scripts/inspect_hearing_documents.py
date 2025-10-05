#!/usr/bin/env python3
"""
Script to inspect actual Congress.gov API document payload structure
"""
import sys
import os
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.client import CongressAPIClient
from config.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def inspect_hearing_documents(congress, chamber, event_id):
    """Fetch and inspect document structure for a hearing"""
    api_client = CongressAPIClient()

    try:
        logger.info(f"Fetching hearing details for {congress}/{chamber}/{event_id}")
        response = api_client.get_hearing_details(congress, chamber, event_id)

        # Save full response to file for inspection
        output_file = f"hearing_{event_id}_response.json"
        with open(output_file, 'w') as f:
            json.dump(response, f, indent=2)
        logger.info(f"Full response saved to {output_file}")

        # Extract the main event data
        event_data = None
        if 'committeeMeeting' in response:
            event_data = response['committeeMeeting']
        elif 'committeeEvent' in response:
            event_data = response['committeeEvent']

        if not event_data:
            logger.error("Could not find event data in response")
            return

        # Inspect witnesses structure
        logger.info("\n=== WITNESSES STRUCTURE ===")
        witnesses = event_data.get('witnesses', [])
        if witnesses:
            for i, witness in enumerate(witnesses[:2]):  # Show first 2
                logger.info(f"\nWitness {i+1}:")
                logger.info(f"  Keys: {list(witness.keys())}")
                logger.info(f"  Name: {witness.get('name')}")
                if 'documents' in witness:
                    logger.info(f"  Documents: {len(witness['documents'])} found")
                    for j, doc in enumerate(witness['documents'][:2]):
                        logger.info(f"    Document {j+1} keys: {list(doc.keys())}")
        else:
            logger.info("No witnesses found in response")

        # Inspect documents structure
        logger.info("\n=== DOCUMENTS STRUCTURE ===")
        for key in ['documents', 'supportingDocuments', 'relatedDocuments', 'transcripts', 'transcript']:
            if key in event_data:
                docs = event_data[key]
                if isinstance(docs, list):
                    logger.info(f"\n{key}: {len(docs)} items")
                    if docs:
                        logger.info(f"  First item keys: {list(docs[0].keys())}")
                        logger.info(f"  Sample: {json.dumps(docs[0], indent=4)}")
                elif isinstance(docs, dict):
                    logger.info(f"\n{key}: (dict)")
                    logger.info(f"  Keys: {list(docs.keys())}")
                    logger.info(f"  Sample: {json.dumps(docs, indent=4)}")

        # Print full structure of top-level keys
        logger.info("\n=== TOP-LEVEL EVENT KEYS ===")
        logger.info(f"Keys: {list(event_data.keys())}")

    except Exception as e:
        logger.error(f"Error inspecting hearing: {e}", exc_info=True)


if __name__ == "__main__":
    # Hearing 1353: congress=119, chamber=house, event_id=118291
    inspect_hearing_documents(119, 'house', '118291')
