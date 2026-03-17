from fastapi import APIRouter, Query
from app.models import Summary
from app.services import sheets
from app.config import settings

router = APIRouter(prefix="/summary", tags=["summary"])

SHEET = settings.TRANSACTIONS_SHEET


@router.get("", response_model=Summary)
def get_summary(
    year: int = Query(...),
    month: int = Query(...),
):
    rows = sheets.get_all_rows(SHEET)
    month_prefix = f"{year}-{month:02d}-"

    income = 0.0
    expense = 0.0
    for row in rows:
        if not row.get("date", "").startswith(month_prefix):
            continue
        amount = float(row.get("amount", 0))
        if row.get("type") == "income":
            income += amount
        elif row.get("type") == "expense":
            expense += amount

    return Summary(
        year=year,
        month=month,
        income=income,
        expense=expense,
        balance=income - expense,
    )


@router.get("/monthly")
def get_monthly_summary(year: int = Query(...)):
    rows = sheets.get_all_rows(SHEET)
    year_prefix = f"{year}-"

    monthly: dict[int, dict] = {m: {"income": 0.0, "expense": 0.0} for m in range(1, 13)}

    for row in rows:
        date = row.get("date", "")
        if not date.startswith(year_prefix):
            continue
        try:
            m = int(date[5:7])
        except (ValueError, IndexError):
            continue
        amount = float(row.get("amount", 0))
        if row.get("type") == "income":
            monthly[m]["income"] += amount
        elif row.get("type") == "expense":
            monthly[m]["expense"] += amount

    return [
        {
            "year": year,
            "month": m,
            "income": v["income"],
            "expense": v["expense"],
            "balance": v["income"] - v["expense"],
        }
        for m, v in monthly.items()
    ]


@router.get("/yearly")
def get_yearly_summary():
    rows = sheets.get_all_rows(SHEET)

    yearly: dict[int, dict] = {}
    for row in rows:
        date = row.get("date", "")
        if not date or len(date) < 4:
            continue
        try:
            y = int(date[:4])
        except ValueError:
            continue
        if y not in yearly:
            yearly[y] = {"income": 0.0, "expense": 0.0}
        amount = float(row.get("amount", 0))
        if row.get("type") == "income":
            yearly[y]["income"] += amount
        elif row.get("type") == "expense":
            yearly[y]["expense"] += amount

    return sorted(
        [
            {
                "year": y,
                "income": v["income"],
                "expense": v["expense"],
                "balance": v["income"] - v["expense"],
            }
            for y, v in yearly.items()
        ],
        key=lambda x: x["year"],
    )
