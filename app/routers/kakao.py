import uuid
import re
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from app.models import Transaction
from app.services import db

router = APIRouter(prefix="/kakao", tags=["kakao"])

# ── 마지막 등록 내역 (취소용, 사용자별 메모리) ────────────────────────────
last_transaction: dict[str, str] = {}  # user_id → transaction_id


# ── 카카오 요청/응답 스키마 ──────────────────────────────────────────────

class _Base(BaseModel):
    model_config = {"extra": "ignore"}

class KakaoUser(_Base):
    id: str = "anonymous"

class KakaoAction(_Base):
    params: dict[str, Any] = {}

class KakaoUserRequest(_Base):
    utterance: str
    user: KakaoUser = KakaoUser()

class KakaoRequest(_Base):
    userRequest: KakaoUserRequest
    action: KakaoAction = KakaoAction()


QUICK_REPLIES = [
    {"action": "message", "label": "📊 이번달 요약", "messageText": "이번달 요약"},
    {"action": "message", "label": "💸 이번달 지출", "messageText": "이번달 지출"},
    {"action": "message", "label": "📈 지난달 비교", "messageText": "지난달"},
]

QUICK_REPLIES_WITH_CANCEL = [
    {"action": "message", "label": "📊 이번달 요약", "messageText": "이번달 요약"},
    {"action": "message", "label": "💸 이번달 지출", "messageText": "이번달 지출"},
    {"action": "message", "label": "📈 지난달 비교", "messageText": "지난달"},
    {"action": "message", "label": "↩️ 취소",        "messageText": "취소"},
]


HOME_URL = "https://money-fe.vercel.app/"

def kakao_text(text: str, with_cancel: bool = False) -> dict:
    replies = QUICK_REPLIES_WITH_CANCEL if with_cancel else QUICK_REPLIES
    return {
        "version": "2.0",
        "template": {
            "outputs": [{
                "basicCard": {
                    "description": text,
                    "buttons": [{
                        "action": "webLink",
                        "label": "🏠 가계부 열기",
                        "webLinkUrl": HOME_URL,
                    }]
                }
            }],
            "quickReplies": replies,
        },
    }


# ── 카테고리 별칭 ────────────────────────────────────────────────────────

CATEGORY_MAP = {
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
    "급여": "급여", "월급": "급여",
    "부업": "부업",
    "용돈": "용돈",
    "기타수입": "기타수입",
}

INCOME_CATEGORIES = {"급여", "부업", "용돈", "기타수입"}


def guess_category(text: str) -> tuple[str, str]:
    for key, cat in CATEGORY_MAP.items():
        if key in text:
            t = "income" if cat in INCOME_CATEGORIES else "expense"
            return cat, t
    return "기타지출", "expense"


def parse_amount(s: str) -> int:
    return int(re.sub(r"[^\d]", "", s))


# ── 파싱 ────────────────────────────────────────────────────────────────

DATE_PREFIX_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})\s+")
KAKAO_PAY_RE   = re.compile(r"\[카카오페이\][^\d]*([\d,]+)원\s*결제\s*(.+?)(?:\s+\d{4}[./]\d{2}|$)")
CARD_RE        = re.compile(r"\[.+?\]\s*([\d,]+)원\s+(.+?)(?:\s+\d{4}[./]\d{2}|$)")
MANUAL_RE      = re.compile(r"^(수입\s+)?(\S+)\s+([\d,]+)(?:원)?\s*(.*)$")


def extract_date(text: str) -> tuple[str, str]:
    m = DATE_PREFIX_RE.match(text)
    if m:
        year = datetime.now().year
        month, day = int(m.group(1)), int(m.group(2))
        try:
            date_str = f"{year}-{month:02d}-{day:02d}"
            datetime.strptime(date_str, "%Y-%m-%d")
            return date_str, text[m.end():]
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%d"), text


def parse(text: str):
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


