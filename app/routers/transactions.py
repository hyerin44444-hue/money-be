import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models import Transaction, TransactionCreate, TransactionUpdate
from app.services import db

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=list[Transaction])
def list_transactions(
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None),
    type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
):
    rows = db.get_all_rows("transactions")
    result = [Transaction(**r) for r in rows]

    if year:
        result = [t for t in result if t.date.startswith(str(year))]
    if month:
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
    db.insert_row("transactions", t.model_dump())
    return t


@router.put("/{transaction_id}", response_model=Transaction)
def update_transaction(transaction_id: str, body: TransactionUpdate):
    rows = db.get_rows_where("transactions", id=transaction_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Transaction not found")

    current = Transaction(**rows[0])
    updated_data = current.model_dump()
    for field, value in body.model_dump(exclude_none=True).items():
        updated_data[field] = value

    updated = Transaction(**updated_data)
    db.update_row("transactions", transaction_id, updated.model_dump())
    return updated


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(transaction_id: str):
    rows = db.get_rows_where("transactions", id=transaction_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete_row("transactions", transaction_id)
