from llm2sql.domain import place_a4_predicate
from llm2sql.map.sql import plan_map_sql


def test_gu_profile_compare_uses_boundaries() -> None:
    plan = plan_map_sql(
        question="금정구와 사하구 건물의 특성을 비교하라",
        sql='SELECT COUNT(*) AS cnt FROM "AL_D010_26_20250704" WHERE "A3" LIKE \'26410%\';',
        route="building_profile_compare",
        ok=True,
    )
    assert plan is not None
    assert plan.kind == "boundary"
    assert "금정구" in plan.sql
    assert "사하구" in plan.sql
    assert "AL_D010" not in plan.sql
    assert "UNION ALL" in plan.sql
    assert "TL_KODIS_BAS" in plan.sql
    assert "26410" in plan.sql
    assert "26380" in plan.sql
    assert 'ADM_CD" LIKE' not in plan.sql


def test_dong_profile_compare_keeps_features() -> None:
    sql = (
        'SELECT COUNT(*) AS cnt FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry, d.geometry)\n'
        "WHERE d.\"ADM_NM\" = '구서1동';\n;\n"
        'SELECT COUNT(*) AS cnt FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry, d.geometry)\n'
        "WHERE d.\"ADM_NM\" = '구서2동';"
    )
    plan = plan_map_sql(
        question="구서1동과 구서2동의 단독주택의 특성을 비교하라.",
        sql=sql,
        route="building_profile_compare",
        ok=True,
    )
    assert plan is not None
    assert plan.kind == "features"
    assert "구서2동" in plan.sql


def test_gu_place_filter_uses_legal_code() -> None:
    pred = place_a4_predicate("금정구")
    assert "26410" in pred
    assert "A3" in pred
    assert "%금정구%" not in pred
