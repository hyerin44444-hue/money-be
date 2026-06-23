import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services import db
from app.models import SavingsRecord, SavingsRecordCreate, SavingsSummary, GoldHolding, GoldHoldingCreate
from app.routers.stocks import fetch_price, is_korean, get_usd_krw
from app.routers.cash import CashCreate, Cash

router = APIRouter(prefix="/sihyeon", tags=["sihyeon"])

# ── 모델 ────────────────────────────────────────────────

class SihyeonStockCreate(BaseModel):
    name: str
    ticker: str
    quantity: float
    avg_price: float
    account_type: str = ""

class SihyeonStock(SihyeonStockCreate):
    id: str

# ── 적금 ────────────────────────────────────────────────

@router.get("/savings", response_model=list[SavingsSummary])
def list_savings():
    rows = db.get_all_rows("sihyeon_savings")
    records = [SavingsRecord(**r) for r in rows]
    groups: dict[str, list] = {}
    for r in sorted(records, key=lambda x: x.date, reverse=True):
        groups.setdefault(r.name, []).append(r)
    return [
        SavingsSummary(name=name, total=sum(r.amount for r in recs), records=recs)
        for name, recs in groups.items()
    ]

@router.post("/savings", response_model=SavingsRecord, status_code=201)
def add_savings(body: SavingsRecordCreate):
    record = SavingsRecord(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("sihyeon_savings", record.model_dump())
    return record

@router.delete("/savings/{record_id}", status_code=204)
def delete_savings(record_id: str):
    if not db.get_rows_where("sihyeon_savings", id=record_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("sihyeon_savings", record_id)

# ── 주식 ────────────────────────────────────────────────

@router.get("/stocks")
def list_stocks():
    rows = db.get_all_rows("sihyeon_stocks")
    if not rows:
        return []
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
        current_price_krw = price * fx if price else None
        avg_price_krw = avg_price * fx
        current_value = current_price_krw * quantity if current_price_krw else None
        purchase_value = avg_price_krw * quantity
        profit = (current_value - purchase_value) if current_value is not None else None
        profit_rate = ((price - avg_price) / avg_price * 100) if price else None
        day_change_krw = day_change * fx if day_change is not None else None
        result.append({
            "id": r["id"],
            "name": r["name"],
            "ticker": r["ticker"],
            "quantity": quantity,
            "avg_price": avg_price,
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

@router.post("/stocks", status_code=201)
def create_stock(body: SihyeonStockCreate):
    rows = db.get_all_rows("sihyeon_stocks")
    if any(r["ticker"].upper() == body.ticker.upper() and r.get("account_type", "") == body.account_type for r in rows):
        raise HTTPException(status_code=409, detail="동일한 계좌에 이미 등록된 티커입니다.")
    stock = SihyeonStock(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("sihyeon_stocks", stock.model_dump())
    return stock

@router.put("/stocks/{stock_id}", status_code=200)
def update_stock(stock_id: str, body: SihyeonStockCreate):
    if not db.get_rows_where("sihyeon_stocks", id=stock_id):
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    db.update_row("sihyeon_stocks", stock_id, body.model_dump())
    return {"ok": True}

@router.delete("/stocks/{stock_id}", status_code=204)
def delete_stock(stock_id: str):
    if not db.get_rows_where("sihyeon_stocks", id=stock_id):
        raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다.")
    db.delete_row("sihyeon_stocks", stock_id)

# ── 현금 ────────────────────────────────────────────────

@router.get("/cash", response_model=list[Cash])
def list_cash():
    return [Cash(**r) for r in db.get_all_rows("sihyeon_cash")]

@router.post("/cash", response_model=Cash, status_code=201)
def create_cash(body: CashCreate):
    item = Cash(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("sihyeon_cash", item.model_dump())
    return item

@router.put("/cash/{item_id}", response_model=Cash)
def update_cash(item_id: str, body: CashCreate):
    if not db.get_rows_where("sihyeon_cash", id=item_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.update_row("sihyeon_cash", item_id, body.model_dump())
    return Cash(**body.model_dump(), id=item_id)

@router.delete("/cash/{item_id}", status_code=204)
def delete_cash(item_id: str):
    if not db.get_rows_where("sihyeon_cash", id=item_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("sihyeon_cash", item_id)

# ── 금 ────────────────────────────────────────────────

@router.get("/gold", response_model=list[GoldHolding])
def list_gold():
    return [GoldHolding(**r) for r in db.get_all_rows("sihyeon_gold")]

@router.post("/gold", response_model=GoldHolding, status_code=201)
def create_gold(body: GoldHoldingCreate):
    item = GoldHolding(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("sihyeon_gold", item.model_dump())
    return item

@router.put("/gold/{item_id}", response_model=GoldHolding)
def update_gold(item_id: str, body: GoldHoldingCreate):
    if not db.get_rows_where("sihyeon_gold", id=item_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.update_row("sihyeon_gold", item_id, body.model_dump())
    return GoldHolding(**body.model_dump(), id=item_id)

@router.delete("/gold/{item_id}", status_code=204)
def delete_gold(item_id: str):
    if not db.get_rows_where("sihyeon_gold", id=item_id):
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("sihyeon_gold", item_id)
