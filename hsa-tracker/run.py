#!/usr/bin/env python3
"""
HSA Spending Tracker - Application Entry Point
Run this file to start the web application.
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("  HSA Spending Tracker")
    print("=" * 50)
    print("\nStarting web server...")
    print("Open http://localhost:5000 in your browser\n")

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=app.config.get('DEBUG', True)
    )