# ── 이번달 요약 ──────────────────────────────────────────────────────────

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

    if mode == "summary":
        return (
            f"📊 {month}월 요약\n\n"
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
        return f"💸 {month}월 지출  {expense:,.0f}원\n\n{lines}"
    if mode == "income":
        by_cat = {}
        for t in txs:
            if t["type"] == "income":
                by_cat[t["category"]] = by_cat.get(t["category"], 0) + float(t["amount"])
        lines = "\n".join(
            f"  {cat}: {amt:,.0f}원"
            for cat, amt in sorted(by_cat.items(), key=lambda x: -x[1])
        ) or "  내역 없음"
        return f"💵 {month}월 수입  {income:,.0f}원\n\n{lines}"
    if mode == "savings":
        return f"🏦 {month}월 저금  {savings:,.0f}원"
    return ""


# ── 지난달 비교 ──────────────────────────────────────────────────────────

def get_compare_text() -> str:
    now = datetime.now()
    y, m = now.year, now.month

    prev_m = m - 1 if m > 1 else 12
    prev_y = y if m > 1 else y - 1

    cur_txs  = db.get_transactions_by_month(y, m)
    prev_txs = db.get_transactions_by_month(prev_y, prev_m)

    cur_exp  = sum(float(t["amount"]) for t in cur_txs  if t["type"] == "expense")
    prev_exp = sum(float(t["amount"]) for t in prev_txs if t["type"] == "expense")
    cur_inc  = sum(float(t["amount"]) for t in cur_txs  if t["type"] == "income")
    prev_inc = sum(float(t["amount"]) for t in prev_txs if t["type"] == "income")

    def diff(cur, prev):
        d = cur - prev
        if d > 0:   return f"▲ {abs(d):,.0f}원 증가"
        if d < 0:   return f"▼ {abs(d):,.0f}원 감소"
        return "변동 없음"

    exp_arrow = "🔴" if cur_exp > prev_exp else "🟢"
    inc_arrow = "🟢" if cur_inc >= prev_inc else "🔴"

    return (
        f"📈 {prev_m}월 → {m}월 비교\n\n"
        f"💸 지출\n"
        f"  {prev_m}월: {prev_exp:,.0f}원\n"
        f"  {m}월: {cur_exp:,.0f}원\n"
        f"  {exp_arrow} {diff(cur_exp, prev_exp)}\n\n"
        f"💵 수입\n"
        f"  {prev_m}월: {prev_inc:,.0f}원\n"
        f"  {m}월: {cur_inc:,.0f}원\n"
        f"  {inc_arrow} {diff(cur_inc, prev_inc)}"
    )


# ── 예산 초과 체크 ───────────────────────────────────────────────────────

def check_budget_exceeded(category: str, new_amount: float) -> str | None:
    now = datetime.now()
    budgets = db.get_all_rows("budgets")
    budget = next((b for b in budgets if b["category"] == category), None)
    if not budget:
        return None

    txs = db.get_transactions_by_month(now.year, now.month)
    spent = sum(float(t["amount"]) for t in txs if t["type"] == "expense" and t["category"] == category)
    spent += new_amount
    limit = float(budget["amount"])

    if spent > limit:
        over = spent - limit
        return f"⚠️ {category} 예산 초과!\n예산 {limit:,.0f}원 / 사용 {spent:,.0f}원\n초과 {over:,.0f}원"
    pct = int(spent / limit * 100)
    if pct >= 80:
        remain = limit - spent
        return f"⚡ {category} 예산 {pct}% 사용\n잔여 {remain:,.0f}원"
    return None


# ── 웹훅 ────────────────────────────────────────────────────────────────

HELP_TEXT = (
    "📒 가계부 입력 방법\n\n"
    "▪ 지출: 카테고리 금액 메모\n"
    "  식비 12000 편의점\n"
    "  5/21 교통비 1500 버스\n\n"
    "▪ 수입: 수입 카테고리 금액\n"
    "  수입 급여 3000000\n\n"
    "▪ 명령어\n"
    "  취소 - 마지막 내역 삭제\n"
    "  지난달 - 지난달 비교\n"
    "  도움말 - 사용법"
)


@router.post("")
def kakao_webhook(req: KakaoRequest):
    text    = req.userRequest.utterance.strip()
    user_id = req.userRequest.user.id

    # ── 시작 ──
    if text in ("시작", "안녕", "처음"):
        return kakao_text(
            "👋 안녕하세요! 가계부 챗봇입니다.\n\n"
            "지출/수입을 바로 입력하거나\n"
            "아래 버튼으로 이번달 현황을 확인하세요!"
        )

    # ── 도움말 ──
    if text in ("도움말", "help", "?", "ㅎ"):
        return kakao_text(HELP_TEXT)

    # ── 이번달 요약/지출/수입/저금 ──
    if text in ("이번달 요약", "요약"):
        return kakao_text(get_monthly_summary_text("summary"))
    if text in ("이번달 지출", "지출"):
        return kakao_text(get_monthly_summary_text("expense"))
    if text in ("이번달 수입", "수입확인"):
        return kakao_text(get_monthly_summary_text("income"))
    if text in ("이번달 저금", "저금"):
        return kakao_text(get_monthly_summary_text("savings"))

    # ── 지난달 비교 ──
    if text in ("지난달", "지난달 비교", "비교"):
        return kakao_text(get_compare_text())

    # ── 마지막 내역 취소 ──
    if text in ("취소", "삭제", "ㅊㅅ"):
        tx_id = last_transaction.get(user_id)
        if not tx_id:
            return kakao_text("❌ 취소할 내역이 없습니다.\n방금 등록한 내역만 취소할 수 있어요.")
        rows = db.get_rows_where("transactions", id=tx_id)
        if not rows:
            return kakao_text("❌ 이미 삭제된 내역입니다.")
        t = rows[0]
        db.delete_row("transactions", tx_id)
        last_transaction.pop(user_id, None)
        return kakao_text(
            f"🗑️ 삭제 완료!\n\n"
            f"날짜: {t['date']}\n"
            f"카테고리: {t['category']}\n"
            f"금액: {float(t['amount']):,.0f}원"
        )

    # ── 내역 등록 ──
    parsed = parse(text)
    if not parsed:
        return kakao_text(
            "❓ 인식하지 못했어요.\n\n"
            "예) 식비 12000 편의점\n"
            "예) 5/21 식비 12000 편의점\n\n"
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
    last_transaction[user_id] = t.id

    type_label = "수입" if tx_type == "income" else "지출"
    note_line  = f"\n메모: {note}" if note else ""

    # 등록 완료 메시지
    msg = (
        f"✅ 등록 완료!\n\n"
        f"날짜: {date}\n"
        f"구분: {type_label}\n"
        f"카테고리: {category}\n"
        f"금액: {amount:,}원"
        f"{note_line}"
    )

    # 예산 초과 경고 (지출일 때만)
    if tx_type == "expense":
        warning = check_budget_exceeded(category, float(amount))
        if warning:
            msg += f"\n\n{warning}"

    return kakao_text(msg, with_cancel=True)
