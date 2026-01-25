"""
Outlook Email Integration Service
Uses Microsoft Graph API to scan inbox for HSA-related emails.
"""
import os
import json
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

import msal
import requests

from ..config import Config

logger = logging.getLogger(__name__)


class OutlookService:
    """Service for interacting with Outlook via Microsoft Graph API."""

    def __init__(self):
        self.client_id = Config.AZURE_CLIENT_ID
        self.client_secret = Config.AZURE_CLIENT_SECRET
        self.tenant_id = Config.AZURE_TENANT_ID
        self.authority = Config.AUTHORITY
        self.scopes = Config.SCOPES
        self.graph_endpoint = Config.GRAPH_API_ENDPOINT
        self.subject_filter = Config.EMAIL_SUBJECT_FILTER

        self._access_token = None
        self._token_cache = None

        # Initialize MSAL app for device code flow (user authentication)
        self._msal_app = None

    def _get_msal_app(self):
        """Get or create MSAL application instance."""
        if self._msal_app is None:
            # Use device code flow for CLI applications
            self._msal_app = msal.PublicClientApplication(
                self.client_id,
                authority=self.authority,
            )
        return self._msal_app

    def authenticate_interactive(self) -> dict:
        """
        Initiate interactive authentication using device code flow.
        Returns device code info for user to complete authentication.
        """
        app = self._get_msal_app()

        # Start device code flow
        flow = app.initiate_device_flow(scopes=self.scopes)

        if "user_code" not in flow:
            raise Exception(f"Failed to create device flow: {flow.get('error_description', 'Unknown error')}")

        return {
            'user_code': flow['user_code'],
            'verification_uri': flow['verification_uri'],
            'message': flow['message'],
            'flow': flow
        }

    def complete_authentication(self, flow: dict) -> bool:
        """
        Complete the device code authentication flow.
        Blocks until user completes authentication or timeout.
        """
        app = self._get_msal_app()

        result = app.acquire_token_by_device_flow(flow)

        if "access_token" in result:
            self._access_token = result['access_token']
            logger.info("Authentication successful")
            return True
        else:
            error = result.get('error_description', result.get('error', 'Unknown error'))
            logger.error(f"Authentication failed: {error}")
            return False

    def authenticate_silent(self) -> bool:
        """Try to authenticate silently using cached credentials."""
        app = self._get_msal_app()
        accounts = app.get_accounts()

        if accounts:
            result = app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and "access_token" in result:
                self._access_token = result['access_token']
                return True
        return False

    def is_authenticated(self) -> bool:
        """Check if we have a valid access token."""
        return self._access_token is not None

    def _make_request(self, endpoint: str, method: str = 'GET', **kwargs) -> dict:
        """Make an authenticated request to Microsoft Graph API."""
        if not self._access_token:
            raise Exception("Not authenticated. Call authenticate() first.")

        headers = {
            'Authorization': f'Bearer {self._access_token}',
            'Content-Type': 'application/json'
        }

        url = f"{self.graph_endpoint}{endpoint}"
        response = requests.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            raise Exception("Access token expired. Please re-authenticate.")

        response.raise_for_status()
        return response.json() if response.text else {}

    def get_user_info(self) -> dict:
        """Get authenticated user's profile information."""
        return self._make_request('/me')

    def search_hsa_emails(self, since_date: Optional[datetime] = None, limit: int = 50) -> list:
        """
        Search for emails with HSA in the subject line.

        Args:
            since_date: Only return emails received after this date
            limit: Maximum number of emails to return

        Returns:
            List of email dictionaries with id, subject, from, receivedDateTime, etc.
        """
        # Build OData filter query
        filters = [f"contains(subject, '{self.subject_filter}')"]

        if since_date:
            date_str = since_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            filters.append(f"receivedDateTime ge {date_str}")

        filter_query = ' and '.join(filters)

        # Select only needed fields for efficiency
        select_fields = 'id,subject,from,receivedDateTime,hasAttachments,bodyPreview'

        endpoint = f"/me/messages?$filter={filter_query}&$select={select_fields}&$top={limit}&$orderby=receivedDateTime desc"

        try:
            result = self._make_request(endpoint)
            return result.get('value', [])
        except Exception as e:
            logger.error(f"Error searching emails: {e}")
            raise

    def get_email_details(self, email_id: str) -> dict:
        """Get full details of a specific email."""
        return self._make_request(f'/me/messages/{email_id}')

    def get_email_attachments(self, email_id: str) -> list:
        """
        Get list of attachments for an email.

        Returns:
            List of attachment metadata (without content)
        """
        endpoint = f"/me/messages/{email_id}/attachments"
        result = self._make_request(endpoint)
        return result.get('value', [])

    def download_attachment(self, email_id: str, attachment_id: str, save_path: Path) -> Path:
        """
        Download a specific attachment and save to disk.

        Args:
            email_id: The email message ID
            attachment_id: The attachment ID
            save_path: Directory to save the attachment

        Returns:
            Path to the saved file
        """
        endpoint = f"/me/messages/{email_id}/attachments/{attachment_id}"
        attachment = self._make_request(endpoint)

        if attachment.get('@odata.type') == '#microsoft.graph.fileAttachment':
            import base64

            filename = attachment.get('name', 'attachment')
            content_bytes = base64.b64decode(attachment.get('contentBytes', ''))

            # Ensure save directory exists
            save_path.mkdir(parents=True, exist_ok=True)

            # Create unique filename to avoid collisions
            file_path = save_path / f"{email_id[:8]}_{filename}"

            with open(file_path, 'wb') as f:
                f.write(content_bytes)

            logger.info(f"Saved attachment: {file_path}")
            return file_path

        raise Exception(f"Unsupported attachment type: {attachment.get('@odata.type')}")

    def process_hsa_emails(self, since_date: Optional[datetime] = None) -> list:
        """
        Fetch and process all HSA emails, including downloading attachments.

        Args:
            since_date: Only process emails received after this date

        Returns:
            List of processed email data dictionaries
        """
        emails = self.search_hsa_emails(since_date=since_date)
        processed = []

        for email in emails:
            email_data = {
                'id': email['id'],
                'subject': email.get('subject', ''),
                'from': email.get('from', {}).get('emailAddress', {}).get('address', ''),
                'received_date': email.get('receivedDateTime'),
                'body_preview': email.get('bodyPreview', ''),
                'attachments': []
            }

            # Process attachments if present
            if email.get('hasAttachments'):
                try:
                    attachments = self.get_email_attachments(email['id'])
                    for att in attachments:
                        if att.get('@odata.type') == '#microsoft.graph.fileAttachment':
                            # Download attachment
                            file_path = self.download_attachment(
                                email['id'],
                                att['id'],
                                Config.ATTACHMENTS_DIR
                            )
                            email_data['attachments'].append({
                                'id': att['id'],
                                'name': att.get('name'),
                                'content_type': att.get('contentType'),
                                'size': att.get('size'),
                                'local_path': str(file_path)
                            })
                except Exception as e:
                    logger.error(f"Error processing attachments for email {email['id']}: {e}")

            processed.append(email_data)

        return processed
