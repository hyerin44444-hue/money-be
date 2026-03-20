"""
Supabase service layer.
"""
from functools import lru_cache
from supabase import create_client, Client
from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


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
