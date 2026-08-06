"""데이터/속성 설명형 질문에 메타데이터로 답변한다."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg.rows import dict_row

# 질문 의도 감지
_META_HINTS = (
    "뭐야",
    "무엇",
    "뭔가",
    "의미",
    "뜻",
    "설명",
    "알려줘",
    "알려 줘",
    "어떤 데이터",
    "무슨 데이터",
    "무슨 테이블",
    "어떤 테이블",
    "어떤 컬럼",
    "무슨 컬럼",
    "속성",
    "필드",
    "컬럼",
    "칼럼",
    "스키마",
    "구조",
    "목록",
    "리스트",
    "소개",
    "개요",
    "메타",
    "정의",
    "무엇인지",
    "어떤 정보",
    "담겨",
    "포함",
)

_DATA_QUERY_HINTS = (
    "몇",
    "건수",
    "개수",
    "채수",
    "상위",
    "조회해",
    "세어",
    "구해",
    "이내",
    "근처",
    "버퍼",
    "교차",
    "안에",
    "내부",
    "넘는",
    "이상",
    "가장 큰",
    "순위",
)

_TABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "AL_D010_26_20250704": (
        "건물",
        "부산 건물",
        "부산건물",
        "gis건물",
        "건물통합",
        "d010",
        "al_d010",
    ),
    "AL_D060_00_20250804": ("산업단지", "단지", "d060", "al_d060"),
    "AL_D198_26260_20250115": ("동래", "동래구", "용도별건물 동래", "d198_26260"),
    "AL_D198_26410_20250115": ("금정", "금정구", "용도별건물 금정", "d198_26410"),
    "BND_ADM_DONG_PG": ("행정동", "행정구역", "동경계", "법정동경계", "bnd"),
    "TL_KODIS_BAS_26_202507": ("기초구역", "기초구역번호", "kodis", "tl_kodis"),
    "pnu_def": ("pnu", "필지", "필지고유번호"),
}

_COL_TOKEN = re.compile(
    r'(?:"(?P<q>[A-Za-z_][A-Za-z0-9_]*)"|\b(?P<u>A\d+|BAS_[A-Z]+|ADM_[A-Z]+|SIG_[A-Z]+|PNU|[A-Z][A-Z0-9_]{1,20})\b)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MetaAnswer:
    intent: str
    answer: str
    tables: list[str]
    rows: list[dict[str, Any]]


_META_COUNT_HINTS = (
    "사용가능",
    "사용 가능",
    "가용",
    "보유 데이터",
    "데이터셋",
    "데이터 개수",
    "테이블 개수",
    "테이블 수",
    "데이터 수",
)


def is_metadata_question(question: str) -> bool:
    """데이터 설명/속성 질의인지 판별 (집계·공간 조회와 구분)."""
    q = question.strip()
    if not q:
        return False
    # 카탈로그 개수: "사용가능한 데이터는 몇개야?"
    if _asks_catalog_count(q):
        return True
    # 명확한 데이터 조회면 메타가 아님
    if any(k in q for k in _DATA_QUERY_HINTS) and not any(
        k in q
        for k in (
            "컬럼",
            "칼럼",
            "속성",
            "필드",
            "의미",
            "뜻",
            "설명",
            "스키마",
            "구조",
            "데이터셋",
            "테이블",
        )
    ):
        return False
    if any(k in q for k in _META_HINTS):
        return True
    # "A4는?", "법정동명이 뭐야" 류
    if _COL_TOKEN.search(q) and any(
        k in q for k in ("뭐", "무엇", "의미", "뜻", "설명", "컬럼", "속성", "필드")
    ):
        return True
    if any(k in q for k in ("테이블 목록", "데이터 목록", "보유 데이터", "어떤 자료")):
        return True
    return False


def _asks_catalog_count(q: str) -> bool:
    if not any(k in q for k in ("몇", "개수", "갯수", "몇개", "몇 개")):
        return False
    if any(k in q for k in _META_COUNT_HINTS):
        return True
    # "데이터는 몇", "테이블은 몇"
    if ("데이터" in q or "테이블" in q or "자료" in q or "데이터셋" in q) and any(
        k in q for k in ("몇", "개수", "갯수")
    ):
        # 실데이터 집계와 구분
        if any(
            k in q
            for k in (
                "건물",
                "기초구역",
                "산업단지",
                "채수",
                "건수",
                "채야",
                "아파트",
                "주택",
                "용도",
            )
        ):
            return False
        return True
    return False


def answer_metadata_question(
    conn: psycopg.Connection,
    question: str,
) -> MetaAnswer | None:
    if not is_metadata_question(question):
        return None

    q = question.strip()

    # 0) 사용 가능 데이터셋 개수
    if _asks_catalog_count(q):
        return _answer_catalog_count(conn)

    tables = _resolve_tables(conn, q)
    col_names = _extract_column_tokens(q)
    display_cols = _match_display_columns(conn, q, tables)

    # 1) 전체 데이터/테이블 목록
    if _asks_catalog(q) and not col_names and not display_cols:
        return _answer_catalog(conn)

    # 2) 특정 컬럼(물리명) 의미
    if col_names:
        return _answer_columns(conn, q, tables, col_names)

    # 3) 한글 표시명으로 컬럼 찾기
    if display_cols:
        return _answer_display_columns(conn, q, display_cols)

    # 4) 테이블 설명 + 주요 속성
    if tables or _asks_table_desc(q):
        if not tables:
            tables = _default_tables(conn, q)
        return _answer_table_overview(conn, q, tables)

    # 5) 키워드만 있는 일반 설명
    if any(k in q for k in ("데이터", "자료", "스키마", "속성", "컬럼", "메타")):
        return _answer_catalog(conn)

    return None


def _asks_catalog(q: str) -> bool:
    return any(
        k in q
        for k in (
            "어떤 데이터",
            "무슨 데이터",
            "어떤 테이블",
            "무슨 테이블",
            "테이블 목록",
            "데이터 목록",
            "보유",
            "전체",
            "목록",
            "리스트",
            "소개",
            "개요",
            "어떤 정보",
            "사용가능",
            "사용 가능",
        )
    )


def _answer_catalog_count(conn: psycopg.Connection) -> MetaAnswer:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT table_name, display_name, category
            FROM table_metadata
            WHERE schema_name = 'public'
            ORDER BY category NULLS LAST, table_name
            """
        )
        rows = list(cur.fetchall())
    n = len(rows)
    names = ", ".join(
        (r["display_name"] or r["table_name"]) for r in rows
    )
    answer = (
        f"현재 사용 가능한 데이터셋은 {n}개입니다.\n"
        f"구성: {names}"
    )
    return MetaAnswer(
        intent="meta_catalog_count",
        answer=answer,
        tables=[r["table_name"] for r in rows],
        rows=rows,
    )


