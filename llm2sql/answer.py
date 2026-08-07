"""SQL 실행 결과를 한국어 자연어 답변으로 변환한다."""

from __future__ import annotations

import json
import re
import time
from typing import Any

import ollama

from llm2sql.domain import extract_place, extract_usage, is_busan_wide
from llm2sql.progress import TokenCallback

ANSWER_SYSTEM_PROMPT = """당신은 부산 GIS 데이터베이스 질의 결과를 사용자에게 설명하는 한국어 안내원입니다.
주어진 질문과 조회 결과(숫자·행 데이터)만 근거로, 자연스럽고 간결한 한국어 문장으로 답하세요.

규칙:
- 제공된 숫자·사실만 사용하세요. 추측·과장·없는 건물명/수치/층수는 절대 만들지 마세요.
- JSON에 없는 속성(지하층, 세대수, 준공연도 등)은 언급하지 마세요.
- 건물면적(A12)과 연면적(A14)을 혼동하지 마세요. 라벨이 있으면 라벨을 따르세요.
- SQL, 컬럼코드(A4, A14 등), 라우트명, 내부 구현을 답에 넣지 마세요.
- 속성명은 반드시 한글(법정동명, 용도명, 연면적, 높이, 지상층수, 건물명 등)로만 말하세요.
- 면적은 ㎡, 높이는 m, 건물은 채/건 등 질문에 맞는 단위를 쓰세요.
- 건수·집계는 한두 문장으로, 랭킹/상세는 핵심 속성만 2~4문장으로.
- 결과가 비면 조건에 맞는 데이터가 없다고 안내하세요.
- coverage_note가 JSON에 있으면 범위 제한은 시스템이 앞에 붙이므로, 본문에서는 반복하지 말고 조회 수치만 말하세요.
- 마크다운 코드펜스·불릿 나열은 쓰지 말고 문장으로 답하세요.
- 출력은 답변 본문만. 서두에 '답변:' 같은 라벨을 붙이지 마세요.
"""

COVERAGE_PREFACE: dict[str, str] = {
    "building_age_count_d198_partial": (
        "안내: 건축년수(사용승인·준공 경과)는 현재 동래구·금정구 용도별건물 "
        "자료에만 있습니다. 부산시 전체가 아니라 동래구·금정구 합산으로 조회합니다."
    ),
}

# 건물 테이블 주요 컬럼 → 한글 라벨 (LLM 혼동 방지)
_COLUMN_LABELS: dict[str, str] = {
    "A4": "법정동명",
    "A5": "지번",
    "A9": "용도명",
    "A12": "건물면적_㎡",
    "A14": "연면적_㎡",
    "A15": "대지면적_㎡",
    "A16": "높이_m",
    "A19": "연면적_㎡",
    "A24": "건물명",
    "A25": "주요용도명",
    "A26": "지상층수",
    "A27": "지하층수",
    "A30": "높이_m",
    "A31": "지상층수",
    "A33": "허가일자",
    "A34": "사용승인일자",
    "cnt": "건수",
    "count": "건수",
    "CNT": "건수",
    "v": "값",
}

_SKIP_SUMMARY_COLS = frozenset({"A0", "A1", "A2", "A3", "geometry", "geom"})


def fmt_value(value: Any) -> str:
    """숫자·스칼라를 한국어 답변용 문자열로 포맷."""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        text = f"{value:,.6f}".rstrip("0").rstrip(".")
        return text
    if value is None:
        return "없음"
    return str(value)


# 하위 호환
_fmt_number = fmt_value


def _korean_ends_with_vowel(word: str) -> bool:
    if not word:
        return False
    last = word.strip()[-1]
    if last.isdigit() or last in "㎡m층채건":
        return False
    code = ord(last)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 == 0
    return False


def _eun_neun(word: str) -> str:
    return "는" if _korean_ends_with_vowel(word) else "은"


def _i_ga(word: str) -> str:
    return "가" if _korean_ends_with_vowel(word) else "이"


def _scalar_from_rows(rows: list[dict[str, Any]]) -> Any | None:
    if not rows:
        return None
    row = rows[0]
    for key in ("v", "cnt", "count", "CNT", "BAS_AR", "A14"):
        if key in row:
            return row[key]
    if len(row) == 1:
        return next(iter(row.values()))
    return None


