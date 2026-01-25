"""
HSA Spending Tracker Application
Main Flask application factory and initialization.
"""
import logging
from flask import Flask
from .config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def create_app(config_class=Config):
    """Application factory for creating Flask app instance."""
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config_class)
    app.secret_key = config_class.SECRET_KEY

    # Ensure directories exist
    config_class.ensure_directories()

    # Initialize database
    from .models import Database
    db = Database(str(config_class.DATABASE_PATH))
    db.create_tables()
    app.db = db

    # Register routes
    from . import routes
    routes.init_app(app)

    return app