def _asks_table_desc(q: str) -> bool:
    return any(
        k in q
        for k in (
            "테이블",
            "데이터셋",
            "자료",
            "설명",
            "구조",
            "스키마",
            "속성",
            "컬럼",
            "칼럼",
            "필드",
            "뭐야",
            "무엇",
        )
    )


def _extract_column_tokens(q: str) -> list[str]:
    found: list[str] = []
    for m in _COL_TOKEN.finditer(q):
        name = (m.group("q") or m.group("u") or "").strip()
        if not name:
            continue
        # 너무 흔한 영단어 제외
        if name.lower() in {"like", "from", "where", "select", "count", "limit"}:
            continue
        # A숫자 / 알려진 키만 (대문자 유지)
        if re.fullmatch(r"A\d+", name, re.I):
            name = name.upper()
        elif name.isupper() or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            name = name.upper() if name.startswith(("A", "BAS", "ADM", "SIG")) else name
        else:
            continue
        if name not in found:
            found.append(name)
    return found


def _resolve_tables(conn: psycopg.Connection, q: str) -> list[str]:
    q_lower = q.lower()
    hit: list[str] = []

    # 물리 테이블명 직접
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, display_name
            FROM table_metadata
            WHERE schema_name = 'public'
            ORDER BY table_name
            """
        )
        rows = list(cur.fetchall())

    for row in rows:
        table_name = row["table_name"]
        display_name = row["display_name"]
        if table_name.lower() in q_lower or table_name in q:
            hit.append(table_name)
            continue
        if display_name and display_name in q:
            hit.append(table_name)
            continue
        aliases = _TABLE_ALIASES.get(table_name, ())
        for alias in aliases:
            # '건물'만으로는 D010만 잡히므로 아래에서 카테고리 확장
            if alias in ("건물", "부산 건물", "부산건물") and "동래" not in q and "금정" not in q:
                continue
            if alias.lower() in q_lower or alias in q:
                hit.append(table_name)
                break

    # 일반 '건물' 질의 → 건물 카테고리 전체
    if ("건물" in q or "용도별건물" in q) and "동래" not in q and "금정" not in q:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM table_metadata
                WHERE schema_name = 'public' AND category = '건물'
                ORDER BY table_name
                """
            )
            for row in cur.fetchall():
                t = row["table_name"]
                if t not in hit:
                    hit.append(t)

    out: list[str] = []
    for t in hit:
        if t not in out:
            out.append(t)
    return out


