"""부산 GIS 질의용 공통 도메인 토큰 (장소·용도)."""

from __future__ import annotations

import re

GU_PATTERN = (
    r"(중구|서구|동구|영도구|부산진구|동래구|남구|북구|해운대구|사하구|"
    r"금정구|강서구|연제구|수영구|사상구|기장군|[가-힣]{1,6}구)"
)
DONG_PATTERN = r"([가-힣0-9]{1,12}동)"

GU_RE = re.compile(GU_PATTERN)
DONG_RE = re.compile(DONG_PATTERN)

USAGE_ALIASES: dict[str, str] = {
    "아파트": "공동주택",
    "공동주택": "공동주택",
    "단독주택": "단독주택",
    "다가구": "단독주택",
    "공장": "공장",
    "창고": "창고시설",
    "창고시설": "창고시설",
    "학교": "교육연구시설",
    "교육연구시설": "교육연구시설",
    "근린생활": "제1종근린생활시설",
    "업무시설": "업무시설",
    "숙박": "숙박시설",
    "숙박시설": "숙박시설",
    "종교": "종교시설",
    "종교시설": "종교시설",
    "공공시설물": "공공용시설",
    "공공시설": "공공용시설",
    "공공용시설": "공공용시설",
}

USAGE_PATTERN = (
    r"(아파트|공동주택|단독주택|공장|창고시설|창고|"
    r"교육연구시설|업무시설|숙박시설|종교시설|"
    r"공공시설물|공공시설|공공용시설)"
)
USAGE_RE = re.compile(USAGE_PATTERN)

# 구 단위 용도별건물(사용승인·허가일자 보유)
D198_BY_GU: dict[str, str] = {
    "동래구": "AL_D198_26260_20250115",
    "금정구": "AL_D198_26410_20250115",
}

# 건축 경과년수 / 준공·사용승인 관련 표현
AGE_HINTS = (
    "지어진",
    "지어진지",
    "지어진 후",
    "건축년",
    "건축 년",
    "건축년수",
    "준공",
    "준공일",
    "사용승인",
    "사용승인일",
    "허가일",
    "허가일자",
    "경과 년",
    "경과년",
    "년수",
    "년 넘",
    "년이 넘",
    "년된",
    "년 된",
    "년 미만",
    "년미만",
    "오래된",
)

D198_TABLES: tuple[str, ...] = (
    "AL_D198_26260_20250115",
    "AL_D198_26410_20250115",
)


# '공동주택'의 '공동' 등 지명이 아닌 ~동 오탐
_FALSE_DONG = frozenset(
    {
        "공동",
        "자동",
        "수동",
        "유동",
        "구동",
        "운동",
        "행동",
        "활동",
        "진동",
        "변동",
        "연동",
        "가동",
        "충동",
    }
)


def extract_place(question: str) -> str | None:
    """질문에서 동 또는 구 명칭을 추출 (동 우선)."""
    places = extract_places(question)
    return places[0] if places else None


def extract_places(question: str) -> list[str]:
    """질문에 등장하는 동·구를 순서대로 (중복 제거)."""
    found: list[str] = []
    for m in DONG_RE.finditer(question):
        dong = m.group(1)
        if dong in _FALSE_DONG:
            continue
        after = question[m.end() : m.end() + 2]
        if after.startswith(("주택", "시설", "차", "력", "원", "사")):
            continue
        if dong not in found:
            found.append(dong)
    if found:
        return found
    for m in GU_RE.finditer(question):
        gu = m.group(1)
        if gu not in found:
            found.append(gu)
    return found


def extract_gu(question: str) -> str | None:
    m = GU_RE.search(question)
    return m.group(1) if m else None


def extract_usage(question: str) -> str | None:
    """질문의 용도 별칭 → DB 건축물용도명(A9). 여러 개면 첫 번째."""
    usages = extract_usages(question)
    return usages[0] if usages else None


