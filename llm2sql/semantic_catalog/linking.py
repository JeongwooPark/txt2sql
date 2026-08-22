"""table / column / value 계층 검색. 모호하면 clarify 신호를 낸다."""

from __future__ import annotations

from dataclasses import dataclass

from llm2sql.semantic_catalog.registry import VALUE_PROFILES
from llm2sql.semantic_plan.catalog import FIELDS_BY_ENTITY


@dataclass(frozen=True)
class LinkHit:
    kind: str
    key: str
    score: float
    binding: str


@dataclass(frozen=True)
class LinkResult:
    hits: tuple[LinkHit, ...]
    clarify: bool
    margin: float


def _score(query: str, text: str) -> float:
    q = query.replace(" ", "")
    t = text.replace(" ", "")
    if q == t:
        return 1.0
    if t in q or q in t:
        return 0.8
    return 0.0


def retrieve_tables(question: str, *, top_k: int = 10) -> LinkResult:
    mapping = {
        "building": ("건물", "아파트", "주택", "건축물", "연면적", "건축면적", "높이", "용도"),
        "admin_area": ("행정동", "구", "동"),
        "basic_zone": ("기초구역",),
        "industrial_complex": ("산업단지", "산단"),
    }
    hits = []
    for key, aliases in mapping.items():
        score = max((_score(question, alias) for alias in aliases), default=0.0)
        if score:
            hits.append(LinkHit("table", key, score, key))
    hits.sort(key=lambda item: item.score, reverse=True)
    return _pack(hits[:top_k])


_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "gross_floor_area_m2": ("연면적", "작은", "큰"),
    "height_m": ("높이", "낮은", "높은"),
    "building_area_m2": ("건축면적",),
    "site_area_m2": ("대지면적",),
    "usage": ("용도",),
}


def retrieve_columns(question: str, *, top_k: int = 20) -> LinkResult:
    hits = []
    for entity_fields in FIELDS_BY_ENTITY.values():
        for key, field in entity_fields.items():
            texts = (field.label, key, *_COLUMN_ALIASES.get(key, ()))
            score = max(_score(question, text) for text in texts)
            if score:
                hits.append(LinkHit("column", key, score, f"{field.table}.{field.column}"))
    for profile in VALUE_PROFILES:
        texts = (profile.canonical, *profile.synonyms)
        score = max(_score(question, text) for text in texts)
        if score:
            hits.append(LinkHit("column", "usage", score, f"{profile.table}.{profile.column}"))
    hits.sort(key=lambda item: item.score, reverse=True)
    return _pack(hits[:top_k])


def retrieve_values(question: str, *, top_k: int = 10) -> LinkResult:
    hits = []
    for profile in VALUE_PROFILES:
        texts = (profile.canonical, *profile.synonyms)
        score = max(_score(question, text) for text in texts)
        if score:
            binding = f"{profile.table}.{profile.column}={profile.canonical}"
            hits.append(LinkHit("value", profile.canonical, score, binding))
    hits.sort(key=lambda item: item.score, reverse=True)
    packed = _pack(hits[:top_k])
    if packed.margin < 0.15 and len(packed.hits) >= 2:
        return LinkResult(packed.hits, True, packed.margin)
    return packed


_POI_NAMES = (
    "부산역",
    "센텀시티역",
    "구서역",
    "서면역",
    "해운대역",
    "사상역",
    "부전역",
)


def retrieve_poi(question: str, *, top_k: int = 5) -> LinkResult:
    cleaned = question.replace("기초구역", "").replace("구역", "")
    if not any(token in cleaned for token in ("역", "터미널", "정류장")):
        return LinkResult((), False, 1.0)
    hits = []
    for name in _POI_NAMES:
        score = _score(question, name)
        if score:
            hits.append(LinkHit("poi", name, score, name))
    if not hits and any(token in cleaned for token in ("역", "터미널", "정류장")):
        return LinkResult((), True, 0.0)
    hits.sort(key=lambda item: item.score, reverse=True)
    packed = _pack(hits[:top_k])
    if packed.margin < 0.15 and len(packed.hits) >= 2:
        return LinkResult(packed.hits, True, packed.margin)
    if packed.hits and packed.hits[0].score < 1.0:
        return LinkResult(packed.hits, True, packed.margin)
    return packed


def _pack(hits: list[LinkHit]) -> LinkResult:
    if not hits:
        return LinkResult((), False, 1.0)
    if len(hits) == 1:
        return LinkResult(tuple(hits), False, 1.0)
    margin = hits[0].score - hits[1].score
    return LinkResult(tuple(hits), False, margin)
