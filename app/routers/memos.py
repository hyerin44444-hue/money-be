import uuid
from fastapi import APIRouter, HTTPException
from app.models import Memo, MemoCreate
from app.services import db

router = APIRouter(prefix="/memos", tags=["memos"])


@router.get("", response_model=list[Memo])
def list_memos(year: int, month: int):
    rows = db.get_rows_where("memos", year=year, month=month)
    return [Memo(**r) for r in rows]


@router.post("", response_model=Memo, status_code=201)
def create_memo(body: MemoCreate):
    memo = Memo(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("memos", memo.model_dump())
    return memo


@router.patch("/{memo_id}", response_model=Memo)
def update_memo(memo_id: str, body: dict):
    rows = db.get_rows_where("memos", id=memo_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    updated = db.update_row("memos", memo_id, body)
    return Memo(**updated)


@router.delete("/{memo_id}", status_code=204)
def delete_memo(memo_id: str):
    rows = db.get_rows_where("memos", id=memo_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("memos", memo_id)
