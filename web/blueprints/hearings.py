"""
Hearing-related routes blueprint
"""
from flask import Blueprint, render_template, request
from database.unified_manager import UnifiedDatabaseManager
from datetime import datetime, timedelta, date

hearings_bp = Blueprint('hearings', __name__)

# Initialize database manager (auto-detects Postgres if POSTGRES_URL is set)
db = UnifiedDatabaseManager()


@hearings_bp.route('/hearings')
def hearings():
    """Browse hearings"""
    try:
        search = request.args.get('search', '')
        chamber = request.args.get('chamber', '')
        committee_id = request.args.get('committee', '')

        # Default to current week if no dates provided
        today = datetime.now()
        # Calculate Monday of current week (weekday 0 = Monday)
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        # Calculate Sunday of current week
        sunday = monday + timedelta(days=6)

        date_from = request.args.get('date_from', monday.strftime('%Y-%m-%d'))
        date_to = request.args.get('date_to', sunday.strftime('%Y-%m-%d'))
        sort_by = request.args.get('sort', 'date')
        sort_order = request.args.get('order', 'desc')
        page = int(request.args.get('page', 1))
        per_page = 20
        offset = (page - 1) * per_page

        # Build query - show all hearings, with committee info when available
        # Show parent committee if the associated committee is a subcommittee
        # Prefer primary committee, but fall back to any committee if no primary exists
        query = '''
            SELECT h.hearing_id, h.title, h.hearing_date_only, h.hearing_time, h.chamber, h.status, h.hearing_type,
                   COALESCE(parent_primary.name, c_primary.name, parent_any.name, c_any.name) as committee_name,
                   COALESCE(parent_primary.committee_id, c_primary.committee_id, parent_any.committee_id, c_any.committee_id) as committee_id,
                   h.updated_at, h.event_id
            FROM hearings h
            LEFT JOIN hearing_committees hc_primary ON h.hearing_id = hc_primary.hearing_id AND hc_primary.is_primary = TRUE
            LEFT JOIN committees c_primary ON hc_primary.committee_id = c_primary.committee_id
            LEFT JOIN committees parent_primary ON c_primary.parent_committee_id = parent_primary.committee_id
            LEFT JOIN hearing_committees hc_any ON h.hearing_id = hc_any.hearing_id
                AND NOT EXISTS (SELECT 1 FROM hearing_committees WHERE hearing_id = h.hearing_id AND is_primary = TRUE)
            LEFT JOIN committees c_any ON hc_any.committee_id = c_any.committee_id
            LEFT JOIN committees parent_any ON c_any.parent_committee_id = parent_any.committee_id
            WHERE 1=1
        '''
        params = []

        if search:
            query += ''' AND (h.title LIKE ?
                         OR c_primary.name LIKE ? OR parent_primary.name LIKE ?
                         OR c_any.name LIKE ? OR parent_any.name LIKE ?)'''
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term, search_term, search_term])

        if chamber:
            query += ' AND h.chamber = ?'
            params.append(chamber)

        if committee_id:
            query += ''' AND (c_primary.committee_id = ? OR parent_primary.committee_id = ?
                          OR c_any.committee_id = ? OR parent_any.committee_id = ?)'''
            params.extend([committee_id, committee_id, committee_id, committee_id])

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
                'committee': 'COALESCE(parent_primary.name, c_primary.name, parent_any.name, c_any.name)',
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

        # Determine active filter based on date range
        active_filter = 'all'
        if date_from and date_to:
            # Check if it's today
            if date_from == date_to == today.strftime('%Y-%m-%d'):
                active_filter = 'today'
            # Check if it's this week
            elif date_from == monday.strftime('%Y-%m-%d') and date_to == sunday.strftime('%Y-%m-%d'):
                active_filter = 'this-week'
            # Check if it's this month
            else:
                month_start = today.replace(day=1)
                # Get last day of month
                if today.month == 12:
                    month_end = today.replace(day=31)
                else:
                    month_end = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
                if date_from == month_start.strftime('%Y-%m-%d') and date_to == month_end.strftime('%Y-%m-%d'):
                    active_filter = 'this-month'
        elif not date_from and not date_to:
            active_filter = 'all'

        return render_template('hearings_v2.html',
                             hearings=hearings_data,
                             chambers=chambers,
                             committees=committees_with_hearings,
                             search=search,
                             selected_chamber=chamber,
                             selected_committee=committee_id,
                             date_from=date_from,
                             date_to=date_to,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             page=page,
                             total_pages=total_pages,
                             has_prev=has_prev,
                             has_next=has_next,
                             total=total,
                             active_filter=active_filter)
    except Exception as e:
        return f"Error: {e}", 500


@hearings_bp.route('/hearing/<int:hearing_id>')
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

            # Get hearing transcripts
            cursor = conn.execute('''
                SELECT transcript_id, jacket_number, title, document_url, pdf_url, html_url, format_type
                FROM hearing_transcripts
                WHERE hearing_id = ?
                ORDER BY created_at DESC
            ''', (hearing_id,))
            transcripts = cursor.fetchall()

            # Get witness documents
            cursor = conn.execute('''
                SELECT wd.document_id, w.witness_id, w.full_name, wd.title, wd.document_url, wd.format_type, wd.document_type
                FROM witness_documents wd
                JOIN witness_appearances wa ON wd.appearance_id = wa.appearance_id
                JOIN witnesses w ON wa.witness_id = w.witness_id
                WHERE wa.hearing_id = ?
                ORDER BY w.last_name, w.first_name
            ''', (hearing_id,))
            witness_documents = cursor.fetchall()

            # Get supporting documents
            cursor = conn.execute('''
                SELECT document_id, title, document_url, format_type, document_type, description
                FROM supporting_documents
                WHERE hearing_id = ?
                ORDER BY created_at DESC
            ''', (hearing_id,))
            supporting_documents = cursor.fetchall()

        return render_template('hearing_detail_v2.html',
                             hearing=hearing,
                             committees=committees,
                             witnesses=witnesses,
                             transcripts=transcripts,
                             witness_documents=witness_documents,
                             supporting_documents=supporting_documents,
                             today=date.today())
    except Exception as e:
        return f"Error: {e}", 500