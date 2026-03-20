import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import db

router = APIRouter(prefix="/budgets", tags=["budgets"])


class BudgetUpsert(BaseModel):
    category: str
    amount: float


@router.get("")
def list_budgets():
    return db.get_all_rows("budgets")


@router.post("")
def upsert_budget(body: BudgetUpsert):
    rows = db.get_all_rows("budgets")
    existing = next((r for r in rows if r["category"] == body.category), None)
    if existing:
        db.update_row("budgets", existing["id"], {"amount": body.amount})
        return {"id": existing["id"], "category": body.category, "amount": body.amount}
    new_id = str(uuid.uuid4())
    db.insert_row("budgets", {"id": new_id, "category": body.category, "amount": body.amount})
    return {"id": new_id, "category": body.category, "amount": body.amount}


@router.delete("/{budget_id}")
def delete_budget(budget_id: str):
    rows = db.get_rows_where("budgets", id=budget_id)
    if not rows:
        raise HTTPException(status_code=404, detail="예산 항목을 찾을 수 없습니다.")
    db.delete_row("budgets", budget_id)
    return {"ok": True}
