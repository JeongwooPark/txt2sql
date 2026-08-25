"""행정동(BND) · 기초구역(BAS) · 건물(D010) 공간 연산 라우트."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from txt2sql.domain import (
    LENGTH_DIST_PATTERN,
    _FALSE_DONG,
    dong_requires_gu,
    extract_gu,
    extract_place,
    extract_places,
    extract_usage,
    looks_like_age_question,
    looks_like_measure_threshold,
)
from txt2sql.spatial_templates import (
    bas_dong_buffer_count_sql,
    bas_dong_count_and_max_sql,
    bas_dong_count_sql,
    bas_dong_list_sql,
    bas_dong_nearest_sql,
    bas_gu_bnd_intersect_count_sql,
    building_bas_count_sql,
    building_bas_list_sql,
    building_in_dong_count_sql,
    building_in_dong_list_sql,
    dong_neighbor_sql,
    legal_dong_admin_members_sql,
    legal_dong_admin_share_sql,
    place_buffer_count_sql,
    place_buffer_list_sql,
)
from txt2sql.units import convert_for_schema, sql_number

if TYPE_CHECKING:
    from txt2sql.intent_router import RoutedQuery

_SHARE_HINT = (
    "몇%",
    "몇 %",
    "몇퍼센트",
    "몇 퍼센트",
    "퍼센트씩",
    "%씩",
    "비율",
    "몇 프로",
    "몇프로",
)

_LENGTH_DIST = LENGTH_DIST_PATTERN
_BAS_ID_RE = re.compile(r"기초구역(?:번호|ID|id)?\s*[:\s]?\s*(\d{4,10})")
_FALSE_PLACE = _FALSE_DONG | {"행정동", "법정동"}


_MEMBER_ASK = (
    "무엇",
    "어떤",
    "목록",
    "리스트",
    "어디",
    "있",
    "구성",
    "나뉘",
    "속하는",
    "속한",
    "포함된",
)
_MEMBER_INSIDE = ("내에", "안에", "속한", "속하는", "포함된", "포함하", "나뉜")
_MEMBER_BLOCK = (
    "인접",
    "맞닿",
    "접하",
    "교차",
    "겹치",
    "기초구역",
    "건물",
    "건축물",
    "아파트",
    "주택",
    "공장",
    "몇",
    "건수",
    "채야",
    "채수",
    "특징",
    "비교",
    "퍼센트",
    "%",
    "뜻",
    "의미",
    "컬럼",
    "속성",
)


def _looks_like_admin_members(q: str) -> bool:
    """「연산동 내에 행정동은 무엇이 있어?」처럼 구성 행정동 목록."""
    if "행정동" not in q:
        return False
    if any(k in q for k in _MEMBER_BLOCK):
        return False
    inside = any(k in q for k in _MEMBER_INSIDE)
    asking = any(k in q for k in _MEMBER_ASK)
    return bool(inside or asking)


def _route_legal_dong_admin_members(q: str):
    from txt2sql.gazetteer import is_locality
    from txt2sql.intent_router import RoutedQuery

    if not _looks_like_admin_members(q):
        return None
    place = extract_place(q)
    if not place or place in _FALSE_PLACE or not is_locality(place):
        return None
    return RoutedQuery(
        "legal_dong_admin_members",
        legal_dong_admin_members_sql(place),
    )


def _looks_like_admin_share(q: str) -> bool:
    if any(k in q for k in _SHARE_HINT):
        return True
    return "%" in q and any(k in q for k in ("동에", "동과", "동별"))


def _numbered_dongs(q: str) -> list[str]:
    found: list[str] = []
    for place in extract_places(q):
        if re.fullmatch(r"[가-힣]+\d+동", place) and place not in found:
            found.append(place)
    return found


def _legal_dong_for_share(q: str) -> str | None:
    numbered = set(_numbered_dongs(q))
    for place in extract_places(q):
        if (
            place.endswith("동")
            and place not in numbered
            and place not in _FALSE_PLACE
        ):
            return place
    return None


def _route_legal_dong_admin_share(q: str):
    from txt2sql.domain import legal_dong_guess
    from txt2sql.intent_router import RoutedQuery

    if not _looks_like_admin_share(q):
        return None
    if not (_has_building(q) or extract_usage(q)):
        return None
    admins = _numbered_dongs(q)
    legal = _legal_dong_for_share(q)
    if legal is None and admins:
        guessed = {legal_dong_guess(a) for a in admins}
        guessed.discard(None)
        if len(guessed) == 1:
            legal = guessed.pop()
    if legal is None:
        return None
    usage = extract_usage(q)
    return RoutedQuery(
        "legal_dong_admin_share",
        legal_dong_admin_share_sql(legal, admins, usage=usage),
    )


def _has_building(q: str) -> bool:
    return any(k in q for k in ("건물", "건축물", "채"))


def _has_bas(q: str) -> bool:
    return "기초구역" in q or "kodis" in q.lower()


def _has_bnd_layer(q: str) -> bool:
    return any(k in q for k in ("행정동", "행정구역", "센서스", "동경계", "동 경계"))


def _extract_dong(q: str) -> str | None:
    from txt2sql.gazetteer import is_locality

    for place in extract_places(q):
        if place not in _FALSE_PLACE and is_locality(place):
            return place
    place = extract_place(q)
    if place and place not in _FALSE_PLACE and is_locality(place):
        return place
    return None


def _extract_bas_id(q: str) -> str | None:
    m = _BAS_ID_RE.search(q)
    return m.group(1) if m else None


def _has_distance_hint(q: str) -> bool:
    if any(k in q for k in ("주변", "근처", "인근", "버퍼", "반경")):
        return True
    return bool(re.search(rf"{_LENGTH_DIST}\s*(?:안|이내)", q))


def _parse_meters(q: str) -> tuple[str, str] | None:
    m = re.search(_LENGTH_DIST, q)
    if not m:
        return None
    converted = convert_for_schema(m.group(1), m.group(2), "m")
    if converted is None:
        return None
    expand = sql_number(max(0.0015, converted.canonical / 111000.0 * 1.5))
    return converted.sql, expand


def _wants_list(q: str) -> bool:
    if any(k in q for k in ("몇", "개수", "건수", "채", "세어", "구해")):
        return False
    if any(k in q for k in ("목록", "리스트", "보여", "어떤", "무엇", "이름")):
        return True
    if any(k in q for k in ("인접", "맞닿", "가까운")):
        return True
    if any(k in q for k in ("있는 건물", "건물은", "건물들", "기초구역은", "행정동은")):
        return True
    stripped = q.rstrip()
    return stripped.endswith(("은?", "는?", "은？", "는？"))


def _spatial_op(q: str) -> str | None:
    if any(k in q for k in ("가장 가까운", "제일 가까운", "최근접")):
        return "nearest"
    if any(k in q for k in ("경계 밖", "바깥", "외부")) and _parse_meters(q):
        return "outside_buffer"
    if _has_distance_hint(q) and _parse_meters(q):
        return "buffer"
    if any(k in q for k in ("일부만 겹", "걸치")):
        return "touches"
    if any(k in q for k in ("완전히", "온전히")):
        return "within"
    if any(k in q for k in ("인접", "맞닿", "접하", "맞붙어")):
        return "touches"
    if any(k in q for k in ("교차", "겹치")):
        return "intersects"
    if any(
        k in q
        for k in ("안에", "내에", "내부", "안쪽", "속하는", "포함", "들어가는", "경계 안")
    ):
        return "intersects"
    return None


def try_spatial_route(question: str) -> RoutedQuery | None:
    """BND ↔ BAS ↔ 건물 공간 연산. 속성 COUNT/목록보다 우선 호출해야 한다."""
    from txt2sql.intent_router import RoutedQuery

    q = question.strip()
    if looks_like_measure_threshold(q) or looks_like_age_question(q):
        return None
    if "좌표" in q or re.search(r"12\d\.\d+", q):
        return None

    share = _route_legal_dong_admin_share(q)
    if share is not None:
        return share

    members = _route_legal_dong_admin_members(q)
    if members is not None:
        return members

    op = _spatial_op(q)
    if op is None:
        return None

    dong = _extract_dong(q)
    gu = extract_gu(q)
    bas_id = _extract_bas_id(q)
    has_bldg = _has_building(q)
    has_bas = _has_bas(q)
    has_bnd = _has_bnd_layer(q) or bool(dong)
    as_list = _wants_list(q)

    # 건물 × 기초구역
    if has_bldg and has_bas and op in {"intersects", "within"}:
        if not bas_id and not gu:
            return None
        if as_list:
            return RoutedQuery(
                "spatial_bldg_bas_list",
                building_bas_list_sql(gu=gu, bas_id=bas_id),
            )
        return RoutedQuery(
            "spatial_bldg_bas_count",
            building_bas_count_sql(gu=gu, bas_id=bas_id),
        )

    # 건물 × 행정동
    if has_bldg and dong and not has_bas:
        meters = _parse_meters(q)
        if op == "outside_buffer" and meters:
            msql, deg = meters
            intent = (
                "place_buffer_outside_list"
                if as_list
                else "place_buffer_outside_count"
            )
            sql = (
                place_buffer_list_sql(dong, msql, deg, exterior=True)
                if as_list
                else place_buffer_count_sql(dong, msql, deg, exterior=True)
            )
            return RoutedQuery(intent, sql)
        if op == "buffer" and meters:
            msql, deg = meters
            intent = "place_buffer_list" if as_list else "place_buffer_count"
            sql = (
                place_buffer_list_sql(dong, msql, deg)
                if as_list
                else place_buffer_count_sql(dong, msql, deg)
            )
            return RoutedQuery(intent, sql)
        if op in {"intersects", "within"}:
            if dong_requires_gu(dong) and not gu:
                return None
            if as_list:
                return RoutedQuery(
                    "building_in_dong_spatial_list",
                    building_in_dong_list_sql(dong),
                )
            return RoutedQuery(
                "building_in_dong_spatial",
                building_in_dong_count_sql(dong),
            )

    # 기초구역 × 행정동
    if has_bas and dong:
        meters = _parse_meters(q)
        if op == "nearest":
            return RoutedQuery(
                "spatial_bas_dong_nearest",
                bas_dong_nearest_sql(dong),
            )
        if op == "buffer" and meters:
            msql, deg = meters
            return RoutedQuery(
                "spatial_bas_dong_buffer_count",
                bas_dong_buffer_count_sql(dong, msql, deg),
            )
        join_op = (
            "within"
            if op == "within"
            else ("touches" if op == "touches" else "intersects")
        )
        if as_list:
            return RoutedQuery(
                "spatial_bas_dong_list",
                bas_dong_list_sql(dong, join_op),
            )
        if any(k in q for k in ("최대", "가장")) and any(
            k in q for k in ("개수", "몇", "채수")
        ):
            return RoutedQuery(
                "spatial_bas_dong_count_max",
                bas_dong_count_and_max_sql(dong, join_op),
            )
        return RoutedQuery(
            "spatial_bas_dong_count",
            bas_dong_count_sql(dong, join_op),
        )

    # 구 기초구역 ∩ 센서스 행정동 (동명 없음)
    if has_bas and has_bnd and gu and not dong and op == "intersects":
        return RoutedQuery(
            "spatial_bas_bnd_gu_count",
            bas_gu_bnd_intersect_count_sql(gu),
        )

    # 행정동 × 행정동 (인접)
    if dong and op == "touches" and not has_bas and not has_bldg:
        return RoutedQuery("spatial_dong_touch_list", dong_neighbor_sql(dong))

    return None
