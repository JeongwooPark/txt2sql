"""업로드·메타데이터 변경 후 질의 엔진(메타·임베딩·D198·물리 테이블)에 연결한다.

활성 건물·기초구역 테이블 resolve 본체는 txt2sql.dataset_tables.
이 모듈은 DB 디스커버리·동기화와 D198 커버리지를 담당한다.
"""

from __future__ import annotations

import re
from typing import Any

from txt2sql.config import Settings
from txt2sql.data import catalog
from txt2sql.data.names import parse_al_table_name, split_schema_table
from txt2sql.dataset_tables import (
    DEFAULT_BASIC_ZONE_TABLE,
    DEFAULT_BUILDING_TABLE,
    DEFAULT_SIDO_PNU,
    basic_zone_coverage_map,
    building_coverage_map,
    primary_sido_pnu,
    reset_dataset_table_coverage,
    resolve_basic_zone_table,
    resolve_building_table,
    set_basic_zone_coverage,
    set_building_coverage,
    set_primary_sido_pnu,
)
from txt2sql.db import connect
from txt2sql.domain import (
    D198_BY_GU,
    gu_from_pnu_code,
    set_d198_coverage,
)

_BAS_RE = re.compile(r"^TL_KODIS_BAS_(\d{2})_(\d{6,8})$", re.I)

__all__ = [
    "DEFAULT_BASIC_ZONE_TABLE",
    "DEFAULT_BUILDING_TABLE",
    "DEFAULT_SIDO_PNU",
    "basic_zone_coverage_map",
    "building_coverage_map",
    "discover_basic_zone_coverage",
    "discover_building_coverage",
    "discover_d198_coverage",
    "parse_bas_table_name",
    "primary_sido_pnu",
    "refresh_dataset_coverage",
    "register_uploaded_dataset",
    "reset_dataset_table_coverage",
    "resolve_basic_zone_table",
    "resolve_building_table",
    "set_basic_zone_coverage",
    "set_building_coverage",
    "set_primary_sido_pnu",
    "sync_dataset_after_change",
]


def parse_bas_table_name(table: str) -> dict[str, str] | None:
    """TL_KODIS_BAS_26_202507 → 시·도 PNU·갱신일."""
    m = _BAS_RE.match((table or "").strip())
    if not m:
        return None
    return {"pnu_code": m.group(1), "update_date": m.group(2)}


def discover_d198_coverage(settings: Settings) -> dict[str, str]:
    """public 스키마의 AL_D198_* 테이블을 구별로 고른다.

    런타임 커버리지가 본선이다. D198_BY_GU_DEFAULT 는 골드/베이스라인
    스냅샷이 DB에 남아 있을 때만 그 구를 고정하는 **폴백**이다.
    """
    from txt2sql.domain import D198_BY_GU_DEFAULT

    schema = settings.map_schema or "public"
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name LIKE 'AL\\_D198\\_%%' ESCAPE '\\'
                """,
                (schema,),
            )
            names = [str(row["table_name"]) for row in cur.fetchall()]
    name_set = set(names)
    best: dict[str, tuple[str, str]] = {}
    for name in names:
        parsed = parse_al_table_name(name)
        if parsed is None or parsed.get("data_code") != "AL_D198":
            continue
        gu = gu_from_pnu_code(parsed["pnu_code"])
        if not gu:
            continue
        date = parsed["update_date"]
        prev = best.get(gu)
        if prev is None or date > prev[0]:
            best[gu] = (date, name)
    # 폴백: 기본 스냅샷이 아직 DB에 있으면 해당 구는 그 테이블을 유지 (골드 호환).
    for gu, default_table in D198_BY_GU_DEFAULT.items():
        if default_table in name_set:
            parsed = parse_al_table_name(default_table)
            date = parsed["update_date"] if parsed else "00000000"
            best[gu] = (date, default_table)
    return {gu: table for gu, (_date, table) in best.items()}


def discover_building_coverage(settings: Settings) -> dict[str, str]:
    """AL_D010_{시·도PNU}_{YYYYMMDD} → 시·도별 최신(또는 기본) 테이블."""
    schema = settings.map_schema or "public"
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name LIKE 'AL\\_D010\\_%%' ESCAPE '\\'
                """,
                (schema,),
            )
            names = [str(row["table_name"]) for row in cur.fetchall()]
    name_set = set(names)
    best: dict[str, tuple[str, str]] = {}
    for name in names:
        parsed = parse_al_table_name(name)
        if parsed is None or parsed.get("data_code") != "AL_D010":
            continue
        code = str(parsed["pnu_code"] or "").strip()
        if not (code.isdigit() and len(code) >= 2):
            continue
        sido = code[:2]
        date = parsed["update_date"]
        prev = best.get(sido)
        if prev is None or date > prev[0]:
            best[sido] = (date, name)
    if DEFAULT_BUILDING_TABLE in name_set:
        parsed = parse_al_table_name(DEFAULT_BUILDING_TABLE)
        sido = (parsed or {}).get("pnu_code", DEFAULT_SIDO_PNU)[:2]
        date = (parsed or {}).get("update_date", "00000000")
        best[sido] = (date, DEFAULT_BUILDING_TABLE)
    return {sido: table for sido, (_date, table) in best.items()}


