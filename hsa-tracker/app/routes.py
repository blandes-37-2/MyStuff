"""
HSA Tracker Web Routes
Flask routes for the web interface and API endpoints.
"""
import logging
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, render_template, request, jsonify,
    redirect, url_for, flash, session, current_app
)

from .models import HSATransaction, Attachment, SyncStatus
from .services import OutlookService, DocumentService
from .config import Config

logger = logging.getLogger(__name__)

# Create blueprints
main_bp = Blueprint('main', __name__)
api_bp = Blueprint('api', __name__, url_prefix='/api')


def init_app(app):
    """Register blueprints with the Flask app."""
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)


# ============================================================================
# Web Interface Routes
# ============================================================================

@main_bp.route('/')
def index():
    """Dashboard home page."""
    db_session = current_app.db.get_session()
    try:
        transactions = db_session.query(HSATransaction).order_by(
            HSATransaction.created_at.desc()
        ).limit(10).all()

        # Calculate summary stats
        total_spent = db_session.query(HSATransaction).with_entities(
            HSATransaction.amount
        ).all()
        total_amount = sum(t.amount or 0 for t in total_spent)

        # Get last sync status
        sync_status = db_session.query(SyncStatus).order_by(
            SyncStatus.created_at.desc()
        ).first()

        return render_template(
            'index.html',
            transactions=[t.to_dict() for t in transactions],
            total_amount=total_amount,
            transaction_count=len(total_spent),
            sync_status=sync_status.to_dict() if sync_status else None,
            is_configured=Config.is_azure_configured()
        )
    finally:
        db_session.close()


@main_bp.route('/transactions')
def transactions():
    """View all transactions."""
    db_session = current_app.db.get_session()
    try:
        all_transactions = db_session.query(HSATransaction).order_by(
            HSATransaction.transaction_date.desc()
        ).all()

        return render_template(
            'transactions.html',
            transactions=[t.to_dict() for t in all_transactions]
        )
    finally:
        db_session.close()


@main_bp.route('/transactions/<int:transaction_id>')
def transaction_detail(transaction_id):
    """View single transaction details."""
    db_session = current_app.db.get_session()
    try:
        transaction = db_session.query(HSATransaction).filter_by(
            id=transaction_id
        ).first()

        if not transaction:
            flash('Transaction not found', 'error')
            return redirect(url_for('main.transactions'))

        return render_template(
            'transaction_detail.html',
            transaction=transaction.to_dict()
        )
    finally:
        db_session.close()


@main_bp.route('/sync')
def sync_page():
    """Email sync management page."""
    return render_template(
        'sync.html',
        is_configured=Config.is_azure_configured()
    )


@main_bp.route('/settings')
def settings():
    """Settings page."""
    return render_template(
        'settings.html',
        is_configured=Config.is_azure_configured()
    )


# ============================================================================
# API Routes
# ============================================================================

@api_bp.route('/transactions', methods=['GET'])
def get_transactions():
    """Get all transactions."""
    db_session = current_app.db.get_session()
    try:
        transactions = db_session.query(HSATransaction).order_by(
            HSATransaction.created_at.desc()
        ).all()
        return jsonify([t.to_dict() for t in transactions])
    finally:
        db_session.close()


@api_bp.route('/transactions', methods=['POST'])
def create_transaction():
    """Create a new transaction manually."""
    data = request.get_json()

    db_session = current_app.db.get_session()
    try:
        transaction = HSATransaction(
            amount=data.get('amount'),
            description=data.get('description'),
            provider=data.get('provider'),
            category=data.get('category', 'Other'),
            transaction_date=datetime.fromisoformat(data['transaction_date']) if data.get('transaction_date') else datetime.now(),
            service_date=datetime.fromisoformat(data['service_date']) if data.get('service_date') else None,
            notes=data.get('notes')
        )
        db_session.add(transaction)
        db_session.commit()

        return jsonify(transaction.to_dict()), 201
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error creating transaction: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        db_session.close()


@api_bp.route('/transactions/<int:transaction_id>', methods=['PUT'])
def update_transaction(transaction_id):
    """Update an existing transaction."""
    data = request.get_json()

    db_session = current_app.db.get_session()
    try:
        transaction = db_session.query(HSATransaction).filter_by(id=transaction_id).first()

        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        # Update fields
        if 'amount' in data:
            transaction.amount = data['amount']
        if 'description' in data:
            transaction.description = data['description']
        if 'provider' in data:
            transaction.provider = data['provider']
        if 'category' in data:
            transaction.category = data['category']
        if 'is_verified' in data:
            transaction.is_verified = data['is_verified']
        if 'is_reimbursed' in data:
            transaction.is_reimbursed = data['is_reimbursed']
        if 'notes' in data:
            transaction.notes = data['notes']

        db_session.commit()
        return jsonify(transaction.to_dict())
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error updating transaction: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        db_session.close()


