import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models import FixedExpense, FixedExpenseCreate, Transaction
from app.services import db

router = APIRouter(prefix="/fixed-expenses", tags=["fixed-expenses"])


def _row_to_fe(row: dict) -> FixedExpense:
    return FixedExpense(
        id=row["id"],
        name=row["name"],
        amount=float(row["amount"]),
        category=row["category"],
        day=int(row["day"]),
        group_name=row.get("group_name") or "",
        sort_order=row.get("sort_order") or 0,
    )


def _sorted_fixed() -> list[FixedExpense]:
    return sorted(
        (_row_to_fe(r) for r in db.get_all_rows("fixed_expenses")),
        key=lambda f: f.sort_order,
    )


@router.get("", response_model=list[FixedExpense])
def list_fixed_expenses():
    return _sorted_fixed()


@router.post("", response_model=FixedExpense, status_code=201)
def create_fixed_expense(body: FixedExpenseCreate):
    max_order = max((f.sort_order for f in _sorted_fixed()), default=-1)
    fe = FixedExpense(**body.model_dump(), id=str(uuid.uuid4()), sort_order=max_order + 1)
    db.insert_row("fixed_expenses", fe.model_dump())
    return fe


class ReorderBody(BaseModel):
    ids: list[str]  # 원하는 순서대로 나열한 고정비 id 목록


@router.put("/reorder", status_code=200)
def reorder_fixed_expenses(body: ReorderBody):
    for i, fe_id in enumerate(body.ids):
        db.update_row("fixed_expenses", fe_id, {"sort_order": i})
    return {"ok": True}


@router.put("/{fe_id}", response_model=FixedExpense)
def update_fixed_expense(fe_id: str, body: FixedExpenseCreate):
    rows = db.get_rows_where("fixed_expenses", id=fe_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    fe = FixedExpense(**body.model_dump(), id=fe_id, sort_order=_row_to_fe(rows[0]).sort_order)
    db.update_row("fixed_expenses", fe_id, fe.model_dump())
    return fe


@router.delete("/{fe_id}", status_code=204)
def delete_fixed_expense(fe_id: str):
    rows = db.get_rows_where("fixed_expenses", id=fe_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("fixed_expenses", fe_id)


class ApplyBody(BaseModel):
    ids: list[str] = []


@router.post("/apply", response_model=list[Transaction])
def apply_fixed_expenses(year: int, month: int, body: ApplyBody = ApplyBody()):
    fixed = _sorted_fixed()
    if body.ids:
        fixed = [f for f in fixed if f.id in body.ids]
    if not fixed:
        return []

    existing = db.get_transactions_by_month(year, month)
    month_prefix = f"{year}-{month:02d}-"

    added = []
    for fe in fixed:
        day = min(fe.day, 28)
        date_str = f"{year}-{month:02d}-{day:02d}"
        already = any(
            r.get("note") == fe.name and r.get("date", "").startswith(month_prefix)
            for r in existing
        )
        if already:
            continue
        t = Transaction(
            id=str(uuid.uuid4()),
            date=date_str,
            type="expense",
            category=fe.category,
            amount=fe.amount,
            note=fe.name,
            created_at=datetime.now().isoformat(),
        )
        db.insert_row("transactions", t.model_dump())
        added.append(t)

    return added
