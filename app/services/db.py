"""
Supabase service layer.
"""
from functools import lru_cache
from supabase import create_client, Client
from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def warmup():
    """앱 시작 시 Supabase 클라이언트를 미리 초기화한다."""
    get_client()


def get_transactions_by_month(year: int, month: int) -> list[dict]:
    """해당 월 거래만 서버 사이드 필터링으로 가져온다."""
    start = f"{year}-{month:02d}-01"
    if month == 12:
        end = f"{year + 1}-01-01"
    else:
        end = f"{year}-{month + 1:02d}-01"
    res = (
        get_client()
        .table("transactions")
        .select("*")
        .gte("date", start)
        .lt("date", end)
        .order("date", desc=True)
        .execute()
    )
    return res.data or []


def get_transactions_by_year(year: int) -> list[dict]:
    """해당 연도 거래만 서버 사이드 필터링으로 가져온다."""
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01"
    res = (
        get_client()
        .table("transactions")
        .select("*")
        .gte("date", start)
        .lt("date", end)
        .execute()
    )
    return res.data or []


def get_all_rows(table: str) -> list[dict]:
    res = get_client().table(table).select("*").execute()
    return res.data or []


def insert_row(table: str, data: dict) -> dict:
    res = get_client().table(table).insert(data).execute()
    return res.data[0]


def update_row(table: str, id_value: str, data: dict) -> dict:
    res = get_client().table(table).update(data).eq("id", id_value).execute()
    return res.data[0]


def delete_row(table: str, id_value: str) -> None:
    get_client().table(table).delete().eq("id", id_value).execute()


def get_rows_where(table: str, **filters) -> list[dict]:
    q = get_client().table(table).select("*")
    for col, val in filters.items():
        if val is not None:
            q = q.eq(col, val)
    res = q.execute()
    return res.data or []