def extract_usages(question: str) -> list[str]:
    """질문에 등장하는 용도들을 순서대로 (중복 제거)."""
    found: list[str] = []
    # 긴 별칭 우선 매칭을 위해 위치 기반으로 스캔
    spans: list[tuple[int, int, str]] = []
    for alias in sorted(USAGE_ALIASES, key=len, reverse=True):
        start = 0
        while True:
            i = question.find(alias, start)
            if i < 0:
                break
            mapped = USAGE_ALIASES[alias]
            spans.append((i, i + len(alias), mapped))
            start = i + len(alias)
    spans.sort(key=lambda x: x[0])
    occupied: list[tuple[int, int]] = []
    for s, e, mapped in spans:
        if any(not (e <= a or s >= b) for a, b in occupied):
            continue
        occupied.append((s, e))
        if mapped not in found:
            found.append(mapped)
    return found


def place_a4_predicate(place: str) -> str:
    """AL_D010 A4 필터 SQL 조각."""
    if place.endswith("동"):
        return f'("A4" LIKE \'% {place}\' OR "A4" = \'{place}\')'
    return f'"A4" LIKE \'%{place}%\''


def d198_table_for_gu(gu: str | None) -> str | None:
    if not gu:
        return None
    return D198_BY_GU.get(gu)


def looks_like_age_question(question: str) -> bool:
    return any(k in question for k in AGE_HINTS)


def extract_age_years(question: str) -> int | None:
    """'30년 넘은', '10년 미만', '건축 20년' 등에서 연수 추출."""
    m = re.search(
        r"(\d+)\s*년\s*(?:이\s*)?(?:넘|이상|이하|미만|초과|이내|된|지남|경과)?",
        question,
    )
    if m:
        return int(m.group(1))
    return None


def extract_age_compare(question: str) -> str:
    """경과년수 비교 방향.

    - lt: N년 미만 (더 최근) → 사용승인일 > today-N
    - lte: N년 이하
    - gt: N년 초과
    - gte: N년 이상/넘는 (기본)
    """
    if re.search(r"\d+\s*년\s*(?:이\s*)?미만", question) or "채 안" in question:
        return "lt"
    if re.search(r"\d+\s*년\s*(?:이\s*)?이내", question):
        return "lte"
    if re.search(r"\d+\s*년\s*(?:이\s*)?이하", question):
        return "lte"
    if re.search(r"\d+\s*년\s*(?:이\s*)?(?:초과|넘는)", question) and "이상" not in question:
        # '넘는' alone often means >= in user speech; keep gte unless 초과
        if "초과" in question:
            return "gt"
    if re.search(r"\d+\s*년\s*(?:이\s*)?(?:이상|넘)", question):
        return "gte"
    return "gte"


def is_busan_wide(question: str) -> bool:
    return any(
        k in question
        for k in (
            "부산광역시",
            "부산시",
            "부산 전체",
            "부산내",
            "부산 내",
            "부산에서",
            "부산시에서",
            "부산광역시에서",
            "부산시에",
            "부산에",
            "부산 ",
        )
    ) or question.strip().startswith("부산")


def has_batchim(text: str) -> bool:
    """마지막 글자에 받침이 있으면 True."""
    s = (text or "").strip()
    if not s:
        return False
    ch = s[-1]
    if "가" <= ch <= "힣":
        return (ord(ch) - 0xAC00) % 28 != 0
    if ch.isdigit():
        return ch in "013678"  # 대략적: 받침 느낌의 숫자 발음
    return False


def with_topic(text: str) -> str:
    """주제 조사 은/는."""
    s = (text or "").strip() or "해당 조건"
    return f"{s}{'은' if has_batchim(s) else '는'}"


def with_subject(text: str) -> str:
    """주격 조사 이/가."""
    s = (text or "").strip() or "해당 조건"
    return f"{s}{'이' if has_batchim(s) else '가'}"


def with_object(text: str) -> str:
    """목적격 조사 을/를."""
    s = (text or "").strip() or "해당 조건"
    return f"{s}{'을' if has_batchim(s) else '를'}"


def fix_dual_particles(text: str) -> str:
    """템플릿/모델이 남긴 '은(는)' 형태를 실제 조사로 교정."""
    if not text:
        return text

    def _repl_topic(m: re.Match[str]) -> str:
        return with_topic(m.group(1))

    def _repl_subj(m: re.Match[str]) -> str:
        return with_subject(m.group(1))

    def _repl_obj(m: re.Match[str]) -> str:
        return with_object(m.group(1))

    out = re.sub(r"([가-힣A-Za-z0-9]+)\s*은\(는\)", _repl_topic, text)
    out = re.sub(r"([가-힣A-Za-z0-9]+)\s*이\(가\)", _repl_subj, out)
    out = re.sub(r"([가-힣A-Za-z0-9]+)\s*을\(를\)", _repl_obj, out)
    return out


