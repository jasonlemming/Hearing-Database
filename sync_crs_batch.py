#!/usr/bin/env python3
"""
Batch CRS sync script with progress reporting
"""
from brookings_ingester.crs_sync import CRSPolicyLibrarySync
from brookings_ingester.models.database import session_scope
import time

def sync_in_batches(batch_size=100):
    """Sync CRS products in batches with progress reporting"""

    sync = CRSPolicyLibrarySync()

    # Fetch all products
    print("Fetching all CRS products...")
    products = sync.fetch_crs_products()
    total = len(products)
    print(f"Found {total} CRS products to sync\n")

    # Process in batches
    total_created = 0
    total_updated = 0
    total_skipped = 0
    total_errors = 0

    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = products[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size

        print(f"Batch {batch_num}/{total_batches}: Processing products {i+1}-{min(i+batch_size, total)}")

        # Process this batch in its own session
        with session_scope() as session:
            source = sync.get_or_create_crs_source(session)

            for product in batch:
                try:
                    result = sync.sync_product_to_policy_library(session, source, product)
                    if result:
                        if session.is_modified(result):
                            total_updated += 1
                        else:
                            total_created += 1
                    else:
                        total_skipped += 1
                except Exception as e:
                    total_errors += 1
                    print(f"  Error syncing {product.get('product_id')}: {e}")

        elapsed = time.time() - start_time
        rate = (i + len(batch)) / elapsed
        remaining = (total - (i + len(batch))) / rate if rate > 0 else 0

        print(f"  Progress: {total_created} created, {total_updated} updated, {total_skipped} skipped, {total_errors} errors")
        print(f"  Speed: {rate:.1f} products/sec | Est. remaining: {remaining/60:.1f} min\n")

    duration = time.time() - start_time

    print(f"\n✓ Sync completed in {duration/60:.1f} minutes")
    print(f"\nFinal Results:")
    print(f"  Products checked: {total}")
    print(f"  Documents created: {total_created}")
    print(f"  Documents updated: {total_updated}")
    print(f"  Documents skipped: {total_skipped}")
    print(f"  Errors: {total_errors}")

if __name__ == '__main__':
    sync_in_batches(batch_size=100)
