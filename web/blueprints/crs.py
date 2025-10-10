"""
CRS Products blueprint - browse and search CRS products
"""
from flask import Blueprint, render_template, request, Response
import psycopg2
import psycopg2.extras
import csv
import io
import os
import sys
import requests
import json
from datetime import datetime

# Add parent directory to path for database imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from database.postgres_config import get_connection

crs_bp = Blueprint('crs', __name__, url_prefix='/crs')


def get_crs_db():
    """
    Get CRS database connection (PostgreSQL)
    Returns context manager for connection
    """
    return get_connection()


def fetch_content_from_blob(blob_url, timeout=10):
    """
    Fetch HTML content from Vercel Blob storage

    Args:
        blob_url: URL to the blob
        timeout: Request timeout in seconds

    Returns:
        HTML content string, or None if fetch fails
    """
    try:
        response = requests.get(blob_url, timeout=timeout)
        if response.status_code == 200:
            return response.text
        else:
            print(f"Error fetching blob: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching blob from {blob_url}: {e}")
        return None


@crs_bp.route('/')
def index():
    """Browse CRS products page"""
    try:
        # Get filter parameters
        product_type = request.args.get('product_type', '')
        status = request.args.get('status', 'Active')
        topic = request.args.get('topic', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        with get_crs_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Build query - PostgreSQL uses %s instead of ?
            query = 'SELECT * FROM products WHERE 1=1'
            params = []

            if status:
                query += ' AND status = %s'
                params.append(status)

            if product_type:
                query += ' AND product_type = %s'
                params.append(product_type)

            if topic:
                # PostgreSQL JSONB: use @> operator for "contains"
                query += ' AND topics @> %s'
                params.append(json.dumps([topic]))

            if date_from:
                query += ' AND publication_date >= %s'
                params.append(date_from)

            if date_to:
                query += ' AND publication_date <= %s'
                params.append(date_to)

            # Get total count
            count_query = f"SELECT COUNT(*) FROM ({query}) AS count_subquery"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['count']

            # Get paginated results
            query += ' ORDER BY publication_date DESC LIMIT %s OFFSET %s'
            params.extend([limit, offset])
            cursor.execute(query, params)
            products = cursor.fetchall()

            # Get filter options
            cursor.execute('SELECT DISTINCT product_type FROM products WHERE product_type IS NOT NULL ORDER BY product_type')
            product_types = [row['product_type'] for row in cursor.fetchall()]

            # PostgreSQL JSONB: use jsonb_array_elements_text for extracting array values
            # Guard against scalar values (migration artifact from SQLite)
            cursor.execute('''
                SELECT DISTINCT jsonb_array_elements_text(topics) as topic
                FROM products
                WHERE topics IS NOT NULL
                  AND jsonb_typeof(topics) = 'array'
                ORDER BY topic
                LIMIT 100
            ''')
            topics = [row['topic'] for row in cursor.fetchall()]

        total_pages = (total + limit - 1) // limit

        return render_template('crs_index.html',
                             products=products,
                             product_types=product_types,
                             topics=topics,
                             selected_product_type=product_type,
                             selected_status=status,
                             selected_topic=topic,
                             date_from=date_from,
                             date_to=date_to,
                             page=page,
                             total=total,
                             total_pages=total_pages,
                             limit=limit)
    except Exception as e:
        return f"Error: {e}", 500


def expand_search_query(query):
    """Expand common compound words to improve search results"""
    # Common compound words that should also search for their separated forms
    expansions = {
        'healthcare': 'healthcare OR health',
        'cybersecurity': 'cybersecurity OR cyber OR security',
        'cryptocurrency': 'cryptocurrency OR crypto',
        'blockchain': 'blockchain OR block',
    }

    # Simple word-by-word expansion
    words = query.lower().split()
    expanded_words = []

    for word in words:
        if word in expansions:
            expanded_words.append(f'({expansions[word]})')
        else:
            expanded_words.append(word)

    return ' '.join(expanded_words)


@crs_bp.route('/search')
def search():
    """Search CRS products"""
    try:
        original_query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        if not original_query:
            return render_template('crs_search.html', query='', results=[], total=0)

        # Expand query for better results
        query = expand_search_query(original_query)

        with get_crs_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Check if product_content_fts exists (full HTML content search)
            has_content_fts = False
            try:
                cursor.execute("SELECT COUNT(*) FROM product_content_fts LIMIT 1")
                has_content_fts = True
            except psycopg2.errors.UndefinedTable:
                conn.rollback()
                pass

            if has_content_fts:
                # PostgreSQL full-text search with ts_rank
                # Search both metadata AND full content with proper weighting
                search_query = '''
                    WITH content_matches AS (
                        SELECT
                            cfts.product_id,
                            ts_rank(cfts.search_vector, websearch_to_tsquery('english', %s)) as content_score
                        FROM product_content_fts cfts
                        WHERE cfts.search_vector @@ websearch_to_tsquery('english', %s)
                    ),
                    metadata_matches AS (
                        SELECT
                            p.product_id,
                            ts_rank(p.search_vector, websearch_to_tsquery('english', %s)) as metadata_score
                        FROM products p
                        WHERE p.search_vector @@ websearch_to_tsquery('english', %s)
                    )
                    SELECT DISTINCT
                        p.*,
                        COALESCE(cm.content_score, 0) + COALESCE(mm.metadata_score, 0) as combined_score,
                        CASE WHEN cm.product_id IS NOT NULL THEN TRUE ELSE FALSE END as has_content_match
                    FROM products p
                    LEFT JOIN content_matches cm ON p.product_id = cm.product_id
                    LEFT JOIN metadata_matches mm ON p.product_id = mm.product_id
                    WHERE cm.product_id IS NOT NULL OR mm.product_id IS NOT NULL
                    ORDER BY combined_score DESC
                    LIMIT %s OFFSET %s
                '''
                cursor.execute(search_query, (query, query, query, query, limit, offset))
                results = cursor.fetchall()

                # Get total count
                count_query = '''
                    WITH content_matches AS (
                        SELECT DISTINCT product_id
                        FROM product_content_fts
                        WHERE search_vector @@ websearch_to_tsquery('english', %s)
                    ),
                    metadata_matches AS (
                        SELECT DISTINCT product_id
                        FROM products
                        WHERE search_vector @@ websearch_to_tsquery('english', %s)
                    )
                    SELECT COUNT(DISTINCT product_id)
                    FROM (
                        SELECT product_id FROM content_matches
                        UNION
                        SELECT product_id FROM metadata_matches
                    ) AS all_matches
                '''
                cursor.execute(count_query, (query, query))
                total = cursor.fetchone()['count']
            else:
                # Fallback to metadata-only search using products.search_vector
                # PostgreSQL: search_vector is auto-updated by trigger
                search_query = '''
                    SELECT p.*,
                           ts_rank(p.search_vector, websearch_to_tsquery('english', %s)) as score
                    FROM products p
                    WHERE p.search_vector @@ websearch_to_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s OFFSET %s
                '''
                cursor.execute(search_query, (query, query, limit, offset))
                results = cursor.fetchall()

                # Get total count
                count_query = '''
                    SELECT COUNT(*)
                    FROM products
                    WHERE search_vector @@ websearch_to_tsquery('english', %s)
                '''
                cursor.execute(count_query, (query,))
                total = cursor.fetchone()['count']

        total_pages = (total + limit - 1) // limit

        return render_template('crs_search.html',
                             query=original_query,  # Show original query to user
                             results=results,
                             total=total,
                             page=page,
                             total_pages=total_pages,
                             limit=limit,
                             has_content_search=has_content_fts)
    except Exception as e:
        return f"Error: {e}", 500


@crs_bp.route('/product/<product_id>')
def product_detail(product_id):
    """Product detail page"""
    try:
        with get_crs_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute('SELECT * FROM products WHERE product_id = %s', (product_id,))
            product = cursor.fetchone()

            if not product:
                return "Product not found", 404

            # Try to fetch current version content
            content_version = None
            try:
                cursor.execute('''
                    SELECT version_id, version_number,
                           structure_json, word_count, ingested_at, blob_url
                    FROM product_versions
                    WHERE product_id = %s AND is_current = TRUE
                ''', (product_id,))
                version_row = cursor.fetchone()

                if version_row:
                    # Already a dict due to RealDictCursor
                    content_version = dict(version_row)

                    # If blob_url exists, fetch content from blob storage
                    if content_version.get('blob_url'):
                        blob_html = fetch_content_from_blob(content_version['blob_url'])
                        if blob_html:
                            # Use blob content
                            content_version['html_content'] = blob_html
                        else:
                            # Blob fetch failed - log warning
                            print(f"Warning: Failed to fetch content from blob URL: {content_version['blob_url']}")
                    else:
                        print(f"Warning: No blob_url found for product {product_id}")

            except psycopg2.errors.UndefinedTable as e:
                # product_versions table doesn't exist yet or column mismatch
                print(f"Database error: {e}")
                conn.rollback()
                pass

        return render_template('crs_detail.html', product=product, content_version=content_version)
    except Exception as e:
        return f"Error: {e}", 500


@crs_bp.route('/api/export')
def export_csv():
    """Export products as CSV"""
    try:
        # Get filter parameters
        product_ids = request.args.get('ids', '')
        original_query = request.args.get('q', '')
        product_type = request.args.get('product_type', '')
        status = request.args.get('status', 'Active')
        topic = request.args.get('topic', '')

        with get_crs_db() as conn:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Build query based on parameters
            if product_ids:
                # Export specific products
                ids = product_ids.split(',')
                placeholders = ','.join(['%s'] * len(ids))
                sql_query = f'SELECT * FROM products WHERE product_id IN ({placeholders})'
                cursor.execute(sql_query, ids)
                products = cursor.fetchall()
            elif original_query:
                # Export search results - expand query for better results
                query = expand_search_query(original_query)
                search_query = '''
                    SELECT p.*
                    FROM products p
                    WHERE p.search_vector @@ websearch_to_tsquery('english', %s)
                    ORDER BY ts_rank(p.search_vector, websearch_to_tsquery('english', %s)) DESC
                '''
                cursor.execute(search_query, (query, query))
                products = cursor.fetchall()
            else:
                # Export filtered browse results
                sql_query = 'SELECT * FROM products WHERE 1=1'
                params = []

                if status:
                    sql_query += ' AND status = %s'
                    params.append(status)
                if product_type:
                    sql_query += ' AND product_type = %s'
                    params.append(product_type)
                if topic:
                    # PostgreSQL JSONB: use @> operator
                    sql_query += ' AND topics @> %s'
                    params.append(json.dumps([topic]))

                sql_query += ' ORDER BY publication_date DESC LIMIT 1000'
                cursor.execute(sql_query, params)
                products = cursor.fetchall()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['product_id', 'title', 'product_type', 'status', 'publication_date',
                        'authors', 'topics', 'url_html', 'url_pdf'])

        # Write rows
        for product in products:
            # JSONB fields are already Python objects (lists), no need to json.loads
            authors = product['authors'] if product['authors'] else []
            topics = product['topics'] if product['topics'] else []

            writer.writerow([
                product['product_id'],
                product['title'],
                product['product_type'],
                product['status'],
                product['publication_date'],
                '; '.join(authors),
                '; '.join(topics),
                product['url_html'] or '',
                product['url_pdf'] or ''
            ])

        # Return as CSV download
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=crs_products_{datetime.now().strftime("%Y%m%d")}.csv'}
        )

    except Exception as e:
        return f"Error: {e}", 500
