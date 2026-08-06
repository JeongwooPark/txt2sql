"""역할·기능 안내 및 범위 외 일반 질문 제한/안내."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HELP_HINTS = (
    "도움말",
    "헬프",
    "help",
    "사용법",
    "사용 방법",
    "어떻게 쓰",
    "어떻게 사용",
    "뭘 할 수",
    "무엇을 할 수",
    "뭐 할 수",
    "무엇을 할 수 있",
    "기능 알려",
    "기능이 뭐",
    "기능은",
    "네 기능",
    "너의 기능",
    "역할",
    "너는 누구",
    "너는 뭐",
    "너 뭐야",
    "당신이 누구",
    "자기소개",
    "소개해 줘",
    "소개해줘",
    "무엇을 묻",
    "뭘 물어",
    "질문 예시",
    "예시 질문",
    "가이드",
    "what can you",
)

_LIMIT_HINTS = (
    "제한",
    "한계",
    "못 하",
    "못하는",
    "안 되는",
    "안되는",
    "할 수 없는",
    "지원하지 않",
    "지원 안",
    "불가",
)

_OUT_OF_SCOPE = (
    "날씨",
    "기온",
    "미세먼지",
    "뉴스",
    "주식",
    "환율",
    "비트코인",
    "암호화폐",
    "축구",
    "야구",
    "경기 결과",
    "요리",
    "레시피",
    "번역해",
    "번역 해",
    "영어로",
    "코드 짜",
    "코딩해",
    "프로그램 짜",
    "파이썬 코드",
    "농담",
    "웃긴",
    "사랑해",
    "심심해",
    "놀아줘",
    "챗gpt",
    "chatgpt",
    "철학",
    "인생",
    "연애",
    "심리상담",
    "의료",
    "병원 추천",
    "맛집",
    "카페 추천",
    "여행 코스",
    "비행기",
    "기차표",
)

_GREETING = (
    "안녕",
    "안녕하세요",
    "하이",
    "hello",
    "hi",
    "반가워",
    "헬로",
)

_DOMAIN_SIGNAL = (
    "건물",
    "아파트",
    "주택",
    "공장",
    "창고",
    "용도",
    "연면적",
    "건물면적",
    "건축",
    "대지면적",
    "높이",
    "지상층",
    "기초구역",
    "산업단지",
    "행정동",
    "법정동",
    "지번",
    "데이터",
    "데이터셋",
    "테이블",
    "컬럼",
    "칼럼",
    "속성",
    "스키마",
    "메타",
    "건수",
    "개수",
    "몇 채",
    "몇채",
    "좌표",
    "버퍼",
    "교차",
    "이내",
    "근처",
    "공간",
    "gis",
    "postgis",
    "조회",
    "특징",
    "특성",
    "요약",
    "상위",
    "AL_D",
    "BND_",
    "PNU",
)

_PLACE = re.compile(
    r"([가-힣0-9]{1,12}동|중구|서구|동구|영도구|부산진구|동래구|남구|북구|"
    r"해운대구|사하구|금정구|강서구|연제구|수영구|사상구|기장군|[가-힣]{1,6}구)"
)
_COL = re.compile(r"\bA\d+\b", re.I)


@dataclass(frozen=True)
class GuideAnswer:
    intent: str
    answer: str


def try_guide(question: str) -> GuideAnswer | None:
    """역할/기능/제한 안내 또는 범위 외 일반 질문이면 안내 반환."""
    q = question.strip()
    if not q:
        return GuideAnswer(
            intent="guide_empty",
            answer=_capabilities_text(intro="질문이 비어 있습니다."),
        )

    q_lower = q.lower()

    # 인사만
    if _is_greeting_only(q):
        return GuideAnswer(
            intent="guide_greeting",
            answer=(
                "안녕하세요. 부산 GIS 건물·행정·산업단지 데이터를 "
                "자연어로 조회하는 도우미입니다.\n"
                + _short_howto()
            ),
        )

    # 제한/못 하는 것
    if any(k in q for k in _LIMIT_HINTS) and (
        any(k in q for k in _HELP_HINTS)
        or any(k in q for k in ("뭐", "무엇", "알려", "설명", "있어", "있나"))
        or "제한" in q
        or "한계" in q
    ):
        return GuideAnswer(intent="guide_limits", answer=_limits_text())

    # 역할/기능/도움말
    if any(k in q for k in _HELP_HINTS) or any(
        k in q_lower for k in ("help", "what can you")
    ):
        # '사용가능한 데이터' 등은 카탈로그 질의로 둠
        if any(
            k in q
            for k in (
                "사용가능",
                "사용 가능",
                "데이터셋",
                "데이터는 몇",
                "데이터가 몇",
            )
        ):
            pass
        else:
            return GuideAnswer(intent="guide_help", answer=_capabilities_text())

    # 범위 외 일반 주제
    if _is_out_of_scope(q):
        return GuideAnswer(intent="guide_out_of_scope", answer=_out_of_scope_text(q))

    # 도메인 신호가 거의 없는 짧은 일반 질문
    if _is_generic_unscoped(q):
        return GuideAnswer(intent="guide_unscoped", answer=_unscoped_text(q))

    return None


def _is_greeting_only(q: str) -> bool:
    cleaned = re.sub(r"[!?？.~\s]", "", q)
    return cleaned.lower() in {
        "안녕",
        "안녕하세요",
        "하이",
        "hello",
        "hi",
        "반가워",
        "헬로",
        "안녕하신가",
    }


def _is_out_of_scope(q: str) -> bool:
    if _has_domain_signal(q):
        return False
    return any(k in q.lower() for k in _OUT_OF_SCOPE)


def _is_generic_unscoped(q: str) -> bool:
    """도메인과 무관한 일반 질문(짧은 잡담·세상사 등)."""
    if _has_domain_signal(q):
        return False
    if len(q) > 80:
        return False
    # 조사/일반 의문만 있는 경우
    generic = (
        "오늘",
        "내일",
        "어제",
        "요즘",
        "생각",
        "느낌",
        "어떻게 살아",
        "뭐해",
        "뭐 해",
        "시간 알려",
        "몇 시",
        "날짜",
        "요일",
        "누가 만들었",
        "너는 ai",
        "너는 AI",
        "모델이 뭐",
        "llm",
    )
    if any(k in q for k in generic):
        return True
    # 한글만 있고 장소/숫자/도메인 없음 + 의문
    if _PLACE.search(q) or _COL.search(q):
        return False
    if re.search(r"\d", q):
        return False
    # "왜?", "그래?" 류
    if q in {"왜?", "왜", "그래?", "그래", "응?", "음", "흠"}:
        return True
    return False


def _has_domain_signal(q: str) -> bool:
    ql = q.lower()
    if any(k in ql for k in _DOMAIN_SIGNAL):
        return True
    if _PLACE.search(q) or _COL.search(q):
        return True
    return False


def _short_howto() -> str:
    return (
        "예시:\n"
        "- 현재 사용가능한 데이터는 몇개야?\n"
        "- 구서동 아파트의 특징은?\n"
        "- 구서동에서 건물면적이 가장 큰 아파트는?\n"
        "- (이어서) 그 아파트의 이름은?\n"
        "도움말: 「기능 알려줘」 / 제한: 「제한이 뭐야?」"
    )


def _capabilities_text(*, intro: str | None = None) -> str:
    lines = []
    if intro:
        lines.append(intro)
    lines.extend(
        [
            "역할: 부산 GIS(건물·행정구역·기초구역·산업단지) 데이터를 "
            "자연어로 조회·설명하는 질의 도우미입니다.",
            "",
            "가능한 기능:",
            "1) 데이터셋/컬럼(속성) 설명 — 예: A4 의미, 어떤 데이터가 있어?",
            "2) 건수·순위·공간 조건 조회 — 예: 해운대구 건물 몇 채, 500m 이내",
            "3) 동·용도 특징 요약 — 예: 구서동 아파트 특징",
            "4) 모호한 표현 확인 — 예: 송정동(복수 구), ‘제일 좋은’",
            "5) 후속 질문 — 예: 그 아파트 이름/지번/높이는?",
            "",
            "제한 요약:",
            "- 날씨·뉴스·코딩·일상 잡담 등 GIS 데이터 밖 주제는 답하지 않습니다.",
            "- 주관적 평가(‘좋은/추천’)는 수치 기준으로 바꿔 물어야 합니다.",
            "- SELECT 조회만 가능하며, 데이터 수정·삭제는 불가합니다.",
            "",
            _short_howto(),
        ]
    )
    return "\n".join(lines)


def _limits_text() -> str:
    return "\n".join(
        [
            "이 시스템의 주요 제한입니다.",
            "1) 범위: 등록된 부산 GIS 메타·공간 데이터만 다룹니다. "
            "일반 상식·날씨·뉴스·코딩·상담 등은 지원하지 않습니다.",
            "2) 주관 판단: ‘제일 좋은/추천’ 등은 직접 평가하지 않고, "
            "연면적·건물면적·높이·층수 등 측정 가능 기준으로 안내합니다.",
            "3) 모호한 지명: 동이 여러 구에 있으면 확인 후 진행합니다.",
            "4) 쓰기 금지: SELECT/조회만 허용, INSERT·UPDATE·DELETE·DDL 불가.",
            "5) 건물명: 건물명(A24)이 비어 있으면 지번·건축물ID로 식별합니다.",
            "6) 후속 질문: 「그 아파트…」는 직전 세션에 특정 건물이 있을 때만 가능합니다 "
            "(대화형 `--chat` 권장).",
            "",
            "기능 전체: 「기능 알려줘」 / 예시: 「질문 예시」",
        ]
    )


def _out_of_scope_text(q: str) -> str:
    return "\n".join(
        [
            f"「{q.strip()}」은(는) 이 도우미의 지원 범위 밖입니다.",
            "여기에서는 부산 GIS 건물·행정·산업단지 데이터의 조회와 속성 설명만 다룹니다.",
            "",
            "제한: 날씨·뉴스·맛집·코딩·잡담 등 일반 질문은 답변할 수 없습니다.",
            "",
            _short_howto(),
        ]
    )


def _unscoped_text(q: str) -> str:
    return "\n".join(
        [
            f"「{q.strip()}」은(는) GIS 데이터 조회로 해석하기 어렵습니다.",
            "역할·기능이 궁금하시면 「기능 알려줘」, 제한은 「제한이 뭐야?」라고 물어 주세요.",
            "",
            _short_howto(),
        ]
    )
