import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models import Transaction, TransactionCreate, TransactionUpdate
from app.services import sheets
from app.config import settings

router = APIRouter(prefix="/transactions", tags=["transactions"])

HEADERS = ["id", "date", "type", "category", "amount", "note", "created_at"]
SHEET = settings.TRANSACTIONS_SHEET


def _row_to_transaction(row: dict) -> Transaction:
    return Transaction(
        id=row.get("id", ""),
        date=row.get("date", ""),
        type=row.get("type", ""),
        category=row.get("category", ""),
        amount=float(row.get("amount", 0)),
        note=row.get("note", ""),
        created_at=row.get("created_at", ""),
    )


def _transaction_to_row(t: Transaction) -> list:
    return [t.id, t.date, t.type, t.category, t.amount, t.note, t.created_at]


@router.get("", response_model=list[Transaction])
def list_transactions(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    rows = sheets.get_all_rows(SHEET)
    result = [_row_to_transaction(r) for r in rows]

    if year:
        result = [t for t in result if t.date.startswith(str(year))]
    if month:
        month_str = f"{year or ''}-{month:02d}" if year else f"-{month:02d}-"
        result = [t for t in result if f"-{month:02d}-" in t.date]
    if type:
        result = [t for t in result if t.type == type]
    if category:
        result = [t for t in result if t.category == category]

    return sorted(result, key=lambda t: t.date, reverse=True)


@router.post("", response_model=Transaction, status_code=201)
def create_transaction(body: TransactionCreate):
    t = Transaction(
        **body.model_dump(),
        id=str(uuid.uuid4()),
        created_at=datetime.now().isoformat(),
    )
    sheets.append_row(SHEET, _transaction_to_row(t))
    return t


@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(transaction_id: str, body: TransactionUpdate):
    row_index = sheets.find_row_index(SHEET, transaction_id)
    if row_index is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    rows = sheets.get_all_rows(SHEET)
    existing = next((r for r in rows if r.get("id") == transaction_id), None)
    if not existing:
        raise HTTPException(status_code=404, detail="Transaction not found")

    current = _row_to_transaction(existing)
    updated_data = current.model_dump()
    for field, value in body.model_dump(exclude_none=True).items():
        updated_data[field] = value

    updated = Transaction(**updated_data)
    sheets.update_row(SHEET, row_index, _transaction_to_row(updated))
    return updated


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str):
    row_index = sheets.find_row_index(SHEET, transaction_id)
    if row_index is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    sheets.delete_row(SHEET, row_index)
