#!/usr/bin/env python3
"""
Flask web application for Congressional Hearing Database - Modular Version

This modular version uses Flask blueprints to organize routes into logical components:
- committees: Committee browsing and details
- hearings: Hearing browsing and details
- main_pages: Members, witnesses, and search functionality
- api: JSON API endpoints
- admin: Administrative interfaces
- policy_library: Multi-source policy research library (CRS, Brookings, GAO, Substack)

This replaces the previous monolithic 841-line app.py with organized, maintainable modules.
"""
import os
import gzip
import shutil
from pathlib import Path

# Decompress Brookings database BEFORE importing any blueprints
def ensure_databases_ready():
    """Decompress databases on Vercel before app initialization"""
    if os.environ.get('VERCEL'):
        # Decompress Brookings database
        brookings_gz = 'brookings_products.db.gz'
        brookings_db = '/tmp/brookings_products.db'
        if os.path.exists(brookings_gz) and not os.path.exists(brookings_db):
            print(f"Decompressing {brookings_gz} to {brookings_db}...")
            with gzip.open(brookings_gz, 'rb') as f_in:
                with open(brookings_db, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print("Brookings database ready!")
            # Set BROOKINGS_DATABASE_URL for Brookings config
            os.environ['BROOKINGS_DATABASE_URL'] = f'sqlite:///{brookings_db}'

# Initialize databases FIRST
ensure_databases_ready()

from flask import Flask, redirect, url_for
from datetime import datetime

# Import blueprints AFTER database setup
from web.blueprints.committees import committees_bp
from web.blueprints.hearings import hearings_bp
from web.blueprints.main_pages import main_pages_bp
from web.blueprints.api import api_bp
from web.blueprints.admin import admin_bp
from web.blueprints.crs import crs_bp
from web.blueprints.policy_library import policy_library_bp

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'congressional-hearing-db-secret-key'

# Register blueprints
app.register_blueprint(committees_bp)
app.register_blueprint(hearings_bp)
app.register_blueprint(main_pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(crs_bp)
app.register_blueprint(policy_library_bp)


# Template filters (shared across all blueprints)
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


@app.template_filter('format_location')
def format_location_filter(location):
    """Format location data - handles both dict strings and plain text"""
    if not location:
        return ""

    # Try to parse as Python dict literal
    if isinstance(location, str) and location.startswith('{'):
        try:
            import ast
            location_dict = ast.literal_eval(location)

            # If it's a dict with building/room, format nicely
            if isinstance(location_dict, dict):
                building = location_dict.get('building', '')
                room = location_dict.get('room', '')

                if building and room:
                    return f"{building}, Room {room}"
                elif building:
                    return building
                elif room:
                    return f"Room {room}"
        except (ValueError, SyntaxError):
            # If parsing fails, return as-is
            pass

    # Return plain text as-is
    return location


@app.template_filter('from_json')
def from_json_filter(json_string):
    """Parse JSON string into Python object"""
    if not json_string:
        return []
    try:
        import json
        return json.loads(json_string)
    except (ValueError, TypeError):
        return []


@app.template_filter('number_format')
def number_format_filter(value):
    """Format number with thousand separators"""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return value


# Main routes
@app.route('/')
def index():
    """Landing page"""
    from flask import render_template
    return render_template('landing.html')


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return "Page not found", 404


@app.errorhandler(500)
def internal_error(error):
    return "Internal server error", 500


if __name__ == '__main__':
    # Install Flask if not already installed
    try:
        import flask
    except ImportError:
        import os
        os.system('pip install flask')

    # Run the application with configurable port
    import os
    port = int(os.environ.get('FLASK_RUN_PORT', 5001))  # Default to 5001 since 5000 and 8000 are in use
    app.run(debug=True, host='0.0.0.0', port=port)