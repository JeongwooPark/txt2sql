from llm2sql.semantic_plan.compiler import compile_semantic_plan
from llm2sql.semantic_plan.models import (
    JoinSpec,
    PlaceSpec,
    SemanticCompileError,
    SemanticQueryPlan,
    SpatialRelationSpec,
    SpatialTargetSpec,
)
from llm2sql.semantic_plan.spatial_policy import resolve_spatial_policy
from llm2sql.semantic_plan.validator import validate_semantic_plan


def _place_rel(relation: str, **extra: object) -> SpatialRelationSpec:
    return SpatialRelationSpec(
        relation=relation,  # type: ignore[arg-type]
        target=SpatialTargetSpec(place=PlaceSpec(name="연산동", kind="admin_dong")),
        **extra,
    )


def test_within_is_covered_by_not_intersects() -> None:
    assert resolve_spatial_policy("within").postgis_fn == "ST_CoveredBy"
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        spatial_relations=[_place_rel("within")],
    )
    sql = compile_semantic_plan(plan).sql
    assert "ST_CoveredBy" in sql
    assert "ON ST_Intersects" not in sql


def test_intersects_touches_buffer_nearest_overlap() -> None:
    inter = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="count",
            entity="building",
            spatial_relations=[_place_rel("intersects")],
        )
    ).sql
    assert "ST_Intersects" in inter

    touch = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="list",
            entity="building",
            spatial_relations=[_place_rel("touches")],
            limit=20,
        )
    ).sql
    assert "ST_Touches" in touch

    buf = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="list",
            entity="building",
            spatial_relations=[_place_rel("buffer", distance_m=300)],
            limit=20,
        )
    ).sql
    assert "ST_DWithin" in buf

    near = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="list",
            entity="building",
            spatial_relations=[_place_rel("nearest")],
        )
    ).sql
    assert "ST_Distance" in near
    assert "LIMIT" not in near.upper()

    overlap = compile_semantic_plan(
        SemanticQueryPlan(
            query_kind="count",
            entity="building",
            spatial_relations=[_place_rel("overlap_ratio", min_ratio=0.4)],
        )
    ).sql
    assert "ST_Intersection" in overlap
    assert "0.4" in overlap


def test_canonical_join_edge_only() -> None:
    plan = SemanticQueryPlan(
        query_kind="count",
        entity="building",
        joins=[JoinSpec(edge_id="building_in_industrial")],
    )
    sql = compile_semantic_plan(plan).sql
    assert "AL_D060_00_20250804" in sql
    try:
        compile_semantic_plan(
            SemanticQueryPlan(
                query_kind="count",
                entity="building",
                joins=[JoinSpec(edge_id="raw_sql_join")],
            )
        )
        raise AssertionError("expected compile error")
    except SemanticCompileError as exc:
        assert "unknown join edge" in str(exc)


def test_ambiguous_poi_clarifies() -> None:
    plan = SemanticQueryPlan(query_kind="count", entity="building")
    checked = validate_semantic_plan(plan, "역 근처 건물 몇 채")
    assert checked.status == "clarify"
    assert "ambiguous_poi" in checked.errors
