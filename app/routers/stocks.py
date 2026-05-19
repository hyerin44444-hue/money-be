import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services import db

router = APIRouter(prefix="/stocks", tags=["stocks"])


class StockCreate(BaseModel):
    name: str               # 종목명 (예: 삼성전자)
    ticker: str             # 티커 (예: 005930.KS / AAPL)
    quantity: float         # 보유수량
    avg_price: float        # 평균매입가
    owner: str = ""         # 소유자 (예: 박혜린)
    account_type: str = ""  # 계좌종류 (예: 개인연금, ISA, 일반)


class Stock(StockCreate):
    id: str


def fetch_price(ticker: str) -> Optional[float]:
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        price = t.fast_info.get("last_price") or t.fast_info.get("lastPrice")
        if price:
            return float(price)
        hist = t.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None


@router.get("")
def list_stocks():
    rows = db.get_all_rows("stocks")
    result = []
    for r in rows:
        price = fetch_price(r["ticker"])
        quantity = float(r["quantity"])
        avg_price = float(r["avg_price"])
        current_value = price * quantity if price else None
        purchase_value = avg_price * quantity
        profit = (current_value - purchase_value) if current_value is not None else None
        profit_rate = ((price - avg_price) / avg_price * 100) if price else None

        result.append({
            "id": r["id"],
            "name": r["name"],
            "ticker": r["ticker"],
            "quantity": quantity,
            "avg_price": avg_price,
            "owner": r.get("owner", ""),
            "account_type": r.get("account_type", ""),
            "current_price": price,
            "current_value": current_value,
            "purchase_value": purchase_value,
            "profit": profit,
            "profit_rate": round(profit_rate, 2) if profit_rate is not None else None,
        })
    return result


@router.post("", status_code=201)
def create_stock(body: StockCreate):
    rows = db.get_all_rows("stocks")
    existing = next((r for r in rows if r["ticker"].upper() == body.ticker.upper()), None)
    if existing:
        raise HTTPException(status_code=409, detail="이미 등록된 티커입니다.")
    stock = Stock(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("stocks", stock.model_dump())
    return stock


@router.put("/{stock_id}", status_code=200)
def update_stock(stock_id: str, body: StockCreate):
    rows = db.get_rows_where("stocks", id=stock_id)
    if not rows:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    db.update_row("stocks", stock_id, body.model_dump())
    return {"ok": True}


@router.delete("/{stock_id}", status_code=204)
def delete_stock(stock_id: str):
    rows = db.get_rows_where("stocks", id=stock_id)
    if not rows:
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    db.delete_row("stocks", stock_id)
