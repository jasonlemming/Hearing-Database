"""
Main pages blueprint - members, witnesses, and search
"""
from flask import Blueprint, render_template, request
from database.manager import DatabaseManager

main_pages_bp = Blueprint('main_pages', __name__)

# Initialize database manager
db = DatabaseManager()


@main_pages_bp.route('/members')
def members():
    """Browse members"""
    try:
        party = request.args.get('party', '')
        state = request.args.get('state', '')
        chamber = request.args.get('chamber', '')
        sort_by = request.args.get('sort', 'name')
        sort_order = request.args.get('order', 'asc')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        query = '''
            SELECT DISTINCT m.member_id, m.full_name, m.party, m.state, m.district,
                   COUNT(DISTINCT cm.committee_id) as committee_count,
                   CASE
                       WHEN m.district IS NULL THEN 'Senate'
                       ELSE 'House'
                   END as chamber
            FROM members m
            LEFT JOIN committee_memberships cm ON m.member_id = cm.member_id AND cm.is_active = 1
            WHERE 1=1
        '''
        params = []

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

        query += ' GROUP BY m.member_id, m.full_name, m.party, m.state, m.district'

        # Count total for pagination
        count_query = f"SELECT COUNT(*) FROM ({query}) as count_query"

        with db.transaction() as conn:
            cursor = conn.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Add sorting
            sort_columns = {
                'name': 'm.full_name',
                'party': 'm.party',
                'state': 'm.state',
                'chamber': 'chamber',
                'committees': 'committee_count'
            }

            sort_column = sort_columns.get(sort_by, 'm.full_name')
            sort_direction = 'ASC' if sort_order == 'asc' else 'DESC'

            query += f' ORDER BY {sort_column} {sort_direction}'

            # Get page of results
            query += ' LIMIT ? OFFSET ?'
            params.extend([per_page, offset])

            cursor = conn.execute(query, params)
            members_data = cursor.fetchall()

            # Get filter options
            cursor = conn.execute('SELECT DISTINCT party FROM members WHERE party IS NOT NULL ORDER BY party')
            parties = [row[0] for row in cursor.fetchall()]

            cursor = conn.execute('SELECT DISTINCT state FROM members WHERE state IS NOT NULL ORDER BY state')
            states = [row[0] for row in cursor.fetchall()]

            chambers = ['House', 'Senate']

        # Pagination info
        total_pages = (total + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages

        return render_template('members.html',
                             members=members_data,
                             parties=parties,
                             states=states,
                             chambers=chambers,
                             selected_party=party,
                             selected_state=state,
                             selected_chamber=chamber,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total=total)
    except Exception as e:
        return f"Error: {e}", 500


@main_pages_bp.route('/witnesses')
def witnesses():
    """Browse witnesses"""
    try:
        search = request.args.get('search', '')
        witness_type = request.args.get('type', '')
        sort_by = request.args.get('sort', 'recent')
        sort_order = request.args.get('order', 'desc')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        # Build query for witnesses with hearing information
        query = '''
            SELECT w.witness_id, w.full_name, w.first_name, w.last_name, w.title, w.organization,
                   wa.witness_type,
                   COUNT(DISTINCT wa.hearing_id) as hearing_count,
                   MAX(h.hearing_date) as latest_appearance
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
                'hearings': 'hearing_count',
                'recent': 'latest_appearance'
            }

            sort_column = sort_columns.get(sort_by, 'w.full_name')
            sort_direction = 'ASC' if sort_order == 'asc' else 'DESC'

            # Handle NULL values for organization and latest_appearance
            if sort_by == 'organization':
                query += f' ORDER BY {sort_column} IS NULL, {sort_column} {sort_direction}'
            elif sort_by == 'recent':
                query += f' ORDER BY {sort_column} DESC NULLS LAST'
            else:
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


@main_pages_bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')


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