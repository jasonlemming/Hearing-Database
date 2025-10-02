#!/usr/bin/env python3
"""
Flask web application for Congressional Hearing Database - Modular Version

This modular version uses Flask blueprints to organize routes into logical components:
- committees: Committee browsing and details
- hearings: Hearing browsing and details
- main_pages: Members, witnesses, and search functionality
- api: JSON API endpoints
- admin: Administrative interfaces

This replaces the previous monolithic 841-line app.py with organized, maintainable modules.
"""
from flask import Flask, redirect, url_for
from datetime import datetime

# Import blueprints
from web.blueprints.committees import committees_bp
from web.blueprints.hearings import hearings_bp
from web.blueprints.main_pages import main_pages_bp
from web.blueprints.api import api_bp
from web.blueprints.admin import admin_bp

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'congressional-hearing-db-secret-key'

# Register blueprints
app.register_blueprint(committees_bp)
app.register_blueprint(hearings_bp)
app.register_blueprint(main_pages_bp)
app.register_blueprint(api_bp)
app.register_blueprint(admin_bp)


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


# Main routes
@app.route('/')
def index():
    """Redirect to hearings page"""
    return redirect('/hearings')


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
        os.system('pip install flask')

    # Run the application
    app.run(debug=True, host='0.0.0.0', port=8000)