import uuid
import re
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from app.models import Transaction
from app.services import db

router = APIRouter(prefix="/kakao", tags=["kakao"])


# ── 카카오 요청/응답 스키마 ──────────────────────────────────────────────

class _Base(BaseModel):
    model_config = {"extra": "ignore"}

class KakaoAction(_Base):
    params: dict[str, Any] = {}

class KakaoUserRequest(_Base):
    utterance: str

class KakaoRequest(_Base):
    userRequest: KakaoUserRequest
    action: KakaoAction = KakaoAction()


QUICK_REPLIES = [
    {"action": "message", "label": "📊 이번달 요약", "messageText": "이번달 요약"},
    {"action": "message", "label": "💸 이번달 지출", "messageText": "이번달 지출"},
    {"action": "message", "label": "💰 이번달 수입", "messageText": "이번달 수입"},
    {"action": "message", "label": "🏦 이번달 저금", "messageText": "이번달 저금"},
]


def kakao_text(text: str, quick_replies: bool = True) -> dict:
    res = {
        "version": "2.0",
        "template": {"outputs": [{"simpleText": {"text": text}}]},
    }
    if quick_replies:
        res["template"]["quickReplies"] = QUICK_REPLIES
    return res


# ── 카테고리 별칭 ────────────────────────────────────────────────────────

CATEGORY_MAP = {
    # 지출
    "식비": "식비", "밥": "식비", "점심": "식비", "저녁": "식비", "아침": "식비",
    "카페": "식비", "커피": "식비", "배달": "식비", "편의점": "식비",
    "교통": "교통비", "교통비": "교통비", "버스": "교통비", "지하철": "교통비", "택시": "교통비",
    "주거": "주거비", "주거비": "주거비", "월세": "주거비", "관리비": "주거비",
    "의류": "의류", "옷": "의류", "쇼핑": "의류",
    "의료": "의료비", "의료비": "의료비", "병원": "의료비", "약": "의료비",
    "문화": "문화/여가", "여가": "문화/여가", "영화": "문화/여가", "운동": "문화/여가",
    "교육": "교육", "학원": "교육",
    "통신": "통신비", "통신비": "통신비", "핸드폰": "통신비",
    "기타": "기타지출",
    # 수입
    "급여": "급여", "월급": "급여",
    "부업": "부업",
    "용돈": "용돈",
    "기타수입": "기타수입",
}

INCOME_CATEGORIES = {"급여", "부업", "용돈", "기타수입"}


def guess_category(text: str) -> tuple[str, str]:
    """(category, type) 반환"""
    for key, cat in CATEGORY_MAP.items():
        if key in text:
            t = "income" if cat in INCOME_CATEGORIES else "expense"
            return cat, t
    return "기타지출", "expense"


def parse_amount(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s))


# ── 파싱 ────────────────────────────────────────────────────────────────
#
#  지원 형식:
#    식비 12000 편의점
#    5/21 식비 12000 편의점
#    5-21 식비 12000 편의점
#    수입 급여 3000000
#    [카카오페이] 12,000원 결제 편의점
#    [신한카드] 12,000원 편의점

DATE_PREFIX_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})\s+")
KAKAO_PAY_RE   = re.compile(r"\[카카오페이\][^\d]*([\d,]+)원\s*결제\s*(.+?)(?:\s+\d{4}[./]\d{2}|$)")
CARD_RE        = re.compile(r"\[.+?\]\s*([\d,]+)원\s+(.+?)(?:\s+\d{4}[./]\d{2}|$)")
MANUAL_RE      = re.compile(r"^(수입\s+)?(\S+)\s+([\d,]+)(?:원)?\s*(.*)$")


def extract_date(text: str) -> tuple[str, str]:
    """날짜 접두사 추출. 반환: (date_str, 나머지_text)"""
    m = DATE_PREFIX_RE.match(text)
    if m:
        year = datetime.now().year
        month, day = int(m.group(1)), int(m.group(2))
        try:
            date_str = f"{year}-{month:02d}-{day:02d}"
            datetime.strptime(date_str, "%Y-%m-%d")  # 유효성 검사
            return date_str, text[m.end():]
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d"), text


def parse(text: str):
    """(tx_type, category, amount, note, date) 또는 None"""
    text = text.strip()
    date, text = extract_date(text)

    m = KAKAO_PAY_RE.search(text)
    if m:
        amount = parse_amount(m.group(1))
        note = m.group(2).strip()
        cat, _ = guess_category(note)
        return "expense", cat, amount, note, date

    m = CARD_RE.search(text)
    if m:
        amount = parse_amount(m.group(1))
        note = m.group(2).strip()
        cat, _ = guess_category(note)
        return "expense", cat, amount, note, date

    m = MANUAL_RE.match(text)
    if m:
        is_income = bool(m.group(1))
        cat_raw   = m.group(2)
        amount    = parse_amount(m.group(3))
        note      = (m.group(4) or "").strip()

        if is_income:
            cat = CATEGORY_MAP.get(cat_raw, cat_raw)
            return "income", cat, amount, note, date

        cat, tx_type = guess_category(cat_raw)
        if cat == "기타지출" and cat_raw not in CATEGORY_MAP:
            cat = cat_raw
        return tx_type, cat, amount, note, date

    return None


