"""SQL 구문·도메인 진단 + PostgreSQL EXPLAIN 검증."""

from __future__ import annotations

import re
from typing import Any

import psycopg

from llm2sql.db import assert_readonly_sql, ensure_limit


def diagnose_sql(question: str, sql: str, *, row_count: int | None = None) -> str | None:
    """문제가 있으면 재생성용 피드백 문자열, 없으면 None."""
    reasons: list[str] = []
    q = question
    s = sql
    upper = sql.upper()

    # 한글 구/동 필터에 A3 사용
    if re.search(r'"A3"\s+LIKE\s+\'%[가-힣]', s):
        reasons.append('Use "A4" (법정동명) for Hangul gu/dong filters, not "A3".')

    # 부산 전역 구 질의인데 D198만 사용 (동래/금정 명시 없을 때)
    uses_d198 = "AL_D198_" in upper
    uses_d010 = "AL_D010_" in upper
    mentions_dongrae = "동래" in q
    mentions_geumjeong = "금정" in q
    gu_in_q = bool(re.search(r"[가-힣]{1,6}구", q))
    busan_wide = any(
        k in q for k in ("부산시", "부산광역시", "부산 전체", "부산내", "부산 내")
    ) or q.strip().startswith("부산")
    if (
        (gu_in_q or busan_wide)
        and "건물" in q
        and uses_d198
        and not uses_d010
        and not mentions_dongrae
        and not mentions_geumjeong
    ):
        reasons.append(
            'For Busan-wide / gu-level building queries prefer "AL_D010_26_20250704", '
            "not district-only AL_D198 tables."
        )

    # 높이 순위인데 D198 A30만 사용 (부산 전역·구 질의)
    if (
        any(k in q for k in ("가장 높", "제일 높", "높이"))
        and uses_d198
        and not uses_d010
        and not mentions_dongrae
        and not mentions_geumjeong
    ):
        reasons.append(
            'Building height ranking for Busan should use "AL_D010_26_20250704"."A16", '
            'not district-only AL_D198 "A30".'
        )

    # 건축년수인데 데이터기준일(A35) 사용
    if any(k in q for k in ("지어진", "건축년", "준공", "사용승인", "년 미만", "년 이상")):
        if re.search(r'"A35"', s) or re.search(r"\bA35\b", s):
            reasons.append(
                'Building age must use AL_D198 "A34"(사용승인일자) or "A33"(허가일자), '
                'never "A35"(데이터기준일자).'
            )
        if "AL_D010" in upper and ("A34" in s or "INTERVAL" in upper):
            reasons.append(
                "AL_D010 has no approval date; use AL_D198_26260 (동래) and/or "
                "AL_D198_26410 (금정) with A34 text date cast."
            )

    # 상위/순위인데 ORDER BY 없음
    if any(
        k in q
        for k in ("상위", "순위", "가장 큰", "가장 많은", "가장 높", "제일 높", "큰 순")
    ) and "ORDER BY" not in upper:
        reasons.append("Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.")

    # 미터 거리/버퍼인데 geography 캐스트 없음 또는 D198 단독
    if any(k in q for k in ("미터", "근처", "버퍼", "이내")) and (
        "129." in q or "좌표" in q or "점(" in q
    ):
        if "AL_D198" in upper and "AL_D010" not in upper:
            reasons.append(
                'Coordinate buffer queries must use "AL_D010_26_20250704", not AL_D198.'
            )
        if "ST_DWITHIN" in upper and "GEOGRAPHY" not in upper:
            reasons.append(
                "For meter distances on SRID 4326, cast geometry to geography in ST_DWithin."
            )

    # 동 공간 의도인데 attribute LIKE만
    if any(k in q for k in ("안에", "내부", "안쪽", "경계 안")) and "건물" in q:
        if "ST_INTERSECTS" not in upper:
            reasons.append(
                'Dong containment requires ST_Intersects with "BND_ADM_DONG_PG".'
            )

    # 산업단지 질의인데 AL_D060 미사용
    if "산업단지" in q and "AL_D060" not in upper and "건물" not in q:
        reasons.append('Industrial-park questions must use "AL_D060_00_20250804".')

    # 동래/금정 주요용도명 → D198 A25
    if "주요용도" in q or (("용도" in q) and ("종류" in q or "몇 가지" in q)):
        if "동래" in q and (
            "AL_D010" in upper or '"A9"' in s or re.search(r"\bA9\b", s)
        ):
            reasons.append(
                '동래구 "주요용도명" kinds/count must use '
                '"AL_D198_26260_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".'
            )
        if "금정" in q and (
            "AL_D010" in upper or '"A9"' in s or re.search(r"\bA9\b", s)
        ):
            reasons.append(
                '금정구 "주요용도명" kinds/count must use '
                '"AL_D198_26410_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".'
            )

    # 동래·금정 외 구 용도/건물 COUNT에 D198 사용
    gu_m = re.search(r"([가-힣]{1,6}구)", q)
    if gu_m:
        gu_name = gu_m.group(1)
        if (
            gu_name not in ("동래구", "금정구")
            and uses_d198
            and not uses_d010
            and not any(k in q for k in ("건축년", "준공", "사용승인", "지어진"))
        ):
            reasons.append(
                f'For {gu_name} building/usage counts use "AL_D010_26_20250704" '
                'with "A9" for 용도 (not district-only AL_D198).'
            )

    # 실행은 됐지만 의심스러운 빈 결과 (구+건물 속성)
    if row_count == 0 and gu_in_q and "건물" in q and uses_d198 and not uses_d010:
        reasons.append(
            "Query returned 0 rows with AL_D198 only; retry with AL_D010 and A4 LIKE gu filter."
        )
    if row_count == 0 and gu_m and gu_m.group(1) not in ("동래구", "금정구") and uses_d198:
        reasons.append(
            "Query returned 0 rows on AL_D198 for a non-동래/금정 gu; "
            'rewrite with "AL_D010_26_20250704" and "A9" for usage filters.'
        )

    if not reasons:
        return None
    return "\n".join(f"- {r}" for r in reasons)