def _default_tables(conn: psycopg.Connection, q: str) -> list[str]:
    if "산업" in q:
        return ["AL_D060_00_20250804"]
    if "기초구역" in q:
        return ["TL_KODIS_BAS_26_202507"]
    if "행정" in q or "동경계" in q:
        return ["BND_ADM_DONG_PG"]
    if "동래" in q:
        return ["AL_D198_26260_20250115"]
    if "금정" in q:
        return ["AL_D198_26410_20250115"]
    if "건물" in q or "용도" in q:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM table_metadata
                WHERE schema_name = 'public' AND category = '건물'
                ORDER BY table_name
                """
            )
            rows = [r["table_name"] for r in cur.fetchall()]
        return rows or ["AL_D010_26_20250704"]
    return ["AL_D010_26_20250704"]


def _match_display_columns(
    conn: psycopg.Connection,
    q: str,
    tables: list[str],
) -> list[dict[str, Any]]:
    """질문에 한글 속성명(법정동명, 연면적 등)이 있으면 매칭."""
    with conn.cursor(row_factory=dict_row) as cur:
        if tables:
            cur.execute(
                """
                SELECT table_name, column_name, display_name, description, data_type, unit
                FROM column_metadata
                WHERE schema_name = 'public'
                  AND table_name = ANY(%s)
                  AND display_name IS NOT NULL
                  AND display_name <> ''
                """,
                (tables,),
            )
        else:
            cur.execute(
                """
                SELECT table_name, column_name, display_name, description, data_type, unit
                FROM column_metadata
                WHERE schema_name = 'public'
                  AND display_name IS NOT NULL
                  AND display_name <> ''
                """
            )
        rows = list(cur.fetchall())

    hits: list[dict[str, Any]] = []
    # 긴 표시명 우선
    rows.sort(key=lambda r: len(r["display_name"] or ""), reverse=True)
    for row in rows:
        name = row["display_name"]
        if name and len(name) >= 2 and name in q:
            hits.append(row)
    return hits


def _answer_catalog(conn: psycopg.Connection) -> MetaAnswer:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT table_name, display_name, category, description
            FROM table_metadata
            WHERE schema_name = 'public'
            ORDER BY category NULLS LAST, table_name
            """
        )
        rows = list(cur.fetchall())

    lines = ["현재 조회 가능한 데이터셋은 다음과 같습니다."]
    for r in rows:
        disp = r["display_name"] or r["table_name"]
        cat = f" [{r['category']}]" if r.get("category") else ""
        desc = _short(r.get("description"), 100)
        extra = f" — {desc}" if desc else ""
        lines.append(f"- {disp} (`{r['table_name']}`){cat}{extra}")
    lines.append(
        "특정 테이블이나 컬럼(예: A4, 법정동명)의 의미를 물으시면 속성 기준으로 설명합니다."
    )
    return MetaAnswer(
        intent="meta_catalog",
        answer="\n".join(lines),
        tables=[r["table_name"] for r in rows],
        rows=rows,
    )


def _answer_table_overview(
    conn: psycopg.Connection,
    question: str,
    tables: list[str],
) -> MetaAnswer:
    parts: list[str] = []
    all_rows: list[dict[str, Any]] = []
    used: list[str] = []

    for table in tables[:3]:
        meta = _load_table(conn, table)
        if not meta:
            continue
        used.append(table)
        disp = meta["display_name"] or table
        cat = meta.get("category") or "미분류"
        desc = _short(meta.get("description"), 200) or "상세 설명은 메타데이터에 없습니다."
        cols = _load_columns(conn, table)
        all_rows.extend(cols)

        parts.append(f"「{disp}」(`{table}`)는 분류상 {cat} 데이터입니다.")
        parts.append(f"설명: {desc}")
        if cols:
            parts.append("주요 속성은 다음과 같습니다.")
            for c in cols[:12]:
                parts.append(_format_column_line(c))
            if len(cols) > 12:
                parts.append(f"… 외 {len(cols) - 12}개 컬럼이 더 있습니다.")
        parts.append("")

    if not parts:
        return MetaAnswer(
            intent="meta_table",
            answer="요청하신 테이블에 대한 메타데이터를 찾지 못했습니다.",
            tables=[],
            rows=[],
        )

    answer = "\n".join(parts).strip()
    if "속성" in question or "컬럼" in question or "칼럼" in question or "필드" in question:
        # already included
        pass
    return MetaAnswer(
        intent="meta_table",
        answer=answer,
        tables=used,
        rows=all_rows,
    )


