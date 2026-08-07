from __future__ import annotations

import hashlib
import re
from typing import Any

import ollama
import psycopg

from llm2sql.semantic_meta import (
    SAMPLE_COLUMNS,
    column_synonyms,
    format_synonyms,
    table_synonyms,
)


# 행정구역/구·동 관련 질문에 강제 포함할 테이블
_ADMIN_HINT_TABLES = (
    "BND_ADM_DONG_PG",
    "TL_KODIS_BAS_26_202507",
    "pnu_def",
)

_ADMIN_KEYWORDS = (
    "구",
    "동",
    "행정",
    "법정동",
    "시군구",
    "기초구역",
    "부산",
    "해운대",
    "금정",
    "동래",
    "연제",
    "수영",
    "사하",
    "사상",
    "기장",
    "중구",
    "서구",
    "동구",
    "남구",
    "북구",
    "영도",
    "진구",
    "강서",
)


def _short_desc(text: str | None, max_len: int = 80) -> str:
    if not text:
        return ""
    # 코드 전체 사전(보조 설명 장문) 제거
    cut = re.split(r",\s*보조 설명:", text, maxsplit=1)[0]
    cut = re.sub(r"\s+", " ", cut).strip()
    if len(cut) > max_len:
        return cut[: max_len - 1] + "…"
    return cut


def embed_text(
    text: str,
    *,
    model: str,
    host: str | None = None,
    client: Any | None = None,
) -> list[float]:
    # mxbai-embed-large 등 임베딩 모델은 컨텍스트가 짧음(≈512 tokens)
    clipped = text.strip()
    if len(clipped) > 400:
        clipped = clipped[:400]
    if client is None:
        if not host:
            raise ValueError("host 또는 client가 필요합니다.")
        client = ollama.Client(host=host)
    response = client.embeddings(model=model, prompt=clipped)
    embedding = response["embedding"] if isinstance(response, dict) else response.embedding
    return list(embedding)


