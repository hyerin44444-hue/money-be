"""
실행: python debug_sheets.py
스프레드시트에 실제로 어떤 시트 탭이 있는지 출력합니다.
"""
import os
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
CREDS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")

print(f"SPREADSHEET_ID: {SPREADSHEET_ID!r}")
print(f"CREDS_FILE: {CREDS_FILE!r}")

creds = Credentials.from_service_account_file(
    CREDS_FILE,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
service = build("sheets", "v4", credentials=creds)
spreadsheets = service.spreadsheets()

metadata = spreadsheets.get(spreadsheetId=SPREADSHEET_ID).execute()

print("\n=== 실제 시트 탭 목록 ===")
for s in metadata["sheets"]:
    title = s["properties"]["title"]
    gid = s["properties"]["sheetId"]
    print(f"  탭 이름: {title!r}  (gid={gid})")

print("\n=== 읽기 테스트 ===")
for sheet_name in [s["properties"]["title"] for s in metadata["sheets"]]:
    try:
        result = spreadsheets.values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{sheet_name}!A1:Z10"
        ).execute()
        print(f"  {sheet_name!r}: OK (rows={len(result.get('values', []))})")
    except Exception as e:
        print(f"  {sheet_name!r}: ERROR - {e}")