def _looks_like_count_question(question: str) -> bool:
    return any(
        k in question
        for k in ("몇", "개수", "건수", "채수", "종류", "얼마", "세어", "총")
    )


def _summarize_rows(rows: list[dict[str, Any]], *, limit: int = 5) -> str:
    lines: list[str] = []
    for i, row in enumerate(rows[:limit], start=1):
        labeled = _label_row(row)
        parts = [f"{k}={_fmt_number(v)}" for k, v in labeled.items()]
        lines.append(f"{i}) " + ", ".join(parts))
    extra = len(rows) - limit
    if extra > 0:
        lines.append(f"… 외 {extra:,}건")
    return "\n".join(lines)


def _subject_phrase(question: str) -> str:
    """질문에서 장소·용도·조건을 모아 주어 구절을 만든다."""
    place = extract_place(question)
    usage = extract_usage(question)
    parts: list[str] = []
    if place:
        parts.append(place)
    elif is_busan_wide(question):
        parts.append("부산시")
    if usage:
        if "아파트" in question and usage == "공동주택":
            parts.append("아파트(공동주택)")
        else:
            parts.append(usage)
    elif "건물" in question:
        parts.append("건물")
    elif "기초구역" in question:
        parts.append("기초구역")
    elif "산업단지" in question:
        parts.append("산업단지")

    m = re.search(r"연면적\s*(\d+)\s*이상", question)
    if m:
        parts.append(f"연면적 {int(m.group(1)):,}㎡ 이상")
    else:
        m = re.search(r"건물면적\s*(\d+)\s*이상", question)
        if m:
            parts.append(f"건물면적 {int(m.group(1)):,}㎡ 이상")
        else:
            m = re.search(r"높이\s*(\d+)\s*미터\s*(이상|넘는|초과)?", question)
            if m:
                op = m.group(2) or "이상"
                if op in ("넘는", "초과"):
                    parts.append(f"높이 {m.group(1)}m 초과")
                else:
                    parts.append(f"높이 {m.group(1)}m 이상")
            else:
                m = re.search(r"지상\s*층?[이]?\s*(\d+)\s*층", question)
                if m:
                    parts.append(f"지상 {m.group(1)}층 이상")

    if not parts:
        return "해당 조건"
    return " ".join(parts)


def _place_label(question: str) -> str:
    place = extract_place(question)
    if place:
        return place
    if is_busan_wide(question):
        return "부산시"
    return ""


def _row_height(row: dict[str, Any]) -> Any:
    if row.get("A16") is not None:
        return row.get("A16")
    return row.get("A30")


def _row_floors(row: dict[str, Any]) -> Any:
    if row.get("A26") is not None:
        return row.get("A26")
    return row.get("A31")


def _row_usage(row: dict[str, Any]) -> Any:
    for key in ("A9", "A25"):
        val = row.get(key)
        if val not in (None, "") and not (isinstance(val, (int, float)) and val < 10):
            return val
    return row.get("A25") or row.get("A9")


def _looks_like_rank_question(question: str) -> bool:
    return any(
        k in question
        for k in (
            "가장 높",
            "제일 높",
            "가장 큰",
            "제일 큰",
            "가장 넓",
            "제일 넓",
            "가장 많",
            "제일 많",
            "최대",
            "1등",
        )
    )


def _infer_rank_route(question: str) -> str | None:
    superlative = any(
        k in question
        for k in (
            "가장 큰",
            "제일 큰",
            "가장 넓은",
            "제일 넓은",
            "가장넓은",
            "제일넓은",
            "최대",
            "1등",
            "최고",
        )
    )
    if any(k in question for k in ("가장 높", "제일 높")) or (
        "높이" in question and any(k in question for k in ("가장", "제일", "최대"))
    ):
        return "building_rank_높이"
    if any(k in question for k in ("건물면적", "건축면적", "건축물면적")) and superlative:
        return "building_rank_건물면적"
    if "연면적" in question and superlative:
        return "building_rank_연면적"
    if "대지면적" in question and superlative:
        return "building_rank_대지면적"
    if any(k in question for k in ("지상층", "층수")) and any(
        k in question for k in ("가장", "제일", "최대")
    ):
        return "building_rank_지상층"
    return None


