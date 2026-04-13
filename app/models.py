from pydantic import BaseModel
from typing import Optional


class TransactionCreate(BaseModel):
    date: str          # "2026-03-17"
    type: str          # "income" | "expense"
    category: str
    amount: float
    note: Optional[str] = ""


class TransactionUpdate(BaseModel):
    date: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    note: Optional[str] = None


class Transaction(TransactionCreate):
    id: str
    created_at: str


class Summary(BaseModel):
    year: int
    month: int
    income: float
    expense: float
    balance: float


class CategoryItem(BaseModel):
    name: str
    type: str  # "income" | "expense" | "both"
    sort_order: Optional[int] = 0


class SavingsRecordCreate(BaseModel):
    name: str       # 적금 이름 (예: 청년적금)
    amount: float
    date: str       # YYYY-MM-DD


class SavingsRecord(SavingsRecordCreate):
    id: str


class SavingsSummary(BaseModel):
    name: str
    total: float
    records: list[SavingsRecord]


class FixedExpenseCreate(BaseModel):
    name: str        # 항목명 (예: 넷플릭스)
    amount: float
    category: str
    day: int = 1     # 매월 몇 일


class FixedExpense(FixedExpenseCreate):
    id: str
