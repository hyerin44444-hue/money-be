import uuid
from fastapi import APIRouter, HTTPException

from app.models import Event, EventCreate
from app.services import db

router = APIRouter(prefix="/events", tags=["events"])


def _row_to_event(row: dict) -> Event:
    return Event(
        id=row["id"],
        person_name=row["person_name"],
        category=row["category"],
        received_amount=float(row.get("received_amount") or 0),
        given_amount=float(row.get("given_amount") or 0),
        received_date=row.get("received_date") or "",
        given_date=row.get("given_date") or "",
        note=row.get("note") or "",
    )


@router.get("", response_model=list[Event])
def list_events():
    return [_row_to_event(r) for r in db.get_all_rows("events")]


@router.post("", response_model=Event, status_code=201)
def create_event(body: EventCreate):
    ev = Event(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("events", ev.model_dump())
    return ev


@router.put("/{event_id}", response_model=Event)
def update_event(event_id: str, body: EventCreate):
    rows = db.get_rows_where("events", id=event_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    ev = Event(**body.model_dump(), id=event_id)
    db.update_row("events", event_id, ev.model_dump())
    return ev


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: str):
    rows = db.get_rows_where("events", id=event_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("events", event_id)
