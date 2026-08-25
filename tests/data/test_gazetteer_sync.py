"""지명 사전 생성·업로드/메타데이터 훅."""

from __future__ import annotations

from txt2sql.config import Settings
from txt2sql.data.coverage import sync_dataset_after_change
from txt2sql.gazetteer import invalidate_gazetteer, load_gazetteer
from txt2sql.gazetteer_build import names_from_rows, write_gazetteer_payload


def test_names_from_rows_skips_false_tails() -> None:
    rows = [
        {"name": "금정구"},
        {"name": "공동"},
        {"name": "구서1동"},
        {"name": "금정구"},
        {"name": "부산직할시"},
        {"name": "가"},
    ]
    assert names_from_rows(rows, "name") == ["금정구", "구서1동"]


def test_invalidate_gazetteer_clears_cache() -> None:
    first = load_gazetteer()
    second = load_gazetteer()
    assert first is second
    invalidate_gazetteer()
    third = load_gazetteer()
    assert third is not first
    assert "금정구" in third.sigungu


def test_sync_rebuilds_gazetteer_on_upload_and_metadata(monkeypatch) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        "txt2sql.data.coverage._upsert_embedding", lambda *a, **k: True
    )
    monkeypatch.setattr(
        "txt2sql.data.coverage.refresh_dataset_coverage", lambda s: {}
    )
    monkeypatch.setattr(
        "txt2sql.data.coverage._auto_fill_metadata", lambda *a, **k: True
    )

    def fake_rebuild(settings: Settings, **kwargs):
        calls.append("rebuild")
        return {"ok": True, "counts": {"sido": 1}}

    monkeypatch.setattr(
        "txt2sql.gazetteer_build.rebuild_gazetteer", fake_rebuild
    )

    settings = Settings(database_url="postgresql://x:x@127.0.0.1/x")
    uploaded = sync_dataset_after_change(
        settings, "AL_D198_26110_20260715", auto_metadata=True
    )
    saved = sync_dataset_after_change(
        settings, "adm_urban_area_per_capita", auto_metadata=False
    )
    assert uploaded["gazetteer"] is True
    assert saved["gazetteer"] is True
    assert calls == ["rebuild", "rebuild"]
    assert "지명 사전" in uploaded["message"]


def test_write_payload_invalidates(tmp_path, monkeypatch) -> None:
    load_gazetteer()
    path = tmp_path / "gazetteer_data.json"
    write_gazetteer_payload(
        {
            "sido": ["서울특별시"],
            "sido_aliases": [],
            "sigungu": ["종로구"],
            "sigungu_sido": {},
            "legal_dong": [],
            "admin_dong": [],
            "admin_dong_prefixes": {},
        },
        path,
    )
    assert path.is_file()
    # 캐시만 비우고, 패키지 JSON은 덮지 않는다.
    assert "금정구" in load_gazetteer().sigungu
