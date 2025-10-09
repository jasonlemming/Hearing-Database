"""
Brookings Institution blueprint - browse and search Brookings research
"""
from flask import Blueprint, render_template, request, Response, jsonify
from sqlalchemy import func, desc
import json
import csv
import io
import re
import sys
sys.path.insert(0, '/Users/jasonlemons/Documents/GitHub/Hearing-Database')

from brookings_ingester.models import get_session, Document, Author, Subject, Source, DocumentAuthor, DocumentSubject
from datetime import datetime
from markupsafe import Markup, escape

brookings_bp = Blueprint('brookings', __name__, url_prefix='/brookings')


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
brookings_bp.add_app_template_filter(format_transcript_text, 'format_transcript')


def get_brookings_source_id():
    """Get Brookings source ID"""
    session = get_session()
    brookings = session.query(Source).filter_by(source_code='BROOKINGS').first()
    source_id = brookings.source_id if brookings else None
    session.close()
    return source_id


@brookings_bp.route('/')
def index():
    """Browse Brookings documents page"""
    try:
        # Get filter parameters
        document_type = request.args.get('document_type', '')
        subject = request.args.get('subject', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        source_id = get_brookings_source_id()
        if not source_id:
            return "Brookings source not found. Please run: python cli.py brookings init", 500

        session = get_session()

        # Build query - exclude "Page not Found" articles
        query = session.query(Document).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))

        if document_type:
            query = query.filter(Document.document_type == document_type)

        if date_from:
            query = query.filter(Document.publication_date >= date_from)

        if date_to:
            query = query.filter(Document.publication_date <= date_to)

        if subject:
            query = query.join(DocumentSubject).join(Subject).filter(Subject.name == subject)

        # Get total count
        total = query.count()

        # Get paginated results
        documents = query.order_by(desc(Document.publication_date)).limit(limit).offset(offset).all()

        # Get filter options - exclude "Page not Found" articles
        document_types = session.query(Document.document_type).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%')).distinct().all()
        document_types = [dt[0] for dt in document_types if dt[0]]

        # Get subjects (limit to top 100 most common) - exclude "Page not Found" articles
        subjects_query = session.query(Subject.name, func.count(DocumentSubject.document_id).label('count'))\
            .join(DocumentSubject)\
            .join(Document)\
            .filter(Document.source_id == source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .group_by(Subject.name)\
            .order_by(desc('count'))\
            .limit(100)
        subjects = [s[0] for s in subjects_query.all()]

        session.close()

        total_pages = (total + limit - 1) // limit

        return render_template('brookings_index.html',
                             documents=documents,
                             document_types=document_types,
                             subjects=subjects,
                             selected_document_type=document_type,
                             selected_subject=subject,
                             date_from=date_from,
                             date_to=date_to,
                             page=page,
                             total=total,
                             total_pages=total_pages,
                             limit=limit)
    except Exception as e:
        return f"Error: {e}", 500


@brookings_bp.route('/search')
def search():
    """Search Brookings documents"""
    try:
        query_text = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        if not query_text:
            return render_template('brookings_search.html', query='', results=[], total=0)

        source_id = get_brookings_source_id()
        if not source_id:
            return "Brookings source not found", 500

        session = get_session()

        # Simple text search (can be enhanced with FTS later)
        search_pattern = f"%{query_text}%"
        query = session.query(Document).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .filter(
                (Document.title.like(search_pattern)) |
                (Document.summary.like(search_pattern)) |
                (Document.full_text.like(search_pattern))
            )

        total = query.count()
        results = query.order_by(desc(Document.publication_date)).limit(limit).offset(offset).all()

        session.close()

        total_pages = (total + limit - 1) // limit

        return render_template('brookings_search.html',
                             query=query_text,
                             results=results,
                             total=total,
                             page=page,
                             total_pages=total_pages,
                             limit=limit)
    except Exception as e:
        return f"Error: {e}", 500


@brookings_bp.route('/document/<int:document_id>')
def document_detail(document_id):
    """Document detail page"""
    try:
        session = get_session()

        document = session.query(Document).get(document_id)

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

        session.close()

        return render_template('brookings_detail.html',
                             document=document,
                             authors=authors,
                             subjects=subjects)
    except Exception as e:
        return f"Error: {e}", 500


@brookings_bp.route('/stats')
def stats():
    """Statistics page"""
    try:
        source_id = get_brookings_source_id()
        if not source_id:
            return "Brookings source not found", 500

        session = get_session()

        # Basic stats - exclude "Page not Found" articles
        total_docs = session.query(Document).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%')).count()
        total_words = session.query(func.sum(Document.word_count)).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%')).scalar() or 0
        with_pdfs = session.query(Document).filter(
            Document.source_id == source_id,
            Document.pdf_url.isnot(None),
            ~Document.title.like('%Page not Found%'),
            ~Document.title.like('%404%')
        ).count()

        # Documents by type
        by_type = session.query(
            Document.document_type,
            func.count(Document.document_id)
        ).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .group_by(Document.document_type).all()

        # Recent documents
        recent = session.query(Document).filter_by(source_id=source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .order_by(desc(Document.created_at)).limit(10).all()

        # Top subjects
        top_subjects = session.query(Subject.name, func.count(DocumentSubject.document_id).label('count'))\
            .join(DocumentSubject)\
            .join(Document)\
            .filter(Document.source_id == source_id)\
            .filter(~Document.title.like('%Page not Found%'))\
            .filter(~Document.title.like('%404%'))\
            .group_by(Subject.name)\
            .order_by(desc('count'))\
            .limit(20).all()

        session.close()

        return render_template('brookings_stats.html',
                             total_docs=total_docs,
                             total_words=total_words,
                             with_pdfs=with_pdfs,
                             by_type=by_type,
                             recent=recent,
                             top_subjects=top_subjects)
    except Exception as e:
        return f"Error: {e}", 500


@brookings_bp.route('/api/export')
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
