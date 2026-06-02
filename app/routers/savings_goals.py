import uuid
from fastapi import APIRouter
from app.models import SavingsGoal, SavingsGoalCreate
from app.services import db

router = APIRouter(prefix="/savings-goals", tags=["savings-goals"])


@router.get("", response_model=SavingsGoal | None)
def get_goal():
    rows = db.get_all_rows("savings_goals")
    return SavingsGoal(**rows[0]) if rows else None


@router.post("", response_model=SavingsGoal)
def upsert_goal(body: SavingsGoalCreate):
    rows = db.get_all_rows("savings_goals")
    if rows:
        updated = db.update_row("savings_goals", rows[0]["id"], body.model_dump())
        return SavingsGoal(**updated)
    goal = SavingsGoal(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("savings_goals", goal.model_dump())
    return goal


@router.delete("", status_code=204)
def delete_goal():
    rows = db.get_all_rows("savings_goals")
    for r in rows:
        db.delete_row("savings_goals", r["id"])
