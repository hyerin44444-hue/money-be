from fastapi import APIRouter, HTTPException, Query
from app.models import CategoryItem
from app.services import db

router = APIRouter(prefix="/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    {"name": "급여",   "type": "income"},
    {"name": "부업",   "type": "income"},
    {"name": "용돈",   "type": "income"},
    {"name": "기타수입", "type": "income"},
    {"name": "식비",   "type": "expense"},
    {"name": "교통비", "type": "expense"},
    {"name": "주거비", "type": "expense"},
    {"name": "의류",   "type": "expense"},
    {"name": "의료비", "type": "expense"},
    {"name": "문화/여가", "type": "expense"},
    {"name": "교육",   "type": "expense"},
    {"name": "통신비", "type": "expense"},
    {"name": "기타지출", "type": "expense"},
]


@router.get("", response_model=list[CategoryItem])
def list_categories():
    rows = db.get_all_rows("categories")
    if not rows:
        for cat in DEFAULT_CATEGORIES:
            db.insert_row("categories", cat)
        return [CategoryItem(**c) for c in DEFAULT_CATEGORIES]
    return [CategoryItem(name=r["name"], type=r["type"]) for r in rows]


@router.post("", response_model=CategoryItem, status_code=201)
def create_category(body: CategoryItem):
    rows = db.get_all_rows("categories")
    if any(r["name"] == body.name and r["type"] == body.type for r in rows):
        raise HTTPException(status_code=409, detail="이미 존재하는 카테고리입니다.")
    db.insert_row("categories", {"name": body.name, "type": body.type})
    return body


@router.delete("/{name}", status_code=204)
def delete_category(name: str, type: str = Query(None)):
    rows = db.get_all_rows("categories")
    target = next(
        (r for r in rows if r["name"] == name and (type is None or r["type"] == type)),
        None
    )
    if not target:
        raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
    db.get_client().table("categories").delete().eq("id", target["id"]).execute()
