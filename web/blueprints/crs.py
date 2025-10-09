"""
CRS Products blueprint - browse and search CRS products
"""
from flask import Blueprint, render_template, request, Response
import sqlite3
import csv
import io
import os
import gzip
import shutil
from datetime import datetime

crs_bp = Blueprint('crs', __name__, url_prefix='/crs')

# Database paths
CRS_DB_GZ_PATH = 'crs_products.db.gz'
# Use /tmp for decompressed database on Vercel (read-only filesystem)
CRS_DB_PATH = os.path.join('/tmp', 'crs_products.db') if os.environ.get('VERCEL') else 'crs_products.db'


def ensure_database_decompressed():
    """Decompress database if needed (for production deployment)"""
    # Check if compressed version exists and decompressed doesn't
    if not os.path.exists(CRS_DB_PATH) and os.path.exists(CRS_DB_GZ_PATH):
        print(f"Decompressing {CRS_DB_GZ_PATH} to {CRS_DB_PATH}...")
        os.makedirs(os.path.dirname(CRS_DB_PATH), exist_ok=True)
        with gzip.open(CRS_DB_GZ_PATH, 'rb') as f_in:
            with open(CRS_DB_PATH, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print("Database decompressed successfully!")


def get_crs_db():
    """Get CRS database connection"""
    ensure_database_decompressed()
    conn = sqlite3.connect(CRS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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

        conn = get_crs_db()
        cursor = conn.cursor()

        # Build query
        query = 'SELECT * FROM products WHERE 1=1'
        params = []

        if status:
            query += ' AND status = ?'
            params.append(status)

        if product_type:
            query += ' AND product_type = ?'
            params.append(product_type)

        if topic:
            query += ' AND EXISTS (SELECT 1 FROM json_each(topics) WHERE value = ?)'
            params.append(topic)

        if date_from:
            query += ' AND publication_date >= ?'
            params.append(date_from)

        if date_to:
            query += ' AND publication_date <= ?'
            params.append(date_to)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM ({query})"
        total = cursor.execute(count_query, params).fetchone()[0]

        # Get paginated results
        query += ' ORDER BY publication_date DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        products = cursor.fetchall()
        cursor.execute(query, params)
        products = cursor.fetchall()

        # Get filter options
        cursor.execute('SELECT DISTINCT product_type FROM products WHERE product_type IS NOT NULL ORDER BY product_type')
        product_types = [row[0] for row in cursor.fetchall()]

        cursor.execute('''
            SELECT DISTINCT value as topic
            FROM products, json_each(topics)
            WHERE topics IS NOT NULL AND value IS NOT NULL
            ORDER BY value
            LIMIT 100
        ''')
        topics = [row[0] for row in cursor.fetchall()]

        conn.close()

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


@crs_bp.route('/search')
def search():
    """Search CRS products"""
    try:
        query = request.args.get('q', '')
        page = int(request.args.get('page', 1))
        limit = 50
        offset = (page - 1) * limit

        if not query:
            return render_template('crs_search.html', query='', results=[], total=0)

        conn = get_crs_db()
        cursor = conn.cursor()

        # Check if FTS table exists and has correct schema
        try:
            cursor.execute("SELECT summary FROM products_fts LIMIT 1")
            fts_has_summary = True
        except sqlite3.OperationalError:
            # FTS doesn't exist or doesn't have summary column
            fts_has_summary = False

        # Rebuild FTS if it doesn't have summary field
        if not fts_has_summary:
            print("Rebuilding FTS index to include summary field...")
            cursor.execute('DROP TABLE IF EXISTS products_fts')
            # Use column weights: title=3, summary=1, topics=2 for better ranking
            cursor.execute('''
                CREATE VIRTUAL TABLE products_fts USING fts5(
                    product_id UNINDEXED,
                    title,
                    summary,
                    topics,
                    tokenize='porter'
                )
            ''')
            cursor.execute('''
                INSERT INTO products_fts(product_id, title, summary, topics)
                SELECT
                    p.product_id,
                    p.title,
                    COALESCE(p.summary, ''),
                    COALESCE(json_group_array(j.value), '')
                FROM products p
                LEFT JOIN json_each(p.topics) j
                GROUP BY p.product_id
            ''')
            conn.commit()
            print("FTS index rebuilt with summary field!")

        # Search query with column weights (title:3, summary:1, topics:2)
        # Use BM25 ranking for better relevance
        search_query = '''
            SELECT p.*, bm25(products_fts, 3.0, 1.0, 2.0) as score
            FROM products_fts fts
            JOIN products p ON fts.product_id = p.product_id
            WHERE products_fts MATCH ?
            ORDER BY score
            LIMIT ? OFFSET ?
        '''

        results = cursor.execute(search_query, (query, limit, offset)).fetchall()

        # Get total count
        count_query = '''
            SELECT COUNT(*)
            FROM products_fts
            WHERE products_fts MATCH ?
        '''
        total = cursor.execute(count_query, (query,)).fetchone()[0]

        conn.close()

        total_pages = (total + limit - 1) // limit

        return render_template('crs_search.html',
                             query=query,
                             results=results,
                             total=total,
                             page=page,
                             total_pages=total_pages,
                             limit=limit)
    except Exception as e:
        return f"Error: {e}", 500


@crs_bp.route('/product/<product_id>')
def product_detail(product_id):
    """Product detail page"""
    try:
        conn = get_crs_db()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
        product = cursor.fetchone()

        conn.close()

        if not product:
            return "Product not found", 404

        return render_template('crs_detail.html', product=product)
    except Exception as e:
        return f"Error: {e}", 500


@crs_bp.route('/api/export')
def export_csv():
    """Export products as CSV"""
    try:
        # Get filter parameters
        product_ids = request.args.get('ids', '')
        query = request.args.get('q', '')
        product_type = request.args.get('product_type', '')
        status = request.args.get('status', 'Active')
        topic = request.args.get('topic', '')

        conn = get_crs_db()
        cursor = conn.cursor()

        # Build query based on parameters
        if product_ids:
            # Export specific products
            ids = product_ids.split(',')
            placeholders = ','.join('?' * len(ids))
            sql_query = f'SELECT * FROM products WHERE product_id IN ({placeholders})'
            products = cursor.execute(sql_query, ids).fetchall()
        elif query:
            # Export search results
            search_query = '''
                SELECT p.*
                FROM products_fts fts
                JOIN products p ON fts.product_id = p.product_id
                WHERE products_fts MATCH ?
                ORDER BY fts.rank
            '''
            products = cursor.execute(search_query, (query,)).fetchall()
        else:
            # Export filtered browse results
            sql_query = 'SELECT * FROM products WHERE 1=1'
            params = []

            if status:
                sql_query += ' AND status = ?'
                params.append(status)
            if product_type:
                sql_query += ' AND product_type = ?'
                params.append(product_type)
            if topic:
                sql_query += ' AND EXISTS (SELECT 1 FROM json_each(topics) WHERE value = ?)'
                params.append(topic)

            sql_query += ' ORDER BY publication_date DESC LIMIT 1000'
            products = cursor.execute(sql_query, params).fetchall()

        conn.close()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['product_id', 'title', 'product_type', 'status', 'publication_date',
                        'authors', 'topics', 'url_html', 'url_pdf'])

        # Write rows
        for product in products:
            import json
            authors = json.loads(product['authors']) if product['authors'] else []
            topics = json.loads(product['topics']) if product['topics'] else []

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
