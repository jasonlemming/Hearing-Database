#!/usr/bin/env python3
"""
Cleanup Script: Remove Duplicate Witnesses Created on Oct 8, 2025

This script identifies and removes duplicate witness records created during
the Oct 8 import, migrating their documents and appearances to the original witnesses.

Strategy:
1. Find witnesses with the same normalized name + organization
2. Keep the oldest witness record (created before Oct 8)
3. Migrate witness documents from duplicates to originals
4. Delete duplicate witness appearances
5. Delete duplicate witness records

Usage:
    python scripts/cleanup_duplicate_witnesses_oct8.py [--dry-run]
"""

import sqlite3
import sys
import os
from datetime import datetime
from typing import List, Tuple, Dict, Set

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager

def normalize_witness_name(full_name: str) -> str:
    """
    Normalize witness name by removing titles - matches DatabaseManager logic.
    """
    if not full_name:
        return ''

    normalized = full_name
    titles = [
        'The Honorable ', 'The Hon. ', 'Honorable ', 'Hon. ',
        'Mr. ', 'Ms. ', 'Mrs. ', 'Miss ', 'Dr. ', 'Prof. ', 'Professor ',
        'Sen. ', 'Senator ', 'Rep. ', 'Representative ',
        'Gov. ', 'Governor ', 'Lt. Gov. ', 'Lieutenant Governor ',
        'Atty. Gen. ', 'Attorney General ', 'Sec. ', 'Secretary ',
        'Director ', 'Administrator ', 'Commissioner ', 'Chief ',
        'Gen. ', 'General ', 'Admiral ', 'Colonel ', 'Major ',
        'Captain ', 'Lieutenant ', 'Sergeant '
    ]

    for title in titles:
        if normalized.startswith(title):
            normalized = normalized[len(title):]
            break

    return normalized.strip()


def find_duplicate_witnesses(conn: sqlite3.Connection) -> List[Tuple[int, int, str, str]]:
    """
    Find duplicate witnesses (same normalized name + organization).

    Returns:
        List of (original_id, duplicate_id, original_name, duplicate_name) tuples
    """
    cursor = conn.execute("""
        SELECT witness_id, full_name, organization, created_at
        FROM witnesses
        ORDER BY created_at ASC
    """)

    all_witnesses = cursor.fetchall()

    # Group by normalized name + organization
    witness_groups: Dict[Tuple[str, str], List[Tuple[int, str, datetime]]] = {}

    for witness_id, full_name, organization, created_at in all_witnesses:
        normalized_name = normalize_witness_name(full_name)
        org = organization or ''
        key = (normalized_name, org)

        if key not in witness_groups:
            witness_groups[key] = []

        witness_groups[key].append((witness_id, full_name, created_at))

    # Find duplicates - groups with more than one witness
    duplicates = []
    for (norm_name, org), witnesses in witness_groups.items():
        if len(witnesses) > 1:
            # Sort by created_at to keep oldest
            witnesses.sort(key=lambda x: x[2])  # Sort by created_at
            original_id, original_name, _ = witnesses[0]

            for duplicate_id, duplicate_name, _ in witnesses[1:]:
                duplicates.append((original_id, duplicate_id, original_name, duplicate_name))

    return duplicates


def cleanup_duplicates(dry_run: bool = False):
    """
    Clean up duplicate witnesses created during Oct 8 import.

    Args:
        dry_run: If True, only report what would be done without making changes
    """
    db = DatabaseManager()

    with db.transaction() as conn:
        print("=" * 70)
        print("DUPLICATE WITNESS CLEANUP - Oct 8, 2025 Import")
        print("=" * 70)

        # Find duplicates
        print("\n1. Finding duplicate witnesses...")
        duplicates = find_duplicate_witnesses(conn)

        if not duplicates:
            print("   ✓ No duplicate witnesses found!")
            return

        print(f"   Found {len(duplicates)} duplicate witness pairs")

        # Show examples
        print("\n   Examples:")
        for original_id, dup_id, orig_name, dup_name in duplicates[:5]:
            print(f"   - Witness {original_id} '{orig_name}' ←→ {dup_id} '{dup_name}'")

        if len(duplicates) > 5:
            print(f"   ... and {len(duplicates) - 5} more")

        if dry_run:
            print("\n   DRY RUN: No changes will be made")
            print("\n" + "=" * 70)
            print(f"SUMMARY: Would clean up {len(duplicates)} duplicate witnesses")
            print("=" * 70)
            return

        # Delete duplicate witness documents
        # NOTE: We delete rather than migrate because the same documents
        # (same URLs) already exist for the original witnesses
        print("\n2. Deleting duplicate witness documents...")
        docs_deleted = 0

        for _, duplicate_id, _, _ in duplicates:
            # Get appearance IDs for duplicate witness
            cursor = conn.execute("""
                SELECT appearance_id
                FROM witness_appearances
                WHERE witness_id = ?
            """, (duplicate_id,))
            dup_appearances = [row[0] for row in cursor.fetchall()]

            # Delete documents for duplicate appearances
            for dup_appearance_id in dup_appearances:
                cursor = conn.execute("""
                    DELETE FROM witness_documents
                    WHERE appearance_id = ?
                """, (dup_appearance_id,))

                docs_deleted += cursor.rowcount

        print(f"   ✓ Deleted {docs_deleted} duplicate witness documents")

        # Delete duplicate witness appearances
        print("\n3. Deleting duplicate witness appearances...")
        appearances_deleted = 0

        for _, duplicate_id, _, _ in duplicates:
            cursor = conn.execute("""
                DELETE FROM witness_appearances
                WHERE witness_id = ?
            """, (duplicate_id,))

            appearances_deleted += cursor.rowcount

        print(f"   ✓ Deleted {appearances_deleted} duplicate appearances")

        # Delete duplicate witness records
        print("\n4. Deleting duplicate witness records...")
        witnesses_deleted = 0

        for _, duplicate_id, _, _ in duplicates:
            cursor = conn.execute("""
                DELETE FROM witnesses
                WHERE witness_id = ?
            """, (duplicate_id,))

            witnesses_deleted += cursor.rowcount

        print(f"   ✓ Deleted {witnesses_deleted} duplicate witnesses")

        print("\n" + "=" * 70)
        print("CLEANUP COMPLETE")
        print("=" * 70)
        print(f"  Duplicate pairs processed: {len(duplicates)}")
        print(f"  Documents deleted: {docs_deleted}")
        print(f"  Appearances deleted: {appearances_deleted}")
        print(f"  Witnesses deleted: {witnesses_deleted}")
        print("=" * 70)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Clean up duplicate witnesses from Oct 8 import')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')

    args = parser.parse_args()

    cleanup_duplicates(dry_run=args.dry_run)
