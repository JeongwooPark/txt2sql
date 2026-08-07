"""PostGIS 공간 질의 템플릿."""

from __future__ import annotations

from llm2sql.domain import extract_place


def extract_place_token(question: str) -> str | None:
    """질문에서 동/구 명칭 후보를 추출."""
    return extract_place(question)


def building_in_dong_count_sql(place: str) -> str:
    return (
        'SELECT COUNT(*) AS cnt\n'
        'FROM "AL_D010_26_20250704" b\n'
        'JOIN "BND_ADM_DONG_PG" d\n'
        "  ON ST_Intersects(b.geometry, d.geometry)\n"
        f'WHERE d."ADM_NM" LIKE \'%{place}%\';'
    )


def spatial_fewshot(place: str | None) -> str:
    sample = place or "예시동"
    return (
        "Required pattern example:\n"
        f"{building_in_dong_count_sql(sample)}\n"
        "Adapt table/columns only if needed; keep ST_Intersects and boundary join."
    )
