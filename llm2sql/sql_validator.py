"""생성된 SQL의 고빈도 논리 오류를 검사한다."""

from __future__ import annotations

import re


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

    # 실행은 됐지만 의심스러운 빈 결과 (구+건물 속성)
    if row_count == 0 and gu_in_q and "건물" in q and uses_d198 and not uses_d010:
        reasons.append(
            "Query returned 0 rows with AL_D198 only; retry with AL_D010 and A4 LIKE gu filter."
        )

    if not reasons:
        return None
    return "\n".join(f"- {r}" for r in reasons)
