"""canonical semantic field → 물리 테이블/컬럼 allowlist."""

from __future__ import annotations

from dataclasses import dataclass

from llm2sql.semantic_plan.models import UnknownSemanticFieldError

BUILDING_TABLE = "AL_D010_26_20250704"
ADMIN_TABLE = "BND_ADM_DONG_PG"
BASIC_ZONE_TABLE = "TL_KODIS_BAS_26_202507"

_TEXT_OPS = ("eq", "neq", "contains", "in", "is_null", "is_not_null")
_NUM_OPS = ("eq", "neq", "gt", "gte", "lt", "lte", "between", "is_null", "is_not_null")


@dataclass(frozen=True)
class SemanticField:
    key: str
    entity: str
    table: str
    column: str
    data_type: str
    unit: str | None = None
    label: str = ""
    allowed_ops: tuple[str, ...] = ()
    sortable: bool = True
    groupable: bool = True
    aggregatable: bool = True


@dataclass(frozen=True)
class SemanticEntity:
    key: str
    default_table: str
    geometry_column: str | None
    id_field: str | None
    label: str


def _text(
    key: str,
    entity: str,
    table: str,
    column: str,
    label: str,
    *,
    groupable: bool = True,
) -> SemanticField:
    return SemanticField(
        key=key,
        entity=entity,
        table=table,
        column=column,
        data_type="text",
        label=label,
        allowed_ops=_TEXT_OPS,
        sortable=True,
        groupable=groupable,
        aggregatable=False,
    )


def _num(
    key: str,
    entity: str,
    table: str,
    column: str,
    label: str,
    unit: str,
) -> SemanticField:
    return SemanticField(
        key=key,
        entity=entity,
        table=table,
        column=column,
        data_type="number",
        unit=unit,
        label=label,
        allowed_ops=_NUM_OPS,
        sortable=True,
        groupable=True,
        aggregatable=True,
    )


ENTITIES: dict[str, SemanticEntity] = {
    "building": SemanticEntity(
        key="building",
        default_table=BUILDING_TABLE,
        geometry_column="geometry",
        id_field="id",
        label="건물",
    ),
    "admin_area": SemanticEntity(
        key="admin_area",
        default_table=ADMIN_TABLE,
        geometry_column="geometry",
        id_field="code",
        label="행정구역",
    ),
    "basic_zone": SemanticEntity(
        key="basic_zone",
        default_table=BASIC_ZONE_TABLE,
        geometry_column="geometry",
        id_field="id",
        label="기초구역",
    ),
}

BUILDING_FIELDS: dict[str, SemanticField] = {
    "id": _text("id", "building", BUILDING_TABLE, "A0", "건물 식별자", groupable=False),
    "name": _text("name", "building", BUILDING_TABLE, "A24", "건물명"),
    "legal_dong": _text("legal_dong", "building", BUILDING_TABLE, "A4", "법정동명"),
    "lot_address": _text("lot_address", "building", BUILDING_TABLE, "A5", "지번"),
    "usage": _text("usage", "building", BUILDING_TABLE, "A9", "용도"),
    "structure": _text("structure", "building", BUILDING_TABLE, "A11", "구조"),
    "building_area_m2": _num(
        "building_area_m2", "building", BUILDING_TABLE, "A12", "건축면적", "m2"
    ),
    "gross_floor_area_m2": _num(
        "gross_floor_area_m2", "building", BUILDING_TABLE, "A14", "연면적", "m2"
    ),
    "site_area_m2": _num(
        "site_area_m2", "building", BUILDING_TABLE, "A15", "대지면적", "m2"
    ),
    "height_m": _num("height_m", "building", BUILDING_TABLE, "A16", "높이", "m"),
    "ground_floors": _num(
        "ground_floors", "building", BUILDING_TABLE, "A26", "지상층수", "floor"
    ),
    "basement_floors": _num(
        "basement_floors", "building", BUILDING_TABLE, "A27", "지하층수", "floor"
    ),
    "geometry": SemanticField(
        key="geometry",
        entity="building",
        table=BUILDING_TABLE,
        column="geometry",
        data_type="geometry",
        label="건물 공간정보",
        allowed_ops=(),
        sortable=False,
        groupable=False,
        aggregatable=False,
    ),
}

