"""
Main pages blueprint - members, witnesses, and search
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import Blueprint, render_template, request
from database.manager import DatabaseManager

main_pages_bp = Blueprint('main_pages', __name__)

# Initialize database manager
db = DatabaseManager()


@main_pages_bp.route('/members')
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
                   COUNT(DISTINCT cm.committee_id) as committee_count,
                   CASE
                       WHEN m.district IS NULL THEN 'Senate'
                       ELSE 'House'
                   END as chamber
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
            if chamber == 'House':
                query += ' AND m.district IS NOT NULL'
            elif chamber == 'Senate':
                query += ' AND m.district IS NULL'

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

            # Get chambers from member data
            chambers = ['House', 'Senate']

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


@main_pages_bp.route('/witnesses')
def witnesses():
    """Browse witnesses"""
    try:
        search = request.args.get('search', '')
        witness_type = request.args.get('type', '')
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

        # Pagination info
        total_pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

        return render_template('witnesses.html',
                             witnesses=witnesses_data,
                             witness_types=witness_types,
                             search=search,
                             selected_type=witness_type,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total=total)
    except Exception as e:
        return f"Error: {e}", 500


@main_pages_bp.route('/member/<int:member_id>')
def member_detail(member_id):
    """Member detail page"""
    try:
        with db.transaction() as conn:
            # Get member details
            cursor = conn.execute('''
                SELECT member_id, bioguide_id, first_name, middle_name, last_name, full_name,
                       party, state, district, birth_year, current_member, honorific_prefix,
                       official_url, office_address, phone, terms_served, congress,
                       CASE WHEN district IS NULL THEN 'Senate' ELSE 'House' END as chamber
                FROM members
                WHERE member_id = ?
            ''', (member_id,))
            member = cursor.fetchone()

            if not member:
                return "Member not found", 404

            # Get committee memberships
            cursor = conn.execute('''
                SELECT c.committee_id, c.name, c.chamber, c.type, cm.role, cm.is_active,
                       c.parent_committee_id, pc.name as parent_committee_name
                FROM committee_memberships cm
                JOIN committees c ON cm.committee_id = c.committee_id
                LEFT JOIN committees pc ON c.parent_committee_id = pc.committee_id
                WHERE cm.member_id = ? AND cm.is_active = 1
                ORDER BY c.parent_committee_id IS NULL DESC, c.name
            ''', (member_id,))
            committees = cursor.fetchall()

            # Get recent hearings this member's committees have participated in
            cursor = conn.execute('''
                SELECT DISTINCT h.hearing_id, h.title, h.hearing_date, h.chamber, c.name as committee_name
                FROM hearings h
                JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                JOIN committees c ON hc.committee_id = c.committee_id
                JOIN committee_memberships cm ON c.committee_id = cm.committee_id
                WHERE cm.member_id = ? AND cm.is_active = 1
                ORDER BY h.hearing_date DESC NULLS LAST
                LIMIT 10
            ''', (member_id,))
            recent_hearings = cursor.fetchall()

        return render_template('member_detail.html',
                             member=member,
                             committees=committees,
                             recent_hearings=recent_hearings)
    except Exception as e:
        return f"Error: {e}", 500


@main_pages_bp.route('/witness/<int:witness_id>')
def witness_detail(witness_id):
    """Witness detail page"""
    try:
        with db.transaction() as conn:
            # Get witness details
            cursor = conn.execute('''
                SELECT witness_id, first_name, last_name, full_name, title, organization,
                       created_at, updated_at
                FROM witnesses
                WHERE witness_id = ?
            ''', (witness_id,))
            witness = cursor.fetchone()

            if not witness:
                return "Witness not found", 404

            # Get all hearings this witness appeared at with detailed information
            cursor = conn.execute('''
                SELECT h.hearing_id, h.title, h.hearing_date, h.chamber, h.congress,
                       h.location, h.status, h.hearing_type,
                       wa.position, wa.witness_type, wa.appearance_order,
                       c.name as primary_committee_name, c.committee_id as primary_committee_id
                FROM witness_appearances wa
                JOIN hearings h ON wa.hearing_id = h.hearing_id
                LEFT JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id AND hc.is_primary = 1
                LEFT JOIN committees c ON hc.committee_id = c.committee_id
                WHERE wa.witness_id = ?
                ORDER BY h.hearing_date DESC NULLS LAST, wa.appearance_order ASC
            ''', (witness_id,))
            appearances = cursor.fetchall()

            # Get summary statistics
            cursor = conn.execute('''
                SELECT
                    COUNT(DISTINCT wa.hearing_id) as total_hearings,
                    COUNT(DISTINCT h.chamber) as chambers_count,
                    MIN(h.hearing_date) as first_appearance,
                    MAX(h.hearing_date) as latest_appearance,
                    SUM(CASE WHEN wa.witness_type = 'Government' THEN 1 ELSE 0 END) as govt_appearances,
                    SUM(CASE WHEN wa.witness_type = 'Private' THEN 1 ELSE 0 END) as private_appearances,
                    SUM(CASE WHEN wa.witness_type = 'Academic' THEN 1 ELSE 0 END) as academic_appearances,
                    SUM(CASE WHEN wa.witness_type = 'Nonprofit' THEN 1 ELSE 0 END) as nonprofit_appearances
                FROM witness_appearances wa
                JOIN hearings h ON wa.hearing_id = h.hearing_id
                WHERE wa.witness_id = ?
            ''', (witness_id,))
            stats = cursor.fetchone()

            # Get committees this witness has appeared before
            cursor = conn.execute('''
                SELECT DISTINCT c.committee_id, c.name, c.chamber, c.type,
                       COUNT(DISTINCT wa.hearing_id) as hearing_count
                FROM witness_appearances wa
                JOIN hearings h ON wa.hearing_id = h.hearing_id
                JOIN hearing_committees hc ON h.hearing_id = hc.hearing_id
                JOIN committees c ON hc.committee_id = c.committee_id
                WHERE wa.witness_id = ?
                GROUP BY c.committee_id
                ORDER BY hearing_count DESC, c.name
            ''', (witness_id,))
            committees = cursor.fetchall()

        return render_template('witness_detail.html',
                             witness=witness,
                             appearances=appearances,
                             stats=stats,
                             committees=committees)
    except Exception as e:
        return f"Error: {e}", 500


@main_pages_bp.route('/search')
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