def sane_height_sql(
    height_col: str = "A16",
    floors_col: str = "A26",
    *,
    max_m: float = 600.0,
) -> str:
    """비정상 높이(날짜 오인입·단위 오류)를 제외하는 SQL 조건.

    층수와 함께 있을 때 층당 약 8m+여유를 넘는 값은 제외한다.
    """
    return (
        f'"{height_col}" > 0 AND "{height_col}" <= {max_m:g} AND '
        f'("{floors_col}" IS NULL OR "{height_col}" <= ("{floors_col}" * 8 + 30))'
    )


def sane_footprint_sql(
    area_col: str = "A12",
    floor_area_col: str = "A14",
    *,
    max_m2: float = 500_000.0,
) -> str:
    """비정상 건물면적(건축면적)을 제외.

    연면적보다 건물면적이 크게 큰 값은 오류로 본다(건축면적 ≤ 연면적).
    """
    return (
        f'"{area_col}" > 0 AND "{area_col}" <= {max_m2:g} AND '
        f'("{floor_area_col}" IS NULL OR "{floor_area_col}" <= 0 OR '
        f'"{area_col}" <= "{floor_area_col}" * 1.05 + 50)'
    )


def sane_floor_area_sql(
    floor_area_col: str = "A14",
    *,
    max_m2: float = 2_000_000.0,
) -> str:
    """비정상 연면적 제외."""
    return f'"{floor_area_col}" > 0 AND "{floor_area_col}" <= {max_m2:g}'

def age_date_predicate(date_col: str, years: int, compare: str) -> str:
    """사용승인/허가일자(text) 경과년수 조건 SQL 조각."""
    valid = f"\"{date_col}\" ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'"
    casted = f"\"{date_col}\"::date"
    boundary = f"(CURRENT_DATE - INTERVAL '{years} years')"
    if compare == "lt":
        op = f"{casted} > {boundary}"
    elif compare == "lte":
        op = f"{casted} >= {boundary}"
    elif compare == "gt":
        op = f"{casted} < {boundary}"
    else:
        op = f"{casted} <= {boundary}"
    return f"{valid} AND {op}"


def legal_dong_guess(admin_dong: str) -> str | None:
    """구서1동 → 구서동 처럼 행정동에서 법정동 후보를 추정."""
    m = re.fullmatch(r"([가-힣]+)\d+동", admin_dong)
    if m:
        return m.group(1) + "동"
    return None


_ANAPHORA_HINTS = (
    "그 ",
    "그거",
    "그게",
    "그것",
    "해당 ",
    "이 건물",
    "그 건물",
    "그 아파트",
    "해당 아파트",
    "앞의",
    "방금",
    "아까",
    "위에서",
)


def has_anaphora(question: str) -> bool:
    q = question.strip()
    if q.startswith(("그", "해당", "앞", "방금", "아까", "이 ", "저 ")):
        return True
    return any(h in q for h in _ANAPHORA_HINTS)


def looks_like_standalone_question(question: str) -> bool:
    """새 장소·새 주제로 보이는 독립 질의 (후속/기준병합 대상 아님)."""
    q = question.strip()
    if not q or has_anaphora(q):
        return False
    if is_busan_wide(q):
        return True
    if extract_gu(q):
        return True
    place = extract_place(q)
    if place and place.endswith("동"):
        return True
    # 짧은 기준 보정("건축년수")은 독립 질문이 아님
    if len(q) <= 12 and looks_like_age_question(q) and extract_age_years(q) is None:
        return False
    # 연수·집계가 한 문장에 갖춰진 신규 질의
    if extract_age_years(q) is not None and looks_like_age_question(q) and len(q) >= 16:
        return True
    if any(k in q for k in ("몇", "건수", "채수", "수는", "보여줘", "목록", "상위")) and len(q) >= 12:
        return True
    return False