ADMIN_FIELDS: dict[str, SemanticField] = {
    "code": _text("code", "admin_area", ADMIN_TABLE, "ADM_CD", "행정구역코드"),
    "name": _text("name", "admin_area", ADMIN_TABLE, "ADM_NM", "행정동명"),
    "geometry": SemanticField(
        key="geometry",
        entity="admin_area",
        table=ADMIN_TABLE,
        column="geometry",
        data_type="geometry",
        label="행정구역 경계",
        allowed_ops=(),
        sortable=False,
        groupable=False,
        aggregatable=False,
    ),
}

BASIC_ZONE_FIELDS: dict[str, SemanticField] = {
    "id": _text("id", "basic_zone", BASIC_ZONE_TABLE, "BAS_ID", "기초구역ID"),
    "area_m2": _num(
        "area_m2", "basic_zone", BASIC_ZONE_TABLE, "BAS_AR", "기초구역면적", "m2"
    ),
    "gu_name": _text("gu_name", "basic_zone", BASIC_ZONE_TABLE, "SIG_KOR_NM", "시군구명"),
    "geometry": SemanticField(
        key="geometry",
        entity="basic_zone",
        table=BASIC_ZONE_TABLE,
        column="geometry",
        data_type="geometry",
        label="기초구역 공간정보",
        allowed_ops=(),
        sortable=False,
        groupable=False,
        aggregatable=False,
    ),
}

FIELDS_BY_ENTITY: dict[str, dict[str, SemanticField]] = {
    "building": BUILDING_FIELDS,
    "admin_area": ADMIN_FIELDS,
    "basic_zone": BASIC_ZONE_FIELDS,
}

ALLOWED_TABLES = frozenset({BUILDING_TABLE, ADMIN_TABLE, BASIC_ZONE_TABLE})
ALLOWED_COLUMNS = frozenset(
    field.column
    for fields in FIELDS_BY_ENTITY.values()
    for field in fields.values()
)
CANONICAL_ALIASES = frozenset(
    {"count", "n", *BUILDING_FIELDS, *ADMIN_FIELDS, *BASIC_ZONE_FIELDS}
)

DEFAULT_LIST_SELECT = (
    "name",
    "legal_dong",
    "lot_address",
    "usage",
    "height_m",
    "gross_floor_area_m2",
    "ground_floors",
)

AREA_FIELD_KEYS = frozenset(
    {"building_area_m2", "gross_floor_area_m2", "site_area_m2"}
)


def get_entity(key: str) -> SemanticEntity:
    entity = ENTITIES.get(key)
    if entity is None:
        raise UnknownSemanticFieldError(f"unknown entity: {key}")
    return entity


def get_field(entity: str, key: str) -> SemanticField:
    fields = FIELDS_BY_ENTITY.get(entity)
    if fields is None:
        raise UnknownSemanticFieldError(f"unknown entity: {entity}")
    field = fields.get(key)
    if field is None:
        raise UnknownSemanticFieldError(f"unknown field: {entity}.{key}")
    return field


def catalog_prompt_text(*, entity: str = "building") -> str:
    """LLM prompt에 넣을 canonical catalog. 물리 컬럼명은 넣지 않는다."""
    fields = FIELDS_BY_ENTITY.get(entity) or BUILDING_FIELDS
    lines = [f"entity: {entity}", "fields:"]
    for key, field in fields.items():
        if key == "geometry":
            continue
        unit = f" {field.unit}" if field.unit else ""
        lines.append(f"- {key} : {field.label}{unit}")
    lines.extend(
        [
            "",
            "supported operators: eq, neq, gt, gte, lt, lte, contains, in, between",
            "supported spatial relations: within, intersects, within_distance, outside_distance",
            "supported query_kind: count, list, rank, aggregate, distribution",
            "spatial_mode auto: 구/법정동은 주소 속성, 행정전용 동은 경계",
            "spatial_mode boundary: 행정 경계 containment (안에/내부)",
            "within_distance: 동·구 경계로부터 미터 거리. 역·POI 좌표는 불가",
            "건축면적 building_area_m2 / 연면적 gross_floor_area_m2 / 대지면적 site_area_m2 는 서로 다름",
            "층수 → ground_floors",
        ]
    )
    return "\n".join(lines)
