from pathlib import Path

from llm2sql.evaluation.import_smoke import compound30_cases, nl100_cases
from llm2sql.evaluation.jsonl import dump_jsonl, load_jsonl
from llm2sql.evaluation.schema import GoldPlanCase


def test_gold_schema_roundtrip(tmp_path: Path) -> None:
    case = GoldPlanCase(
        id="X1",
        question="해운대구 건물 수",
        status="draft",
        split="candidate",
        source="unit",
    )
    path = tmp_path / "g.jsonl"
    dump_jsonl(path, [case])
    loaded = load_jsonl(path)
    assert loaded[0].id == "X1"
    assert loaded[0].status == "draft"


def test_smoke_import_is_draft_not_verified() -> None:
    c30 = compound30_cases()
    n100 = nl100_cases()
    assert len(c30) == 30
    assert len(n100) == 100
    assert all(item.status == "draft" for item in c30 + n100)
    assert all(item.gold_plan is None for item in c30)
    assert all("not copied" in item.verification or "unverified" in item.verification for item in c30)
