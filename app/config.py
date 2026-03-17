import os
import json
import tempfile
from dotenv import load_dotenv

load_dotenv()


def _resolve_credentials_file() -> str:
    """GOOGLE_CREDENTIALS_JSON 환경변수가 있으면 임시 파일로 저장해 경로를 반환."""
    json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if json_str:
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        tmp.write(json_str)
        tmp.flush()
        return tmp.name
    return os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")


class Settings:
    SPREADSHEET_ID: str = os.getenv("SPREADSHEET_ID", "")
    GOOGLE_CREDENTIALS_FILE: str = _resolve_credentials_file()
    TRANSACTIONS_SHEET: str = "transactions"
    CATEGORIES_SHEET: str = "categories"
    FIXED_EXPENSES_SHEET: str = "fixed_expenses"
    BUDGETS_SHEET: str = "budgets"


settings = Settings()
