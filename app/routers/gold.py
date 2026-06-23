import uuid
from fastapi import APIRouter, HTTPException
from app.models import GoldHolding, GoldHoldingCreate
from app.services import db

router = APIRouter(prefix="/gold", tags=["gold"])

# 금 시세 캐시 (빈번한 호출 방지)
_gold_cache: dict = {}


def fetch_gold_price_krw() -> dict | None:
    """국제 금 시세 → KRW/g 변환 (살때/팔때)"""
    try:
        import yfinance as yf

        # 금 선물 (USD/troy oz)
        gc = yf.Ticker("GC=F")
        gold_usd = gc.fast_info.get("last_price") or gc.fast_info.get("lastPrice")
        if not gold_usd:
            hist = gc.history(period="1d")
            gold_usd = float(hist["Close"].iloc[-1]) if not hist.empty else None

        if not gold_usd:
            return None

        # USD/KRW
        usd_krw = yf.Ticker("USDKRW=X").fast_info.get("last_price") or 1380.0

        # 전일 종가
        prev_close = gc.fast_info.get("previous_close") or gc.fast_info.get("previousClose")
        if not prev_close:
            hist = gc.history(period="5d")
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else gold_usd

        # 그램당 기준가 (1 troy oz = 31.1035g)
        base_per_gram = float(gold_usd) * float(usd_krw) / 31.1035
        prev_per_gram = float(prev_close) * float(usd_krw) / 31.1035
        day_change_per_gram = base_per_gram - prev_per_gram
        day_change_rate = (day_change_per_gram / prev_per_gram) * 100 if prev_per_gram else 0

        return {
            "base_per_gram": round(base_per_gram),
            "buy_per_gram":  round(base_per_gram * 1.05),
            "sell_per_gram": round(base_per_gram * 0.97),
            "gold_usd_oz":   round(float(gold_usd), 2),
            "usd_krw":       round(float(usd_krw)),
            "day_change_per_gram": round(day_change_per_gram),
            "day_change_rate":     round(day_change_rate, 2),
        }
    except Exception:
        return None


@router.get("/price")
def get_gold_price():
    data = fetch_gold_price_krw()
    if not data:
        raise HTTPException(status_code=503, detail="금 시세 조회 실패")
    return data


@router.get("", response_model=list[GoldHolding])
def list_gold():
    return [GoldHolding(**r) for r in db.get_all_rows("gold")]


@router.post("", response_model=GoldHolding, status_code=201)
def create_gold(body: GoldHoldingCreate):
    holding = GoldHolding(**body.model_dump(), id=str(uuid.uuid4()))
    db.insert_row("gold", holding.model_dump())
    return holding


@router.put("/{gold_id}", response_model=GoldHolding)
def update_gold(gold_id: str, body: GoldHoldingCreate):
    rows = db.get_rows_where("gold", id=gold_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.update_row("gold", gold_id, body.model_dump())
    return GoldHolding(**body.model_dump(), id=gold_id)


@router.delete("/{gold_id}", status_code=204)
def delete_gold(gold_id: str):
    rows = db.get_rows_where("gold", id=gold_id)
    if not rows:
        raise HTTPException(status_code=404, detail="항목을 찾을 수 없습니다.")
    db.delete_row("gold", gold_id)
