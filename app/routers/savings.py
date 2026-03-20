import uuid
from fastapi import APIRouter, HTTPException
from app.models import SavingsRecord, SavingsRecordCreate, SavingsSummary
from app.services import db

router = APIRouter(prefix="/savings", tags=["savings"])


@router.get("", response_model=list[SavingsSummary])
def list_savings():
    rows = db.get_all_rows("savings")
    records = [SavingsRecord(**r) for r in rows]

    groups: dict[str, list[SavingsRecord]] = {}
    for r in sorted(records, key=lambda x: x.date, reverse=True):
        groups.setdefault(r.name, []).append(r)

    return [
        SavingsSummary(name=name, total=sum(r.amount for r in recs), records=recs)
        for name, recs in groups.items()
    ]


@router.post("", response_model=SavingsRecord, status_code=201)
def add_savings(body: SavingsRecordCreate):
    record = SavingsRecord(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("savings", record.model_dump())
    return record


@router.delete("/{record_id}", status_code=204)
def delete_savings(record_id: str):
    rows = db.get_rows_where("savings", id=record_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("savings", record_id)
