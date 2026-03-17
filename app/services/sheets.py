"""
Google Sheets service layer using gspread.
"""

from functools import lru_cache
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


@lru_cache(maxsize=1)
def _get_spreadsheet():
    creds = Credentials.from_service_account_file(settings.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(settings.SPREADSHEET_ID)


@lru_cache(maxsize=None)
def get_sheet(sheet_name: str):
    spreadsheet = _get_spreadsheet()
    return spreadsheet.worksheet(sheet_name)


def get_all_rows(sheet_name: str) -> list[dict]:
    return get_sheet(sheet_name).get_all_records()


def append_row(sheet_name: str, values: list[Any]) -> None:
    get_sheet(sheet_name).append_row(values, value_input_option="USER_ENTERED")


def find_row_index(sheet_name: str, id_value: str) -> int | None:
    cell = get_sheet(sheet_name).find(id_value, in_column=1)
    return cell.row if cell else None


def update_row(sheet_name: str, row_index: int, values: list[Any]) -> None:
    ws = get_sheet(sheet_name)
    ws.update(f"A{row_index}", [values])


def delete_row(sheet_name: str, row_index: int) -> None:
    get_sheet(sheet_name).delete_rows(row_index)


def ensure_headers(sheet_name: str, headers: list[str]) -> None:
    ensure_all_headers([(sheet_name, headers)])


def ensure_all_headers(sheets_config: list[tuple[str, list[str]]]) -> None:
    """시트 목록을 한 번만 조회한 뒤 누락된 시트를 일괄 생성하고 헤더를 설정한다."""
    spreadsheet = _get_spreadsheet()
    existing = {ws.title: ws for ws in spreadsheet.worksheets()}

    for sheet_name, headers in sheets_config:
        if sheet_name in existing:
            ws = existing[sheet_name]
        else:
            ws = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=len(headers))
            existing[sheet_name] = ws

        if not ws.row_values(1):
            ws.update("A1", [headers])

    get_sheet.cache_clear()
