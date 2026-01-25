# HSA Spending Tracker

A web application for tracking Health Savings Account (HSA) spending by automatically scanning your Outlook inbox for HSA-related emails, extracting documents, and organizing transaction data.

## Features

- **Outlook Email Integration**: Scan your inbox for emails with "HSA" in the subject line
- **Document Extraction**: Automatically extract data from PDF receipts and EOBs
- **OCR Support**: Optional OCR for image-based receipts (requires Tesseract)
- **Transaction Management**: View, edit, and categorize HSA transactions
- **Spending Categories**: Medical, Dental, Vision, Prescription, and Other
- **Status Tracking**: Mark transactions as verified or reimbursed
- **Data Export**: Export all data to JSON format

## Quick Start

### 1. Install Dependencies

```bash
cd hsa-tracker
pip install -r requirements.txt
```

### 2. Configure Azure AD (for Outlook sync)

1. Go to [Azure App Registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. Create a new registration:
   - Name: "HSA Tracker"
   - Supported account types: "Personal Microsoft accounts only"
3. Configure API permissions:
   - Add Microsoft Graph > Delegated permissions: `Mail.Read`, `User.Read`
4. Enable public client flows in Authentication settings
5. Copy your Client ID

### 3. Set Up Environment

```bash
cp .env.example .env
# Edit .env and add your Azure credentials
```

### 4. Run the Application

```bash
python run.py
```

Open http://localhost:5000 in your browser.

## Usage

### Syncing Emails

1. Navigate to the **Sync** page
2. Click "Connect to Outlook" and follow the authentication flow
3. Click "Sync HSA Emails" to scan your inbox
4. View imported transactions on the **Dashboard** or **Transactions** page

### Manual Transactions

You can also add transactions manually:
1. Go to **Transactions**
2. Click "Add Transaction"
3. Fill in the details and save

### Managing Transactions

- **View**: Click on any transaction to see full details and attachments
- **Verify**: Mark transactions as verified after reviewing
- **Reimbursed**: Track which expenses have been reimbursed
- **Delete**: Remove transactions you no longer need

## Project Structure

```
hsa-tracker/
├── app/
│   ├── __init__.py          # Flask application factory
│   ├── config.py             # Configuration settings
│   ├── models.py             # Database models
│   ├── routes.py             # Web routes and API endpoints
│   ├── services/
│   │   ├── outlook_service.py    # Outlook/Graph API integration
│   │   └── document_service.py   # PDF/OCR document processing
│   ├── static/
│   │   └── css/style.css     # Application styles
│   └── templates/            # HTML templates
├── data/                     # Database and attachments storage
├── requirements.txt          # Python dependencies
├── run.py                    # Application entry point
└── .env.example              # Environment configuration template
```

## Optional: OCR Support

For better receipt scanning, install Tesseract OCR:

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download from [GitHub Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/transactions` | GET | List all transactions |
| `/api/transactions` | POST | Create a new transaction |
| `/api/transactions/<id>` | PUT | Update a transaction |
| `/api/transactions/<id>` | DELETE | Delete a transaction |
| `/api/stats` | GET | Get spending statistics |
| `/api/auth/start` | POST | Start Outlook authentication |
| `/api/sync/emails` | POST | Sync HSA emails |

## Security Notes

- Credentials are stored locally in the `.env` file
- Email attachments are saved to `data/attachments/`
- The SQLite database is stored at `data/hsa_tracker.db`
- Never commit your `.env` file to version control

## License

MIT License
