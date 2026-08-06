"""LLM SQL 생성용 few-shot 예제와 도메인 힌트."""

from __future__ import annotations

FEW_SHOT_EXAMPLES = """
Examples (follow the same style):

Q: 해운대구 연면적 상위 5개 건물의 법정동명, 용도, 연면적을 보여줘
SQL:
SELECT "A4", "A9", "A14"
FROM "AL_D010_26_20250704"
WHERE "A4" LIKE '%해운대구%'
ORDER BY "A14" DESC NULLS LAST
LIMIT 5;

Q: 수영구 기초구역 면적이 큰 순으로 10개
SQL:
SELECT "BAS_ID", "SIG_KOR_NM", "BAS_AR"
FROM "TL_KODIS_BAS_26_202507"
WHERE "SIG_KOR_NM" = '수영구'
ORDER BY "BAS_AR" DESC NULLS LAST
LIMIT 10;

Q: 좌표(129.08, 35.16)에서 500미터 이내 건물 건수
SQL:
SELECT COUNT(*) AS cnt
FROM "AL_D010_26_20250704" b
WHERE ST_DWithin(
  b.geometry::geography,
  ST_SetSRID(ST_MakePoint(129.08, 35.16), 4326)::geography,
  500
);

Q: 산업단지와 교차하는 해운대구 기초구역 목록
SQL:
SELECT DISTINCT t."BAS_ID", t."SIG_KOR_NM", t."BAS_AR"
FROM "TL_KODIS_BAS_26_202507" t
JOIN "AL_D060_00_20250804" i
  ON ST_Intersects(t.geometry, i.geometry)
WHERE t."SIG_KOR_NM" = '해운대구'
LIMIT 100;
"""

DOMAIN_HINTS = """
Domain mapping (critical):
- Busan-wide / gu-level building attributes → prefer "AL_D010_26_20250704"
  - "A4"=법정동명(use LIKE '%구명%'), "A9"=건축물용도명, "A14"=연면적,
    "A16"=높이(m), "A26"=지상층, "A27"=지하층
  - NEVER filter Hangul gu/dong names with "A3" (that is a code column).
- District-only building tables:
  - 동래구 → "AL_D198_26260_20250115" ("A25"=주요용도명, "A19"=연면적, "A30"=높이, "A31"=지상층)
  - 금정구 → "AL_D198_26410_20250115" (same column pattern as 동래)
- 기초구역 → "TL_KODIS_BAS_26_202507" ("SIG_KOR_NM", "BAS_AR", "BAS_ID")
- 행정동 경계 → "BND_ADM_DONG_PG" ("ADM_NM", "ADM_CD")
- 산업단지 → "AL_D060_00_20250804" ("A4"=원천시도시군구코드, "A6"=용도지역지구코드명)
- Ranking/top-N → ORDER BY ... DESC NULLS LAST + LIMIT
- Meter buffer/distance on 4326 → cast geometry to geography for ST_DWithin
"""
