from txt2sql.semantic_plan.compiler import compile_semantic_plan
from txt2sql.semantic_plan.models import (
    FilterSpec,
    PlaceSpec,
    ScopeSpec,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)


def test_compiler_admin_boundary_intersects() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(
            place=PlaceSpec(name="연산동", kind="admin_dong"),
            spatial_mode="boundary",
        ),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
        select=["name", "gross_floor_area_m2"],
        limit=10,
    )
    sql = compile_semantic_plan(plan).sql
    assert "BND_ADM_DONG_PG" in sql
    assert "ST_Intersects" in sql
    assert "ADM_CD" in sql
    assert "INSERT" not in sql.upper()


def test_compiler_st_dwithin_place_buffer() -> None:
    plan = SemanticQueryPlan(
        query_kind="list",
        entity="building",
        scope=ScopeSpec(place=PlaceSpec(name="구서동", kind="legal_dong")),
        filters=[FilterSpec(field="usage", operator="eq", value="공동주택")],
        select=["name"],
        spatial_relations=[
            SpatialRelationSpec(
                relation="within_distance",
                target=SpatialTargetSpec(
                    place=PlaceSpec(name="구서동", kind="legal_dong")
                ),
                distance_m=500,
            )
        ],
        limit=50,
    )
    sql = compile_semantic_plan(plan).sql
    assert "ST_DWithin" in sql
    assert "::geography" in sql
    assert "500" in sql
    assert "BND_ADM_DONG_PG" in sql
    assert "ST_Union" in sql
    # 같은 장소면 A4 LIKE를 중복하지 않는다
    assert '"A4"' not in sql


def test_compiler_outside_distance() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        spatial_relations=[
            SpatialRelationSpec(
                relation="outside_distance",
                target=SpatialTargetSpec(place=PlaceSpec(name="구서동", kind="legal_dong")),
                distance_m=200,
            )
        ],
    )
    sql = compile_semantic_plan(plan).sql
    assert "ST_DWithin" in sql
    assert "NOT ST_DWithin" in sql