def _natural_rank(question: str, route: str, row: dict[str, Any]) -> str:
    metric = str(route).replace("building_rank_", "")
    place = _place_label(question)
    usage = extract_usage(question)
    if "아파트" in question and usage == "공동주택":
        target = "아파트"
    elif usage:
        target = usage
    else:
        target = "건물"

    where = f"{place} " if place else ""
    name = row.get("A24")
    name_s = (
        str(name)
        if name not in (None, "") and str(name).lower() != "nan"
        else None
    )
    jibeon = row.get("A5")

    if metric == "높이":
        lead = f"{where}{target} 중 높이가 가장 높은 건물은"
    elif metric == "지상층":
        lead = f"{where}{target} 중 지상층이 가장 많은 건물은"
    elif metric in {"건물면적", "연면적", "대지면적"} and any(
        k in question for k in ("넓", "넓은")
    ):
        lead = f"{where}{target} 중 {metric}이 가장 넓은 건물은"
    else:
        lead = f"{where}{target} 중 {metric}{_i_ga(metric)} 가장 큰 건물은"

    if name_s:
        lead += f" 「{name_s}」입니다."
    elif jibeon:
        lead += f" 지번 {jibeon} 건물입니다."
    else:
        lead += " 다음과 같습니다."

    detail = (
        f"위치는 {row.get('A4') or '—'}, 용도는 {_row_usage(row) or '—'}이며, "
        f"건물면적 {_fmt_number(row.get('A12'))}㎡, "
        f"연면적 {_fmt_number(row.get('A14') if row.get('A14') is not None else row.get('A19'))}㎡, "
        f"높이 {_fmt_number(_row_height(row))}m, "
        f"지상 {_fmt_number(_row_floors(row))}층입니다."
    )
    return f"{lead} {detail}"


def _natural_count(question: str, n: Any) -> str:
    subject = _subject_phrase(question)
    n_s = _fmt_number(n)
    unit = "채" if any(k in question for k in ("채", "아파트", "주택", "건물")) else "건"
    if "종류" in question:
        return f"{subject}의 종류는 {n_s}가지입니다."
    return f"{subject}{_eun_neun(subject)} 모두 {n_s}{unit}입니다."


def _label_row(row: dict[str, Any]) -> dict[str, Any]:
    labeled: dict[str, Any] = {}
    for k, v in row.items():
        if k in _SKIP_SUMMARY_COLS:
            continue
        if v is None or isinstance(v, (str, int, float, bool)):
            val: Any = v
        else:
            # Decimal 등
            try:
                val = int(v) if int(v) == v else float(v)
            except Exception:
                val = str(v)
        key = _COLUMN_LABELS.get(k, k)
        # 원본 컬럼코드(A9 등)는 사용자 답변에 노출하지 않음
        if re.fullmatch(r"A\d+", str(key)):
            continue
        labeled[key] = val
    return labeled


def _result_payload(
    *,
    rows: list[dict[str, Any]],
    row_count: int,
    route: str | None,
    preview_limit: int = 8,
) -> dict[str, Any]:
    preview = rows[:preview_limit]
    clean_rows = [_label_row(row) for row in preview]
    payload: dict[str, Any] = {
        "row_count": row_count,
        "preview_rows": clean_rows,
        "preview_truncated": max(0, row_count - len(clean_rows)),
    }
    scalar = _scalar_from_rows(rows) if rows else None
    if scalar is not None and row_count == 1 and len(rows[0]) <= 2:
        if hasattr(scalar, "__int__") and not isinstance(scalar, bool):
            try:
                scalar = int(scalar)
            except Exception:
                pass
        payload["scalar_value"] = scalar
    if route:
        # 내부 라우트명을 그대로 노출하지 않고 힌트만
        if str(route).startswith("building_rank_"):
            payload["result_type"] = "건물_순위_1건"
            payload["rank_metric"] = str(route).replace("building_rank_", "")
        elif route == "building_age_count_d198_partial":
            payload["result_type"] = "건축경과년_건수"
            payload["coverage_note"] = COVERAGE_PREFACE[route]
            payload["scope"] = "동래구+금정구"
        elif "count" in str(route).lower() or "cnt" in str(route).lower():
            payload["result_type"] = "건수"
        else:
            payload["result_type"] = "조회"
    return payload


