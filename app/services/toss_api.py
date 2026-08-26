import os
import time
import requests

TOSS_BASE = "https://openapi.tossinvest.com"
_token_cache: dict = {"token": None, "expires_at": 0}


def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    client_id = os.getenv("TOSS_CLIENT_ID", "")
    client_secret = os.getenv("TOSS_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise ValueError("TOSS_CLIENT_ID / TOSS_CLIENT_SECRET 환경변수가 설정되지 않았습니다.")

    res = requests.post(
        f"{TOSS_BASE}/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    res.raise_for_status()
    data = res.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + data.get("expires_in", 86400)
    return _token_cache["token"]


def _headers(account_seq: str | None = None) -> dict:
    h = {"Authorization": f"Bearer {_get_token()}"}
    if account_seq:
        h["X-Tossinvest-Account"] = account_seq
    return h


def get_accounts() -> list:
    res = requests.get(f"{TOSS_BASE}/api/v1/accounts", headers=_headers(), timeout=10)
    res.raise_for_status()
    return res.json()


def get_holdings(account_seq: str) -> dict:
    res = requests.get(
        f"{TOSS_BASE}/api/v1/holdings",
        headers=_headers(account_seq),
        timeout=10,
    )
    res.raise_for_status()
    return res.json()
