"""
Document Processing Service
Extracts data from PDF receipts, EOBs, and other HSA-related documents.
"""
import re
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for extracting data from HSA-related documents."""

    # Common patterns for extracting financial data
    AMOUNT_PATTERNS = [
        r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # $1,234.56
        r'(?:amount|total|charge|payment|due|balance)[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
        r'(?:you owe|patient responsibility|your cost)[:\s]*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',
    ]

    DATE_PATTERNS = [
        r'(?:date of service|service date|dos)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
        r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    ]

    # Common healthcare provider patterns
    PROVIDER_PATTERNS = [
        r'(?:provider|physician|doctor|dr\.?)[:\s]*([A-Za-z\s,\.]+?)(?:\n|$)',
        r'(?:facility|clinic|hospital|medical center)[:\s]*([A-Za-z\s,\.]+?)(?:\n|$)',
    ]

    def __init__(self):
        self._ocr_available = self._check_ocr_available()

    def _check_ocr_available(self) -> bool:
        """Check if OCR (tesseract) is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            logger.info("Tesseract OCR not available. Image processing will be limited.")
            return False

    def extract_text_from_pdf(self, file_path: Path) -> str:
        """
        Extract text content from a PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            Extracted text content
        """
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return '\n'.join(text_parts)

        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            return ""

    def extract_text_from_image(self, file_path: Path) -> str:
        """
        Extract text from an image using OCR.

        Args:
            file_path: Path to the image file

        Returns:
            Extracted text content
        """
        if not self._ocr_available:
            logger.warning("OCR not available. Cannot extract text from image.")
            return ""

        try:
            import pytesseract
            from PIL import Image

            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text

        except Exception as e:
            logger.error(f"Error extracting text from image {file_path}: {e}")
            return ""

    def extract_text(self, file_path: Path) -> str:
        """
        Extract text from a document based on its file type.

        Args:
            file_path: Path to the document

        Returns:
            Extracted text content
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()

        if suffix == '.pdf':
            return self.extract_text_from_pdf(file_path)
        elif suffix in ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif']:
            return self.extract_text_from_image(file_path)
        elif suffix in ['.txt', '.text']:
            try:
                return file_path.read_text()
            except Exception as e:
                logger.error(f"Error reading text file {file_path}: {e}")
                return ""
        else:
            logger.warning(f"Unsupported file type: {suffix}")
            return ""

    def extract_amounts(self, text: str) -> list[float]:
        """
        Extract monetary amounts from text.

        Args:
            text: Text content to search

        Returns:
            List of extracted amounts
        """
        amounts = []
        text_lower = text.lower()

        for pattern in self.AMOUNT_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                try:
                    # Remove commas and convert to float
                    amount = float(match.replace(',', ''))
                    if amount > 0 and amount < 100000:  # Sanity check
                        amounts.append(amount)
                except ValueError:
                    continue

        # Remove duplicates while preserving order
        seen = set()
        unique_amounts = []
        for amount in amounts:
            if amount not in seen:
                seen.add(amount)
                unique_amounts.append(amount)

        return unique_amounts

    def extract_dates(self, text: str) -> list[datetime]:
        """
        Extract dates from text.

        Args:
            text: Text content to search

        Returns:
            List of extracted datetime objects
        """
        dates = []
        text_lower = text.lower()

        for pattern in self.DATE_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            for match in matches:
                try:
                    parsed_date = date_parser.parse(match)
                    # Only include reasonable dates (not too far in past/future)
                    if datetime(2000, 1, 1) <= parsed_date <= datetime(2100, 1, 1):
                        dates.append(parsed_date)
                except Exception:
                    continue

        # Remove duplicates
        return list(set(dates))

    def extract_provider(self, text: str) -> Optional[str]:
        """
        Extract healthcare provider name from text.

        Args:
            text: Text content to search

        Returns:
            Provider name or None
        """
        for pattern in self.PROVIDER_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                provider = match.group(1).strip()
                # Clean up the provider name
                provider = re.sub(r'\s+', ' ', provider)
                if len(provider) > 2 and len(provider) < 100:
                    return provider
        return None

    def categorize_document(self, text: str, filename: str) -> str:
        """
        Determine the category of an HSA document.

        Args:
            text: Document text content
            filename: Original filename

        Returns:
            Category string (Medical, Dental, Vision, Prescription, Other)
        """
        combined = (text + ' ' + filename).lower()

        if any(word in combined for word in ['dental', 'dentist', 'orthodont', 'tooth', 'teeth']):
            return 'Dental'
        elif any(word in combined for word in ['vision', 'eye', 'optical', 'optometrist', 'glasses', 'contacts']):
            return 'Vision'
        elif any(word in combined for word in ['pharmacy', 'prescription', 'rx', 'medication', 'drug']):
            return 'Prescription'
        elif any(word in combined for word in ['medical', 'hospital', 'clinic', 'doctor', 'physician', 'lab', 'diagnostic']):
            return 'Medical'
        else:
            return 'Other'

    def process_document(self, file_path: Path) -> dict:
        """
        Fully process a document and extract all relevant HSA data.

        Args:
            file_path: Path to the document

        Returns:
            Dictionary with extracted data:
            - text: Full extracted text
            - amounts: List of found amounts
            - primary_amount: Best guess at the main amount
            - dates: List of found dates
            - service_date: Best guess at the service date
            - provider: Extracted provider name
            - category: Document category
        """
        file_path = Path(file_path)

        # Extract text
        text = self.extract_text(file_path)

        if not text:
            return {
                'text': '',
                'amounts': [],
                'primary_amount': None,
                'dates': [],
                'service_date': None,
                'provider': None,
                'category': 'Other',
                'error': 'Could not extract text from document'
            }

        # Extract data
        amounts = self.extract_amounts(text)
        dates = self.extract_dates(text)
        provider = self.extract_provider(text)
        category = self.categorize_document(text, file_path.name)

        # Determine primary amount (usually the largest amount that's reasonable)
        primary_amount = None
        if amounts:
            # Filter out very large amounts (likely account balances, etc.)
            reasonable_amounts = [a for a in amounts if a < 10000]
            if reasonable_amounts:
                primary_amount = max(reasonable_amounts)

        # Determine service date (usually the earliest date)
        service_date = None
        if dates:
            # Filter to past dates only
            past_dates = [d for d in dates if d <= datetime.now()]
            if past_dates:
                service_date = min(past_dates)

        return {
            'text': text,
            'amounts': amounts,
            'primary_amount': primary_amount,
            'dates': dates,
            'service_date': service_date,
            'provider': provider,
            'category': category
        }
