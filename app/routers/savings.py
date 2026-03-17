import uuid
from fastapi import APIRouter, HTTPException
from app.models import SavingsRecord, SavingsRecordCreate, SavingsSummary
from app.services import sheets

router = APIRouter(prefix="/savings", tags=["savings"])

SHEET = "savings"
HEADERS = ["id", "name", "amount", "date"]


def _row_to_record(row: dict) -> SavingsRecord:
    return SavingsRecord(
        id=row.get("id", ""),
        name=row.get("name", ""),
        amount=float(row.get("amount", 0)),
        date=row.get("date", ""),
    )


@router.get("", response_model=list[SavingsSummary])
def list_savings():
    """적금 이름별로 그룹핑해서 누적 금액과 함께 반환"""
    rows = sheets.get_all_rows(SHEET)
    records = [_row_to_record(r) for r in rows]

    groups: dict[str, list[SavingsRecord]] = {}
    for r in sorted(records, key=lambda x: x.date, reverse=True):
        groups.setdefault(r.name, []).append(r)

    return [
        SavingsSummary(
            name=name,
            total=sum(r.amount for r in recs),
            records=recs,
        )
        for name, recs in groups.items()
    ]


@router.post("", response_model=SavingsRecord, status_code=201)
def add_savings(body: SavingsRecordCreate):
    record = SavingsRecord(**body.model_dump(), id=str(uuid.uuid4()))
    sheets.append_row(SHEET, [record.id, record.name, record.amount, record.date])
    return record


@router.delete("/{record_id}", status_code=204)
def delete_savings(record_id: str):
    row_index = sheets.find_row_index(SHEET, record_id)
    if row_index is None:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    sheets.delete_row(SHEET, row_index)
