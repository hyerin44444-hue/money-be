import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from typing import Optional

from app.models import FixedExpense, FixedExpenseCreate, Transaction
from app.services import sheets
from app.config import settings

router = APIRouter(prefix="/fixed-expenses", tags=["fixed-expenses"])

SHEET = "fixed_expenses"
HEADERS = ["id", "name", "amount", "category", "day"]
TX_SHEET = settings.TRANSACTIONS_SHEET


def _row_to_fe(row: dict) -> FixedExpense:
    return FixedExpense(
        id=row.get("id", ""),
        name=row.get("name", ""),
        amount=float(row.get("amount", 0)),
        category=row.get("category", ""),
        day=int(row.get("day", 1)),
    )


@router.get("", response_model=list[FixedExpense])
def list_fixed_expenses():
    return [_row_to_fe(r) for r in sheets.get_all_rows(SHEET)]


@router.post("", response_model=FixedExpense, status_code=201)
def create_fixed_expense(body: FixedExpenseCreate):
    fe = FixedExpense(**body.model_dump(), id=str(uuid.uuid4()))
    sheets.append_row(SHEET, [fe.id, fe.name, fe.amount, fe.category, fe.day])
    return fe


@router.put("/{fe_id}", response_model=FixedExpense)
def update_fixed_expense(fe_id: str, body: FixedExpenseCreate):
    row_index = sheets.find_row_index(SHEET, fe_id)
    if row_index is None:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    fe = FixedExpense(**body.model_dump(), id=fe_id)
    sheets.update_row(SHEET, row_index, [fe.id, fe.name, fe.amount, fe.category, fe.day])
    return fe


@router.delete("/{fe_id}", status_code=204)
def delete_fixed_expense(fe_id: str):
    row_index = sheets.find_row_index(SHEET, fe_id)
    if row_index is None:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    sheets.delete_row(SHEET, row_index)


@router.post("/apply", response_model=list[Transaction])
def apply_fixed_expenses(year: int, month: int):
    """고정비를 해당 월의 거래 내역으로 일괄 추가"""
    fixed = [_row_to_fe(r) for r in sheets.get_all_rows(SHEET)]
    if not fixed:
        return []

    existing = sheets.get_all_rows(TX_SHEET)
    month_prefix = f"{year}-{month:02d}-"

    added = []
    for fe in fixed:
        day = min(fe.day, 28)
        date_str = f"{year}-{month:02d}-{day:02d}"

        # 같은 달에 같은 항목이 이미 있으면 스킵
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
        sheets.append_row(TX_SHEET, [t.id, t.date, t.type, t.category, t.amount, t.note, t.created_at])
        added.append(t)

    return added
