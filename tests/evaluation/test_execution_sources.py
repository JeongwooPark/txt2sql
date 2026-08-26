from txt2sql.evaluation.execution_sources import share_execution_sources


def test_share_execution_sources_counts_and_untracked() -> None:
    payload = {
        "rows": [
            {"id": "a", "pass": True, "execution_source": "semantic_v2", "route": "semantic_v2"},
            {"id": "b", "pass": False, "execution_source": "legacy_router", "route": "building_place_count"},
            {"id": "c", "pass": False, "route": "semantic_plan_aggregate"},
            {"id": "d", "pass": False, "route": None, "sql": "SELECT 1"},
            {"id": "e", "pass": False},
        ]
    }
    share = share_execution_sources(payload)
    assert share["total"] == 5
    assert share["counts"]["semantic_v2"] == 1
    assert share["counts"]["legacy_router"] == 1
    assert share["counts"]["semantic_plan"] == 1
    assert share["counts"]["rag_sql"] == 1
    assert share["untracked"] == 1
