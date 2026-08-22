from llm2sql.config import Settings
from llm2sql.semantic_plan.generator import _generate_with_llm, parse_plan_json
from llm2sql.semantic_plan.models import SemanticPlanGenerationError, SemanticQueryPlan


def test_parse_migrates_to_v11() -> None:
    raw = '{"query_kind":"count","entity":"building","filters":[{"field":"usage","operator":"eq","value":"공동주택"}]}'
    plan = parse_plan_json(raw)
    assert plan.version == "1.1"
    assert plan.predicate is not None


def test_repair_once_then_fail(monkeypatch) -> None:
    calls: list[object] = []

    def fake_chat(**kwargs):
        calls.append(kwargs.get("response_format"))
        return "not-json"

    monkeypatch.setattr("llm2sql.semantic_plan.generator.chat", fake_chat)
    settings = Settings(database_url="postgresql://x:x@localhost/x", semantic_plan_max_retries=1)
    try:
        _generate_with_llm("질문", settings, hints={}, ollama_client=object())
    except SemanticPlanGenerationError:
        assert len(calls) == 2
        assert isinstance(calls[0], dict)
        return
    raise AssertionError("expected generation error")


def test_schema_is_pydantic_json_schema() -> None:
    schema = SemanticQueryPlan.model_json_schema()
    assert "properties" in schema
    assert "predicate" in schema["properties"]