def _answer_columns(
    conn: psycopg.Connection,
    question: str,
    tables: list[str],
    col_names: list[str],
) -> MetaAnswer:
    with conn.cursor(row_factory=dict_row) as cur:
        if tables:
            cur.execute(
                """
                SELECT table_name, column_name, display_name, description, data_type, unit
                FROM column_metadata
                WHERE schema_name = 'public'
                  AND table_name = ANY(%s)
                  AND upper(column_name) = ANY(%s)
                ORDER BY table_name, column_name
                """,
                (tables, [c.upper() for c in col_names]),
            )
        else:
            cur.execute(
                """
                SELECT table_name, column_name, display_name, description, data_type, unit
                FROM column_metadata
                WHERE schema_name = 'public'
                  AND upper(column_name) = ANY(%s)
                ORDER BY table_name, column_name
                """,
                ([c.upper() for c in col_names],),
            )
        rows = list(cur.fetchall())

    if not rows:
        names = ", ".join(col_names)
        hint = ""
        if tables:
            hint = f" (검색 테이블: {', '.join(tables)})"
        return MetaAnswer(
            intent="meta_column",
            answer=f"컬럼 {names}에 대한 속성 설명을 메타데이터에서 찾지 못했습니다.{hint}",
            tables=tables,
            rows=[],
        )

    # 동일 물리명이 테이블마다 다를 수 있음 → 모두 안내
    lines = [f"질문하신 속성({', '.join(col_names)})의 의미는 다음과 같습니다."]
    for r in rows:
        tmeta = _load_table(conn, r["table_name"])
        tdisp = (tmeta or {}).get("display_name") or r["table_name"]
        lines.append(f"[{tdisp} / `{r['table_name']}`]")
        lines.append(_format_column_line(r, detailed=True))
    if len({r["table_name"] for r in rows}) > 1:
        lines.append(
            "참고: 같은 컬럼명(예: A4)이라도 테이블마다 의미가 다를 수 있습니다."
        )
    return MetaAnswer(
        intent="meta_column",
        answer="\n".join(lines),
        tables=sorted({r["table_name"] for r in rows}),
        rows=rows,
    )


def _answer_display_columns(
    conn: psycopg.Connection,
    question: str,
    hits: list[dict[str, Any]],
) -> MetaAnswer:
    # 동일 display_name 그룹
    lines = ["질문하신 속성에 대한 설명입니다."]
    seen: set[tuple[str, str]] = set()
    tables: list[str] = []
    for r in hits:
        key = (r["table_name"], r["column_name"])
        if key in seen:
            continue
        seen.add(key)
        tables.append(r["table_name"])
        tmeta = _load_table(conn, r["table_name"])
        tdisp = (tmeta or {}).get("display_name") or r["table_name"]
        lines.append(f"[{tdisp} / `{r['table_name']}`]")
        lines.append(_format_column_line(r, detailed=True))
    return MetaAnswer(
        intent="meta_column_display",
        answer="\n".join(lines),
        tables=sorted(set(tables)),
        rows=hits,
    )


def _load_table(conn: psycopg.Connection, table: str) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT table_name, display_name, category, description
            FROM table_metadata
            WHERE schema_name = 'public' AND table_name = %s
            """,
            (table,),
        )
        return cur.fetchone()


def _load_columns(conn: psycopg.Connection, table: str) -> list[dict[str, Any]]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT table_name, column_name, display_name, description, data_type, unit
            FROM column_metadata
            WHERE schema_name = 'public' AND table_name = %s
            ORDER BY
              CASE
                WHEN column_name ~ '^A[0-9]+$' THEN 1
                WHEN column_name = 'geometry' THEN 3
                ELSE 2
              END,
              CASE
                WHEN column_name ~ '^A[0-9]+$'
                  THEN substring(column_name from 2)::int
                ELSE 0
              END,
              column_name
            """,
            (table,),
        )
        return list(cur.fetchall())


def _format_column_line(row: dict[str, Any], *, detailed: bool = False) -> str:
    col = row["column_name"]
    disp = row.get("display_name") or "(표시명 없음)"
    dtype = row.get("data_type") or ""
    unit = row.get("unit")
    unit_s = f", 단위: {unit}" if unit else ""
    desc = _clean_desc(row.get("description"))
    base = f"- `{col}` → {disp}"
    if dtype:
        base += f" ({dtype}{unit_s})"
    elif unit_s:
        base += f" ({unit_s.lstrip(', ')})"
    if detailed and desc:
        base += f"\n  {desc}"
    elif desc and not detailed:
        short = _short(desc, 70)
        if short:
            base += f" — {short}"
    return base


def _clean_desc(text: str | None) -> str:
    if not text:
        return ""
    # 너무 긴 코드표는 앞부분만
    t = re.sub(r"\s+", " ", text).strip()
    if "보조 설명:" in t:
        main, rest = t.split("보조 설명:", 1)
        main = main.strip(" ,;")
        rest = rest.strip()
        if len(rest) > 120:
            rest = rest[:117] + "…"
        if main:
            return f"{main} (코드표: {rest})" if rest else main
        return f"코드표: {rest}" if rest else ""
    return t


def _short(text: str | None, n: int) -> str:
    if not text:
        return ""
    t = re.sub(r"\s+", " ", text).strip()
    if "보조 설명:" in t:
        t = t.split("보조 설명:", 1)[0].strip(" ,;")
    if len(t) > n:
        return t[: n - 1] + "…"
    return t
