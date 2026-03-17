from fastapi import APIRouter, HTTPException
from app.models import CategoryItem
from app.services import sheets
from app.config import settings

router = APIRouter(prefix="/categories", tags=["categories"])

SHEET = settings.CATEGORIES_SHEET
HEADERS = ["name", "type"]

DEFAULT_CATEGORIES = [
    ["급여", "income"],
    ["부업", "income"],
    ["용돈", "income"],
    ["기타수입", "income"],
    ["식비", "expense"],
    ["교통비", "expense"],
    ["주거비", "expense"],
    ["의류", "expense"],
    ["의료비", "expense"],
    ["문화/여가", "expense"],
    ["교육", "expense"],
    ["통신비", "expense"],
    ["기타지출", "expense"],
]


@router.get("", response_model=list[CategoryItem])
def list_categories():
    rows = sheets.get_all_rows(SHEET)
    if not rows:
        for cat in DEFAULT_CATEGORIES:
            sheets.append_row(SHEET, cat)
        return [CategoryItem(name=c[0], type=c[1]) for c in DEFAULT_CATEGORIES]
    return [CategoryItem(name=r.get("name", ""), type=r.get("type", "")) for r in rows]


@router.post("", response_model=CategoryItem, status_code=201)
def create_category(body: CategoryItem):
    rows = sheets.get_all_rows(SHEET)
    if any(r.get("name") == body.name and r.get("type") == body.type for r in rows):
        raise HTTPException(status_code=409, detail="이미 존재하는 카테고리입니다.")
    sheets.append_row(SHEET, [body.name, body.type])
    return body


@router.delete("/{name}", status_code=204)
def delete_category(name: str, type: str = None):
    rows = sheets.get_all_rows(SHEET)
    for i, r in enumerate(rows):
        if r.get("name") == name and (type is None or r.get("type") == type):
            sheets.delete_row(SHEET, i + 2)  # +2: header row + 0-index offset
            return
    raise HTTPException(status_code=404, detail="카테고리를 찾을 수 없습니다.")
