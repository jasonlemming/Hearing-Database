"""
Committee-related routes blueprint
"""
from flask import Blueprint, render_template, request
from database.manager import DatabaseManager

committees_bp = Blueprint('committees', __name__)

# Initialize database manager
db = DatabaseManager()


@committees_bp.route('/committees')
def committees():
    """Browse committees"""
    try:
        chamber = request.args.get('chamber', '')
        committee_type = request.args.get('type', '')

        # Get parent committees with their subcommittees
        # Only count hearings that are exclusively associated with this committee
        query = '''
            SELECT c.committee_id, c.system_code, c.name, c.chamber, c.type,
                   COUNT(DISTINCT CASE
                       WHEN hc.hearing_id IN (
                           SELECT hearing_id
                           FROM hearing_committees hc2
                           WHERE hc2.hearing_id = hc.hearing_id
                           GROUP BY hearing_id
                           HAVING COUNT(*) = 1
                       ) THEN hc.hearing_id
                       ELSE NULL
                   END) as hearing_count,
                   COUNT(DISTINCT sub.committee_id) as subcommittee_count
            FROM committees c
            LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
            LEFT JOIN committees sub ON c.committee_id = sub.parent_committee_id
            WHERE c.parent_committee_id IS NULL
        '''
        params = []

        if chamber:
            query += ' AND c.chamber = ?'
            params.append(chamber)

        if committee_type:
            query += ' AND c.type = ?'
            params.append(committee_type)

        query += '''
            GROUP BY c.committee_id
            ORDER BY c.chamber, c.name
        '''

        with db.transaction() as conn:
            cursor = conn.execute(query, params)
            parent_committees = cursor.fetchall()

            # Get subcommittees for each parent
            committees_with_subs = []
            for parent in parent_committees:
                parent_id = parent[0]

                # Get subcommittees for this parent
                # Only count hearings that are exclusively associated with this subcommittee
                sub_query = '''
                    SELECT c.committee_id, c.system_code, c.name, c.chamber, c.type,
                           COUNT(DISTINCT CASE
                               WHEN hc.hearing_id IN (
                                   SELECT hearing_id
                                   FROM hearing_committees hc2
                                   WHERE hc2.hearing_id = hc.hearing_id
                                   GROUP BY hearing_id
                                   HAVING COUNT(*) = 1
                               ) THEN hc.hearing_id
                               ELSE NULL
                           END) as hearing_count
                    FROM committees c
                    LEFT JOIN hearing_committees hc ON c.committee_id = hc.committee_id
                    WHERE c.parent_committee_id = ?
                    GROUP BY c.committee_id
                    ORDER BY c.name
                '''
                cursor = conn.execute(sub_query, (parent_id,))
                subcommittees = cursor.fetchall()

                committees_with_subs.append({
                    'parent': parent,
                    'subcommittees': subcommittees
                })

            # Get filter options
            cursor = conn.execute('SELECT DISTINCT chamber FROM committees ORDER BY chamber')
            rows = cursor.fetchall()
            chambers = [row.get('chamber', row[0]) if hasattr(row, 'keys') else row[0] for row in rows]

            cursor = conn.execute('SELECT DISTINCT type FROM committees ORDER BY type')
            rows = cursor.fetchall()
            types = [row.get('type', row[0]) if hasattr(row, 'keys') else row[0] for row in rows]

            # Get parent committees only for the selector dropdown
            cursor = conn.execute('''
                SELECT committee_id, name, chamber
                FROM committees
                WHERE is_current = 1 AND parent_committee_id IS NULL
                ORDER BY chamber, name
            ''')
            all_committees = cursor.fetchall()

        return render_template('committees.html',
                             committees_hierarchy=committees_with_subs,
                             chambers=chambers,
                             types=types,
                             selected_chamber=chamber,
                             selected_type=committee_type,
                             sort_by='chamber',
                             sort_order='asc')
    except Exception as e:
        return f"Error: {e}", 500


@committees_bp.route('/committee/<int:committee_id>')
def committee_detail(committee_id):
    """Committee detail page"""
    try:
        with db.transaction() as conn:
            # Get committee info
            cursor = conn.execute('''
                SELECT c.*, parent.name as parent_name
                FROM committees c
                LEFT JOIN committees parent ON c.parent_committee_id = parent.committee_id
                WHERE c.committee_id = ?
            ''', (committee_id,))
            committee = cursor.fetchone()

            if not committee:
                return "Committee not found", 404

            # Get hearings for this committee
            cursor = conn.execute('''
                SELECT h.hearing_id, h.title, h.hearing_date, h.status, h.hearing_type,
                       hc.is_primary
                FROM hearings h
                JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                WHERE hc.committee_id = ?
                ORDER BY h.hearing_date DESC NULLS LAST, h.updated_at DESC
            ''', (committee_id,))
            hearings = cursor.fetchall()

            # Get subcommittees
            cursor = conn.execute('''
                SELECT committee_id, system_code, name, type
                FROM committees
                WHERE parent_committee_id = ?
                ORDER BY name
            ''', (committee_id,))
            subcommittees = cursor.fetchall()

        return render_template('committee_detail.html',
                             committee=committee,
                             hearings=hearings,
                             subcommittees=subcommittees)
    except Exception as e:
        return f"Error: {e}", 500


