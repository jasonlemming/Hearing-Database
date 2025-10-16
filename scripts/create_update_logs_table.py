#!/usr/bin/env python3
"""
Create the update_logs table in PostgreSQL database.
"""

import os
import psycopg2

def main():
    # Get the database URL from environment
    db_url = os.environ.get('BROOKINGS_DATABASE_URL') or os.environ.get('DATABASE_URL')

    if not db_url:
        print("Error: BROOKINGS_DATABASE_URL or DATABASE_URL environment variable not set")
        return

    print(f"Connecting to PostgreSQL...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    try:
        # Create the update_logs table
        print("Creating update_logs table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS update_logs (
                log_id SERIAL PRIMARY KEY,
                update_date DATE NOT NULL,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                duration_seconds REAL,
                hearings_checked INTEGER DEFAULT 0,
                hearings_updated INTEGER DEFAULT 0,
                hearings_added INTEGER DEFAULT 0,
                committees_updated INTEGER DEFAULT 0,
                witnesses_updated INTEGER DEFAULT 0,
                api_requests INTEGER DEFAULT 0,
                error_count INTEGER DEFAULT 0,
                errors TEXT,
                success BOOLEAN DEFAULT TRUE,
                trigger_source VARCHAR(50),
                schedule_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("✓ update_logs table created successfully")

        # Check if it exists now
        cursor.execute("SELECT COUNT(*) FROM update_logs")
        count = cursor.fetchone()[0]
        print(f"Table verified - contains {count} records")

    except Exception as e:
        print(f"Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    main()
