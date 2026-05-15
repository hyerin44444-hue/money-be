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

class KakaoAction(BaseModel):
    model_config = {"extra": "ignore"}
    params: dict[str, Any] = {}

class KakaoIntent(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = ""

class KakaoUserRequest(BaseModel):
    model_config = {"extra": "ignore"}
    utterance: str
    action: KakaoAction = KakaoAction()
    intent: KakaoIntent = KakaoIntent()

class KakaoRequest(BaseModel):
    model_config = {"extra": "ignore"}
    userRequest: KakaoUserRequest
    action: KakaoAction = KakaoAction()


def kakao_response(text: str) -> dict:
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}]
        }
    }


# ── 메시지 파싱 ──────────────────────────────────────────────────────────
# 지원 형식:
#   "식비 12000 편의점"
#   "식비 12,000원 편의점"
#   "수입 급여 3000000"
#   카카오페이: "[카카오페이] 12,000원 결제 편의점"
#   카드문자:   "[신한카드] 12,000원 편의점"

KAKAO_PAY_RE = re.compile(
    r'\[카카오페이\]\s*([\d,]+)원\s*결제\s*(.+?)(?:\s*\d{4}/\d{2}/\d{2})?$'
)
CARD_RE = re.compile(
    r'\[.+?카드\]\s*([\d,]+)원\s*(.+?)(?:\s*\d{4}/\d{2}/\d{2})?$'
)
MANUAL_RE = re.compile(
    r'^(수입|지출)?\s*([가-힣a-zA-Z/\s]+?)\s+([\d,]+)(?:원)?\s*(.*)$'
)
AMOUNT_NOTE_RE = re.compile(
    r'^([가-힣a-zA-Z/\s]+?)\s+([\d,]+)(?:원)?\s*(.*)$'
)


CATEGORY_ALIASES = {
    "식비": "식비", "밥": "식비", "밥값": "식비", "점심": "식비", "저녁": "식비", "아침": "식비",
    "카페": "식비", "커피": "식비",
    "교통": "교통비", "교통비": "교통비", "버스": "교통비", "지하철": "교통비", "택시": "교통비",
    "주거": "주거비", "주거비": "주거비", "월세": "주거비", "관리비": "주거비",
    "의류": "의류", "옷": "의류",
    "의료": "의료비", "의료비": "의료비", "병원": "의료비", "약": "의료비",
    "문화": "문화/여가", "여가": "문화/여가", "영화": "문화/여가", "운동": "문화/여가",
    "교육": "교육", "학원": "교육",
    "통신": "통신비", "통신비": "통신비", "핸드폰": "통신비",
    "급여": "급여", "월급": "급여",
    "부업": "부업",
    "용돈": "용돈",
}


def guess_category(text: str) -> str:
    text = text.strip()
    for key, cat in CATEGORY_ALIASES.items():
        if key in text:
            return cat
    return "기타지출"


def parse_amount(s: str) -> int:
    return int(s.replace(",", "").replace("원", "").strip())


def parse_utterance(text: str):
    """
    반환: (type, category, amount, note) 또는 None
    """
    text = text.strip()

    # 카카오페이 문자
    m = KAKAO_PAY_RE.search(text)
    if m:
        amount = parse_amount(m.group(1))
        note = m.group(2).strip()
        return ("expense", guess_category(note), amount, note)

    # 카드 문자
    m = CARD_RE.search(text)
    if m:
        amount = parse_amount(m.group(1))
        note = m.group(2).strip()
        return ("expense", guess_category(note), amount, note)

    # 수동 입력: "수입 급여 3000000" / "식비 12000 편의점"
    m = MANUAL_RE.match(text)
    if m:
        t_type = m.group(1)   # "수입" | "지출" | None
        category_raw = m.group(2).strip()
        amount = parse_amount(m.group(3))
        note = (m.group(4) or "").strip()

        if t_type == "수입":
            tx_type = "income"
            category = CATEGORY_ALIASES.get(category_raw, category_raw)
        else:
            tx_type = "expense"
            category = CATEGORY_ALIASES.get(category_raw, guess_category(category_raw))

        return (tx_type, category, amount, note)

    return None


# ── 웹훅 엔드포인트 ─────────────────────────────────────────────────────

@router.post("")
def kakao_webhook(req: KakaoRequest):
    text = req.userRequest.utterance.strip()

    # 도움말
    if text in ("도움말", "?", "help", "ㅎ"):
        return kakao_response(
            "📒 가계부 입력 방법\n\n"
            "▪ 지출: 카테고리 금액 메모\n"
            "  예) 식비 12000 편의점\n"
            "  예) 교통비 1500 버스\n\n"
            "▪ 수입: 수입 카테고리 금액\n"
            "  예) 수입 급여 3000000\n\n"
            "▪ 카카오페이 문자 붙여넣기도 가능\n\n"
            "카테고리: 식비 교통비 주거비 의류\n"
            "의료비 문화/여가 교육 통신비\n"
            "수입: 급여 부업 용돈"
        )

    parsed = parse_utterance(text)
    if not parsed:
        return kakao_response(
            "❓ 인식하지 못했어요.\n\n"
            "형식: 카테고리 금액 메모\n"
            "예) 식비 12000 편의점\n\n"
            "\"도움말\" 을 입력하면 사용법을 볼 수 있어요."
        )

    tx_type, category, amount, note = parsed
    today = datetime.now().strftime("%Y-%m-%d")

    t = Transaction(
        id=str(uuid.uuid4()),
        date=today,
        type=tx_type,
        category=category,
        amount=float(amount),
        note=note,
        created_at=datetime.now().isoformat(),
    )
    db.insert_row("transactions", t.model_dump())

    type_label = "수입" if tx_type == "income" else "지출"
    return kakao_response(
        f"✅ 등록 완료!\n\n"
        f"날짜: {today}\n"
        f"구분: {type_label}\n"
        f"카테고리: {category}\n"
        f"금액: {amount:,}원\n"
        f"{'메모: ' + note if note else ''}"
    )
