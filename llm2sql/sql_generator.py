from __future__ import annotations

import re

import ollama

from llm2sql.prompt_examples import DOMAIN_HINTS, FEW_SHOT_EXAMPLES


SYSTEM_PROMPT = f"""You are a PostgreSQL + PostGIS expert for a Korean GIS database.
Convert the user's natural language question into a single SQL query.

Rules:
- Output ONLY the SQL query. No markdown fences, no explanation, no thinking aloud.
- Use ONLY tables/columns from the provided schema.
- Table names in SQL MUST be the physical quoted names after TABLE, e.g. "AL_D010_26_20250704".
  Never use Korean display names as table identifiers.
- Always quote identifiers with double quotes, e.g. "A4", "ADM_NM", "AL_D010_26_20250704".
- SELECT/WITH only. Never INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE/CREATE.
- Always include LIMIT (default 100) unless the query is a pure COUNT/aggregate returning few rows.
- Do NOT select raw geometry columns by default. Prefer attributes only.
  Never use SELECT *. List needed columns explicitly.
  If geometry output is explicitly requested, use ST_AsGeoJSON(geometry) AS geojson.
- SRID is 4326 for all spatial tables.
- Allowed spatial functions: ST_Intersects, ST_Within, ST_DWithin, ST_Distance,
  ST_Area, ST_Centroid, ST_MakePoint, ST_SetSRID, ST_Transform, ST_AsGeoJSON, ST_AsText.
- For meter distances on 4326 data, cast to geography, e.g.
  ST_DWithin(a.geometry::geography, b.geometry::geography, 500).
- When the question means "inside / within / contained in" a dong/gu (안에, 내부, 속하는),
  you MUST use a spatial join with "BND_ADM_DONG_PG" (or "TL_KODIS_BAS_26_202507" for 기초구역):
  filter boundary by "ADM_NM" / "SIG_KOR_NM" with LIKE, then
  ST_Intersects(building.geometry, boundary.geometry).
  Do not approximate this with attribute LIKE on building "A4" alone when spatial intent is clear.
- For gu/dong name filters on text columns, prefer LIKE '%이름%' not exact equality.
- Prefer Korean text columns for filters (e.g. "A9" 용도명) over opaque codes ("A8").
- Use GiST-friendly predicates (ST_Intersects / &&) rather than full-table scans.
- If unsupported, output: SELECT 'UNSUPPORTED' AS error;

{DOMAIN_HINTS}
"""


def _extract_sql(text: str) -> str:
    text = text.strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    match = re.search(r"(?is)\b(with|select)\b.*", text)
    if match:
        text = match.group(0).strip()
    return text.rstrip(";").strip() + ";"


def generate_sql(
    question: str,
    schema_text: str,
    *,
    model: str,
    host: str,
    error_feedback: str | None = None,
    include_few_shot: bool = True,
) -> str:
    client = ollama.Client(host=host)
    few = FEW_SHOT_EXAMPLES if include_few_shot else ""
    if error_feedback:
        user_content = (
            f"Schema:\n{schema_text}\n\n"
            f"{few}\n"
            f"Question: {question}\n\n"
            f"Previous SQL failed with error:\n{error_feedback}\n\n"
            "Write a corrected SQL:"
        )
    else:
        user_content = (
            f"Schema:\n{schema_text}\n\n"
            f"{few}\n"
            f"Question: {question}\n\n"
            "SQL:"
        )

    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        options={"temperature": 0},
    )
    content = response["message"]["content"]
    return _extract_sql(content)
