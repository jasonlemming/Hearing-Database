"""
Policy Library blueprint - browse and search multi-source policy research
"""
from flask import Blueprint, render_template, request, Response, jsonify
from sqlalchemy import func, desc
from sqlalchemy.orm import joinedload
import json
import csv
import io
import re
import sys
import os

# Add project root to path (works both locally and on Vercel)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from brookings_ingester.models import get_session, Document, Author, Subject, Source, DocumentAuthor, DocumentSubject
from datetime import datetime
from markupsafe import Markup, escape

policy_library_bp = Blueprint('policy_library', __name__, url_prefix='/library')

# PostgreSQL database configuration
# Use BROOKINGS_DATABASE_URL environment variable (separate from main DATABASE_URL)
def ensure_brookings_database_configured():
    """Ensure policy library database connection is configured"""
    if not os.environ.get('BROOKINGS_DATABASE_URL'):
        # Default to Neon PostgreSQL (production)
        os.environ['BROOKINGS_DATABASE_URL'] = (
            'postgresql://neondb_owner:npg_7Z4JjDIFYctk@ep-withered-frost-add6lq34-pooler.c-2.us-east-1.aws.neon.tech/'
            'neondb?sslmode=require'
        )


def format_transcript_text(text):
    """
    Format plain text with intelligent formatting for transcripts and structured content

    Detects and formats:
    - Tables (marked with [TABLE]...[/TABLE])
    - Figures (marked with [FIGURE N: description])
    - Headings (marked with [H2], [H3], etc.)
    - Speaker labels (ALL CAPS followed by colon)
    - Publication names (common patterns)
    - Paragraph structure
    """
    if not text:
        return ''

    # Escape HTML first
    text = escape(text)

    # Process tables first (before line-by-line processing)
    def format_table(match):
        table_content = match.group(1)
        lines = [l.strip() for l in table_content.split('\n') if l.strip()]

        if not lines:
            return ''

        # Build HTML table
        table_html = ['<table class="content-table">']

        # Check if we have a header (line with --- separators)
        has_header = any('---' in line for line in lines)

        if has_header:
            # Find header row (before ---)
            header_idx = next(i for i, line in enumerate(lines) if '---' in line)
            if header_idx > 0:
                # Process header
                header_line = lines[header_idx - 1]
                if header_line.startswith('|'):
                    cells = [c.strip() for c in header_line.split('|')[1:-1]]
                    table_html.append('<thead><tr>')
                    for cell in cells:
                        table_html.append(f'<th>{cell}</th>')
                    table_html.append('</tr></thead>')

                # Process data rows (after ---)
                table_html.append('<tbody>')
                for line in lines[header_idx + 1:]:
                    if line.startswith('|'):
                        cells = [c.strip() for c in line.split('|')[1:-1]]
                        table_html.append('<tr>')
                        for cell in cells:
                            table_html.append(f'<td>{cell}</td>')
                        table_html.append('</tr>')
                table_html.append('</tbody>')
        else:
            # No header, just process all rows
            table_html.append('<tbody>')
            for line in lines:
                if line.startswith('|'):
                    cells = [c.strip() for c in line.split('|')[1:-1]]
                    table_html.append('<tr>')
                    for cell in cells:
                        table_html.append(f'<td>{cell}</td>')
                    table_html.append('</tr>')
            table_html.append('</tbody>')

        table_html.append('</table>')
        return '\n'.join(table_html)

    # Replace [TABLE]...[/TABLE] blocks with HTML tables
    text = re.sub(r'\[TABLE\](.*?)\[/TABLE\]', format_table, text, flags=re.DOTALL)

    # Process figures: [FIGURE N: description]
    def format_figure(match):
        figure_num = match.group(1)
        description = match.group(2)
        # Create a styled div for the figure
        return f'<div class="content-figure"><div class="figure-label">Figure {figure_num}</div><div class="figure-description">{description}</div></div>'

    # Replace [FIGURE N: description] with formatted divs
    text = re.sub(r'\[FIGURE (\d+): ([^\]]+)\]', format_figure, text)

    # Handle image source lines: [Image source: URL]
    def format_image_source(match):
        url = match.group(1)
        return f'<div class="figure-source"><a href="{url}" target="_blank" rel="noopener">View image</a></div>'

    text = re.sub(r'\[Image source: ([^\]]+)\]', format_image_source, text)

    # Handle interactive chart lines: [Interactive chart: URL] - embed actual iframe
    def format_interactive_chart(match):
        url = match.group(1)
        # Embed the iframe directly with responsive sizing
        # Initial height of 600px, will be adjusted by Datawrapper's postMessage
        iframe_html = f'<div class="interactive-chart-container"><iframe src="{url}" scrolling="no" frameborder="0" style="width: 0; min-width: 100% !important; border: none;" height="600" allowfullscreen></iframe></div>'
        return iframe_html

    text = re.sub(r'\[Interactive chart: ([^\]]+)\]', format_interactive_chart, text)

    # Split into lines
    lines = text.split('\n')
    formatted_lines = []

    in_table = False
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip table HTML (already processed)
        if line.startswith('<table') or line.startswith('</table>') or \
           line.startswith('<thead') or line.startswith('</thead>') or \
           line.startswith('<tbody') or line.startswith('</tbody>') or \
           line.startswith('<tr') or line.startswith('</tr>') or \
           line.startswith('<th') or line.startswith('</th>') or \
           line.startswith('<td') or line.startswith('</td>'):
            formatted_lines.append(line)
            continue

        # Detect heading markers ([H2], [H3], etc.)
        heading_match = re.match(r'^\[H([2-6])\](.+)$', line)
        if heading_match:
            level = heading_match.group(1)
            heading_text = heading_match.group(2).strip()
            # Use h-tag class for styling consistency
            formatted_lines.append(f'<h{level} class="content-heading content-h{level}">{heading_text}</h{level}>')
            continue

        # Detect speaker labels (ALL CAPS followed by colon at start of line)
        speaker_match = re.match(r'^([A-Z][A-Z\s\.]+):\s*(.*)$', line)
        if speaker_match:
            speaker = speaker_match.group(1)
            content = speaker_match.group(2)
            formatted_lines.append(f'<p class="speaker-line"><span class="speaker-label">{speaker}:</span> {content}</p>')
            continue

        # Detect publication/program names (heuristic: title case with "Brookings" or all caps short phrases)
        # Wrap in em tags for italic styling
        line_formatted = re.sub(
            r'\b(Brookings\s+(?:Papers?|Podcast|Program|Project)(?:\s+on\s+[\w\s]+)?)\b',
            r'<em>\1</em>',
            line,
            flags=re.IGNORECASE
        )

        # Regular paragraph
        formatted_lines.append(f'<p>{line_formatted}</p>')

    # Join with newlines for readability in source
    html = '\n'.join(formatted_lines)

    return Markup(html)


