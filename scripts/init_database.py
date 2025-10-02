#!/usr/bin/env python3
"""
Initialize database with schema
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.settings import settings
from config.logging_config import setup_logging, get_logger

def main():
    """Initialize database with schema"""
    setup_logging()
    logger = get_logger(__name__)

    try:
        logger.info("Initializing database...")

        # Create database manager
        db_manager = DatabaseManager()

        # Initialize schema
        db_manager.initialize_schema()

        # Insert sample policy areas
        insert_sample_data(db_manager)

        logger.info(f"Database initialized successfully at: {settings.database_path}")

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)

def insert_sample_data(db_manager: DatabaseManager):
    """Insert sample policy areas"""
    policy_areas = [
        ("Healthcare", "Health insurance, medical care, public health"),
        ("Immigration", "Border security, visa policy, naturalization"),
        ("Tax Policy", "Federal taxation, IRS oversight"),
        ("National Security", "Defense, intelligence, homeland security"),
        ("Environment", "EPA, climate change, conservation"),
        ("Education", "Federal education policy, student loans"),
        ("Transportation", "Infrastructure, aviation, highways"),
        ("Energy", "Energy policy, utilities, renewable energy"),
        ("Financial Services", "Banking, securities, insurance regulation"),
        ("Agriculture", "Farm policy, food safety, rural development"),
        ("Technology", "Telecommunications, cybersecurity, privacy"),
        ("Trade", "International trade, tariffs, trade agreements"),
        ("Labor", "Employment law, workplace safety, unions"),
        ("Housing", "Housing policy, urban development, mortgages"),
        ("Veterans Affairs", "Veterans benefits, military healthcare")
    ]

    for name, description in policy_areas:
        db_manager.execute(
            "INSERT OR IGNORE INTO policy_areas (name, description) VALUES (?, ?)",
            (name, description)
        )

if __name__ == "__main__":
    main()