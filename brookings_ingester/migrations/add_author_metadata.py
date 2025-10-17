#!/usr/bin/env python3
"""
Database migration: Add author metadata fields

Adds the following columns to the authors table:
- job_title: Author's job title (e.g., "Senior Fellow")
- affiliation_text: Department/program affiliation
- profile_url: Source's author profile page URL
- linkedin_url: LinkedIn profile URL

Compatible with both PostgreSQL and SQLite.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path to import brookings_ingester
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from brookings_ingester.models import database as db_module
from sqlalchemy import text


def migrate_up():
    """Add new author metadata columns"""
    print("Running migration: add_author_metadata...")

    # Initialize database first
    db_module.init_database()

    # Check if using SQLite or PostgreSQL
    with db_module.engine.connect() as conn:
        # Add job_title column
        try:
            conn.execute(text("""
                ALTER TABLE authors
                ADD COLUMN job_title VARCHAR(200)
            """))
            conn.commit()
            print("✓ Added job_title column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("  job_title column already exists, skipping")
            else:
                raise

        # Add affiliation_text column
        try:
            conn.execute(text("""
                ALTER TABLE authors
                ADD COLUMN affiliation_text VARCHAR(500)
            """))
            conn.commit()
            print("✓ Added affiliation_text column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("  affiliation_text column already exists, skipping")
            else:
                raise

        # Add profile_url column
        try:
            conn.execute(text("""
                ALTER TABLE authors
                ADD COLUMN profile_url VARCHAR(500)
            """))
            conn.commit()
            print("✓ Added profile_url column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("  profile_url column already exists, skipping")
            else:
                raise

        # Add linkedin_url column
        try:
            conn.execute(text("""
                ALTER TABLE authors
                ADD COLUMN linkedin_url VARCHAR(500)
            """))
            conn.commit()
            print("✓ Added linkedin_url column")
        except Exception as e:
            if "already exists" in str(e) or "duplicate column" in str(e).lower():
                print("  linkedin_url column already exists, skipping")
            else:
                raise

    print("Migration complete!")


def migrate_down():
    """Remove author metadata columns (rollback)"""
    print("Rolling back migration: add_author_metadata...")

    db_module.init_database()

    with db_module.engine.connect() as conn:
        # Drop columns (note: SQLite doesn't support DROP COLUMN easily)
        # This is mainly for PostgreSQL
        try:
            conn.execute(text("ALTER TABLE authors DROP COLUMN job_title"))
            conn.execute(text("ALTER TABLE authors DROP COLUMN affiliation_text"))
            conn.execute(text("ALTER TABLE authors DROP COLUMN profile_url"))
            conn.execute(text("ALTER TABLE authors DROP COLUMN linkedin_url"))
            conn.commit()
            print("✓ Removed author metadata columns")
        except Exception as e:
            print(f"Note: Could not drop columns (may be using SQLite): {e}")
            print("For SQLite, you would need to recreate the table without these columns")

    print("Rollback complete!")


if __name__ == '__main__':
    # Run migration
    action = sys.argv[1] if len(sys.argv) > 1 else 'up'

    if action == 'up':
        migrate_up()
    elif action == 'down':
        migrate_down()
    else:
        print(f"Unknown action: {action}")
        print("Usage: python add_author_metadata.py [up|down]")
        sys.exit(1)