# Register the custom filter
policy_library_bp.add_app_template_filter(format_transcript_text, 'format_transcript')


def get_brookings_source_id():
    """Get Brookings source ID"""
    # Ensure database is configured
    ensure_brookings_database_configured()

    session = get_session()
    brookings = session.query(Source).filter_by(source_code='BROOKINGS').first()
    source_id = brookings.source_id if brookings else None
    session.close()
    return source_id


@policy_library_bp.route('/')
def index():
    """Browse policy library documents"""
    try:
        # Get filter parameters
        search_query = request.args.get('q', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        source_filter = request.args.get('source', '')  # New: source filter
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        session = get_session()

        # Build query - exclude "Page not Found" articles
        query = session.query(Document)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))

        # Apply source filter if specified
        if source_filter:
            source = session.query(Source).filter_by(source_code=source_filter).first()
            if source:
                query = query.filter_by(source_id=source.source_id)

        # Add search filter if query provided
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                (Document.title.like(search_pattern)) |
                (Document.summary.like(search_pattern)) |
                (Document.full_text.like(search_pattern))
            )

        if date_from:
            query = query.filter(Document.publication_date >= date_from)

        if date_to:
            query = query.filter(Document.publication_date <= date_to)

        # Get total count
        total = query.count()

        # Get paginated results with eagerly loaded source relationship
        documents = query.options(joinedload(Document.source))\
            .order_by(desc(Document.publication_date)).limit(limit).offset(offset).all()

        # Get only sources that have documents in the current filtered view (excluding source filter itself)
        # Build a base query without the source filter
        sources_query = session.query(Document)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))

        # Apply the same filters as documents (except source)
        if search_query:
            search_pattern = f"%{search_query}%"
            sources_query = sources_query.filter(
                (Document.title.like(search_pattern)) |
                (Document.summary.like(search_pattern)) |
                (Document.full_text.like(search_pattern))
            )
        if date_from:
            sources_query = sources_query.filter(Document.publication_date >= date_from)
        if date_to:
            sources_query = sources_query.filter(Document.publication_date <= date_to)

        # Get distinct source IDs from the filtered documents
        available_source_ids = [s[0] for s in sources_query.with_entities(Document.source_id).distinct().all()]

        # Get only those sources
        all_sources = session.query(Source)\
            .filter(Source.source_id.in_(available_source_ids))\
            .order_by(Source.name).all() if available_source_ids else []

        session.close()

        total_pages = (total + limit - 1) // limit

        return render_template('policy_library_index.html',
                             documents=documents,
                             query=search_query,
                             date_from=date_from,
                             date_to=date_to,
                             source_filter=source_filter,
                             all_sources=all_sources,
                             page=page,
                             total=total,
                             total_pages=total_pages,
                             limit=limit)
    except Exception as e:
        return f"Error: {e}", 500


