"""
HSA Tracker Database Models
Defines the data structures for HSA transactions and related entities.
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()


class HSATransaction(Base):
    """Represents an HSA spending transaction."""
    __tablename__ = 'hsa_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Transaction details
    amount = Column(Float, nullable=False)
    description = Column(String(500))
    provider = Column(String(255))  # Healthcare provider name
    category = Column(String(100))  # e.g., "Medical", "Dental", "Vision", "Prescription"

    # Dates
    transaction_date = Column(DateTime)
    service_date = Column(DateTime)  # Date of actual service
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Source email information
    email_id = Column(String(255))  # Microsoft Graph email ID
    email_subject = Column(String(500))
    email_received_date = Column(DateTime)
    email_sender = Column(String(255))

    # Status
    is_verified = Column(Boolean, default=False)  # User has verified the data
    is_reimbursed = Column(Boolean, default=False)  # HSA reimbursement received

    # Notes
    notes = Column(Text)

    # Relationships
    attachments = relationship("Attachment", back_populates="transaction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HSATransaction(id={self.id}, amount={self.amount}, provider={self.provider})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'amount': self.amount,
            'description': self.description,
            'provider': self.provider,
            'category': self.category,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'service_date': self.service_date.isoformat() if self.service_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'email_subject': self.email_subject,
            'email_received_date': self.email_received_date.isoformat() if self.email_received_date else None,
            'email_sender': self.email_sender,
            'is_verified': self.is_verified,
            'is_reimbursed': self.is_reimbursed,
            'notes': self.notes,
            'attachments': [att.to_dict() for att in self.attachments]
        }


class Attachment(Base):
    """Represents a document attachment from an HSA email."""
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(Integer, ForeignKey('hsa_transactions.id'), nullable=False)

    # File information
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))  # Local storage path
    file_type = Column(String(50))  # MIME type
    file_size = Column(Integer)  # Size in bytes

    # Extraction status
    is_processed = Column(Boolean, default=False)
    extracted_text = Column(Text)  # OCR or extracted text content
    extracted_amount = Column(Float)  # Amount found in document

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    transaction = relationship("HSATransaction", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment(id={self.id}, filename={self.filename})>"

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'transaction_id': self.transaction_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'is_processed': self.is_processed,
            'extracted_amount': self.extracted_amount,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class SyncStatus(Base):
    """Tracks email synchronization status."""
    __tablename__ = 'sync_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    last_sync_date = Column(DateTime)
    emails_processed = Column(Integer, default=0)
    last_email_id = Column(String(255))  # Track last processed email for delta sync
    sync_errors = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'last_sync_date': self.last_sync_date.isoformat() if self.last_sync_date else None,
            'emails_processed': self.emails_processed,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Database:
    """Database connection manager."""

    def __init__(self, db_path: str):
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(self.engine)

    def get_session(self):
        """Get a new database session."""
        return self.Session()
