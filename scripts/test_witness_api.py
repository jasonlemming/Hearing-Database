#!/usr/bin/env python3
"""
Test script to explore Congress.gov API hearing details for witness information
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from api.client import CongressAPIClient
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)

def test_hearing_details():
    """Test fetching hearing details to explore witness data structure"""

    # Initialize API client
    client = CongressAPIClient()

    # Test with a sample hearing
    congress = 119
    chamber = "house"
    event_id = "118296"  # From our database

    try:
        logger.info(f"Fetching hearing details for event {event_id}")
        details = client.get_hearing_details(congress, chamber, event_id)

        # Save full response for analysis
        output_file = f"hearing_details_{event_id}.json"
        with open(output_file, 'w') as f:
            json.dump(details, f, indent=2)

        logger.info(f"Full response saved to {output_file}")

        # Explore structure for witness information
        print(f"\n=== Hearing Details Structure for Event {event_id} ===")
        print(f"Top-level keys: {list(details.keys())}")

        # Look for witness-related fields
        witness_fields = []
        for key, value in details.items():
            if any(witness_term in key.lower() for witness_term in ['witness', 'testify', 'panel', 'speaker']):
                witness_fields.append(key)
                print(f"\nPotential witness field: {key}")
                if isinstance(value, list):
                    print(f"  Type: list with {len(value)} items")
                    if value:
                        print(f"  Sample item keys: {list(value[0].keys()) if isinstance(value[0], dict) else 'Not a dict'}")
                elif isinstance(value, dict):
                    print(f"  Type: dict with keys: {list(value.keys())}")
                else:
                    print(f"  Type: {type(value)}, Value: {value}")

        # Also check nested structures
        for key, value in details.items():
            if isinstance(value, dict):
                nested_witness_fields = []
                for nested_key in value.keys():
                    if any(witness_term in nested_key.lower() for witness_term in ['witness', 'testify', 'panel', 'speaker']):
                        nested_witness_fields.append(nested_key)

                if nested_witness_fields:
                    print(f"\nNested witness fields in '{key}': {nested_witness_fields}")
                    for nested_key in nested_witness_fields:
                        nested_value = value[nested_key]
                        if isinstance(nested_value, list):
                            print(f"  {nested_key}: list with {len(nested_value)} items")
                            if nested_value:
                                print(f"    Sample item: {nested_value[0]}")
                        else:
                            print(f"  {nested_key}: {nested_value}")

        print(f"\n=== Summary ===")
        print(f"Found {len(witness_fields)} potential witness fields")
        print(f"Witness-related fields: {witness_fields}")

        return details

    except Exception as e:
        logger.error(f"Error testing hearing details: {e}")
        return None

def test_multiple_hearings():
    """Test multiple hearings to find one with witness data"""

    client = CongressAPIClient()
    congress = 119
    chamber = "house"

    # Test event IDs from our database
    test_events = ["118296", "118295", "118293", "118292", "118291"]

    for event_id in test_events:
        try:
            logger.info(f"Testing event {event_id} for witness data...")
            details = client.get_hearing_details(congress, chamber, event_id)

            # Quick check for witness-related content
            details_str = json.dumps(details).lower()
            witness_indicators = ['witness', 'testify', 'panel', 'speaker', 'testimony']

            found_indicators = [indicator for indicator in witness_indicators if indicator in details_str]

            print(f"Event {event_id}: Found indicators: {found_indicators}")

            if found_indicators:
                print(f"  Saving detailed response for event {event_id}")
                with open(f"hearing_details_{event_id}_with_witnesses.json", 'w') as f:
                    json.dump(details, f, indent=2)

        except Exception as e:
            logger.error(f"Error testing event {event_id}: {e}")

if __name__ == "__main__":
    print("Testing Congress.gov API for witness data structure...")

    # Test single hearing in detail
    details = test_hearing_details()

    print("\n" + "="*60)

    # Test multiple hearings for witness content
    test_multiple_hearings()

    print("\nTest complete. Check generated JSON files for detailed API responses.")