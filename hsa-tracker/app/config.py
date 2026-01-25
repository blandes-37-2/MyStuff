"""
HSA Tracker Configuration Module
Loads environment variables and provides configuration settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Application configuration settings."""

    # Azure AD / Microsoft Graph settings
    AZURE_CLIENT_ID = os.getenv('AZURE_CLIENT_ID', '')
    AZURE_CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET', '')
    AZURE_TENANT_ID = os.getenv('AZURE_TENANT_ID', 'common')

    # Microsoft Graph API endpoints
    GRAPH_API_ENDPOINT = 'https://graph.microsoft.com/v1.0'
    AUTHORITY = f'https://login.microsoftonline.com/{AZURE_TENANT_ID}'
    SCOPES = ['Mail.Read', 'Mail.ReadBasic', 'User.Read']

    # Outlook settings
    OUTLOOK_EMAIL = os.getenv('OUTLOOK_EMAIL', '')
    EMAIL_SUBJECT_FILTER = 'HSA'

    # Flask settings
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # Database
    DATABASE_PATH = BASE_DIR / os.getenv('DATABASE_PATH', 'data/hsa_tracker.db')
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'

    # File storage
    ATTACHMENTS_DIR = BASE_DIR / 'data' / 'attachments'

    @classmethod
    def is_azure_configured(cls) -> bool:
        """Check if Azure credentials are configured."""
        return bool(cls.AZURE_CLIENT_ID and cls.AZURE_CLIENT_SECRET)

    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist."""
        cls.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cls.ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