# ── 웹훅 ────────────────────────────────────────────────────────────────

HELP_TEXT = (
    "📒 가계부 입력 방법\n\n"
    "▪ 지출\n"
    "  식비 12000 편의점\n"
    "  교통비 1500 버스\n\n"
    "▪ 수입\n"
    "  수입 급여 3000000\n\n"
    "▪ 카카오페이/카드 문자\n"
    "  그대로 붙여넣기\n\n"
    "카테고리: 식비 교통비 주거비\n"
    "의류 의료비 문화/여가 교육 통신비\n"
    "수입: 급여 부업 용돈"
)


def get_monthly_summary_text(mode: str) -> str:
    now = datetime.now()
    year, month = now.year, now.month

    txs = db.get_transactions_by_month(year, month)
    income  = sum(float(t["amount"]) for t in txs if t["type"] == "income")
    expense = sum(float(t["amount"]) for t in txs if t["type"] == "expense")

    savings_rows = db.get_all_rows("savings")
    savings = sum(
        float(r["amount"]) for r in savings_rows
        if r["date"].startswith(f"{year}-{month:02d}")
    )

    balance = income - expense - savings
    label = f"{month}월"

    if mode == "summary":
        return (
            f"📊 {label} 요약\n\n"
            f"💵 수입   {income:>12,.0f}원\n"
            f"💸 지출   {expense:>12,.0f}원\n"
            f"🏦 저금   {savings:>12,.0f}원\n"
            f"──────────────\n"
            f"💡 잔액   {balance:>12,.0f}원"
        )
    if mode == "expense":
        by_cat = {}
        for t in txs:
            if t["type"] == "expense":
                by_cat[t["category"]] = by_cat.get(t["category"], 0) + float(t["amount"])
        lines = "\n".join(
            f"  {cat}: {amt:,.0f}원"
            for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
        ) or "  내역 없음"
        return f"💸 {label} 지출  {expense:,.0f}원\n\n{lines}"

    if mode == "income":
        by_cat = {}
        for t in txs:
            if t["type"] == "income":
                by_cat[t["category"]] = by_cat.get(t["category"], 0) + float(t["amount"])
        lines = "\n".join(
            f"  {cat}: {amt:,.0f}원"
            for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
        ) or "  내역 없음"
        return f"💵 {label} 수입  {income:,.0f}원\n\n{lines}"

    if mode == "savings":
        return f"🏦 {label} 저금  {savings:,.0f}원"

    return ""


@router.post("")
def kakao_webhook(req: KakaoRequest):
    text = req.userRequest.utterance.strip()

    if text in ("시작", "안녕", "처음"):
        return kakao_text(
            "👋 안녕하세요! 가계부 챗봇입니다.\n\n"
            "지출/수입을 바로 입력하거나\n"
            "아래 버튼으로 이번달 현황을 확인하세요!"
        )

    if text in ("도움말", "help", "?", "ㅎ"):
        return kakao_text(HELP_TEXT)

    if text in ("이번달 요약", "요약"):
        return kakao_text(get_monthly_summary_text("summary"))
    if text in ("이번달 지출", "지출"):
        return kakao_text(get_monthly_summary_text("expense"))
    if text in ("이번달 수입", "수입확인"):
        return kakao_text(get_monthly_summary_text("income"))
    if text in ("이번달 저금", "저금"):
        return kakao_text(get_monthly_summary_text("savings"))

    parsed = parse(text)
    if not parsed:
        return kakao_text(
            "❓ 인식하지 못했어요.\n\n"
            "예) 식비 12000 편의점\n"
            "예) 5/21 식비 12000 편의점\n"
            "예) 수입 급여 3000000\n\n"
            "\"도움말\" 을 입력하면 사용법을 볼 수 있어요."
        )

    tx_type, category, amount, note, date = parsed

    t = Transaction(
        id=str(uuid.uuid4()),
        date=date,
        type=tx_type,
        category=category,
        amount=float(amount),
        note=note,
        created_at=datetime.now().isoformat(),
    )
    db.insert_row("transactions", t.model_dump())

    type_label = "수입" if tx_type == "income" else "지출"
    note_line  = f"\n메모: {note}" if note else ""

    return kakao_text(
        f"✅ 등록 완료!\n\n"
        f"날짜: {date}\n"
        f"구분: {type_label}\n"
        f"카테고리: {category}\n"
        f"금액: {amount:,}원"
        f"{note_line}"
    )
