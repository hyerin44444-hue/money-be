from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.models import CategoryItem
from app.services import db

router = APIRouter(prefix="/categories", tags=["categories"])

DEFAULT_CATEGORIES = [
    {"name": "급여",   "type": "income",  "sort_order": 0},
    {"name": "부업",   "type": "income",  "sort_order": 1},
    {"name": "용돈",   "type": "income",  "sort_order": 2},
    {"name": "기타수입", "type": "income",  "sort_order": 3},
    {"name": "식비",   "type": "expense", "sort_order": 0},
    {"name": "교통비", "type": "expense", "sort_order": 1},
    {"name": "주거비", "type": "expense", "sort_order": 2},
    {"name": "의류",   "type": "expense", "sort_order": 3},
    {"name": "의료비", "type": "expense", "sort_order": 4},
    {"name": "문화/여가", "type": "expense", "sort_order": 5},
    {"name": "교육",   "type": "expense", "sort_order": 6},
    {"name": "통신비", "type": "expense", "sort_order": 7},
    {"name": "기타지출", "type": "expense", "sort_order": 8},
]


def _parse_category(row: dict) -> CategoryItem:
    return CategoryItem(
        name=row["name"],
        type=row["type"],
        sort_order=row.get("sort_order", 0) or 0,
        parent=row.get("parent") or None,
    )


@router.get("", response_model=list[CategoryItem])
def list_categories():
    rows = db.get_all_rows("categories")
    if not rows:
        for cat in DEFAULT_CATEGORIES:
            db.insert_row("categories", cat)
        return [CategoryItem(**c) for c in DEFAULT_CATEGORIES]
    result = [_parse_category(r) for r in rows]
    result.sort(key=lambda c: (c.type, c.sort_order))
    return result


@router.post("", response_model=CategoryItem, status_code=201)
def create_category(body: CategoryItem):
    rows = db.get_all_rows("categories")
    if any(r["name"] == body.name and r["type"] == body.type for r in rows):
        raise HTTPException(status_code=409, detail="이미 존재하는 카테고리입니다.")
    # 새 카테고리는 같은 타입 중 마지막 순서로 추가
    same_type = [r for r in rows if r["type"] == body.type]
    max_order = max((r.get("sort_order", 0) or 0 for r in same_type), default=-1)
    data = {"name": body.name, "type": body.type, "sort_order": max_order + 1}
    if body.parent:
        data["parent"] = body.parent
    db.insert_row("categories", data)
    return CategoryItem(**data)


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


class ReorderRequest(BaseModel):
    categories: list[dict]  # [{"name": "식비", "type": "expense", "sort_order": 0}, ...]


@router.put("/reorder", status_code=200)
def reorder_categories(body: ReorderRequest):
    rows = db.get_all_rows("categories")
    for item in body.categories:
        target = next(
            (r for r in rows if r["name"] == item["name"] and r["type"] == item["type"]),
            None
        )
        if target:
            db.update_row("categories", target["id"], {"sort_order": item["sort_order"]})
    return {"ok": True}
