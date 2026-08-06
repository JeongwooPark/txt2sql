"""SQL 실행 결과를 한국어 자연어 답변으로 변환한다."""

from __future__ import annotations

import re
from typing import Any


def _fmt_number(value: Any) -> str:
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


def _korean_ends_with_vowel(word: str) -> bool:
    if not word:
        return False
    code = ord(word[-1])
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 == 0
    return False


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
        parts = [f"{k}={_fmt_number(v)}" for k, v in row.items()]
        lines.append(f"{i}) " + ", ".join(parts))
    extra = len(rows) - limit
    if extra > 0:
        lines.append(f"… 외 {extra:,}건")
    return "\n".join(lines)


def format_success(
    question: str,
    *,
    sql: str,
    rows: list[dict[str, Any]],
    row_count: int,
    route: str | None = None,
) -> str:
    """성공 시 자연스러운 한국어 답변."""
    q = question.strip().rstrip("?？")

    if row_count == 0:
        return (
            f"「{q}」에 해당하는 데이터를 찾지 못했습니다. "
            "조건을 바꿔 다시 질문해 주세요."
        )

    scalar = _scalar_from_rows(rows)
    single_metric = row_count == 1 and scalar is not None and len(rows[0]) <= 2

    if (
        row_count == 1
        and route
        and str(route).startswith("building_rank_")
        and {"A4", "A14"}.issubset(rows[0].keys())
    ):
        row = rows[0]
        metric = str(route).replace("building_rank_", "")
        particle = "가" if _korean_ends_with_vowel(metric) else "이"
        superlative = {
            "연면적": "가장 큰",
            "건물면적": "가장 큰",
            "대지면적": "가장 큰",
            "높이": "가장 높은",
            "지상층": "가장 많은",
        }.get(metric, "가장 큰")
        parts = [
            f"법정동 {row.get('A4')}",
            f"용도 {row.get('A9') or '—'}",
            f"건물면적 {_fmt_number(row.get('A12'))}㎡" if "A12" in row else None,
            f"연면적 {_fmt_number(row.get('A14'))}㎡",
            f"높이 {_fmt_number(row.get('A16'))}m",
            f"지상 {_fmt_number(row.get('A26'))}층",
        ]
        parts = [p for p in parts if p]
        name = row.get("A24")
        name_line = ""
        if name not in (None, "") and str(name).lower() != "nan":
            name_line = f"건물명 {name}, "
        elif row.get("A5"):
            name_line = f"지번 {row.get('A5')}, "
        return (
            f"「{q}」 기준으로 {metric}{particle} {superlative} 건물은 다음과 같습니다.\n"
            + name_line
            + ", ".join(parts)
        )

    if single_metric and _looks_like_count_question(question):
        if any(k in question for k in ("면적", "연면적")) and not any(
            k in question for k in ("몇 개", "개수", "건수", "채")
        ):
            return f"「{q}」에 대한 값은 {_fmt_number(scalar)}입니다."
        if "종류" in question:
            return f"「{q}」 결과는 {_fmt_number(scalar)}가지입니다."
        return f"「{q}」 결과는 {_fmt_number(scalar)}건입니다."

    if single_metric:
        return f"「{q}」에 대한 값은 {_fmt_number(scalar)}입니다."

    # 집계/목록
    preview = _summarize_rows(rows)
    if row_count == 1:
        return f"「{q}」에 대한 조회 결과는 다음과 같습니다.\n{preview}"
    return (
        f"「{q}」에 대해 총 {row_count:,}건을 조회했습니다. "
        f"주요 결과는 아래와 같습니다.\n{preview}"
    )


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
        f"「{q}」 질의에 답하지 못했습니다.",
        f"사유: {reason}",
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
    # 너무 긴 영문 에러는 앞부분만
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