def discover_basic_zone_coverage(settings: Settings) -> dict[str, str]:
    """TL_KODIS_BAS_{시·도PNU}_{YYYYMM…} → 시·도별 최신(또는 기본) 테이블."""
    schema = settings.map_schema or "public"
    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                  AND table_type = 'BASE TABLE'
                  AND table_name LIKE 'TL\\_KODIS\\_BAS\\_%%' ESCAPE '\\'
                """,
                (schema,),
            )
            names = [str(row["table_name"]) for row in cur.fetchall()]
    name_set = set(names)
    best: dict[str, tuple[str, str]] = {}
    for name in names:
        parsed = parse_bas_table_name(name)
        if parsed is None:
            continue
        sido = parsed["pnu_code"]
        date = parsed["update_date"]
        prev = best.get(sido)
        if prev is None or date > prev[0]:
            best[sido] = (date, name)
    if DEFAULT_BASIC_ZONE_TABLE in name_set:
        parsed = parse_bas_table_name(DEFAULT_BASIC_ZONE_TABLE)
        sido = (parsed or {}).get("pnu_code", DEFAULT_SIDO_PNU)
        date = (parsed or {}).get("update_date", "000000")
        best[sido] = (date, DEFAULT_BASIC_ZONE_TABLE)
    return {sido: table for sido, (_date, table) in best.items()}


def refresh_dataset_coverage(settings: Settings) -> dict[str, str]:
    """DB 커버리지를 질의 라우팅 맵에 반영. 실패·빈 결과는 기존 맵 유지."""
    try:
        discovered = discover_d198_coverage(settings)
    except Exception:
        discovered = {}
    if discovered:
        set_d198_coverage(discovered)

    primary = None
    try:
        from txt2sql.gazetteer import sido_pnu_prefix

        primary = sido_pnu_prefix(settings.default_sido) or DEFAULT_SIDO_PNU
    except Exception:
        primary = DEFAULT_SIDO_PNU
    set_primary_sido_pnu(primary)

    try:
        buildings = discover_building_coverage(settings)
    except Exception:
        buildings = {}
    if buildings:
        set_building_coverage(buildings, primary_sido=primary)

    try:
        zones = discover_basic_zone_coverage(settings)
    except Exception:
        zones = {}
    if zones:
        set_basic_zone_coverage(zones, primary_sido=primary)

    return dict(D198_BY_GU)


def register_uploaded_dataset(settings: Settings, table_name: str) -> dict[str, Any]:
    """Shapefile 업로드 직후: 메타 채우기 → 스키마 임베딩 → D198 → 지명 사전."""
    return sync_dataset_after_change(settings, table_name, auto_metadata=True)


def sync_dataset_after_change(
    settings: Settings,
    table_name: str | None = None,
    *,
    auto_metadata: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "metadata": False,
        "embedding": False,
        "gazetteer": False,
        "d198_coverage": {},
        "building_table": resolve_building_table(),
        "basic_zone_table": resolve_basic_zone_table(),
        "message": "",
    }
    if table_name:
        if auto_metadata:
            try:
                result["metadata"] = _auto_fill_metadata(settings, table_name)
            except Exception:
                result["metadata"] = False
        try:
            result["embedding"] = _upsert_embedding(settings, table_name)
        except Exception:
            result["embedding"] = False
    result["d198_coverage"] = refresh_dataset_coverage(settings)
    result["building_table"] = resolve_building_table()
    result["basic_zone_table"] = resolve_basic_zone_table()
    try:
        gaz = _refresh_gazetteer(settings)
        result["gazetteer"] = bool(gaz.get("ok"))
        result["gazetteer_unchanged"] = bool(gaz.get("unchanged"))
    except Exception:
        result["gazetteer"] = False
        result["gazetteer_unchanged"] = False
    if table_name:
        short = table_name.split(".")[-1]
        from txt2sql.domain import gu_from_d198_table

        gu = gu_from_d198_table(short)
        if gu:
            result["message"] = (
                f"{gu} 용도별건물({short})이 질의 엔진에 연결되었습니다."
            )
        elif result["embedding"]:
            result["message"] = f"{short} 스키마가 질의 엔진에 연결되었습니다."
        elif result["metadata"]:
            result["message"] = f"{short} 메타데이터가 자동 등록되었습니다."
        if result["gazetteer"] and not result.get("gazetteer_unchanged"):
            extra = "지명 사전을 갱신했습니다."
            result["message"] = (
                f"{result['message']} {extra}".strip()
                if result["message"]
                else extra
            )
    return result


def _auto_fill_metadata(settings: Settings, table_name: str) -> bool:
    parsed = catalog.parse_table_code(settings, table_name)
    if parsed is None:
        return False
    data_code = str(parsed.get("data_code") or "")
    category = ""
    if data_code in {"AL_D198", "AL_D010"}:
        category = "건물"
    elif data_code == "AL_D060":
        category = "산업단지"
    table_meta = {
        "display_name": parsed.get("display_name") or "",
        "description": parsed.get("description") or "",
        "category": category,
    }
    columns = parsed.get("column_metadata") or {}
    catalog.update_table_metadata(settings, table_name, table_meta, columns)
    return True


def _upsert_embedding(settings: Settings, table_name: str) -> bool:
    from txt2sql.schema_retriever import upsert_catalog_embedding

    _, table = split_schema_table(table_name, settings.map_schema or "public")
    with connect(settings.database_url) as conn:
        upsert_catalog_embedding(
            conn,
            table,
            embed_model=settings.ollama_embed_model,
            host=settings.ollama_host,
        )
        conn.commit()
    return True


def _refresh_gazetteer(settings: Settings) -> dict[str, Any]:
    from txt2sql.gazetteer_build import rebuild_gazetteer

    return rebuild_gazetteer(settings)
