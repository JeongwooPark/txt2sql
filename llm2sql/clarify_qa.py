"""의미가 불분명·모호한 질의어를 감지하고 확인을 요청한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

_DONG = re.compile(r"([가-힣0-9]{1,12}동)")
_GU = re.compile(
    r"(중구|서구|동구|영도구|부산진구|동래구|남구|북구|해운대구|사하구|"
    r"금정구|강서구|연제구|수영구|사상구|기장군|[가-힣]{1,6}구)"
)
_COL = re.compile(r"\b(A\d+)\b", re.I)

# 의도·문법 조사 등 (미지 단어 판별에서 제외)
_STOP = {
    "현재",
    "사용",
    "가능",
    "가능한",
    "사용가능",
    "사용가능한",
    "있는",
    "없는",
    "있는지",
    "있습니까",
    "해줘",
    "해주세요",
    "알려줘",
    "알려",
    "보여줘",
    "구해",
    "조회",
    "말해",
    "대한",
    "관련",
    "기준",
    "에서",
    "으로",
    "로서",
    "에는",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "과",
    "와",
    "도",
    "만",
    "좀",
    "요",
    "까",
    "까요",
    "인가",
    "인가요",
    "입니까",
    "뭐야",
    "무엇",
    "어떤",
    "무슨",
    "몇",
    "개",
    "개수",
    "갯수",
    "몇개",
    "몇개야",
    "건수",
    "채",
    "채야",
    "수",
    "총",
    "및",
    "또는",
    "그리고",
    "또",
    "등",
    "약",
    "정도",
    "대략",
    "주요",
    "가장",
    "큰",
    "작은",
    "많은",
    "적은",
    "상위",
    "하위",
    "이상",
    "이하",
    "초과",
    "미만",
    "넘는",
    "이내",
    "근처",
    "안에",
    "내부",
    "경계",
    "교차",
    "버퍼",
    "거리",
    "좌표",
    "점",
    "미터",
    "제곱미터",
    "층",
    "높이",
    "면적",
    "연면적",
    "건물면적",
    "건축면적",
    "건축물면적",
    "대지면적",
    "특징",
    "특성",
    "요약",
    "설명",
    "의미",
    "뜻",
    "속성",
    "컬럼",
    "칼럼",
    "필드",
    "테이블",
    "데이터",
    "데이터셋",
    "자료",
    "스키마",
    "목록",
    "리스트",
    "소개",
    "개요",
    "구조",
    "구성",
    "포함",
    "담겨",
    "건물",
    "건축물",
    "아파트",
    "공동주택",
    "단독주택",
    "공장",
    "창고",
    "창고시설",
    "산업단지",
    "기초구역",
    "행정동",
    "법정동",
    "용도",
    "질문",
    "결과",
    "답변",
    "부산",
    "부산시",
    "부산광역시",
    "모든",
    "전체",
    "각각",
    "해당",
    "그",
    "저",
    "그런",
    "저런",
    "이런",
    "궁금",
    "궁금해",
    "알고",
    "싶어",
    "부탁",
    "부탁해",
}

# 측정 기준이 불명확한 형용사/감성어
_VAGUE = (
    "제일 좋은",
    "가장 좋은",
    "제일 괜찮은",
    "가장 괜찮은",
    "좋은",
    "괜찮은",
    "핫한",
    "핫한곳",
    "유명한",
    "예쁜",
    "멋진",
    "최고의",
    "최악",
    "최악의",
    "살기좋은",
    "살기 좋은",
    "추천",
    "괜찮은가",
    "좋은가",
    "어때보여",
    "베스트",
    "최고야",
    "최고인",
)

_USAGE_WORDS = (
    "아파트",
    "공동주택",
    "단독주택",
    "공장",
    "창고",
    "창고시설",
    "교육연구시설",
    "업무시설",
    "숙박시설",
    "종교시설",
)


@dataclass(frozen=True)
class ClarifyAnswer:
    intent: str
    answer: str
    ambiguous_terms: list[str]
    options: list[dict[str, Any]]


def check_ambiguity(
    conn: psycopg.Connection,
    question: str,
) -> ClarifyAnswer | None:
    """모호하면 확인 요청 답변을 반환. 문제 없으면 None."""
    q = question.strip()
    if not q:
        return None

    # 1) 감성·추천 등 측정 기준 불명
    vague_hits = [v for v in _VAGUE if v in q]
    # 긴 표현 우선 (제일 좋은 > 좋은)
    vague_hits = sorted(set(vague_hits), key=len, reverse=True)
    # 부분 중복 제거: '제일 좋은'이 있으면 '좋은' 제외
    filtered: list[str] = []
    for v in vague_hits:
        if any(v != keep and v in keep for keep in filtered):
            continue
        filtered.append(v)
    vague_hits = filtered
    if vague_hits:
        return ClarifyAnswer(
            intent="clarify_vague",
            ambiguous_terms=vague_hits,
            options=[],
            answer=_vague_guidance(q, vague_hits),
        )

    place = _extract_place(q)
    gu_in_q = _GU.search(q)
    gu_name = gu_in_q.group(1) if gu_in_q else None

    # 2) 지명 모호/미존재 (동이 여러 구에 있거나 데이터에 없음)
    if place and place.endswith("동"):
        places = _lookup_places(conn, place, gu=gu_name)
        if not places:
            return ClarifyAnswer(
                intent="clarify_unknown_place",
                ambiguous_terms=[place],
                options=[],
                answer=(
                    f"「{place}」에 해당하는 법정동명을 건물 데이터에서 찾지 못했습니다.\n"
                    "구 이름을 함께 적어 주시거나, 정확한 동명으로 다시 질문해 주세요.\n"
                    "예: 금정구 구서동 아파트 특징, 해운대구 중동 건물 건수"
                ),
            )
        # 구가 지정되지 않았고 후보가 2개 이상
        if gu_name is None and len(places) > 1:
            lines = [
                f"「{place}」이(가) 여러 지역에 있어 의미가 불분명합니다.",
                "아래 중 어디를 말씀하신 건가요?",
            ]
            for i, p in enumerate(places, start=1):
                lines.append(
                    f"{i}) {p['place']} (건물 {int(p['n']):,}동)"
                )
            lines.append(
                f"예: {places[0]['place'].split()[-2]} {place} 건물 몇 채야?"
            )
            return ClarifyAnswer(
                intent="clarify_place",
                ambiguous_terms=[place],
                options=places,
                answer="\n".join(lines),
            )

    # 3) 물리 컬럼명만 있고 테이블/맥락이 불명확한 조회성 질문
    cols = [m.group(1).upper() for m in _COL.finditer(q)]
    if cols and _looks_like_data_query(q) and not _has_table_hint(q):
        # 메타 설명 질문이면 통과 (meta_qa가 테이블별 설명)
        if any(k in q for k in ("의미", "뜻", "뭐야", "무엇", "설명", "속성")):
            pass
        else:
            return ClarifyAnswer(
                intent="clarify_column",
                ambiguous_terms=cols,
                options=[],
                answer=(
                    f"컬럼 {', '.join(cols)}은(는) 테이블마다 의미가 다를 수 있습니다.\n"
                    "어느 데이터(예: 부산 건물 AL_D010, 산업단지, 동래/금정 용도별건물)를 "
                    "기준으로 할지 알려 주세요.\n"
                    f"또는 「{cols[0]} 컬럼 의미가 뭐야?」처럼 설명부터 요청할 수 있습니다."
                ),
            )

    # 4) 도메인에서 해석되지 않는 단어
    unknown = _unknown_terms(q, place=place, gu=gu_name)
    if unknown:
        return ClarifyAnswer(
            intent="clarify_unknown_term",
            ambiguous_terms=unknown,
            options=[],
            answer=(
                f"질문 속 「{', '.join(unknown)}」의 의미가 데이터 속성으로 분명하지 않습니다.\n"
                "다음 중 무엇에 가까운지 알려 주시면 정확히 답할 수 있습니다.\n"
                "- 장소(구/동), 건물 용도(공동주택·단독주택 등), "
                "수치 조건(연면적·높이·층수), 데이터셋/컬럼 설명"
            ),
        )

    return None


def _vague_guidance(q: str, vague_hits: list[str]) -> str:
    place = _extract_place(q)
    usage_label = None
    if "아파트" in q or "공동주택" in q:
        usage_label = "아파트(공동주택)"
    elif "단독" in q:
        usage_label = "단독주택"
    elif "건물" in q:
        usage_label = "건물"

    terms = ", ".join(vague_hits)
    lines = [
        f"「{terms}」은(는) 주관적인 표현이라 데이터만으로 ‘최고’를 정할 수 없습니다.",
        "어떤 기준이 ‘좋음’인지 알려 주시면 그 속성으로 순위·대표 건물을 찾아 드립니다.",
    ]
    scope = ""
    if place and usage_label:
        scope = f"{place} {usage_label}"
    elif place:
        scope = place
    elif usage_label:
        scope = usage_label

    if scope:
        lines.append(f"예를 들어 {scope} 기준으로는 이렇게 물을 수 있습니다.")
        base = place or "해당 지역"
        target = "아파트" if usage_label and "아파트" in usage_label else (usage_label or "건물")
        lines.extend(
            [
                f"- {base}에서 연면적이 가장 큰 {target}는?",
                f"- {base}에서 건물면적이 가장 큰 {target}는?",
                f"- {base}에서 높이가 가장 높은 {target}는?",
                f"- {base}에서 지상층이 가장 많은 {target}는?",
                f"- {base} {target} 특징 요약해줘",
                "건물을 찾은 뒤에는 「그 아파트의 이름은?」「지번은?」처럼 이어서 물을 수 있습니다.",
            ]
        )
    else:
        lines.extend(
            [
                "예:",
                "- 구서동에서 연면적이 가장 큰 아파트는?",
                "- 구서동에서 건물면적이 가장 큰 아파트는?",
                "- 해운대구 높이 상위 5개 건물",
                "- 구서동 아파트 특징은?",
            ]
        )
    return "\n".join(lines)


def _extract_place(q: str) -> str | None:
    m = _DONG.search(q)
    if m:
        return m.group(1)
    m = _GU.search(q)
    if m:
        return m.group(1)
    return None


def _lookup_places(
    conn: psycopg.Connection,
    dong: str,
    *,
    gu: str | None = None,
) -> list[dict[str, Any]]:
    """동명 정확 매칭(끝 토큰). 구가 있으면 해당 구만."""
    with conn.cursor(row_factory=dict_row) as cur:
        if gu:
            cur.execute(
                """
                SELECT "A4" AS place, COUNT(*) AS n
                FROM "AL_D010_26_20250704"
                WHERE ("A4" LIKE %s OR "A4" LIKE %s)
                  AND "A4" LIKE %s
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 10
                """,
                (f"% {dong}", dong, f"%{gu}%"),
            )
        else:
            cur.execute(
                """
                SELECT "A4" AS place, COUNT(*) AS n
                FROM "AL_D010_26_20250704"
                WHERE "A4" LIKE %s OR "A4" = %s
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 10
                """,
                (f"% {dong}", dong),
            )
        return list(cur.fetchall())


def _looks_like_data_query(q: str) -> bool:
    return any(
        k in q
        for k in (
            "몇",
            "개수",
            "건수",
            "조회",
            "보여",
            "구해",
            "상위",
            "목록",
            "리스트",
            "세어",
        )
    )


def _has_table_hint(q: str) -> bool:
    keys = (
        "건물",
        "AL_D010",
        "D010",
        "산업단지",
        "D060",
        "동래",
        "금정",
        "D198",
        "기초구역",
        "행정동",
        "BND",
    )
    return any(k in q for k in keys)


def _unknown_terms(
    q: str,
    *,
    place: str | None,
    gu: str | None,
) -> list[str]:
    """조사 제거 후 남은 미등록 한글 토큰."""
    text = q
    for token in filter(None, [place, gu]):
        text = text.replace(token, " ")
    for w in _USAGE_WORDS:
        text = text.replace(w, " ")
    for col in _COL.findall(text):
        text = re.sub(re.escape(col), " ", text, flags=re.I)
    # 숫자·영문·기호 제거
    text = re.sub(r"[0-9a-zA-Z_\"'.,?？!！()[\]{}]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    raw = [t for t in re.findall(r"[가-힣]{2,}", text) if t not in _STOP]
    # 조사 꼬리 제거
    cleaned: list[str] = []
    for t in raw:
        t2 = re.sub(r"(은|는|이|가|을|를|의|과|와|도|만|에|로|으로|까지|부터)$", "", t)
        if len(t2) < 2 or t2 in _STOP:
            continue
        if t2.endswith(("동", "구")):  # 장소는 별도 처리
            continue
        if t2 not in cleaned:
            cleaned.append(t2)
    # 너무 공격적이지 않게: 질문 길이가 짧고 미지 토큰이 있을 때만
    if not cleaned:
        return []
    # 알려진 패턴(특징/건수 등)만 있으면 통과 — 이미 STOP에 있음
    # 실질 미지 단어만 반환 (최대 3개)
    # 너무 공격적이지 않게: 2글자 일반어는 제외, 3글자 이상만
    return [t for t in cleaned if len(t) >= 3][:3]
