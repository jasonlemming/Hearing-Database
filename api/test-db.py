#!/usr/bin/env python3
"""
Test endpoint to check database connection and recent documents
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/test-db')
def test_db():
    """Test database connection and show recent Substack posts"""
    try:
        from brookings_ingester.models import get_session, Document, Source

        # Get database URL (masked)
        db_url = os.environ.get('BROOKINGS_DATABASE_URL', 'NOT SET')
        db_type = 'postgresql' if 'postgresql' in db_url else 'sqlite' if 'sqlite' in db_url else 'unknown'

        session = get_session()

        # Get Substack source
        source = session.query(Source).filter_by(source_code='SUBSTACK').first()

        if not source:
            return jsonify({
                'error': 'Substack source not found',
                'db_type': db_type,
                'db_url_prefix': db_url[:50] if db_url != 'NOT SET' else 'NOT SET'
            })

        # Get recent posts (last 10 days)
        cutoff_date = datetime.now().date() - timedelta(days=10)
        recent_posts = session.query(Document).filter(
            Document.source_id == source.source_id,
            Document.publication_date >= cutoff_date
        ).order_by(Document.publication_date.desc()).all()

        # Get total count
        total_count = session.query(Document).filter_by(source_id=source.source_id).count()

        session.close()

        return jsonify({
            'success': True,
            'db_type': db_type,
            'db_url_prefix': db_url[:50] if db_url != 'NOT SET' else 'NOT SET',
            'total_substack_docs': total_count,
            'recent_posts_count': len(recent_posts),
            'recent_posts': [
                {
                    'date': str(post.publication_date),
                    'title': post.title[:60]
                }
                for post in recent_posts
            ]
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'db_type': db_type if 'db_type' in locals() else 'unknown',
            'db_url_prefix': db_url[:50] if 'db_url' in locals() and db_url != 'NOT SET' else 'NOT SET'
        }), 500


if __name__ == '__main__':
    app.run()
