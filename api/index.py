#!/usr/bin/env python3
"""
Vercel entry point for Flask application
"""
import sys
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import the Flask app
from web.app import app

# Vercel expects this variable name
application = app

if __name__ == "__main__":
    app.run()