def _strip_answer_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    fence = re.search(r"```(?:\w+)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"^(답변|Answer)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _resolve_client(*, host: str | None, client: Any | None) -> Any:
    if client is not None:
        return client
    if not host:
        raise ValueError("host 또는 client가 필요합니다.")
    return ollama.Client(host=host)


def _chat(
    *,
    model: str,
    messages: list[dict[str, str]],
    host: str | None = None,
    client: Any | None = None,
    temperature: float = 0.2,
) -> str:
    client = _resolve_client(host=host, client=client)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature},
    }
    try:
        response = client.chat(**kwargs, think=False)
    except TypeError:
        response = client.chat(**kwargs)
    return response["message"]["content"]


def _chat_stream(
    *,
    model: str,
    messages: list[dict[str, str]],
    host: str | None = None,
    client: Any | None = None,
    temperature: float = 0.2,
    on_token: TokenCallback | None = None,
) -> str:
    """Ollama chat 스트림. 토큰마다 on_token을 호출하고 전체 문자열을 반환."""
    client = _resolve_client(host=host, client=client)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "options": {"temperature": temperature},
        "stream": True,
    }
    try:
        stream = client.chat(**kwargs, think=False)
    except TypeError:
        stream = client.chat(**kwargs)

    parts: list[str] = []
    for chunk in stream:
        message = chunk.get("message") if isinstance(chunk, dict) else None
        content = ""
        if isinstance(message, dict):
            content = message.get("content") or ""
        elif message is not None:
            content = getattr(message, "content", None) or ""
        if not content:
            continue
        parts.append(content)
        if on_token is not None:
            on_token(content)
    return "".join(parts)


def emit_text_chunks(
    text: str,
    on_token: TokenCallback | None,
    *,
    chunk_size: int = 8,
    delay_s: float = 0.012,
) -> None:
    """비스트림 답변을 UI용으로 쪼개 전달."""
    if on_token is None or not text:
        return
    for i in range(0, len(text), chunk_size):
        on_token(text[i : i + chunk_size])
        if delay_s > 0:
            time.sleep(delay_s)


# 하위 호환
_emit_text_chunks = emit_text_chunks


PROFILE_SYSTEM_PROMPT = """당신은 부산 GIS 건물 집계 결과를 사용자에게 설명하는 한국어 안내원입니다.
주어진 질문과 집계 JSON만 근거로, 대화하듯 자연스러운 문단으로 요약하세요.

규칙:
- 제공된 숫자·사실만 사용하세요. 추측·없는 수치를 만들지 마세요.
- 불릿·번호 목록·마크다운을 쓰지 말고 2~6문장의 문단으로 답하세요.
- compare=true 이고 compare_kind=top_building 이면 각 지역의 ‘최고 건물’을 모두 소개하고, metric 기준으로 어느 지역 건물이 더 높은지/큰지 비교하세요.
- compare=true 이고 일반 groups 집계면 평균·동 수 등을 비교하세요.
- SQL, 컬럼코드(A12 등), 테이블명, 라우트명을 넣지 마세요.
- 면적은 ㎡, 높이는 m, 층은 층, 건물은 동/채로 쓰세요.
- apartment_note가 있으면 아파트=공동주택 집계라는 점을 자연스럽게 한 문장으로 언급하세요.
- 출력은 답변 본문만.
"""


