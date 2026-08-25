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

Q: 구서동 주변 100m안에 있는 건물은?
SQL:
SELECT b."A0", b."A4", b."A5", b."A9", b."A12", b."A14", b."A16", b."A24", b."A26"
FROM "AL_D010_26_20250704" b
CROSS JOIN (
  SELECT ST_Union(d.geometry) AS geom
  FROM "BND_ADM_DONG_PG" d
  WHERE (d."ADM_NM" = '구서동' OR d."ADM_NM" ~ '^구서[0-9]+동$')
) z
WHERE z.geom IS NOT NULL
  AND b.geometry && ST_Expand(z.geom, 0.0015)
  AND ST_DWithin(b.geometry::geography, z.geom::geography, 100)
ORDER BY ST_Distance(b.geometry::geography, z.geom::geography),
  b."A14" DESC NULLS LAST
LIMIT 50;

Q: 산업단지와 교차하는 해운대구 기초구역 목록
SQL:
SELECT DISTINCT t."BAS_ID", t."SIG_KOR_NM", t."BAS_AR"
FROM "TL_KODIS_BAS_26_202507" t
JOIN "AL_D060_00_20250804" i
  ON ST_Intersects(t.geometry, i.geometry)
WHERE t."SIG_KOR_NM" = '해운대구'
LIMIT 100;

Q: 금정구에서 가장 최근에 지어진 아파트는?
SQL:
SELECT "A4", "A13", "A25", "A27", "A34"
FROM "AL_D198_26410_20250115"
WHERE "A4" LIKE '%금정구%'
  AND "A27" ILIKE '%아파트%'
  AND "A34" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
ORDER BY "A34" DESC NULLS LAST
LIMIT 1;
"""

_DOMAIN_HINTS_TEMPLATE = """
Domain mapping (critical):
- Busan-wide / gu-level building attributes → prefer "AL_D010_26_20250704"
  - "A4"=법정동명(use LIKE '%구명%'), "A9"=건축물용도명, "A14"=연면적,
    "A16"=높이(m), "A26"=지상층, "A27"=지하층
  - NEVER filter Hangul gu/dong names with "A3" (that is a code column).
  - AL_D010 has NO reliable construction/approval year.
    "A13" is often empty; "A22" is 데이터기준일자 only.
    NEVER SELECT MAX("A13") or alias it as 최신건설일.
  - For registered D198 gus "가장 최근에 지어진" / "가장 오래된":
      FROM AL_D198_… ORDER BY "A34" DESC (or ASC) NULLS LAST LIMIT 1
      아파트 → "A27" ILIKE '%아파트%' (or "A25"='공동주택')
- District-only building tables (have approval dates):
__D198_LISTING__
  - "A25"=주요용도명, "A19"=연면적, "A30"=높이, "A31"=지상층
  - "A33"=허가일자, "A34"=사용승인일자 (text 'YYYY-MM-DD')
  - For 달력 연도(2020년 이후/이전에 지어진·준공):
      "A34" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' AND "A34"::date >= '2020-01-01'
      NEVER INTERVAL '2020 years'. 1900~2100 is a calendar year, not building age.
  - For 건축년수/준공/지어진지 N년 (N is elapsed years like 30, not 2020):
      "A34" ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' AND
      - N년 이상/넘는: "A34"::date <= (CURRENT_DATE - INTERVAL 'N years')
      - N년 미만: "A34"::date > (CURRENT_DATE - INTERVAL 'N years')
    NEVER use "A35"(데이터기준일자) for building age.
  - 부산 전체 건축년수 → UNION/SUM of registered D198 tables only (other gus lack dates).
    Say in the answer that coverage is __D198_LABEL__(사용승인일 보유 구).
  - "주요용도명" 종류/건수 for registered D198 gus → ALWAYS D198 "A25" (never AL_D010 "A9").
  - Other gus (not listed above) building/usage counts → ALWAYS "AL_D010_26_20250704"
    with "A9" (never AL_D198; those tables only cover __D198_LABEL__).
- 공공시설/공공시설물 → AL_D010 "A9"='공공용시설' or AL_D198 "A29"='공공용'
- 행정동(구서1동 등) → join "BND_ADM_DONG_PG" on ST_Intersects; 법정동은 구서동
- 동 주변 N m 버퍼 → ST_Union of matching "BND_ADM_DONG_PG" + ST_DWithin geography (구서동 → 구서1동/구서2동)
- 건물 ∩ 기초구역 → "TL_KODIS_BAS_26_202507" ST_Intersects; 동 ∩ 기초구역도 동일
- 인접 행정동 → 같은 센서스 ADM_CD 접두어끼리 ST_Intersects (자기 제외)
- 기초구역 → "TL_KODIS_BAS_26_202507" ("SIG_KOR_NM", "BAS_AR", "BAS_ID")
- 행정동 경계 → "BND_ADM_DONG_PG" ("ADM_NM", "ADM_CD")
- 산업단지 → "AL_D060_00_20250804" ("A4"=원천시도시군구코드, "A6"=용도지역지구코드명)
- Ranking/top-N → ORDER BY ... DESC NULLS LAST + LIMIT
- Meter buffer/distance on 4326 → cast geometry to geography for ST_DWithin
- Area columns are ㎡. Convert 평 with 1평 = 400/121 ㎡ (≈3.3058). Convert km² to ㎡ (×1,000,000).
- Height and ST_DWithin distances are meters. Convert km to m (×1000).
"""


def domain_hints() -> str:
    from llm2sql.domain import D198_BY_GU, d198_coverage_label

    lines = [
        f'  - {gu} → "{table}"' for gu, table in D198_BY_GU.items()
    ]
    listing = "\n".join(lines) if lines else "  - (등록된 AL_D198 없음)"
    return (
        _DOMAIN_HINTS_TEMPLATE.replace("__D198_LISTING__", listing).replace(
            "__D198_LABEL__", d198_coverage_label()
        )
    )


DOMAIN_HINTS = domain_hints()
