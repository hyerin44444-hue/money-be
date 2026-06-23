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


def fetch_korean_price(code: str) -> dict:
    """네이버 금융 실시간 시세 (한국 주식)"""
    try:
        import requests
        url = f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{code}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        data = res.json()
        items = data["result"]["areas"][0]["datas"]
        if items:
            d = items[0]
            price = float(d["nv"])
            day_change = float(d.get("cv", 0))      # 전일 대비 등락폭
            day_change_rate = float(d.get("cr", 0)) # 등락률 %
            return {"price": price, "day_change": day_change, "day_change_rate": day_change_rate}
    except Exception:
        pass
    return {"price": None, "day_change": None, "day_change_rate": None}


def fetch_us_price(ticker: str) -> dict:
    """yfinance 시세 (미국 주식)"""
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        fi = t.fast_info
        price = fi.get("last_price") or fi.get("lastPrice")
        prev_close = fi.get("previous_close") or fi.get("previousClose")
        if price:
            price = float(price)
            day_change = round(price - float(prev_close), 4) if prev_close else None
            day_change_rate = round((price - float(prev_close)) / float(prev_close) * 100, 2) if prev_close else None
            return {"price": price, "day_change": day_change, "day_change_rate": day_change_rate}
        hist = t.history(period="2d")
        if len(hist) >= 2:
            price = float(hist["Close"].iloc[-1])
            prev = float(hist["Close"].iloc[-2])
            return {"price": price, "day_change": round(price - prev, 4), "day_change_rate": round((price - prev) / prev * 100, 2)}
        if len(hist) == 1:
            return {"price": float(hist["Close"].iloc[-1]), "day_change": None, "day_change_rate": None}
    except Exception:
        pass
    return {"price": None, "day_change": None, "day_change_rate": None}


def fetch_price(ticker: str) -> dict:
    if is_korean(ticker):
        code = ticker.upper().replace(".KS", "").replace(".KQ", "")
        return fetch_korean_price(code)
    return fetch_us_price(ticker)


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
        pdata = fetch_price(r["ticker"])
        price = pdata["price"]
        day_change = pdata["day_change"]
        day_change_rate = pdata["day_change_rate"]

        quantity = float(r["quantity"])
        avg_price = float(r["avg_price"])
        korean = is_korean(r["ticker"])
        fx = 1.0 if korean else usd_krw

        current_price_krw  = price * fx if price else None
        avg_price_krw      = avg_price * fx
        current_value      = current_price_krw * quantity if current_price_krw else None
        purchase_value     = avg_price_krw * quantity
        profit             = (current_value - purchase_value) if current_value is not None else None
        profit_rate        = ((price - avg_price) / avg_price * 100) if price else None
        day_change_krw     = day_change * fx if day_change is not None else None

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
            "day_change": day_change,
            "day_change_krw": round(day_change_krw) if day_change_krw is not None else None,
            "day_change_rate": day_change_rate,
        })
    return result


@router.post("", status_code=201)
def create_stock(body: StockCreate):
    rows = db.get_all_rows("stocks")
    existing = next((
        r for r in rows
        if r["ticker"].upper() == body.ticker.upper()
        and r.get("owner", "") == body.owner
        and r.get("account_type", "") == body.account_type
    ), None)
    if existing:
        raise HTTPException(status_code=409, detail="동일한 소유자/계좌에 이미 등록된 티커입니다.")
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
