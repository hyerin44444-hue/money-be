import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import transactions, summary, categories, fixed_expenses, savings, budgets
from app.services import sheets
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 스프레드시트 메타데이터를 한 번만 조회해 모든 시트를 일괄 초기화
    sheets.ensure_all_headers([
        (settings.TRANSACTIONS_SHEET, ["id", "date", "type", "category", "amount", "note", "created_at"]),
        (settings.CATEGORIES_SHEET,   ["name", "type"]),
        (settings.FIXED_EXPENSES_SHEET, ["id", "name", "amount", "category", "day"]),
        ("savings",                   ["id", "name", "amount", "date"]),
        (settings.BUDGETS_SHEET,      ["id", "category", "amount"]),
    ])
    yield


app = FastAPI(title="가계부 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(fixed_expenses.router, prefix="/api")
app.include_router(savings.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
