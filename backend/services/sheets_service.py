"""
Google Sheets Service - Reads and updates lead data from Google Sheets.
Falls back to MongoDB-only mode if Google Sheets is not configured.
"""
import json
import base64
import logging
from typing import Optional, List
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from config import settings
from models.schemas import Lead

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly"
]

# Expected column headers
EXPECTED_HEADERS = ["id", "name", "phone", "status", "call_attempts", "language", "last_called_at", "whatsapp_sent"]


class SheetsService:
    def __init__(self):
        self.client = None
        self.sheet = None
        self._initialized = False

    def _init_client(self):
        """Initialize Google Sheets client with service account credentials."""
        if self._initialized:
            return self._initialized

        if not settings.is_sheets_configured():
            logger.warning("Google Sheets not configured. Using MongoDB-only mode.")
            return False

        try:
            creds_json = json.loads(
                base64.b64decode(settings.GOOGLE_SERVICE_ACCOUNT_JSON).decode()
            )
            credentials = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
            self.client = gspread.authorize(credentials)
            self.sheet = self.client.open_by_key(settings.GOOGLE_SHEET_ID).sheet1
            self._initialized = True
            logger.info("Google Sheets client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            return False

    def get_all_leads(self) -> List[Lead]:
        """Read all leads from Google Sheet."""
        if not self._init_client():
            return []

        try:
            records = self.sheet.get_all_records()
            leads = []
            for idx, record in enumerate(records, start=2):  # Row 1 is header
                lead = Lead(
                    id=str(record.get("id", "")),
                    name=str(record.get("name", "")),
                    phone=str(record.get("phone", "")),
                    status=str(record.get("status", "")),
                    call_attempts=int(record.get("call_attempts", 0) or 0),
                    language=str(record.get("language", "")),
                    last_called_at=str(record.get("last_called_at", "")) or None,
                    whatsapp_sent=str(record.get("whatsapp_sent", "No")),
                    row_number=idx
                )
                leads.append(lead)
            logger.info(f"Retrieved {len(leads)} leads from Google Sheets")
            return leads
        except Exception as e:
            logger.error(f"Error reading leads from Sheets: {e}")
            return []

    def get_next_eligible_lead(self) -> Optional[Lead]:
        """Get the next lead eligible for calling."""
        leads = self.get_all_leads()
        for lead in leads:
            if lead.status == "" and lead.call_attempts < 2:
                logger.info(f"Next eligible lead: {lead.name} ({lead.phone})")
                return lead
        logger.info("No eligible leads found")
        return None

    def update_lead_status(self, row_number: int, status: str, call_attempts: int,
                           language: str = "", whatsapp_sent: str = "No"):
        """Update a lead's status in Google Sheets."""
        if not self._init_client():
            return False

        try:
            now = datetime.now(timezone.utc).isoformat()
            # Update columns: status(D), call_attempts(E), language(F), last_called_at(G), whatsapp_sent(H)
            self.sheet.update_cell(row_number, 4, status)
            self.sheet.update_cell(row_number, 5, call_attempts)
            if language:
                self.sheet.update_cell(row_number, 6, language)
            self.sheet.update_cell(row_number, 7, now)
            self.sheet.update_cell(row_number, 8, whatsapp_sent)
            logger.info(f"Updated lead at row {row_number}: status={status}")
            return True
        except Exception as e:
            logger.error(f"Error updating lead in Sheets: {e}")
            return False


sheets_service = SheetsService()
