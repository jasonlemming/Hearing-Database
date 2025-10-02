#!/usr/bin/env python3
"""
Comprehensive database audit and improvement script
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.manager import DatabaseManager
from config.logging_config import get_logger

logger = get_logger(__name__)

def audit_database():
    """Conduct comprehensive audit of current database state"""

    db = DatabaseManager()

    print("=" * 80)
    print("COMPREHENSIVE DATABASE AUDIT")
    print("=" * 80)

    with db.transaction() as conn:
        # 1. BASIC STATISTICS
        print("\n1. BASIC STATISTICS")
        print("-" * 40)

        cursor = conn.execute('SELECT COUNT(*) FROM committees')
        total_committees = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NULL')
        parent_committees = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM committees WHERE parent_committee_id IS NOT NULL')
        subcommittees = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM hearings')
        total_hearings = cursor.fetchone()[0]

        cursor = conn.execute('SELECT COUNT(*) FROM hearing_committees')
        total_relationships = cursor.fetchone()[0]

        print(f"Committees: {total_committees} (Parents: {parent_committees}, Subs: {subcommittees})")
        print(f"Hearings: {total_hearings}")
        print(f"Committee-Hearing Relationships: {total_relationships}")

        # 2. DATA COMPLETENESS ANALYSIS
        print("\n2. DATA COMPLETENESS ANALYSIS")
        print("-" * 40)

        cursor = conn.execute('''
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_titles,
                COUNT(CASE WHEN hearing_date_only IS NOT NULL THEN 1 END) as with_dates,
                COUNT(CASE WHEN hearing_time IS NOT NULL THEN 1 END) as with_times,
                COUNT(CASE WHEN location IS NOT NULL THEN 1 END) as with_locations
            FROM hearings
        ''')

        completeness = cursor.fetchone()
        print(f"Hearings with titles: {completeness[1]}/{completeness[0]} ({completeness[1]/completeness[0]*100:.1f}%)")
        print(f"Hearings with dates: {completeness[2]}/{completeness[0]} ({completeness[2]/completeness[0]*100:.1f}%)")
        print(f"Hearings with times: {completeness[3]}/{completeness[0]} ({completeness[3]/completeness[0]*100:.1f}%)")
        print(f"Hearings with locations: {completeness[4]}/{completeness[0]} ({completeness[4]/completeness[0]*100:.1f}%)")

        # Committee assignment completeness
        cursor = conn.execute('''
            SELECT COUNT(DISTINCT h.hearing_id)
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.hearing_id IS NULL
        ''')
        unassigned_hearings = cursor.fetchone()[0]
        assigned_hearings = total_hearings - unassigned_hearings

        print(f"Hearings with committee assignments: {assigned_hearings}/{total_hearings} ({assigned_hearings/total_hearings*100:.1f}%)")
        print(f"Unassigned hearings: {unassigned_hearings}")

        # 3. CHAMBER BREAKDOWN
        print("\n3. CHAMBER BREAKDOWN")
        print("-" * 40)

        cursor = conn.execute('''
            SELECT
                h.chamber,
                COUNT(*) as total_hearings,
                COUNT(CASE WHEN h.title IS NOT NULL AND h.title != '' THEN 1 END) as with_titles,
                COUNT(CASE WHEN hc.hearing_id IS NOT NULL THEN 1 END) as with_committees
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            GROUP BY h.chamber
            ORDER BY h.chamber
        ''')

        for row in cursor.fetchall():
            chamber, total, titles, committees = row
            print(f"{chamber}: {total} hearings, {titles} with titles ({titles/total*100:.1f}%), {committees} with committees ({committees/total*100:.1f}%)")

        # 4. DATE RANGE ANALYSIS
        print("\n4. DATE RANGE ANALYSIS")
        print("-" * 40)

        cursor = conn.execute('''
            SELECT
                MIN(hearing_date_only) as earliest,
                MAX(hearing_date_only) as latest,
                COUNT(DISTINCT strftime('%Y-%m', hearing_date_only)) as months_covered
            FROM hearings
            WHERE hearing_date_only IS NOT NULL
        ''')

        date_range = cursor.fetchone()
        print(f"Date range: {date_range[0]} to {date_range[1]}")
        print(f"Months covered: {date_range[2]}")

        # Recent activity analysis
        cursor = conn.execute('''
            SELECT
                strftime('%Y-%m', hearing_date_only) as month,
                COUNT(*) as hearings
            FROM hearings
            WHERE hearing_date_only >= date('now', '-6 months')
            GROUP BY strftime('%Y-%m', hearing_date_only)
            ORDER BY month DESC
        ''')

        print("\nRecent 6 months activity:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} hearings")

        # 5. COMMITTEE COVERAGE ANALYSIS
        print("\n5. COMMITTEE COVERAGE ANALYSIS")
        print("-" * 40)

        cursor = conn.execute('''
            SELECT
                c.chamber,
                c.name,
                COUNT(hc.hearing_id) as hearing_count,
                COUNT(CASE WHEN h.hearing_date_only >= '2025-01-01' THEN 1 END) as recent_hearings
            FROM committees c
            LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
            LEFT JOIN hearings h ON hc.hearing_id = h.hearing_id
            WHERE c.parent_committee_id IS NULL
            GROUP BY c.committee_id, c.chamber, c.name
            HAVING hearing_count > 0
            ORDER BY hearing_count DESC
            LIMIT 15
        ''')

        print("Top 15 committees by hearing count:")
        for row in cursor.fetchall():
            chamber, name, total, recent = row
            name_short = name[:50] + "..." if len(name) > 50 else name
            print(f"  {chamber[:1]}: {name_short:<53} | {total:3d} total, {recent:2d} recent")

        # 6. DATA QUALITY ISSUES
        print("\n6. DATA QUALITY ISSUES")
        print("-" * 40)

        # Duplicate event IDs
        cursor = conn.execute('''
            SELECT event_id, COUNT(*) as count
            FROM hearings
            WHERE event_id IS NOT NULL
            GROUP BY event_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC
            LIMIT 5
        ''')

        duplicates = cursor.fetchall()
        print(f"Duplicate event IDs: {len(duplicates)} cases")
        for dup in duplicates:
            print(f"  Event {dup[0]}: {dup[1]} duplicates")

        # Missing essential data
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE event_id IS NULL AND (title IS NULL OR title = '')
        ''')
        missing_key_data = cursor.fetchone()[0]
        print(f"Hearings missing both event_id and title: {missing_key_data}")

        # Committee relationship gaps
        cursor = conn.execute('''
            SELECT
                h.chamber,
                COUNT(*) as unassigned_count
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
            WHERE hc.hearing_id IS NULL
            AND h.event_id IS NOT NULL
            GROUP BY h.chamber
            ORDER BY unassigned_count DESC
        ''')

        print("\nUnassigned hearings by chamber:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} unassigned hearings")

        # 7. ENHANCEMENT OPPORTUNITIES
        print("\n7. ENHANCEMENT OPPORTUNITIES")
        print("-" * 40)

        # Hearings that could be enhanced
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings
            WHERE event_id IS NOT NULL
            AND (title IS NULL OR title = '' OR hearing_date_only IS NULL)
        ''')
        enhanceable = cursor.fetchone()[0]
        print(f"Hearings that could be enhanced via API: {enhanceable}")

        # Potential committee relationships via proximity
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings h1
            WHERE h1.event_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM hearing_committees hc WHERE hc.hearing_id = h1.hearing_id
            )
            AND EXISTS (
                SELECT 1 FROM hearings h2
                JOIN hearing_committees hc2 ON h2.hearing_id = hc2.hearing_id
                WHERE h2.chamber = h1.chamber
                AND h2.event_id IS NOT NULL
                AND ABS(CAST(h1.event_id AS INTEGER) - CAST(h2.event_id AS INTEGER)) <= 100
            )
        ''')
        proximity_candidates = cursor.fetchone()[0]
        print(f"Hearings that could be linked via event ID proximity: {proximity_candidates}")

        # Potential relationships via title keywords
        cursor = conn.execute('''
            SELECT COUNT(*) FROM hearings h
            WHERE h.title IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM hearing_committees hc WHERE hc.hearing_id = h.hearing_id
            )
            AND (
                h.title LIKE '%Agriculture%' OR h.title LIKE '%Farm%' OR
                h.title LIKE '%Defense%' OR h.title LIKE '%Armed Services%' OR
                h.title LIKE '%Finance%' OR h.title LIKE '%Banking%' OR
                h.title LIKE '%Judiciary%' OR h.title LIKE '%Justice%' OR
                h.title LIKE '%Education%' OR h.title LIKE '%Energy%' OR
                h.title LIKE '%Environment%' OR h.title LIKE '%Health%' OR
                h.title LIKE '%Veterans%' OR h.title LIKE '%Transportation%'
            )
        ''')
        keyword_candidates = cursor.fetchone()[0]
        print(f"Hearings that could be linked via title keywords: {keyword_candidates}")

        return {
            'total_hearings': total_hearings,
            'total_relationships': total_relationships,
            'unassigned_hearings': unassigned_hearings,
            'enhanceable_hearings': enhanceable,
            'proximity_candidates': proximity_candidates,
            'keyword_candidates': keyword_candidates
        }

if __name__ == "__main__":
    audit_results = audit_database()

    print(f"\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)
    print(f"Recommended next steps:")
    print(f"1. Enhance {audit_results['enhanceable_hearings']} hearings via API")
    print(f"2. Apply proximity inference to {audit_results['proximity_candidates']} candidates")
    print(f"3. Apply keyword matching to {audit_results['keyword_candidates']} candidates")
    print(f"4. Current unassigned hearings: {audit_results['unassigned_hearings']}")