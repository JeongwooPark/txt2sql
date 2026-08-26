"""Canonical semantic concepts (no physical names in public API of QueryIR)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Concept:
    key: str
    entity: str
    label: str
    unit: str | None = None
    synonyms: tuple[str, ...] = ()


CONCEPTS: dict[str, Concept] = {
    "building.height": Concept("building.height", "building", "높이", "m", ("높이", "height_m")),
    "building.usage": Concept("building.usage", "building", "용도", None, ("용도", "usage")),
    "building.detail_usage": Concept(
        "building.detail_usage", "building", "세부용도", None, ("세부용도", "detail_usage")
    ),
    "building.approval_date": Concept(
        "building.approval_date", "building", "사용승인일", None, ("사용승인일", "approval_date")
    ),
    "building.floor_area_ratio": Concept(
        "building.floor_area_ratio", "building", "용적률", "%", ("용적률", "floor_area_ratio")
    ),
    "building.building_coverage_ratio": Concept(
        "building.building_coverage_ratio",
        "building",
        "건폐율",
        "%",
        ("건폐율", "building_coverage_ratio"),
    ),
    "building.gross_floor_area": Concept(
        "building.gross_floor_area",
        "building",
        "연면적",
        "m2",
        ("연면적", "gross_floor_area_m2"),
    ),
    "building.ground_floors": Concept(
        "building.ground_floors", "building", "지상층수", None, ("지상층수", "ground_floors")
    ),
    "building.basement_floors": Concept(
        "building.basement_floors",
        "building",
        "지하층수",
        None,
        ("지하층수", "basement_floors", "지하"),
    ),
    "building.age": Concept("building.age", "building", "건축연령", "year", ("건축연령", "age")),
    "admin.sigungu": Concept("admin.sigungu", "admin_area", "시군구", None, ("구", "sigungu_name")),
    "admin.legal_dong": Concept(
        "admin.legal_dong", "admin_area", "법정동", None, ("동", "legal_dong")
    ),
}

# Legacy canonical field -> concept key
FIELD_TO_CONCEPT: dict[str, str] = {
    "height_m": "building.height",
    "usage": "building.usage",
    "detail_usage": "building.detail_usage",
    "approval_date": "building.approval_date",
    "floor_area_ratio": "building.floor_area_ratio",
    "building_coverage_ratio": "building.building_coverage_ratio",
    "gross_floor_area_m2": "building.gross_floor_area",
    "ground_floors": "building.ground_floors",
    "basement_floors": "building.basement_floors",
    "sigungu_name": "admin.sigungu",
    "legal_dong": "admin.legal_dong",
}


def resolve_concept(token: str) -> Concept | None:
    if token in CONCEPTS:
        return CONCEPTS[token]
    if token in FIELD_TO_CONCEPT:
        return CONCEPTS[FIELD_TO_CONCEPT[token]]
    lowered = token.strip().lower()
    for concept in CONCEPTS.values():
        if lowered == concept.key.lower() or lowered in {s.lower() for s in concept.synonyms}:
            return concept
        if lowered == concept.label.lower():
            return concept
    return None