def narrate_building_profile(
    question: str,
    *,
    payload: dict[str, Any],
    model: str,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> str:
    """특징 집계 JSON을 자연어 문단으로 변환."""
    user_content = (
        f"사용자 질문:\n{question.strip()}\n\n"
        f"집계 결과(JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "위 집계만 근거로 한국어 특징 요약을 작성하세요."
    )
    messages = [
        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    if on_token is not None:
        raw = _chat_stream(
            model=model,
            host=host,
            client=client,
            messages=messages,
            temperature=0.3,
            on_token=on_token,
        )
    else:
        raw = _chat(
            model=model,
            host=host,
            client=client,
            messages=messages,
            temperature=0.3,
        )
    answer = _strip_answer_text(raw)
    if not answer:
        raise ValueError("빈 프로필 LLM 답변")
    return answer


def generate_natural_answer(
    question: str,
    *,
    rows: list[dict[str, Any]],
    row_count: int,
    sql: str | None = None,
    route: str | None = None,
    model: str,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> str:
    """조회 결과를 LLM으로 자연스러운 한국어 답변으로 변환."""
    payload = _result_payload(rows=rows, row_count=row_count, route=route)
    user_content = (
        f"사용자 질문:\n{question.strip()}\n\n"
        f"조회 결과(JSON):\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        "위 결과만 근거로 한국어 답변을 작성하세요."
    )
    # SQL은 모델이 숫자 왜곡하지 않도록 넣지 않음 (필요 시 실패 경로에서만)
    _ = sql
    messages = [
        {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
    if on_token is not None:
        raw = _chat_stream(
            model=model,
            host=host,
            client=client,
            messages=messages,
            temperature=0.2,
            on_token=on_token,
        )
    else:
        raw = _chat(
            model=model,
            host=host,
            client=client,
            messages=messages,
            temperature=0.2,
        )
    answer = _strip_answer_text(raw)
    if not answer:
        raise ValueError("빈 LLM 답변")
    return answer


def format_success_template(
    question: str,
    *,
    sql: str,
    rows: list[dict[str, Any]],
    row_count: int,
    route: str | None = None,
) -> str:
    """LLM 없이 규칙 기반으로 한국어 답변 (폴백)."""
    if row_count == 0:
        subject = _subject_phrase(question)
        return (
            f"{subject}에 해당하는 데이터를 찾지 못했습니다. "
            "조건을 바꿔 다시 질문해 주세요."
        )

    scalar = _scalar_from_rows(rows)
    single_metric = row_count == 1 and scalar is not None and len(rows[0]) <= 2

    rank_route = (
        str(route)
        if route and str(route).startswith("building_rank_")
        else _infer_rank_route(question)
    )
    if (
        row_count == 1
        and rank_route
        and "A4" in rows[0]
        and any(k in rows[0] for k in ("A14", "A16", "A12", "A19", "A30", "A24"))
    ):
        return _natural_rank(question, rank_route, rows[0])

    if single_metric and _looks_like_count_question(question):
        if "종류" in question:
            return (
                f"{_subject_phrase(question)}의 종류는 "
                f"{_fmt_number(scalar)}가지입니다."
            )
        if any(k in question for k in ("면적값", "연면적 값", "얼마")) and not any(
            k in question for k in ("몇", "개수", "건수", "채")
        ):
            return (
                f"{_subject_phrase(question)}의 값은 "
                f"{_fmt_number(scalar)}입니다."
            )
        return _natural_count(question, scalar)

    if single_metric:
        subject = _subject_phrase(question)
        return f"{subject}에 대한 조회 값은 {_fmt_number(scalar)}입니다."

    preview = _summarize_rows(rows)
    subject = _subject_phrase(question)
    if row_count == 1:
        return f"{subject}에 대한 조회 결과는 다음과 같습니다.\n{preview}"
    return (
        f"{subject} 기준으로 총 {row_count:,}건을 찾았습니다. "
        f"주요 결과는 아래와 같습니다.\n{preview}"
    )


def coverage_preface(route: str | None) -> str | None:
    """데이터 범위가 질문보다 좁을 때 앞에 붙일 안내문."""
    if not route:
        return None
    return COVERAGE_PREFACE.get(str(route))


def with_coverage_preface(answer: str, route: str | None) -> str:
    preface = coverage_preface(route)
    if not preface:
        return answer
    body = answer.strip()
    # LLM이 비슷한 안내를 넣었으면 중복 제거에 가깝게 본문만 유지
    if body.startswith("안내:"):
        return body
    return f"{preface}\n\n{body}"


def format_success(
    question: str,
    *,
    sql: str,
    rows: list[dict[str, Any]],
    row_count: int,
    route: str | None = None,
    model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    on_token: TokenCallback | None = None,
) -> str:
    """성공 시 자연스러운 한국어 답변 (가능하면 LLM, 실패 시 템플릿)."""
    # 건물 순위는 템플릿이 컬럼 혼동·과장 없이 더 안전하다.
    prefer_template = bool(
        (route and str(route).startswith("building_rank_"))
        or (
            row_count == 1
            and rows
            and _infer_rank_route(question)
            and "A4" in rows[0]
        )
    )
    if prefer_template:
        answer = format_success_template(
            question,
            sql=sql,
            rows=rows,
            row_count=row_count,
            route=route,
        )
        final = with_coverage_preface(answer, route)
        if on_token is not None:
            emit_text_chunks(final, on_token)
        return final

    preface = coverage_preface(route)
    streamed = False

    def _preface_once() -> None:
        nonlocal streamed
        if preface and on_token is not None and not streamed:
            on_token(f"{preface}\n\n")
            streamed = True

    answer: str
    if model and (client is not None or host):
        try:
            _preface_once()

            def _token(piece: str) -> None:
                nonlocal streamed
                streamed = True
                if on_token is not None:
                    on_token(piece)

            answer = generate_natural_answer(
                question,
                rows=rows,
                row_count=row_count,
                sql=sql,
                route=route,
                model=model,
                host=host,
                client=client,
                on_token=_token if on_token is not None else None,
            )
        except Exception:
            answer = format_success_template(
                question,
                sql=sql,
                rows=rows,
                row_count=row_count,
                route=route,
            )
            if on_token is not None and not streamed:
                emit_text_chunks(with_coverage_preface(answer, route), on_token)
                streamed = True
    else:
        answer = format_success_template(
            question,
            sql=sql,
            rows=rows,
            row_count=row_count,
            route=route,
        )
        if on_token is not None:
            emit_text_chunks(with_coverage_preface(answer, route), on_token)
            streamed = True

    final = with_coverage_preface(answer, route)
    if on_token is not None and not streamed:
        emit_text_chunks(final, on_token)
    return final


def format_failure(
    question: str,
    *,
    error: str | Exception,
    sql: str | None = None,
) -> str:
    """실패 시 한국어 사유 설명."""
    q = question.strip().rstrip("?？")
    msg = str(error)
    reason = _humanize_error(msg)

    parts = [
        f"요청하신 「{q}」에는 지금은 답하지 못했습니다.",
        f"이유: {reason}",
    ]
    if sql:
        parts.append(f"시도한 SQL: {sql.strip()}")
    parts.append("질문을 조금 더 구체적으로 바꿔 다시 시도해 주세요.")
    return "\n".join(parts)


def _humanize_error(msg: str) -> str:
    lower = msg.lower()
    if "unsupported" in lower:
        return "현재 지원하지 않는 요청입니다(조회 외 작업 등)."
    if "undefinedcolumn" in lower or "칼럼은 없습니다" in msg:
        col = _extract_quoted(msg) or "알 수 없는 컬럼"
        return f"존재하지 않는 컬럼을 참조했습니다({col})."
    if "undefinedtable" in lower or "릴레이션" in msg:
        table = _extract_quoted(msg) or "알 수 없는 테이블"
        return f"존재하지 않는 테이블을 참조했습니다({table})."
    if "undefinedfunction" in lower or "연산자 없음" in msg:
        return "데이터 타입에 맞지 않는 연산/함수를 사용했습니다."
    if "syntaxerror" in lower or "구문 오류" in msg:
        return "생성된 SQL 구문이 올바르지 않습니다."
    if "readonly" in lower or "금지된 키워드" in msg or "select/with" in lower:
        return "데이터 변경/삭제 등 허용되지 않는 SQL입니다."
    if "timeout" in lower or "canceling statement" in lower:
        return "질의 실행 시간이 너무 길어 중단되었습니다."
    if "connection" in lower or "연결" in msg:
        return "데이터베이스 연결에 실패했습니다."
    compact = re.sub(r"\s+", " ", msg).strip()
    if len(compact) > 160:
        compact = compact[:157] + "..."
    return compact


def _extract_quoted(msg: str) -> str | None:
    m = re.search(r'"([^"]+)"', msg)
    if m:
        return m.group(1)
    m = re.search(r"'([^']+)'", msg)
    if m:
        return m.group(1)
    return None
