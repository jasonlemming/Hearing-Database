#!/usr/bin/env python3
"""
Manual test for batch processing logic (Day 3).

This script manually tests the batch processing implementation
without requiring pytest to be installed.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from updaters.daily_updater import DailyUpdater, Checkpoint, BatchResult

def test_divide_into_batches():
    """Test the _divide_into_batches method"""
    print("\n" + "="*70)
    print("Testing _divide_into_batches() method")
    print("="*70)

    updater = DailyUpdater(congress=119, lookback_days=7)

    # Test 1: Equal sizes (100 hearings, batch size 50)
    print("\nTest 1: Equal sizes (100 hearings, batch size 50)")
    hearings = [f"HEARING-{i:03d}" for i in range(100)]
    batches = updater._divide_into_batches(hearings, batch_size=50)
    assert len(batches) == 2, f"Expected 2 batches, got {len(batches)}"
    assert len(batches[0]) == 50, f"Expected batch 0 size 50, got {len(batches[0])}"
    assert len(batches[1]) == 50, f"Expected batch 1 size 50, got {len(batches[1])}"
    print(f"✅ PASS: Created {len(batches)} batches with sizes {[len(b) for b in batches]}")

    # Test 2: Unequal sizes (120 hearings, batch size 50)
    print("\nTest 2: Unequal sizes (120 hearings, batch size 50)")
    hearings = [f"HEARING-{i:03d}" for i in range(120)]
    batches = updater._divide_into_batches(hearings, batch_size=50)
    assert len(batches) == 3, f"Expected 3 batches, got {len(batches)}"
    assert len(batches[0]) == 50, f"Expected batch 0 size 50, got {len(batches[0])}"
    assert len(batches[1]) == 50, f"Expected batch 1 size 50, got {len(batches[1])}"
    assert len(batches[2]) == 20, f"Expected batch 2 size 20, got {len(batches[2])}"
    print(f"✅ PASS: Created {len(batches)} batches with sizes {[len(b) for b in batches]}")

    # Test 3: Small dataset (10 hearings, batch size 50)
    print("\nTest 3: Small dataset (10 hearings, batch size 50)")
    hearings = [f"HEARING-{i:03d}" for i in range(10)]
    batches = updater._divide_into_batches(hearings, batch_size=50)
    assert len(batches) == 1, f"Expected 1 batch, got {len(batches)}"
    assert len(batches[0]) == 10, f"Expected batch 0 size 10, got {len(batches[0])}"
    print(f"✅ PASS: Created {len(batches)} batch with size {len(batches[0])}")

    # Test 4: Empty dataset
    print("\nTest 4: Empty dataset (0 hearings)")
    hearings = []
    batches = updater._divide_into_batches(hearings, batch_size=50)
    assert len(batches) == 0, f"Expected 0 batches, got {len(batches)}"
    print(f"✅ PASS: Created {len(batches)} batches (empty list)")

def test_checkpoint_class():
    """Test the Checkpoint class"""
    print("\n" + "="*70)
    print("Testing Checkpoint class")
    print("="*70)

    # Test creation
    print("\nTest: Checkpoint creation")
    checkpoint = Checkpoint(batch_number=1)
    assert checkpoint.batch_number == 1
    assert checkpoint.hearings_to_update == []
    assert checkpoint.hearings_to_add == []
    assert checkpoint.witnesses_to_add == []
    assert checkpoint.documents_to_add == []
    print(f"✅ PASS: Checkpoint created for batch {checkpoint.batch_number}")

    # Test tracking
    print("\nTest: Checkpoint tracking")
    checkpoint.track_update("HEARING-001", {"title": "Test"})
    checkpoint.track_addition("HEARING-002")
    checkpoint.track_witness_addition("WITNESS-001")
    checkpoint.track_document_addition("DOC-001")
    assert "HEARING-001" in checkpoint.hearings_to_update
    assert "HEARING-002" in checkpoint.hearings_to_add
    assert "WITNESS-001" in checkpoint.witnesses_to_add
    assert "DOC-001" in checkpoint.documents_to_add
    print(f"✅ PASS: Checkpoint tracked 4 items across all types")

def test_batch_result_class():
    """Test the BatchResult class"""
    print("\n" + "="*70)
    print("Testing BatchResult class")
    print("="*70)

    # Test success result
    print("\nTest: Success result")
    result = BatchResult(success=True, records=50)
    assert result.success == True
    assert result.records == 50
    assert result.error is None
    result_dict = result.to_dict()
    assert result_dict['success'] == True
    assert result_dict['records'] == 50
    print(f"✅ PASS: Success result created (50 records)")

    # Test failure result
    print("\nTest: Failure result")
    result = BatchResult(success=False, error="Validation failed", issues=["Issue 1", "Issue 2"])
    assert result.success == False
    assert result.error == "Validation failed"
    assert len(result.issues) == 2
    result_dict = result.to_dict()
    assert result_dict['success'] == False
    print(f"✅ PASS: Failure result created with 2 issues")

def test_process_batch_skeleton():
    """Test the _process_batch skeleton"""
    print("\n" + "="*70)
    print("Testing _process_batch() skeleton")
    print("="*70)

    updater = DailyUpdater(congress=119, lookback_days=7)
    checkpoint = Checkpoint(batch_number=1)

    # Test with sample batch
    print("\nTest: Process batch skeleton")
    batch = [{"eventId": f"TEST-{i}"} for i in range(10)]
    result = updater._process_batch(batch, batch_number=1, checkpoint=checkpoint)
    assert result.success == True
    assert result.records == 10
    print(f"✅ PASS: Processed batch of {result.records} records")

def test_validate_batch():
    """Test the _validate_batch method"""
    print("\n" + "="*70)
    print("Testing _validate_batch() method")
    print("="*70)

    updater = DailyUpdater(congress=119, lookback_days=7)

    # Test 1: All valid hearings
    print("\nTest 1: All valid hearings")
    batch = [
        {
            'eventId': 'TEST-119-001',
            'chamber': 'House',
            'title': 'Test Hearing 1',
            'date': '2025-10-15T10:00:00Z',
            'congress': 119
        },
        {
            'eventId': 'TEST-119-002',
            'chamber': 'Senate',
            'title': 'Test Hearing 2',
            'date': '2025-10-16T14:00:00Z',
            'congress': 119
        }
    ]
    is_valid, issues = updater._validate_batch(batch)
    assert is_valid == True, f"Expected valid, got issues: {issues}"
    assert len(issues) == 0
    print(f"✅ PASS: Validated {len(batch)} valid hearings")

    # Test 2: Duplicate event IDs
    print("\nTest 2: Duplicate event IDs")
    batch = [
        {'eventId': 'TEST-119-001', 'chamber': 'House', 'title': 'Test 1'},
        {'eventId': 'TEST-119-001', 'chamber': 'Senate', 'title': 'Test 2'},  # Duplicate
        {'eventId': 'TEST-119-002', 'chamber': 'House', 'title': 'Test 3'}
    ]
    is_valid, issues = updater._validate_batch(batch)
    assert is_valid == False, "Expected invalid due to duplicates"
    assert len(issues) > 0
    assert any('Duplicate' in issue for issue in issues)
    print(f"✅ PASS: Detected duplicate event IDs")

    # Test 3: Missing required fields
    print("\nTest 3: Missing required fields")
    batch = [
        {'chamber': 'House', 'title': 'Test 1'},  # Missing eventId
        {'eventId': 'TEST-119-002', 'title': 'Test 2'}  # Missing chamber
    ]
    is_valid, issues = updater._validate_batch(batch)
    assert is_valid == False, "Expected invalid due to missing fields"
    assert len(issues) >= 2
    assert any('eventId' in issue for issue in issues)
    assert any('chamber' in issue for issue in issues)
    print(f"✅ PASS: Detected missing required fields")

    # Test 4: Invalid data formats
    print("\nTest 4: Invalid data formats")
    batch = [
        {
            'eventId': 'TEST-119-001',
            'chamber': 'InvalidChamber',  # Invalid
            'title': 'Test 1'
        },
        {
            'eventId': 'TEST-119-002',
            'chamber': 'House',
            'title': 'Test 2',
            'date': 'not-a-date',  # Invalid date
            'congress': 'not-a-number'  # Invalid congress
        }
    ]
    is_valid, issues = updater._validate_batch(batch)
    assert is_valid == False, "Expected invalid due to format errors"
    assert len(issues) >= 3
    assert any('chamber' in issue for issue in issues)
    assert any('date' in issue for issue in issues)
    assert any('Congress' in issue for issue in issues)
    print(f"✅ PASS: Detected invalid data formats")

    # Test 5: Mixed update and addition formats
    print("\nTest 5: Mixed update and addition formats")
    batch = [
        {'eventId': 'TEST-119-001', 'chamber': 'House', 'title': 'Test 1'},
        {
            'existing': {'eventId': 'TEST-119-002'},
            'new_data': {'eventId': 'TEST-119-002', 'chamber': 'Senate', 'title': 'Test 2'}
        }
    ]
    is_valid, issues = updater._validate_batch(batch)
    assert is_valid == True, f"Expected valid, got issues: {issues}"
    assert len(issues) == 0
    print(f"✅ PASS: Validated mixed formats")

def main():
    """Run all manual tests"""
    print("\n" + "="*70)
    print("MANUAL TEST SUITE - Phase 2.3.1 Day 3-4")
    print("="*70)

    try:
        test_checkpoint_class()
        test_batch_result_class()
        test_divide_into_batches()
        test_process_batch_skeleton()
        test_validate_batch()

        print("\n" + "="*70)
        print("ALL TESTS PASSED ✅")
        print("="*70)
        print("\nSummary:")
        print("- Checkpoint class: ✅ Working")
        print("- BatchResult class: ✅ Working")
        print("- _divide_into_batches(): ✅ Working (4/4 tests)")
        print("- _process_batch() skeleton: ✅ Working")
        print("- _validate_batch(): ✅ Working (5/5 tests)")
        print("\nDay 3-4 implementation complete!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