def vector_literal(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def _fqname_to_table(fqname: str) -> str | None:
    # public.AL_D010_... or just table
    parts = fqname.split(".")
    name = parts[-1] if parts else fqname
    if name in {
        "geometry_columns",
        "geography_columns",
        "spatial_ref_sys",
        "col_def",
        "column_metadata",
        "table_metadata",
        "llm_schema_catalog",
        "temp_data_sessions",
    }:
        return None
    if name.startswith("v_") or name.startswith("v__"):
        return None
    return name


# RAG 대상: mxbai로 재임베딩하는 공간/참조 테이블만 검색
_SEARCHABLE_FQNAMES = (
    "public.AL_D010_26_20250704",
    "public.AL_D060_00_20250804",
    "public.AL_D198_26260_20250115",
    "public.AL_D198_26410_20250115",
    "public.BND_ADM_DONG_PG",
    "public.TL_KODIS_BAS_26_202507",
    "public.pnu_def",
)


def search_catalog_tables(
    conn: psycopg.Connection,
    question: str,
    *,
    embed_model: str,
    host: str | None = None,
    client: Any | None = None,
    top_k: int = 5,
) -> list[str]:
    embedding = embed_text(
        question, model=embed_model, host=host, client=client
    )
    lit = vector_literal(embedding)
    rows = conn.execute(
        """
        SELECT fqname, kind
        FROM llm_schema_catalog
        WHERE embedding IS NOT NULL
          AND fqname = ANY(%s)
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """,
        (list(_SEARCHABLE_FQNAMES), lit, top_k),
    ).fetchall()

    tables: list[str] = []
    for row in rows:
        name = _fqname_to_table(row["fqname"])
        if name and name not in tables:
            tables.append(name)
    return tables


def apply_admin_boost(question: str, tables: list[str]) -> list[str]:
    if not any(kw in question for kw in _ADMIN_KEYWORDS):
        return tables
    out = list(tables)
    for t in _ADMIN_HINT_TABLES:
        if t not in out:
            out.append(t)
    return out


def _fetch_pk_columns(conn: psycopg.Connection, table_name: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = %s
          AND tc.constraint_type = 'PRIMARY KEY'
        ORDER BY kcu.ordinal_position
        """,
        (table_name,),
    ).fetchall()
    return [r["column_name"] for r in rows]


def _fetch_fk_lines(conn: psycopg.Connection, table_name: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT
            kcu.column_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.table_schema = 'public'
          AND tc.table_name = %s
          AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY kcu.ordinal_position
        """,
        (table_name,),
    ).fetchall()
    lines: list[str] = []
    for r in rows:
        lines.append(
            f'  FK "{r["column_name"]}" -> '
            f'"{r["foreign_table"]}"."{r["foreign_column"]}"'
        )
    return lines


def _fetch_sample_values(
    conn: psycopg.Connection,
    table_name: str,
    column_name: str,
    *,
    limit: int = 4,
) -> list[str]:
    """대표 텍스트 컬럼의 DISTINCT 샘플 (실패 시 빈 목록)."""
    try:
        rows = conn.execute(
            f"""
            SELECT DISTINCT "{column_name}" AS v
            FROM "{table_name}"
            WHERE "{column_name}" IS NOT NULL
              AND btrim("{column_name}"::text) <> ''
            LIMIT %s
            """,
            (limit,),
        ).fetchall()
        out: list[str] = []
        for r in rows:
            val = r.get("v")
            if val is None:
                continue
            text = str(val).strip()
            if text and text not in out:
                out.append(text[:40])
        return out
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []


def build_compact_schema(
    conn: psycopg.Connection,
    table_names: list[str],
    *,
    question: str = "",
    include_sample_values: bool = True,
) -> str:
    """M-Schema 스타일 compact schema (설명·동의어·PK/FK·샘플값)."""
    if not table_names:
        return "(관련 테이블을 찾지 못했습니다)"

    parts: list[str] = []
    for table_name in table_names:
        meta = conn.execute(
            """
            SELECT display_name, description, category
            FROM table_metadata
            WHERE schema_name = 'public' AND table_name = %s
            """,
            (table_name,),
        ).fetchone()

        geom = conn.execute(
            """
            SELECT type, srid, f_geometry_column
            FROM geometry_columns
            WHERE f_table_schema = 'public' AND f_table_name = %s
            """,
            (table_name,),
        ).fetchone()

        cols = conn.execute(
            """
            SELECT
                c.column_name,
                c.udt_name,
                cm.display_name,
                cm.description,
                cm.unit
            FROM information_schema.columns c
            LEFT JOIN column_metadata cm
              ON cm.schema_name = c.table_schema
             AND cm.table_name = c.table_name
             AND cm.column_name = c.column_name
            WHERE c.table_schema = 'public' AND c.table_name = %s
            ORDER BY c.ordinal_position
            """,
            (table_name,),
        ).fetchall()

        pk_cols = set(_fetch_pk_columns(conn, table_name))
        fk_lines = _fetch_fk_lines(conn, table_name)
        sample_cols = set(SAMPLE_COLUMNS.get(table_name, ()))
        samples: dict[str, list[str]] = {}
        if include_sample_values:
            for col_name in SAMPLE_COLUMNS.get(table_name, ()):
                samples[col_name] = _fetch_sample_values(conn, table_name, col_name)

        header = f'# Table: "{table_name}"'
        if meta:
            header += (
                f"\n  [display_name={meta['display_name']}; "
                "DO NOT use display_name as SQL table id]"
            )
            if meta.get("category"):
                header += f"\n  [category={meta['category']}]"
            if meta.get("description"):
                header += f"\n  [desc] {_short_desc(meta['description'], 100)}"
        syn_t = format_synonyms(table_synonyms(table_name))
        if syn_t:
            header += f"\n  [synonyms] {syn_t}"
        if pk_cols:
            header += "\n  [primary_key] " + ", ".join(f'"{c}"' for c in pk_cols)
        if geom:
            header += (
                f'\n  [geometry] "{geom["f_geometry_column"]}" '
                f"{geom['type']}, SRID={geom['srid']}"
            )

        col_lines: list[str] = []
        for col in cols:
            if col["udt_name"] in ("geometry", "geography"):
                continue
            cname = col["column_name"]
            flags: list[str] = []
            if cname in pk_cols:
                flags.append("PK")
            line = f'  - "{cname}" ({col["udt_name"]}'
            if flags:
                line += ", " + ",".join(flags)
            line += ")"
            if col.get("display_name"):
                line += f" | {col['display_name']}"
            extras: list[str] = []
            short = _short_desc(col.get("description"))
            if short:
                extras.append(short)
            if col.get("unit"):
                extras.append(f"unit={col['unit']}")
            syn_c = format_synonyms(column_synonyms(table_name, cname))
            if syn_c:
                extras.append(f"synonyms={syn_c}")
            if cname in sample_cols and samples.get(cname):
                shown = ", ".join(samples[cname][:4])
                extras.append(f"samples=[{shown}]")
            if extras:
                line += " | " + "; ".join(extras)
            col_lines.append(line)

        block = header + "\n  [columns]\n" + "\n".join(col_lines)
        if fk_lines:
            block += "\n" + "\n".join(fk_lines)
        parts.append(block)

    tips = (
        "\n\nRules for columns:\n"
        "- Prefer Korean name columns for filters (e.g. \"A9\" 건축물용도명 over \"A8\" code).\n"
        "- Quote all identifiers. Do not SELECT geometry unless asked. Never SELECT *.\n"
        "- Always include LIMIT.\n"
        "- District/dong name filters: use LIKE '%이름%'.\n"
        "- Use synonyms above for schema linking (e.g. 인구/구/동 → matching columns).\n"
    )
    spatial_intent = any(
        k in question
        for k in ("안에", "내부", "속하는", "교차", "버퍼", "거리", "근처", "이내")
    )
    if spatial_intent:
        tips += (
            "- SPATIAL INTENT DETECTED: use ST_Intersects with "
            '"BND_ADM_DONG_PG" or "TL_KODIS_BAS_26_202507"; do not rely on attribute-only filters.\n'
        )
    return "\n\n".join(parts) + tips


def retrieve_schema(
    conn: psycopg.Connection,
    question: str,
    *,
    embed_model: str,
    host: str | None = None,
    client: Any | None = None,
    top_k: int = 5,
    include_sample_values: bool = True,
) -> dict[str, Any]:
    tables = search_catalog_tables(
        conn,
        question,
        embed_model=embed_model,
        host=host,
        client=client,
        top_k=top_k,
    )
    tables = apply_admin_boost(question, tables)

    # 건물 속성 질의: 기본은 AL_D010. D198은 동래/금정·건축년수·주요용도명만.
    building_hints = ("건물", "건축", "연면적", "용도", "공동주택", "아파트", "주택")
    needs_d198 = (
        "동래" in question
        or "금정" in question
        or "주요용도" in question
        or any(
            k in question
            for k in (
                "건축년",
                "준공",
                "사용승인",
                "허가일",
                "지어진",
                "경과년",
            )
        )
    )
    if any(h in question for h in building_hints):
        if "AL_D010_26_20250704" not in tables:
            tables.append("AL_D010_26_20250704")
        if needs_d198:
            for t in (
                "AL_D198_26260_20250115",
                "AL_D198_26410_20250115",
            ):
                if t not in tables:
                    tables.append(t)
        else:
            # 연제·사하 등 타 구 질의에서 D198로 빠지지 않게 제거
            tables = [t for t in tables if not t.startswith("AL_D198_")]

    if "산업단지" in question:
        if "AL_D060_00_20250804" not in tables:
            tables.append("AL_D060_00_20250804")
        # 산업단지 전용 질의에서는 건물 테이블을 스키마에서 제외해 혼동 방지
        if "건물" not in question:
            tables = [
                t
                for t in tables
                if not t.startswith("AL_D010") and not t.startswith("AL_D198")
            ]
            if "AL_D060_00_20250804" not in tables:
                tables.insert(0, "AL_D060_00_20250804")

    # 구별 전용 테이블 우선 + 스키마 힌트
    extra_tips = ""
    if "금정" in question:
        if "AL_D198_26410_20250115" in tables:
            tables = ["AL_D198_26410_20250115"] + [
                t for t in tables if t != "AL_D198_26410_20250115"
            ]
        else:
            tables.insert(0, "AL_D198_26410_20250115")
        # 동래구 테이블은 금정 질의에서 제외
        tables = [t for t in tables if t != "AL_D198_26260_20250115"]
        extra_tips = (
            '\n- For 금정구 use table "AL_D198_26410_20250115" '
            '(연면적 column "A19") or "AL_D010_26_20250704" ("A14").\n'
        )
        if "주요용도" in question:
            extra_tips += (
                '\n- "주요용도명" for 금정구 MUST use '
                '"AL_D198_26410_20250115"."A25" (not AL_D010 "A9").\n'
            )
            # 주요용도명 전용: D010 제외해 A9 혼동 방지
            tables = [t for t in tables if not t.startswith("AL_D010")]
    if "동래" in question:
        if "AL_D198_26260_20250115" not in tables:
            tables.insert(0, "AL_D198_26260_20250115")
        if "주요용도" in question:
            extra_tips += (
                '\n- "주요용도명" for 동래구 MUST use '
                '"AL_D198_26260_20250115"."A25" (not AL_D010 "A9").\n'
            )
            tables = [t for t in tables if not t.startswith("AL_D010")]
            tables = [t for t in tables if t != "AL_D198_26410_20250115"]

    schema_text = (
        build_compact_schema(
            conn,
            tables,
            question=question,
            include_sample_values=include_sample_values,
        )
        + extra_tips
    )
    return {"tables": tables, "schema_text": schema_text}


def build_catalog_summary(
    conn: psycopg.Connection,
    table_name: str,
) -> tuple[str, str]:
    """llm_schema_catalog용 summary / summary_kw 생성."""
    meta = conn.execute(
        """
        SELECT display_name, description, category
        FROM table_metadata
        WHERE table_name = %s
        """,
        (table_name,),
    ).fetchone()
    geom = conn.execute(
        """
        SELECT type, srid, f_geometry_column
        FROM geometry_columns
        WHERE f_table_schema = 'public' AND f_table_name = %s
        """,
        (table_name,),
    ).fetchone()
    cols = conn.execute(
        """
        SELECT c.column_name, c.udt_name, cm.display_name
        FROM information_schema.columns c
        LEFT JOIN column_metadata cm
          ON cm.table_name = c.table_name AND cm.column_name = c.column_name
        WHERE c.table_schema = 'public' AND c.table_name = %s
        ORDER BY c.ordinal_position
        """,
        (table_name,),
    ).fetchall()
    cnt = conn.execute(
        """
        SELECT reltuples::bigint AS n
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relname = %s
        """,
        (table_name,),
    ).fetchone()

    display = (meta or {}).get("display_name") or table_name
    category = (meta or {}).get("category") or ""
    description = _short_desc((meta or {}).get("description"), 120)

    lines = [
        f"[테이블] public.{table_name}",
        f"- 표시명:{display} | 분류:{category} | {description}",
    ]
    if geom:
        lines.append(
            f"- geom={geom['type']}, SRID={geom['srid']}, col={geom['f_geometry_column']}"
        )
    if cnt:
        lines.append(f"- rows≈{cnt['n']}")

    # 핵심 한글 컬럼명만 (임베딩 컨텍스트 절약)
    labels = [
        col["display_name"]
        for col in cols
        if col.get("display_name") and col["udt_name"] not in ("geometry", "geography")
    ][:12]
    if labels:
        lines.append("- 주요컬럼: " + ", ".join(labels))

    summary = "\n".join(lines)
    kw_parts = [table_name, display, category, *labels[:8]]
    summary_kw = " ".join(p for p in kw_parts if p)[:200]
    return summary, summary_kw


def upsert_catalog_embedding(
    conn: psycopg.Connection,
    table_name: str,
    *,
    embed_model: str,
    host: str,
) -> None:
    summary, summary_kw = build_catalog_summary(conn, table_name)
    text = f"{summary}\n{summary_kw}"
    emb = embed_text(text, model=embed_model, host=host)
    lit = vector_literal(emb)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    fqname = f"public.{table_name}"
    conn.execute(
        """
        INSERT INTO llm_schema_catalog (fqname, kind, summary, summary_kw, embedding, summary_hash, updated_at)
        VALUES (%s, 'table', %s, %s, %s::vector, %s, NOW())
        ON CONFLICT (fqname) DO UPDATE SET
          kind = EXCLUDED.kind,
          summary = EXCLUDED.summary,
          summary_kw = EXCLUDED.summary_kw,
          embedding = EXCLUDED.embedding,
          summary_hash = EXCLUDED.summary_hash,
          updated_at = NOW()
        """,
        (fqname, summary, summary_kw, lit, digest),
    )