@policy_library_bp.route('/search')
def search():
    """Search policy library documents using PostgreSQL full-text search"""
    try:
        query_text = request.args.get('q', '')
        source_filter = request.args.get('source', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        if not query_text:
            session = get_session()
            all_sources = session.query(Source).order_by(Source.name).all()
            session.close()
            return render_template('policy_library_search.html', query='', results=[], total=0, all_sources=all_sources, source_filter='')

        session = get_session()

        # Use PostgreSQL full-text search with ranking
        from sqlalchemy import text

        # Build FTS query using websearch_to_tsquery for natural language search
        # This supports phrases, AND, OR, and NOT operators
        query = session.query(Document)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .filter(Document.search_vector.op('@@')(func.websearch_to_tsquery('english', query_text)))

        # Apply source filter if specified
        if source_filter:
            source = session.query(Source).filter_by(source_code=source_filter).first()
            if source:
                query = query.filter_by(source_id=source.source_id)

        total = query.count()

        # Order by relevance ranking (title > summary > full_text based on weights A, B, C)
        results = query.options(joinedload(Document.source))\
            .order_by(
                desc(func.ts_rank(Document.search_vector, func.websearch_to_tsquery('english', query_text))),
                desc(Document.publication_date)
            ).limit(limit).offset(offset).all()

        # Get only sources that have documents matching the search (excluding source filter)
        # Build a base query without the source filter using FTS
        sources_query = session.query(Document)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .filter(Document.search_vector.op('@@')(func.websearch_to_tsquery('english', query_text)))

        # Get distinct source IDs from the search results
        available_source_ids = [s[0] for s in sources_query.with_entities(Document.source_id).distinct().all()]

        # Get only those sources
        all_sources = session.query(Source)\
            .filter(Source.source_id.in_(available_source_ids))\
            .order_by(Source.name).all() if available_source_ids else []

        session.close()

        total_pages = (total + limit - 1) // limit

        return render_template('policy_library_search.html',
                             query=query_text,
                             results=results,
                             total=total,
                             page=page,
                             total_pages=total_pages,
                             limit=limit,
                             all_sources=all_sources,
                             source_filter=source_filter)
    except Exception as e:
        return f"Error: {e}", 500


def get_source_display_config(source_code):
    """Get display configuration for a source"""
    configs = {
        'BROOKINGS': {
            'link_text': 'View on Brookings.edu',
            'domain': 'brookings.edu'
        },
        'SUBSTACK': {
            'link_text': 'Read on Substack',
            'domain': 'substack.com'
        },
        'CRS': {
            'link_text': 'View on Congress.gov',
            'domain': 'congress.gov'
        },
        'GAO': {
            'link_text': 'View on GAO.gov',
            'domain': 'gao.gov'
        }
    }
    return configs.get(source_code, {
        'link_text': 'View Original',
        'domain': 'source'
    })


@policy_library_bp.route('/document/<int:document_id>')
def document_detail(document_id):
    """Document detail page"""
    try:
        session = get_session()

        document = session.query(Document).options(joinedload(Document.source)).get(document_id)

        if not document:
            session.close()
            return "Document not found", 404

        # Get authors
        authors = session.query(Author).join(DocumentAuthor).filter(
            DocumentAuthor.document_id == document_id
        ).all()

        # Get subjects
        subjects = session.query(Subject).join(DocumentSubject).filter(
            DocumentSubject.document_id == document_id
        ).all()

        # Get source display config
        source_config = get_source_display_config(
            document.source.source_code if document.source else None
        )

        session.close()

        return render_template('policy_library_detail.html',
                             document=document,
                             authors=authors,
                             subjects=subjects,
                             source_config=source_config)
    except Exception as e:
        return f"Error: {e}", 500


@policy_library_bp.route('/api/trigger-update', methods=['POST'])
def trigger_update():
    """Manually trigger policy library update (for testing/emergency use)"""
    try:
        from updaters.policy_library_updater import PolicyLibraryUpdater

        updater = PolicyLibraryUpdater(
            lookback_days=30,  # Check last 30 days
            publication='jamiedupree.substack.com',
            author='Jamie Dupree'
        )

        result = updater.run_daily_update()

        return jsonify(result)

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@policy_library_bp.route('/test-update')
def test_update_page():
    """Test page for manual updates"""
    return render_template('test_update.html')


@policy_library_bp.route('/api/export')
def export_csv():
    """Export documents as CSV"""
    try:
        # Get filter parameters
        document_ids = request.args.get('ids', '')
        query_text = request.args.get('q', '')

        source_id = get_brookings_source_id()
        if not source_id:
            return "Brookings source not found", 500

        session = get_session()

        # Build query based on parameters
        if document_ids:
            # Export specific documents
            ids = [int(id.strip()) for id in document_ids.split(',')]
            documents = session.query(Document).filter(Document.document_id.in_(ids)).all()
        elif query_text:
            # Export search results - exclude "Page not Found" articles
            search_pattern = f"%{query_text}%"
            documents = session.query(Document).filter_by(source_id=source_id)\
                .filter(~Document.title.like('%Page not Found%'))\
                .filter(~Document.title.like('%404%'))\
                .filter(
                    (Document.title.like(search_pattern)) |
                    (Document.summary.like(search_pattern))
                ).order_by(desc(Document.publication_date)).limit(1000).all()
        else:
            # Export all (limited to 1000) - exclude "Page not Found" articles
            documents = session.query(Document).filter_by(source_id=source_id)\
                .filter(~Document.title.like('%Page not Found%'))\
                .filter(~Document.title.like('%404%'))\
                .order_by(desc(Document.publication_date)).limit(1000).all()

        session.close()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['document_id', 'identifier', 'title', 'document_type', 'publication_date',
                        'summary', 'word_count', 'url', 'pdf_url'])

        # Write rows
        for doc in documents:
            writer.writerow([
                doc.document_id,
                doc.document_identifier,
                doc.title,
                doc.document_type or '',
                doc.publication_date or '',
                (doc.summary or '')[:200],  # Truncate summary
                doc.word_count or 0,
                doc.url or '',
                doc.pdf_url or ''
            ])

        # Return as CSV download
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=brookings_{datetime.now().strftime("%Y%m%d")}.csv'}
        )

    except Exception as e:
        return f"Error: {e}", 500
