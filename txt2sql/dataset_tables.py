"""활성 건물·기초구역 물리 테이블 resolve (전국 다중 시·도 대응).

SQL 생성 경로는 하드코드 테이블명 대신 여기 resolve_* 만 호출한다.
data.coverage 가 DB 스캔 후 set_* 로 맵을 채우며, 비어 있으면 DEFAULT_* 폴백.
"""

from __future__ import annotations

# 의도적 폴백: 커버리지 맵이 비었을 때 쓰는 부산 스냅샷 (골드·로컬 기본).
DEFAULT_BUILDING_TABLE = "AL_D010_26_20250704"
DEFAULT_BASIC_ZONE_TABLE = "TL_KODIS_BAS_26_202507"
DEFAULT_SIDO_PNU = "26"  # 부산광역시 법정동(PNU) 시·도 접두

_BUILDING_BY_SIDO: dict[str, str] = {}
_BASIC_ZONE_BY_SIDO: dict[str, str] = {}
_PRIMARY_SIDO_PNU: str = DEFAULT_SIDO_PNU


def primary_sido_pnu() -> str:
    return _PRIMARY_SIDO_PNU or DEFAULT_SIDO_PNU


def set_primary_sido_pnu(code: str | None) -> None:
    global _PRIMARY_SIDO_PNU
    text = (code or "").strip()
    if text.isdigit() and len(text) >= 2:
        _PRIMARY_SIDO_PNU = text[:2]
    elif not text:
        _PRIMARY_SIDO_PNU = DEFAULT_SIDO_PNU


def building_coverage_map() -> dict[str, str]:
    return dict(_BUILDING_BY_SIDO)


def basic_zone_coverage_map() -> dict[str, str]:
    return dict(_BASIC_ZONE_BY_SIDO)


def set_building_coverage(
    by_sido: dict[str, str],
    *,
    primary_sido: str | None = None,
) -> None:
    """시·도 PNU 접두 → AL_D010_* 맵. 빈 dict 는 무시."""
    global _BUILDING_BY_SIDO
    if not by_sido:
        return
    cleaned: dict[str, str] = {}
    for key, table in by_sido.items():
        code = str(key or "").strip()[:2]
        name = str(table or "").strip()
        if code.isdigit() and name:
            cleaned[code] = name
    if not cleaned:
        return
    _BUILDING_BY_SIDO = cleaned
    if primary_sido is not None:
        set_primary_sido_pnu(primary_sido)
    elif DEFAULT_SIDO_PNU in cleaned:
        set_primary_sido_pnu(DEFAULT_SIDO_PNU)
    elif cleaned:
        set_primary_sido_pnu(sorted(cleaned.keys())[0])


def set_basic_zone_coverage(
    by_sido: dict[str, str],
    *,
    primary_sido: str | None = None,
) -> None:
    """시·도 PNU 접두 → TL_KODIS_BAS_* 맵. 빈 dict 는 무시."""
    global _BASIC_ZONE_BY_SIDO
    if not by_sido:
        return
    cleaned: dict[str, str] = {}
    for key, table in by_sido.items():
        code = str(key or "").strip()[:2]
        name = str(table or "").strip()
        if code.isdigit() and name:
            cleaned[code] = name
    if not cleaned:
        return
    _BASIC_ZONE_BY_SIDO = cleaned
    if primary_sido is not None:
        set_primary_sido_pnu(primary_sido)


def reset_dataset_table_coverage() -> None:
    """건물·기초구역 커버리지를 기본 폴백으로 되돌린다."""
    global _BUILDING_BY_SIDO, _BASIC_ZONE_BY_SIDO, _PRIMARY_SIDO_PNU
    _BUILDING_BY_SIDO = {}
    _BASIC_ZONE_BY_SIDO = {}
    _PRIMARY_SIDO_PNU = DEFAULT_SIDO_PNU


def resolve_building_table(
    *,
    sido_code: str | None = None,
    sido: str | None = None,
) -> str:
    """활성 GIS건물통합(AL_D010) 물리 테이블.

    우선순위: 명시 시·도 코드 맵 → primary_sido 맵 → DEFAULT_BUILDING_TABLE.
    """
    code = _sido_pnu_code(sido_code=sido_code, sido=sido)
    if code and code in _BUILDING_BY_SIDO:
        return _BUILDING_BY_SIDO[code]
    primary = primary_sido_pnu()
    if primary in _BUILDING_BY_SIDO:
        return _BUILDING_BY_SIDO[primary]
    if _BUILDING_BY_SIDO:
        return next(iter(sorted(_BUILDING_BY_SIDO.items())))[1]
    return DEFAULT_BUILDING_TABLE


def resolve_basic_zone_table(
    *,
    sido_code: str | None = None,
    sido: str | None = None,
) -> str:
    """활성 기초구역(TL_KODIS_BAS) 물리 테이블."""
    code = _sido_pnu_code(sido_code=sido_code, sido=sido)
    if code and code in _BASIC_ZONE_BY_SIDO:
        return _BASIC_ZONE_BY_SIDO[code]
    primary = primary_sido_pnu()
    if primary in _BASIC_ZONE_BY_SIDO:
        return _BASIC_ZONE_BY_SIDO[primary]
    if _BASIC_ZONE_BY_SIDO:
        return next(iter(sorted(_BASIC_ZONE_BY_SIDO.items())))[1]
    return DEFAULT_BASIC_ZONE_TABLE


def _sido_pnu_code(
    *,
    sido_code: str | None = None,
    sido: str | None = None,
) -> str | None:
    raw = (sido_code or "").strip()
    if raw.isdigit() and len(raw) >= 2:
        return raw[:2]
    if not (sido or "").strip():
        return None
    from txt2sql.gazetteer import sido_pnu_prefix

    return sido_pnu_prefix(sido)
