"""속성 테이블 LLM 설명: 넓은 업로드 레이어도 422 없이 통과한다."""

from txt2sql.config import Settings
from txt2sql.map.explain import explain_attributes
from txt2sql.map.router import ExplainRequest


class _BoomClient:
    def chat(self, **_kwargs):
        raise RuntimeError("llm down")


def _wide_columns(n: int = 66) -> list[str]:
    return [f"col_{i:02d}" for i in range(n)]


def test_explain_request_accepts_wide_table() -> None:
    cols = _wide_columns(66)
    body = ExplainRequest.model_validate(
        {
            "kind": "table",
            "title": "활동인구 1인당 시가화용지 활용/미활용 면적_행정동",
            "layer": "adm_urban_area_per_capita",
            "columns": cols,
            "rows": [{c: i for i, c in enumerate(cols)}],
            "total": 205,
            "fields": {c: f"열 {i}" for i, c in enumerate(cols)},
        }
    )
    assert body.kind == "table"
    assert body.layer == "adm_urban_area_per_capita"
    assert body.columns is not None
    assert len(body.columns) == 66
    assert body.rows and "col_00" in body.rows[0]


def test_explain_request_trims_extra_wide_columns() -> None:
    cols = _wide_columns(120)
    body = ExplainRequest.model_validate(
        {
            "kind": "table",
            "layer": "uploaded_spatial",
            "columns": cols,
            "rows": [{c: 1 for c in cols}],
            "total": 10,
        }
    )
    assert body.columns is not None
    assert len(body.columns) == 80
    assert body.rows is not None
    assert len(body.rows[0]) == 80


def test_wide_table_still_explains_without_llm() -> None:
    cols = _wide_columns(66)
    settings = Settings(
        database_url="postgresql://u:p@localhost:5432/gisdb",
        geoserver_url="",
        ollama_host="http://127.0.0.1:9",
    )
    result = explain_attributes(
        settings,
        kind="table",
        title="활동인구 1인당 시가화용지 활용/미활용 면적_행정동",
        columns=cols,
        rows=[{c: i for i, c in enumerate(cols)}],
        total=205,
        fields={c: f"열 {i}" for i, c in enumerate(cols)},
        client=_BoomClient(),
    )
    text = result.get("explanation") or ""
    assert result.get("used_llm") is False
    assert "205건" in text
    assert "시가화용지" in text
