"""닫힌 KorDB 카탈로그에 질문 멘션을 연결한다. 벡터 검색이 아니다."""

from __future__ import annotations

from dataclasses import dataclass, field

from llm2sql.domain import (
    D198_BY_GU,
    looks_like_age_question,
    d198_gu_mentioned,
)


@dataclass(frozen=True)
class DatasetHit:
    id: str
    confidence: float


@dataclass(frozen=True)
class SpatialPath:
    op: str
    left_entity: str
    right_entity: str


@dataclass
class Binding:
    datasets: list[DatasetHit] = field(default_factory=list)
    fields: list[dict[str, object]] = field(default_factory=list)
    values: list[dict[str, object]] = field(default_factory=list)
    spatial_path: SpatialPath | None = None
    aliases: dict[str, list[str]] = field(default_factory=dict)
    confidence: float = 1.0


# 허용된 공간 조인만 SQP가 컴파일한다.
SPATIAL_PATHS: dict[tuple[str, str, str], SpatialPath] = {
    ("building", "intersects", "admin_area"): SpatialPath(
        "intersects", "building", "admin_area"
    ),
    ("building", "within", "admin_area"): SpatialPath("within", "building", "admin_area"),
    ("building", "intersects", "basic_zone"): SpatialPath(
        "intersects", "building", "basic_zone"
    ),
    ("admin_area", "intersects", "basic_zone"): SpatialPath(
        "intersects", "admin_area", "basic_zone"
    ),
    ("building", "within", "industrial_complex"): SpatialPath(
        "within", "building", "industrial_complex"
    ),
    ("point", "dwithin", "building"): SpatialPath("dwithin", "point", "building"),
}


def lookup_spatial_path(left: str, op: str, right: str) -> SpatialPath | None:
    return SPATIAL_PATHS.get((left, op, right))


def bind_catalog(question: str) -> Binding:
    q = question or ""
    datasets: list[DatasetHit] = []
    path: SpatialPath | None = None

    wants_bas = "기초구역" in q or "BAS_" in q.upper()
    wants_industrial = "산업단지" in q or "사업지구" in q
    wants_d198 = _needs_d198(q)
    wants_admin = any(k in q for k in ("행정동", "행정구역", "센서스"))
    wants_buffer = any(k in q for k in ("반경", "이내", "버퍼", "주변", "좌표"))
    wants_cross = any(k in q for k in ("교차", "겹치", "맞닿", "안에", "내부", "경계 안"))

    if wants_bas:
        datasets.append(DatasetHit("bas", 0.9))
    if wants_industrial:
        datasets.append(DatasetHit("industrial", 0.9))
    if wants_d198:
        datasets.append(DatasetHit("d198", 0.85))
    if wants_admin:
        datasets.append(DatasetHit("admin", 0.8))
    datasets.append(DatasetHit("d010", 0.7 if datasets else 1.0))

    if wants_buffer and ("건물" in q or "건축" in q):
        path = lookup_spatial_path("point", "dwithin", "building")
    elif wants_industrial and ("건물" in q or "공장" in q or "안에" in q or "내부" in q):
        path = lookup_spatial_path("building", "within", "industrial_complex")
    elif wants_bas and wants_admin:
        path = lookup_spatial_path("admin_area", "intersects", "basic_zone")
    elif wants_bas and ("건물" in q or "건축" in q or "교차" in q):
        path = lookup_spatial_path("building", "intersects", "basic_zone")
    elif wants_cross and wants_bas:
        path = lookup_spatial_path("building", "intersects", "basic_zone")

    from llm2sql.domain import expand_building_name_aliases, extract_building_name_candidate

    aliases: dict[str, list[str]] = {}
    name = extract_building_name_candidate(q)
    if name:
        aliases[name] = expand_building_name_aliases(name)

    conf = 1.0
    if wants_d198 and d198_gu_mentioned(q) is None and not any(
        g in q for g in D198_BY_GU
    ):
        conf = 0.6
    return Binding(
        datasets=datasets,
        spatial_path=path,
        aliases=aliases,
        confidence=conf,
    )


def _needs_d198(question: str) -> bool:
    if d198_gu_mentioned(question) is not None:
        return True
    if any(
        k in question
        for k in (
            "용도별건물",
            "주요용도",
            "세부용도",
            "용도분류",
            "건축년",
            "준공",
            "사용승인",
            "허가일",
            "지어진",
            "경과년",
            "AL_D198",
            "D198",
        )
    ):
        return True
    return looks_like_age_question(question)
