import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import sheets
from app.config import settings

router = APIRouter(prefix="/budgets", tags=["budgets"])
SHEET = settings.BUDGETS_SHEET


class BudgetUpsert(BaseModel):
    category: str
    amount: float


@router.get("")
def list_budgets():
    return sheets.get_all_rows(SHEET)


@router.post("")
def upsert_budget(body: BudgetUpsert):
    rows = sheets.get_all_rows(SHEET)
    for row in rows:
        if row.get("category") == body.category:
            idx = sheets.find_row_index(SHEET, row["id"])
            sheets.update_row(SHEET, idx, [row["id"], body.category, body.amount])
            return {"id": row["id"], "category": body.category, "amount": body.amount}
    new_id = str(uuid.uuid4())
    sheets.append_row(SHEET, [new_id, body.category, body.amount])
    return {"id": new_id, "category": body.category, "amount": body.amount}


@router.delete("/{budget_id}")
def delete_budget(budget_id: str):
    idx = sheets.find_row_index(SHEET, budget_id)
    if not idx:
        raise HTTPException(status_code=404, detail="예산 항목을 찾을 수 없습니다.")
    sheets.delete_row(SHEET, idx)
    return {"ok": True}
