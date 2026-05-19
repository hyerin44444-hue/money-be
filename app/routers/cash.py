import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services import db

router = APIRouter(prefix="/cash", tags=["cash"])


class CashCreate(BaseModel):
    category: str
    amount: float
    note: Optional[str] = ""
    date: Optional[str] = None


class Cash(CashCreate):
    id: str
    created_at: str


@router.get("")
def list_cash():
    rows = db.get_all_rows("cash")
    return sorted(rows, key=lambda r: r.get("created_at", ""), reverse=True)


@router.post("", status_code=201)
def create_cash(body: CashCreate):
    data = body.model_dump()
    data["date"] = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    item = Cash(
        **data,
        id=str(uuid.uuid4()),
        created_at=datetime.now().isoformat(),
    )
    db.insert_row("cash", item.model_dump())
    return item


@router.put("/{cash_id}", status_code=200)
def update_cash(cash_id: str, body: CashCreate):
    rows = db.get_rows_where("cash", id=cash_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.update_row("cash", cash_id, body.model_dump())
    return {"ok": True}


@router.delete("/{cash_id}", status_code=204)
def delete_cash(cash_id: str):
    rows = db.get_rows_where("cash", id=cash_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("cash", cash_id)
