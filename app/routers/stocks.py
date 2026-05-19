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


def is_korean(ticker: str) -> bool:
    return ticker.upper().endswith(".KS") or ticker.upper().endswith(".KQ")


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


_usd_krw_cache: dict = {"rate": None}

def get_usd_krw() -> float:
    try:
        import yfinance as yf
        rate = yf.Ticker("USDKRW=X").fast_info.get("last_price")
        if rate:
            _usd_krw_cache["rate"] = float(rate)
            return float(rate)
    except Exception:
        pass
    return _usd_krw_cache.get("rate") or 1380.0  # 조회 실패 시 기본값


@router.get("")
def list_stocks():
    rows = db.get_all_rows("stocks")
    if not rows:
        return []

    # 미국 주식이 하나라도 있으면 환율 조회
    has_us = any(not is_korean(r["ticker"]) for r in rows)
    usd_krw = get_usd_krw() if has_us else 1.0

    result = []
    for r in rows:
        price = fetch_price(r["ticker"])
        quantity = float(r["quantity"])
        avg_price = float(r["avg_price"])
        korean = is_korean(r["ticker"])
        fx = 1.0 if korean else usd_krw  # 원화 환산 배율

        current_price_krw  = price * fx if price else None
        avg_price_krw      = avg_price * fx
        current_value      = current_price_krw * quantity if current_price_krw else None
        purchase_value     = avg_price_krw * quantity
        profit             = (current_value - purchase_value) if current_value is not None else None
        profit_rate        = ((price - avg_price) / avg_price * 100) if price else None

        result.append({
            "id": r["id"],
            "name": r["name"],
            "ticker": r["ticker"],
            "quantity": quantity,
            "avg_price": avg_price,
            "owner": r.get("owner", ""),
            "account_type": r.get("account_type", ""),
            "currency": "KRW" if korean else "USD",
            "usd_krw": round(usd_krw) if not korean else None,
            "current_price": price,
            "current_price_krw": current_price_krw,
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
