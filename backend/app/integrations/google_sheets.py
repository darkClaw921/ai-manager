"""Google Sheets exporter: export leads and analytics to Google Spreadsheets.

Uses gspread with service account authentication.
Optional integration -- gracefully skips when credentials are not configured.
"""

import asyncio
import json
import structlog
from datetime import datetime, timezone
from typing import Any

logger = structlog.get_logger(__name__)

# Column headers for leads export
LEAD_COLUMNS = [
    "ID",
    "Имя",
    "Email",
    "Телефон",
    "Компания",
    "Канал",
    "Статус",
    "Interest Score",
    "Этап квалификации",
    "Дата создания",
]

ANALYTICS_COLUMNS = [
    "Дата",
    "Всего лидов",
    "Новых за день",
    "Квалифицированных",
    "Записей",
    "Средний score",
    "Уровень квалификации %",
]


class GoogleSheetsExporter:
    """Export leads and analytics data to Google Sheets via service account.

    Requires:
        - credentials_json: Service account JSON key (as string).
        - spreadsheet_id: ID of the target Google Spreadsheet.

    If credentials are not provided, all export calls are silently skipped.
    """

    def __init__(self, credentials_json: str, spreadsheet_id: str) -> None:
        self._credentials_json = credentials_json
        self._spreadsheet_id = spreadsheet_id
        self._client = None
        self._spreadsheet = None

    def _get_client(self):
        """Lazy-initialize gspread client with service account credentials.

        Returns:
            gspread.Client or None if initialization fails.
        """
        if self._client is not None:
            return self._client

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            logger.warning("gspread or google-auth not installed, Google Sheets export disabled")
            return None

        if not self._credentials_json:
            logger.warning("No Google Sheets credentials configured, export disabled")
            return None

        try:
            creds_data = json.loads(self._credentials_json)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            credentials = Credentials.from_service_account_info(creds_data, scopes=scopes)
            self._client = gspread.authorize(credentials)
            return self._client
        except Exception:
            logger.exception("Failed to initialize Google Sheets client")
            return None

    def _get_spreadsheet(self):
        """Get the target spreadsheet, creating it if needed.

        Returns:
            gspread.Spreadsheet or None.
        """
        if self._spreadsheet is not None:
            return self._spreadsheet

        client = self._get_client()
        if client is None:
            return None

        try:
            self._spreadsheet = client.open_by_key(self._spreadsheet_id)
            return self._spreadsheet
        except Exception:
            logger.exception("Failed to open spreadsheet: %s", self._spreadsheet_id)
            return None

    def _get_or_create_worksheet(self, title: str, headers: list[str]):
        """Get worksheet by title, or create it with headers if it doesn't exist.

        Args:
            title: Worksheet (tab) name.
            headers: Column headers for a new worksheet.

        Returns:
            gspread.Worksheet or None.
        """
        spreadsheet = self._get_spreadsheet()
        if spreadsheet is None:
            return None

        try:
            return spreadsheet.worksheet(title)
        except Exception:
            # Worksheet not found, create it
            try:
                ws = spreadsheet.add_worksheet(title=title, rows=1000, cols=len(headers))
                ws.append_row(headers)
                logger.info("Created worksheet '%s' in spreadsheet", title)
                return ws
            except Exception:
                logger.exception("Failed to create worksheet '%s'", title)
                return None

    async def export_leads(self, leads_data: list[dict[str, Any]]) -> int:
        """Export leads to the 'Лиды' worksheet (append mode).

        Args:
            leads_data: List of lead dicts with keys matching LEAD_COLUMNS.

        Returns:
            Number of rows exported. 0 if skipped or failed.
        """
        if not self._credentials_json:
            logger.debug("Google Sheets export skipped: no credentials")
            return 0

        def _sync_export() -> int:
            ws = self._get_or_create_worksheet("Лиды", LEAD_COLUMNS)
            if ws is None:
                return 0

            rows = []
            for lead in leads_data:
                rows.append([
                    str(lead.get("id", "")),
                    lead.get("name", "") or "",
                    lead.get("email", "") or "",
                    lead.get("phone", "") or "",
                    lead.get("company", "") or "",
                    lead.get("channel_type", "") or "",
                    lead.get("status", "") or "",
                    lead.get("interest_score", 0),
                    lead.get("qualification_stage", "") or "",
                    lead.get("created_at", ""),
                ])

            if not rows:
                return 0

            try:
                ws.append_rows(rows, value_input_option="USER_ENTERED")
                logger.info("Exported %d leads to Google Sheets", len(rows))
                return len(rows)
            except Exception:
                logger.exception("Failed to export leads to Google Sheets")
                return 0

        try:
            return await asyncio.to_thread(_sync_export)
        except Exception:
            logger.exception("Error in async lead export")
            return 0

    async def export_analytics(self, data: dict[str, Any]) -> int:
        """Export analytics snapshot to the 'Аналитика' worksheet.

        Args:
            data: Analytics dict with keys: date, total_leads, new_today,
                  qualified_count, bookings_count, avg_score, qualification_rate.

        Returns:
            Number of rows exported (1 on success, 0 on failure/skip).
        """
        if not self._credentials_json:
            logger.debug("Google Sheets analytics export skipped: no credentials")
            return 0

        def _sync_export() -> int:
            ws = self._get_or_create_worksheet("Аналитика", ANALYTICS_COLUMNS)
            if ws is None:
                return 0

            row = [
                data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                data.get("total_leads", 0),
                data.get("new_today", 0),
                data.get("qualified_count", 0),
                data.get("bookings_count", 0),
                data.get("avg_score", 0),
                data.get("qualification_rate", 0),
            ]

            try:
                ws.append_row(row, value_input_option="USER_ENTERED")
                logger.info("Exported analytics to Google Sheets")
                return 1
            except Exception:
                logger.exception("Failed to export analytics to Google Sheets")
                return 0

        try:
            return await asyncio.to_thread(_sync_export)
        except Exception:
            logger.exception("Error in async analytics export")
            return 0
