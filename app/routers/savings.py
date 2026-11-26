import uuid
from fastapi import APIRouter, HTTPException
from app.models import SavingsRecord, SavingsRecordCreate, SavingsSummary
from app.services import db

router = APIRouter(prefix="/savings", tags=["savings"])


EMERGENCY = "비상금"


def _emergency_withdrawals() -> list[SavingsRecord]:
    """내역에서 '비상금에서 사용'으로 표시한 지출을 비상금의 출금(음수) 기록으로 변환한다."""
    try:
        rows = db.get_rows_where("transactions", from_emergency=True)
    except Exception:  # from_emergency 컬럼을 아직 추가하지 않은 경우
        return []
    return [
        SavingsRecord(
            id=f"tx-{r['id']}",
            name=EMERGENCY,
            amount=-float(r["amount"]),
            date=r["date"],
            is_stock=False,
        )
        for r in rows
        if r.get("type") == "expense"
    ]


@router.get("", response_model=list[SavingsSummary])
def list_savings():
    rows = db.get_all_rows("savings")
    records = [SavingsRecord(**r) for r in rows]
    records += _emergency_withdrawals()

    groups: dict[str, list[SavingsRecord]] = {}
    for r in sorted(records, key=lambda x: x.date, reverse=True):
        groups.setdefault(r.name, []).append(r)

    return [
        SavingsSummary(
            name=name,
            total=sum(r.amount for r in recs),
            non_stock_total=sum(r.amount for r in recs if not r.is_stock),
            records=recs,
        )
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
