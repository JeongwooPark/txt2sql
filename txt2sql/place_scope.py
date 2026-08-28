"""건물 테이블 장소 스코프 SQL 정책.

| kind | 물리 표현 |
|------|-----------|
| 구·군 | A3 LIKE '{sigungu_a3_prefix}%' |
| 법정동 | A4 이름 일치 |
| 행정동 | BND_ADM_DONG_PG ∩ geometry (호출측 JOIN) |

이 모듈은 A3/A4 predicate 만 만든다. 행정동 BND JOIN 은 compiler/templates 가 담당.
"""

from __future__ import annotations

from txt2sql.gazetteer import resolve_place_kind, sigungu_a3_prefix, uses_admin_boundary


def _quote_ident(alias: str, column: str) -> str:
    if alias:
        return f'{alias}."{column}"'
    return f'"{column}"'


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def legal_dong_a4_predicate(place: str, *, alias: str = "") -> str:
    """법정동 → A4 이름 매칭."""
    col = _quote_ident(alias, "A4")
    lit = _sql_str(place)
    return f"({col} LIKE {_sql_str('% ' + place)} OR {col} = {lit})"


def sigungu_a3_predicate(
    place: str,
    *,
    alias: str = "",
    sido: str | None = None,
) -> str | None:
    """구·군 → A3 접두. 코드 없으면 None."""
    code = sigungu_a3_prefix(place, sido=sido)
    if not code:
        return None
    col = _quote_ident(alias, "A3")
    return f"{col} LIKE {_sql_str(code + '%')}"


def building_place_predicate(
    place: str,
    *,
    alias: str = "",
    sido: str | None = None,
) -> str:
    """건물 테이블용 장소 필터 (구=A3, 법정동=A4).

    행정동은 BND 경로가 본선이므로 여기선 A4 최후 폴백만 둔다.
    """
    text = (place or "").strip()
    if not text:
        return "TRUE"
    kind = resolve_place_kind(text)
    if kind == "admin_dong" or uses_admin_boundary(text):
        return legal_dong_a4_predicate(text, alias=alias)
    if text.endswith(("동", "가", "리", "로")) or kind == "legal_dong":
        return legal_dong_a4_predicate(text, alias=alias)
    if kind == "gu" or text.endswith(("구", "군")):
        pred = sigungu_a3_predicate(text, alias=alias, sido=sido)
        if pred:
            return pred
    pred = sigungu_a3_predicate(text, alias=alias, sido=sido)
    if pred:
        return pred
    col = _quote_ident(alias, "A4")
    return f"{col} LIKE {_sql_str('%' + text + '%')}"


# 레거시 이름 (router / templates / profile_qa)
def place_a4_predicate(place: str) -> str:
    return building_place_predicate(place)
