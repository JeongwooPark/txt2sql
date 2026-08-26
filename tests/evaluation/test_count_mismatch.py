from txt2sql.evaluation.count_mismatch import classify_count_mismatch, decompose_count_mismatches


def test_classify_count_mismatch_spatial_temporal_predicate() -> None:
    assert (
        classify_count_mismatch(
            question="해운대 주변 100m 건물 수",
            sql="SELECT COUNT(*) FROM t WHERE ST_DWithin(a,b,100)",
            reason="count-mismatch",
        )
        == "spatial"
    )
    assert (
        classify_count_mismatch(
            question="1990년대 사용승인 건물 수",
            sql="SELECT COUNT(*) FROM t WHERE A13 ~ '199'",
            reason="count-mismatch",
        )
        == "temporal"
    )
    assert (
        classify_count_mismatch(
            question="철골조 건물 수",
            sql="SELECT COUNT(*) FROM t",
            reason="count-mismatch",
            root_causes=["PREDICATE_DROPPED"],
        )
        == "predicate"
    )


def test_decompose_count_mismatches_concrete_ratio() -> None:
    payload = {
        "rows": [
            {
                "id": "1",
                "pass": False,
                "reason": "count-mismatch",
                "q": "해운대 주변 50m",
                "sql": "SELECT COUNT(*) WHERE ST_DWithin(g,g,50)",
            },
            {
                "id": "2",
                "pass": False,
                "reason": "count-mismatch",
                "q": "1990년 이후",
                "sql": "SELECT COUNT(*)",
            },
            {
                "id": "3",
                "pass": False,
                "reason": "count-mismatch",
                "q": "xxx",
                "sql": "",
            },
            {"id": "4", "pass": True, "reason": "ok"},
        ]
    }
    out = decompose_count_mismatches(payload)
    assert out["total_count_mismatch"] == 3
    assert out["concrete_pct"] >= 66.0