@api_bp.route('/transactions/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """Delete a transaction."""
    db_session = current_app.db.get_session()
    try:
        transaction = db_session.query(HSATransaction).filter_by(id=transaction_id).first()

        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404

        db_session.delete(transaction)
        db_session.commit()
        return jsonify({'message': 'Transaction deleted'}), 200
    except Exception as e:
        db_session.rollback()
        logger.error(f"Error deleting transaction: {e}")
        return jsonify({'error': str(e)}), 400
    finally:
        db_session.close()


@api_bp.route('/auth/start', methods=['POST'])
def start_auth():
    """Start Outlook authentication flow."""
    if not Config.is_azure_configured():
        return jsonify({'error': 'Azure AD not configured. Please set up .env file.'}), 400

    try:
        outlook = OutlookService()
        auth_info = outlook.authenticate_interactive()

        # Store flow in session for completion
        session['auth_flow'] = auth_info['flow']

        return jsonify({
            'user_code': auth_info['user_code'],
            'verification_uri': auth_info['verification_uri'],
            'message': auth_info['message']
        })
    except Exception as e:
        logger.error(f"Error starting auth: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/auth/complete', methods=['POST'])
def complete_auth():
    """Complete Outlook authentication flow."""
    flow = session.get('auth_flow')
    if not flow:
        return jsonify({'error': 'No authentication flow in progress'}), 400

    try:
        outlook = OutlookService()
        success = outlook.complete_authentication(flow)

        if success:
            session.pop('auth_flow', None)
            session['outlook_authenticated'] = True
            return jsonify({'message': 'Authentication successful'})
        else:
            return jsonify({'error': 'Authentication failed'}), 400
    except Exception as e:
        logger.error(f"Error completing auth: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sync/emails', methods=['POST'])
def sync_emails():
    """Sync HSA emails from Outlook."""
    if not Config.is_azure_configured():
        return jsonify({'error': 'Azure AD not configured'}), 400

    try:
        outlook = OutlookService()

        # Try silent auth first
        if not outlook.authenticate_silent():
            return jsonify({'error': 'Not authenticated. Please authenticate first.'}), 401

        # Get last sync date
        db_session = current_app.db.get_session()
        last_sync = db_session.query(SyncStatus).order_by(
            SyncStatus.created_at.desc()
        ).first()

        since_date = last_sync.last_sync_date if last_sync else None

        # Fetch and process emails
        emails = outlook.process_hsa_emails(since_date=since_date)

        # Process each email
        doc_service = DocumentService()
        processed_count = 0

        for email in emails:
            # Check if already processed
            existing = db_session.query(HSATransaction).filter_by(
                email_id=email['id']
            ).first()

            if existing:
                continue

            # Create transaction
            transaction = HSATransaction(
                email_id=email['id'],
                email_subject=email['subject'],
                email_sender=email['from'],
                email_received_date=datetime.fromisoformat(
                    email['received_date'].replace('Z', '+00:00')
                ) if email['received_date'] else None,
                description=email['body_preview'][:500] if email.get('body_preview') else None
            )

            # Process attachments
            for att_data in email.get('attachments', []):
                attachment = Attachment(
                    filename=att_data['name'],
                    file_path=att_data['local_path'],
                    file_type=att_data['content_type'],
                    file_size=att_data['size']
                )

                # Extract data from document
                if att_data.get('local_path'):
                    doc_data = doc_service.process_document(Path(att_data['local_path']))
                    attachment.extracted_text = doc_data.get('text', '')[:5000]
                    attachment.extracted_amount = doc_data.get('primary_amount')
                    attachment.is_processed = True

                    # Use extracted data for transaction if not set
                    if doc_data.get('primary_amount') and not transaction.amount:
                        transaction.amount = doc_data['primary_amount']
                    if doc_data.get('service_date') and not transaction.service_date:
                        transaction.service_date = doc_data['service_date']
                    if doc_data.get('provider') and not transaction.provider:
                        transaction.provider = doc_data['provider']
                    if doc_data.get('category'):
                        transaction.category = doc_data['category']

                transaction.attachments.append(attachment)

            db_session.add(transaction)
            processed_count += 1

        # Update sync status
        sync_status = SyncStatus(
            last_sync_date=datetime.utcnow(),
            emails_processed=processed_count
        )
        db_session.add(sync_status)
        db_session.commit()

        return jsonify({
            'message': f'Synced {processed_count} new emails',
            'emails_processed': processed_count
        })

    except Exception as e:
        logger.error(f"Error syncing emails: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        db_session.close()


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get spending statistics."""
    db_session = current_app.db.get_session()
    try:
        transactions = db_session.query(HSATransaction).all()

        total_spent = sum(t.amount or 0 for t in transactions)

        # Group by category
        by_category = {}
        for t in transactions:
            cat = t.category or 'Other'
            by_category[cat] = by_category.get(cat, 0) + (t.amount or 0)

        # Group by month
        by_month = {}
        for t in transactions:
            if t.transaction_date:
                month_key = t.transaction_date.strftime('%Y-%m')
                by_month[month_key] = by_month.get(month_key, 0) + (t.amount or 0)

        return jsonify({
            'total_spent': total_spent,
            'transaction_count': len(transactions),
            'by_category': by_category,
            'by_month': by_month,
            'verified_count': sum(1 for t in transactions if t.is_verified),
            'reimbursed_count': sum(1 for t in transactions if t.is_reimbursed)
        })
    finally:
        db_session.close()