def check_sql_syntax(sql: str) -> str | None:
    """SQLGlot로 PostgreSQL 구문 검사. 문제 있으면 피드백, 없으면 None."""
    try:
        import sqlglot
        from sqlglot.errors import ParseError
    except ImportError:
        return None

    try:
        sqlglot.parse_one(sql, read="postgres")
    except ParseError as exc:
        return f"SQL parse error (sqlglot/postgres): {exc}"
    except Exception as exc:
        return f"SQL parse error: {type(exc).__name__}: {exc}"
    return None


def explain_sql(
    conn: psycopg.Connection,
    sql: str,
    *,
    default_limit: int = 100,
) -> str | None:
    """EXPLAIN으로 실행 가능성 검사. 문제 있으면 피드백, 없으면 None."""
    try:
        assert_readonly_sql(sql)
        limited = ensure_limit(sql, default_limit=default_limit)
        body = limited.rstrip().rstrip(";")
        with conn.cursor() as cur:
            cur.execute(f"EXPLAIN {body}")
            _ = cur.fetchall()
        return None
    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        return f"EXPLAIN failed: {type(exc).__name__}: {exc}"


def validate_sql_preexec(
    question: str,
    sql: str,
    *,
    conn: psycopg.Connection | None = None,
    default_limit: int = 100,
    use_explain: bool = True,
) -> str | None:
    """사전 검증 통합: 도메인 진단 → SQLGlot → EXPLAIN."""
    parts: list[str] = []
    domain = diagnose_sql(question, sql)
    if domain:
        parts.append(domain)
    syntax = check_sql_syntax(sql)
    if syntax:
        parts.append(f"- {syntax}")
    if use_explain and conn is not None:
        expl = explain_sql(conn, sql, default_limit=default_limit)
        if expl:
            parts.append(f"- {expl}")
    if not parts:
        return None
    return "\n".join(parts)
