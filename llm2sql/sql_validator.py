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
    if (
        gu_in_q
        and "건물" in q
        and uses_d198
        and not uses_d010
        and not mentions_dongrae
        and not mentions_geumjeong
    ):
        reasons.append(
            'For Busan gu-level building queries prefer "AL_D010_26_20250704", '
            "not district-only AL_D198 tables."
        )

    # 높이인데 A16/A30 없음
    if "높이" in q and "A16" not in s and "A30" not in s:
        reasons.append('Height filters should use "A16" on AL_D010 (or "A30" on AL_D198).')

    # 상위/순위인데 ORDER BY 없음
    if any(k in q for k in ("상위", "순위", "가장 큰", "가장 많은", "큰 순")) and "ORDER BY" not in upper:
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
