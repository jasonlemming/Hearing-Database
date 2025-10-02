#!/usr/bin/env python3
"""
Flask web application for Congressional Hearing Database
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, redirect, url_for
from database.manager import DatabaseManager
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'congressional-hearing-db-secret-key'

# Add custom date filters for template
@app.template_filter('strptime')
def strptime_filter(date_string, format):
    """Parse date string into datetime object"""
    return datetime.strptime(date_string, format)

@app.template_filter('strftime')
def strftime_filter(date_obj, format):
    """Format datetime object as string"""
    return date_obj.strftime(format)

@app.template_filter('congress_gov_url')
def congress_gov_url_filter(hearing):
    """Generate Congress.gov URL for a hearing"""
    if not hearing or not hearing[1] or not hearing[2] or not hearing[3]:  # event_id, congress, chamber
        return None

    event_id = hearing[1]
    congress = hearing[2]
    chamber = hearing[3].lower()

    return f"https://www.congress.gov/event/{congress}th-congress/{chamber}-event/{event_id}"

# Initialize database manager
db = DatabaseManager()

@app.route('/')
def index():
    """Redirect to hearings page"""
    return redirect(url_for('hearings'))

@app.route('/committees')
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
            chambers = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute('SELECT DISTINCT type FROM committees ORDER BY type')
            types = [row[0] for row in cursor.fetchall()]

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
                             all_committees=all_committees,
                             selected_chamber=chamber,
                             selected_type=committee_type)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/committee/<int:committee_id>')
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

@app.route('/hearings')
def hearings():
    """Browse hearings"""
    try:
        search = request.args.get('search', '')
        chamber = request.args.get('chamber', '')
        committee_id = request.args.get('committee', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        sort_by = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        # Build query - show all hearings, with committee info when available
        # Show parent committee if the associated committee is a subcommittee
        query = '''
            SELECT h.hearing_id, h.title, h.hearing_date_only, h.hearing_time, h.chamber, h.status, h.hearing_type,
                   COALESCE(parent.name, c.name) as committee_name,
                   COALESCE(parent.committee_id, c.committee_id) as committee_id,
                   h.updated_at, h.event_id
            FROM hearings h
            LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id AND hc.is_primary = 1
            LEFT JOIN committees c ON hc.committee_id = c.committee_id
            LEFT JOIN committees parent ON c.parent_committee_id = parent.committee_id
            WHERE 1=1
        '''
        params = []

        if search:
            query += ' AND (h.title LIKE ? OR c.name LIKE ? OR parent.name LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])

        if chamber:
            query += ' AND h.chamber = ?'
            params.append(chamber)

        if committee_id:
            query += ' AND (c.committee_id = ? OR parent.committee_id = ?)'
            params.extend([committee_id, committee_id])

        if date_from:
            query += ' AND h.hearing_date_only >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND h.hearing_date_only <= ?'
            params.append(date_to)

        # Count total for pagination
        count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"

        with db.transaction() as conn:
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Add sorting
            sort_columns = {
                'title': 'h.title',
                'committee': 'COALESCE(parent.name, c.name)',
                'date': 'h.hearing_date_only',
                'chamber': 'h.chamber',
                'status': 'h.status'
            }

            sort_column = sort_columns.get(sort_by, 'h.hearing_date_only')
            sort_direction = 'ASC' if sort_order == 'asc' else 'DESC'

            # Special handling for date sorting (nulls last for DESC, nulls first for ASC)
            if sort_by == 'date':
                if sort_order == 'desc':
                    query += f' ORDER BY {sort_column} DESC NULLS LAST, h.hearing_time DESC NULLS LAST, h.updated_at DESC'
                else:
                    query += f' ORDER BY {sort_column} ASC NULLS FIRST, h.hearing_time ASC NULLS FIRST, h.updated_at ASC'
            else:
                query += f' ORDER BY {sort_column} {sort_direction}, h.hearing_date_only DESC NULLS LAST'

            # Get page of results
            query += ' LIMIT ? OFFSET ?'
            params.extend([per_page, offset])

            cursor = conn.execute(query, params)
            hearings_data = cursor.fetchall()

            # Get filter options
            cursor = conn.execute('SELECT DISTINCT chamber FROM hearings ORDER BY chamber')
            chambers = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute('''
                SELECT DISTINCT
                    COALESCE(parent.committee_id, c.committee_id) as committee_id,
                    COALESCE(parent.name, c.name) as committee_name
                FROM committees c
                JOIN hearing_committees hc ON c.committee_id = hc.committee_id
                LEFT JOIN committees parent ON c.parent_committee_id = parent.committee_id
                ORDER BY committee_name
            ''')
            committees_with_hearings = cursor.fetchall()

        # Pagination info
        total_pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

        return render_template('hearings.html',
                             hearings=hearings_data,
                             chambers=chambers,
                             committees=committees_with_hearings,
                             search=search,
                             selected_chamber=chamber,
                             selected_committee=committee_id,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total=total)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/hearing/<int:hearing_id>')
def hearing_detail(hearing_id):
    """Hearing detail page"""
    try:
        with db.transaction() as conn:
            # Get hearing info
            cursor = conn.execute('SELECT * FROM hearings WHERE hearing_id = ?', (hearing_id,))
            hearing = cursor.fetchone()

            if not hearing:
                return "Hearing not found", 404

            # Get associated committees
            cursor = conn.execute('''
                SELECT c.committee_id, c.name, c.system_code, hc.is_primary
                FROM committees c
                JOIN hearing_committees hc ON c.committee_id = hc.committee_id
                WHERE hc.hearing_id = ?
                ORDER BY hc.is_primary DESC, c.name
            ''', (hearing_id,))
            committees = cursor.fetchall()

            # Get witnesses for this hearing
            cursor = conn.execute('''
                SELECT w.witness_id, w.full_name, w.first_name, w.last_name, w.title, w.organization,
                       wa.witness_type, wa.appearance_order, wa.position
                FROM witnesses w
                JOIN witness_appearances wa ON w.witness_id = wa.witness_id
                WHERE wa.hearing_id = ?
                ORDER BY wa.appearance_order, w.last_name, w.first_name
            ''', (hearing_id,))
            witnesses = cursor.fetchall()

        return render_template('hearing_detail.html', hearing=hearing, committees=committees, witnesses=witnesses)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/members')
def members():
    """Browse members"""
    try:
        search = request.args.get('search', '')
        party = request.args.get('party', '')
        state = request.args.get('state', '')
        chamber = request.args.get('chamber', '')
        committee = request.args.get('committee', '')

        query = '''
            SELECT DISTINCT m.member_id, m.full_name, m.party, m.state, m.district,
                   COUNT(DISTINCT cm.committee_id) as committee_count
            FROM members m
            LEFT JOIN committee_memberships cm ON m.member_id = cm.member_id AND cm.is_active = 1
            LEFT JOIN committees c ON cm.committee_id = c.committee_id
            WHERE 1=1
        '''
        params = []

        if search:
            query += ' AND m.full_name LIKE ?'
            params.append(f'%{search}%')

        if party:
            query += ' AND m.party = ?'
            params.append(party)

        if state:
            query += ' AND m.state = ?'
            params.append(state)

        if chamber:
            query += ' AND c.chamber = ?'
            params.append(chamber)

        if committee:
            query += ' AND cm.committee_id = ?'
            params.append(committee)

        query += '''
            GROUP BY m.member_id, m.full_name, m.party, m.state, m.district
            ORDER BY m.last_name, m.first_name
        '''

        with db.transaction() as conn:
            cursor = conn.execute(query, params)
            members_data = cursor.fetchall()

            # Get filter options
            cursor = conn.execute('SELECT DISTINCT party FROM members ORDER BY party')
            parties = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute('SELECT DISTINCT state FROM members ORDER BY state')
            states = [row[0] for row in cursor.fetchall()]

            # Get chambers from committees that have members
            cursor = conn.execute('''
                SELECT DISTINCT c.chamber
                FROM committees c
                JOIN committee_memberships cm ON c.committee_id = cm.committee_id
                WHERE cm.is_active = 1
                ORDER BY c.chamber
            ''')
            chambers = [row[0] for row in cursor.fetchall()]

            # Get committees that have members
            cursor = conn.execute('''
                SELECT DISTINCT c.committee_id, c.name
                FROM committees c
                JOIN committee_memberships cm ON c.committee_id = cm.committee_id
                WHERE cm.is_active = 1 AND c.parent_committee_id IS NULL
                ORDER BY c.name
            ''')
            committees = cursor.fetchall()

        return render_template('members.html',
                             members=members_data,
                             parties=parties,
                             states=states,
                             chambers=chambers,
                             committees=committees,
                             search=search,
                             selected_party=party,
                             selected_state=state,
                             selected_chamber=chamber,
                             selected_committee=committee)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/search')
def search():
    """Global search page"""
    query = request.args.get('q', '')

    if not query:
        return render_template('search.html', query='', results={})

    try:
        results = {
            'committees': [],
            'hearings': [],
            'members': [],
            'witnesses': []
        }

        search_term = f'%{query}%'

        with db.transaction() as conn:
            # Search committees
            cursor = conn.execute('''
                SELECT committee_id, name, chamber, type
                FROM committees
                WHERE name LIKE ?
                ORDER BY name
                LIMIT 10
            ''', (search_term,))
            results['committees'] = cursor.fetchall()

            # Search hearings
            cursor = conn.execute('''
                SELECT h.hearing_id, h.title, h.hearing_date, c.name as committee_name
                FROM hearings h
                LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id AND hc.is_primary = 1
                LEFT JOIN committees c ON hc.committee_id = c.committee_id
                WHERE h.title LIKE ?
                ORDER BY h.hearing_date DESC NULLS LAST
                LIMIT 10
            ''', (search_term,))
            results['hearings'] = cursor.fetchall()

            # Search members
            cursor = conn.execute('''
                SELECT member_id, full_name, party, state, district
                FROM members
                WHERE full_name LIKE ?
                ORDER BY last_name, first_name
                LIMIT 10
            ''', (search_term,))
            results['members'] = cursor.fetchall()

            # Search witnesses
            cursor = conn.execute('''
                SELECT w.witness_id, w.full_name, w.organization, wa.witness_type,
                       COUNT(DISTINCT wa.hearing_id) as hearing_count
                FROM witnesses w
                LEFT JOIN witness_appearances wa ON w.witness_id = wa.witness_id
                WHERE w.full_name LIKE ? OR w.organization LIKE ?
                GROUP BY w.witness_id
                ORDER BY w.full_name
                LIMIT 10
            ''', (search_term, search_term))
            results['witnesses'] = cursor.fetchall()

        return render_template('search.html', query=query, results=results)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/witnesses')
def witnesses():
    """Browse witnesses"""
    try:
        search = request.args.get('search', '')
        witness_type = request.args.get('type', '')
        organization = request.args.get('organization', '')
        sort_by = request.args.get('sort', 'name')
        sort_order = request.args.get('order', 'asc')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        # Build query for witnesses with hearing information
        query = '''
            SELECT w.witness_id, w.full_name, w.first_name, w.last_name, w.title, w.organization,
                   wa.witness_type,
                   COUNT(DISTINCT wa.hearing_id) as hearing_count,
                   GROUP_CONCAT(h.title, '|||') as hearing_titles,
                   GROUP_CONCAT(wa.hearing_id, '|||') as hearing_ids
            FROM witnesses w
            LEFT JOIN witness_appearances wa ON w.witness_id = wa.witness_id
            LEFT JOIN hearings h ON wa.hearing_id = h.hearing_id
            WHERE 1=1
        '''
        params = []

        if search:
            query += ' AND (w.full_name LIKE ? OR w.organization LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term])

        if witness_type:
            query += ' AND wa.witness_type = ?'
            params.append(witness_type)

        if organization:
            query += ' AND w.organization LIKE ?'
            params.append(f'%{organization}%')

        query += ' GROUP BY w.witness_id'

        # Count total for pagination
        count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"

        with db.transaction() as conn:
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Add sorting
            sort_columns = {
                'name': 'w.full_name',
                'organization': 'w.organization',
                'type': 'wa.witness_type',
                'hearings': 'hearing_count'
            }

            sort_column = sort_columns.get(sort_by, 'w.full_name')
            sort_direction = 'ASC' if sort_order == 'asc' else 'DESC'
            query += f' ORDER BY {sort_column} {sort_direction}'

            # Get page of results
            query += ' LIMIT ? OFFSET ?'
            params.extend([per_page, offset])

            cursor = conn.execute(query, params)
            witnesses_data = cursor.fetchall()

            # Get filter options
            cursor = conn.execute('SELECT DISTINCT witness_type FROM witness_appearances WHERE witness_type IS NOT NULL ORDER BY witness_type')
            witness_types = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute('SELECT DISTINCT organization FROM witnesses WHERE organization IS NOT NULL ORDER BY organization')
            organizations = [row[0] for row in cursor.fetchall()]

        # Pagination info
        total_pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

        return render_template('witnesses.html',
                             witnesses=witnesses_data,
                             witness_types=witness_types,
                             organizations=organizations,
                             search=search,
                             selected_type=witness_type,
                             selected_organization=organization,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total=total)
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/api/witness-import-status')
def api_witness_import_status():
    """API endpoint for witness import progress"""
    try:
        with db.transaction() as conn:
            status = {}

            # Total hearings available for import
            cursor = conn.execute('SELECT COUNT(*) FROM hearings WHERE event_id IS NOT NULL AND event_id != ""')
            status['total_hearings'] = cursor.fetchone()[0]

            # Hearings with witnesses imported
            cursor = conn.execute('''
                SELECT COUNT(DISTINCT h.hearing_id)
                FROM hearings h
                JOIN witness_appearances wa ON h.hearing_id = wa.hearing_id
                WHERE h.event_id IS NOT NULL AND h.event_id != ""
            ''')
            status['hearings_with_witnesses'] = cursor.fetchone()[0]

            # Total witnesses and appearances
            cursor = conn.execute('SELECT COUNT(*) FROM witnesses')
            status['total_witnesses'] = cursor.fetchone()[0]

            cursor = conn.execute('SELECT COUNT(*) FROM witness_appearances')
            status['total_appearances'] = cursor.fetchone()[0]

            # Recent import activity (witnesses added in last hour) - skip if no created_at column
            try:
                cursor = conn.execute('''
                    SELECT COUNT(*) FROM witnesses
                    WHERE created_at > datetime('now', '-1 hour')
                ''')
                status['recent_witnesses'] = cursor.fetchone()[0]
            except:
                status['recent_witnesses'] = 0

            # Calculate progress percentage
            if status['total_hearings'] > 0:
                status['progress_percentage'] = round((status['hearings_with_witnesses'] / status['total_hearings']) * 100, 1)
            else:
                status['progress_percentage'] = 0

            # Estimate completion
            status['is_complete'] = status['progress_percentage'] >= 95.0

            return jsonify(status)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """API endpoint for database statistics"""
    try:
        with db.transaction() as conn:
            stats = {}
            tables = ['committees', 'members', 'hearings', 'hearing_committees', 'policy_areas']

            for table in tables:
                cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                stats[table] = cursor.fetchone()[0]

        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update-status')
def update_status():
    """API endpoint to get daily update status and history"""
    try:
        with db.transaction() as conn:
            # Check if update_logs table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='update_logs'
            """)

            if not cursor.fetchone():
                return jsonify({
                    'status': 'no_logs',
                    'message': 'Update logging not yet configured',
                    'last_update': None,
                    'recent_updates': []
                })

            # Get most recent update
            cursor = conn.execute("""
                SELECT * FROM update_logs
                ORDER BY start_time DESC
                LIMIT 1
            """)
            latest = cursor.fetchone()

            # Get recent updates (last 7 days)
            cursor = conn.execute("""
                SELECT update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, success
                FROM update_logs
                WHERE update_date >= date('now', '-7 days')
                ORDER BY start_time DESC
            """)
            recent_updates = []
            for row in cursor.fetchall():
                recent_updates.append({
                    'date': row[0],
                    'start_time': row[1],
                    'end_time': row[2],
                    'duration_seconds': row[3],
                    'hearings_checked': row[4],
                    'hearings_updated': row[5],
                    'hearings_added': row[6],
                    'committees_updated': row[7],
                    'witnesses_updated': row[8],
                    'api_requests': row[9],
                    'error_count': row[10],
                    'success': bool(row[11])
                })

            last_update = None
            if latest:
                last_update = {
                    'date': latest[1],  # update_date
                    'start_time': latest[2],  # start_time
                    'end_time': latest[3],  # end_time
                    'duration_seconds': latest[4],
                    'hearings_checked': latest[5],
                    'hearings_updated': latest[6],
                    'hearings_added': latest[7],
                    'success': bool(latest[12])
                }

            # Calculate status
            status = 'unknown'
            if latest:
                if latest[12]:  # success
                    # Check if update was today
                    update_date = datetime.fromisoformat(latest[2]).date()
                    if update_date == datetime.now().date():
                        status = 'updated_today'
                    else:
                        status = 'last_update_successful'
                else:
                    status = 'last_update_failed'

            return jsonify({
                'status': status,
                'last_update': last_update,
                'recent_updates': recent_updates,
                'total_recent_updates': len(recent_updates)
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/updates')
def admin_updates():
    """Admin page to view update history and status"""
    try:
        with db.transaction() as conn:
            # Check if update_logs table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='update_logs'
            """)

            if not cursor.fetchone():
                return render_template('admin_updates.html',
                                     updates=[],
                                     table_exists=False)

            # Get update history (last 30 days)
            cursor = conn.execute("""
                SELECT log_id, update_date, start_time, end_time, duration_seconds,
                       hearings_checked, hearings_updated, hearings_added,
                       committees_updated, witnesses_updated, api_requests,
                       error_count, errors, success, created_at
                FROM update_logs
                WHERE update_date >= date('now', '-30 days')
                ORDER BY start_time DESC
                LIMIT 50
            """)

            updates = []
            for row in cursor.fetchall():
                errors_json = row[12]
                error_list = []
                if errors_json:
                    try:
                        import json
                        error_list = json.loads(errors_json)
                    except:
                        error_list = [errors_json]

                updates.append({
                    'log_id': row[0],
                    'update_date': row[1],
                    'start_time': row[2],
                    'end_time': row[3],
                    'duration_seconds': row[4],
                    'hearings_checked': row[5],
                    'hearings_updated': row[6],
                    'hearings_added': row[7],
                    'committees_updated': row[8],
                    'witnesses_updated': row[9],
                    'api_requests': row[10],
                    'error_count': row[11],
                    'errors': error_list,
                    'success': bool(row[13]),
                    'created_at': row[14]
                })

            return render_template('admin_updates.html',
                                 updates=updates,
                                 table_exists=True)

    except Exception as e:
        return f"Error: {e}", 500


if __name__ == '__main__':
    # Install Flask if not already installed
    try:
        import flask
    except ImportError:
        os.system('pip install flask')

    app.run(host='0.0.0.0', port=3000, debug=True)