"""동적 few-shot example store + 임베딩 검색."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any

from llm2sql.schema_retriever import embed_text


@dataclass(frozen=True)
class SqlExample:
    question: str
    sql: str
    tables: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


# 정적 seed 예제 (임베딩 검색 대상)
EXAMPLE_BANK: tuple[SqlExample, ...] = (
    SqlExample(
        question="해운대구 연면적 상위 5개 건물의 법정동명, 용도, 연면적을 보여줘",
        sql=(
            'SELECT "A4", "A9", "A14"\n'
            'FROM "AL_D010_26_20250704"\n'
            "WHERE \"A4\" LIKE '%해운대구%'\n"
            'ORDER BY "A14" DESC NULLS LAST\n'
            "LIMIT 5;"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("rank", "area", "gu"),
    ),
    SqlExample(
        question="수영구 기초구역 면적이 큰 순으로 10개",
        sql=(
            'SELECT "BAS_ID", "SIG_KOR_NM", "BAS_AR"\n'
            'FROM "TL_KODIS_BAS_26_202507"\n'
            "WHERE \"SIG_KOR_NM\" = '수영구'\n"
            'ORDER BY "BAS_AR" DESC NULLS LAST\n'
            "LIMIT 10;"
        ),
        tables=("TL_KODIS_BAS_26_202507",),
        tags=("bas", "rank"),
    ),
    SqlExample(
        question="좌표(129.08, 35.16)에서 500미터 이내 건물 건수",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704" b\n'
            "WHERE ST_DWithin(\n"
            "  b.geometry::geography,\n"
            "  ST_SetSRID(ST_MakePoint(129.08, 35.16), 4326)::geography,\n"
            "  500\n"
            ");"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("buffer", "spatial", "count"),
    ),
    SqlExample(
        question="구서동 주변 100m안에 있는 건물은?",
        sql=(
            'SELECT b."A0", b."A4", b."A5", b."A9", b."A12", b."A14", b."A16", '
            'b."A24", b."A26"\n'
            'FROM "AL_D010_26_20250704" b\n'
            "CROSS JOIN (\n"
            "  SELECT ST_Union(d.geometry) AS geom\n"
            '  FROM "BND_ADM_DONG_PG" d\n'
            "  WHERE (d.\"ADM_NM\" = '구서동' OR d.\"ADM_NM\" ~ '^구서[0-9]+동$')\n"
            ") z\n"
            "WHERE z.geom IS NOT NULL\n"
            "  AND b.geometry && ST_Expand(z.geom, 0.0015)\n"
            "  AND ST_DWithin(b.geometry::geography, z.geom::geography, 100)\n"
            "ORDER BY ST_Distance(b.geometry::geography, z.geom::geography),\n"
            '  b."A14" DESC NULLS LAST\n'
            "LIMIT 50;"
        ),
        tables=("AL_D010_26_20250704", "BND_ADM_DONG_PG"),
        tags=("buffer", "spatial", "dong", "list"),
    ),
    SqlExample(
        question="산업단지와 교차하는 해운대구 기초구역 목록",
        sql=(
            'SELECT DISTINCT t."BAS_ID", t."SIG_KOR_NM", t."BAS_AR"\n'
            'FROM "TL_KODIS_BAS_26_202507" t\n'
            'JOIN "AL_D060_00_20250804" i\n'
            "  ON ST_Intersects(t.geometry, i.geometry)\n"
            "WHERE t.\"SIG_KOR_NM\" = '해운대구'\n"
            "LIMIT 100;"
        ),
        tables=("TL_KODIS_BAS_26_202507", "AL_D060_00_20250804"),
        tags=("spatial", "industrial", "bas"),
    ),
    SqlExample(
        question="사하구 단독주택은 몇 채야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704"\n'
            "WHERE \"A4\" LIKE '%사하구%' AND \"A9\" = '단독주택';"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("count", "usage", "gu"),
    ),
    SqlExample(
        question="우1동 안에 있는 건물 건수는?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704" b\n'
            'JOIN "BND_ADM_DONG_PG" d ON ST_Intersects(b.geometry, d.geometry)\n'
            "WHERE d.\"ADM_NM\" LIKE '%우1동%';"
        ),
        tables=("AL_D010_26_20250704", "BND_ADM_DONG_PG"),
        tags=("spatial", "dong", "count"),
    ),
    SqlExample(
        question="구서1동과 교차하는 기초구역은 몇 개야?",
        sql=(
            'SELECT COUNT(DISTINCT t."BAS_ID") AS cnt\n'
            'FROM "TL_KODIS_BAS_26_202507" t\n'
            'JOIN "BND_ADM_DONG_PG" d\n'
            "  ON t.geometry && d.geometry AND ST_Intersects(t.geometry, d.geometry)\n"
            "WHERE d.\"ADM_NM\" = '구서1동' AND d.\"ADM_CD\" LIKE '21%';"
        ),
        tables=("TL_KODIS_BAS_26_202507", "BND_ADM_DONG_PG"),
        tags=("spatial", "bas", "dong", "count"),
    ),
    SqlExample(
        question="해운대구에서 건물 높이가 50미터 이상인 건물은 몇 개야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704"\n'
            "WHERE \"A4\" LIKE '%해운대구%' AND \"A16\" >= 50;"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("count", "height", "gu"),
    ),
    SqlExample(
        question="사하구 기초구역은 몇 개야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "TL_KODIS_BAS_26_202507"\n'
            "WHERE \"SIG_KOR_NM\" = '사하구';"
        ),
        tables=("TL_KODIS_BAS_26_202507",),
        tags=("bas", "count"),
    ),
    SqlExample(
        question="산업단지 중 원천시도시군구코드가 26으로 시작하는 것은 몇 개야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D060_00_20250804"\n'
            "WHERE \"A4\" LIKE '26%';"
        ),
        tables=("AL_D060_00_20250804",),
        tags=("industrial", "count"),
    ),
    SqlExample(
        question="금정구에서 지상층이 10층 이상인 건물은 몇 개야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704"\n'
            "WHERE \"A4\" LIKE '%금정구%' AND \"A26\" >= 10;"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("floors", "count", "gu"),
    ),
    SqlExample(
        question="동래구 건물의 주요용도명 종류는 몇 가지야?",
        sql=(
            'SELECT COUNT(DISTINCT "A25") AS cnt\n'
            'FROM "AL_D198_26260_20250115"\n'
            "WHERE \"A4\" LIKE '%동래구%' AND \"A25\" IS NOT NULL;"
        ),
        tables=("AL_D198_26260_20250115",),
        tags=("usage", "distinct", "d198", "dongrae"),
    ),
    SqlExample(
        question="연제구 공동주택은 몇 채야?",
        sql=(
            "SELECT COUNT(*) AS cnt\n"
            'FROM "AL_D010_26_20250704"\n'
            "WHERE \"A4\" LIKE '%연제구%' AND \"A9\" = '공동주택';"
        ),
        tables=("AL_D010_26_20250704",),
        tags=("count", "usage", "gu"),
    ),
)

_TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9_]+")

# (embed_model, question) -> embedding cache
_EMB_CACHE: dict[tuple[str, str], list[float]] = {}


def _cached_embed(
    text: str,
    *,
    model: str,
    host: str | None,
    client: Any | None,
) -> list[float]:
    key = (model, text.strip())
    cached = _EMB_CACHE.get(key)
    if cached is not None:
        return cached
    emb = embed_text(text, model=model, host=host, client=client)
    _EMB_CACHE[key] = emb
    return emb


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _format_examples(examples: list[SqlExample]) -> str:
    if not examples:
        return ""
    blocks = ["Examples (follow the same style):"]
    for ex in examples:
        blocks.append(f"\nQ: {ex.question}\nSQL:\n{ex.sql.strip()}")
    return "\n".join(blocks) + "\n"


def retrieve_examples(
    question: str,
    *,
    top_k: int = 3,
    embed_model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
    bank: tuple[SqlExample, ...] | None = None,
) -> list[SqlExample]:
    """질문과 유사한 few-shot 예제를 고른다.

    임베딩이 가능하면 cosine, 아니면 토큰 Jaccard로 폴백한다.
    """
    pool = list(bank or EXAMPLE_BANK)
    if top_k <= 0 or not pool:
        return []

    q = question.strip()
    scored: list[tuple[float, SqlExample]] = []

    q_emb: list[float] | None = None
    if embed_model and (client is not None or host):
        try:
            q_emb = _cached_embed(
                q, model=embed_model, host=host, client=client
            )
        except Exception:
            q_emb = None

    q_tok = _tokens(q)
    for ex in pool:
        # 동일/거의 동일한 질문은 제외 (정답 누수 방지에 가깝게)
        if ex.question.strip() == q:
            continue
        if q_emb is not None:
            try:
                e_emb = _cached_embed(
                    ex.question, model=embed_model or "", host=host, client=client
                )
                score = _cosine(q_emb, e_emb)
            except Exception:
                score = _jaccard(q_tok, _tokens(ex.question))
        else:
            score = _jaccard(q_tok, _tokens(ex.question))
            # 태그 힌트 소폭 가산
            for tag in ex.tags:
                if tag in q.lower() or any(tag in t for t in q_tok):
                    score += 0.05
        scored.append((score, ex))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:top_k]]


def format_retrieved_examples(
    question: str,
    *,
    top_k: int = 3,
    embed_model: str | None = None,
    host: str | None = None,
    client: Any | None = None,
) -> str:
    examples = retrieve_examples(
        question,
        top_k=top_k,
        embed_model=embed_model,
        host=host,
        client=client,
    )
    return _format_examples(examples)
