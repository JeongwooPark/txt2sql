from txt2sql.observability import (
    is_unpinned_latest,
    mask_mapping,
    mask_text,
    official_benchmark_allowed,
)
from txt2sql.progress import ProgressTracker


def test_mask_hides_database_url_and_password() -> None:
    text = mask_text("postgresql://user:secretpw@localhost:5432/db password=hunter2")
    assert "secretpw" not in text
    assert "hunter2" not in text
    assert "***" in text
    mapped = mask_mapping({"database_url": "postgresql://u:p@h/db", "sql": "SELECT 1"})
    assert mapped["database_url"] == "***"
    assert mapped["sql"] == "SELECT 1"


def test_progress_trace_is_masked() -> None:
    tracker = ProgressTracker()
    tracker.emit("sql", "compile", sql="postgresql://u:secret@localhost/db")
    detail = tracker.steps[0]["detail"]
    assert "secret" not in str(detail)


def test_official_benchmark_rejects_latest() -> None:
    assert is_unpinned_latest("qwen3:latest") is True
    ok, why = official_benchmark_allowed("qwen3:latest", "mxbai-embed-large")
    assert ok is False
    assert "latest" in why
    ok2, _ = official_benchmark_allowed("qwen3:500a1f", "mxbai-embed-large")
    assert ok2 is True
