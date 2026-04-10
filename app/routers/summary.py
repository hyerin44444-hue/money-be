from fastapi import APIRouter, Query
from app.models import Summary
from app.services import db

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=Summary)
def get_summary(year: int = Query(...), month: int = Query(...)):
    rows = db.get_transactions_by_month(year, month)

    income = expense = 0.0
    for row in rows:
        amount = float(row.get("amount", 0))
        if row.get("type") == "income":
            income += amount
        elif row.get("type") == "expense":
            expense += amount

    return Summary(year=year, month=month, income=income, expense=expense, balance=income - expense)


@router.get("/monthly")
def get_monthly_summary(year: int = Query(...)):
    rows = db.get_transactions_by_year(year)

    monthly: dict[int, dict] = {m: {"income": 0.0, "expense": 0.0} for m in range(1, 13)}
    for row in rows:
        date = row.get("date", "")
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
        {"year": year, "month": m, "income": v["income"], "expense": v["expense"], "balance": v["income"] - v["expense"]}
        for m, v in monthly.items()
    ]


@router.get("/yearly")
def get_yearly_summary():
    rows = db.get_all_rows("transactions")

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
        [{"year": y, "income": v["income"], "expense": v["expense"], "balance": v["income"] - v["expense"]}
         for y, v in yearly.items()],
        key=lambda x: x["year"],
    )
