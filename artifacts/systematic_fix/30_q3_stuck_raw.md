## r0_20  0/24  (file total 338/500)
## r1  3/24  (file total 3/24)
## r2  3/24  (file total 3/24)
## r3  4/24  (file total 4/24)
## full28  5/24  (file total 392/500)

## 문항별 궤적

| ID | 질문 | r0 pass/route | r1 | r2 | r3 | full28 | r3 reason | r3 sql |
|---|---|---|---|---|---|---|---|---|
| Q200 | 해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이 | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | list-top-missing 마린시티두산위브포세이돈 | SELECT /   COUNT(*) AS cnt, /   ROUND(AVG("A14")::numeric, 1) AS avg_area, /   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area, /   ROUND(MIN("A14")::numeric, 1) AS min_area, /   ROUND(M |
| Q201 | 수영구 건폐율 상위 8개 숙박시설의 이름·건폐율·연면적 | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | FAIL/building_profile | list-top-missing 호텔아쿠아펠리스 | SELECT /   COUNT(*) AS cnt, /   ROUND(AVG("A14")::numeric, 1) AS avg_area, /   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area, /   ROUND(MIN("A14")::numeric, 1) AS min_area, /   ROUND(M |
| Q220 | 동구 지하층 합계와 지하층이 있는 건물 수 | FAIL/building_place_count | FAIL/building_place_count | FAIL/building_place_count | FAIL/building_place_count | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[2344.0, 2682.0] | SELECT COUNT(*) AS cnt / FROM "AL_D010_26_20250704" / WHERE "A4" LIKE '%동구%'; |
| Q221 | 남구 건물동명에 '상가'가 들어가는 건물 수와 평균 연면적 | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[73.0, 2129.7754] | SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%남구%' AND b."A25" IS NOT NULL; |
| Q222 | 사하구 위반건축물 비율(위반/(위반+N)) | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[1.5357] | SELECT 100.0 * COUNT(*) FILTER (WHERE b."A20" = 'Y')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%사하구%'; |
| Q223 | 금정구 산지 비율(산 / 전체) % | FAIL/meta_catalog | FAIL/meta_catalog | FAIL/meta_catalog | FAIL/semantic_plan_clarify | FAIL/semantic_plan_clarify | scalar-mismatch hits=0 gold=[3.7068] |  |
| Q227 | 수영구 건물 용도별 평균 연면적 상위 10개 용도 | FAIL/None | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | group-nums | SELECT b."A9" AS "usage", /        AVG(b."A14"::float8) AS "avg_gross_floor_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%수영구%' / GROUP BY b."A9" / ORDER BY "avg_gross_floor_area_m2" DESC NULLS LAST / ... |
| Q230 | 남구에서 공동주택이 전체 건물에서 차지하는 비율 % | FAIL/meta_catalog | FAIL/meta_catalog | FAIL/meta_catalog | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | scalar-nums 1/1 | SELECT 100.0 * COUNT(*) FILTER (WHERE b."A9" = '공동주택')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%남구%'; |
| Q231 | 영도구 15층 이상 건물 중 공동주택 비율 % | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[91.716] | SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A9" = '공동주택' AND b."A26"::float8 >= 15))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%영도구%'; |
| Q232 | 부산진구 용도별 평균 높이(높이 있는 건물만) 상위 8 | FAIL/None | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | group-nums | SELECT b."A9" AS "usage", /        AVG(b."A16"::float8) AS "avg_height_m" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%부산진구%' / GROUP BY b."A9" / ORDER BY "avg_height_m" DESC NULLS LAST; |
| Q237 | 광안동 숙박시설 연면적 합계·평균·최대 높이 | FAIL/None | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | OK/semantic_plan_aggregate | scalar-nums 3/4 | SELECT AVG(b."A16"::float8) AS "avg_height_m", /        AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        SUM(b."A16"::float8) AS "sum_height_m", /        SUM(b."A14"::float8) AS "sum_gross_floor_area_m2", /... |
| Q238 | 장림동 공장 중 연면적 1000㎡ 이상 비율 % | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[24.7444] | SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A9" = '공장' AND b."A14"::float8 >= 1000))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE (b."A4" LIKE '% 장림동' OR b."A4" = '장림동'); |
| Q239 | 대연동 공동주택 층수 구간별 건수(1-5, 6-10, 11-20, 21+) | FAIL/d198_value_bins | FAIL/d198_value_bins | FAIL/d198_value_bins | FAIL/d198_value_bins | FAIL/d198_value_bins | group-mismatch | SELECT period, SUM(n) AS n / FROM ( / SELECT (FLOOR("A31" / 1) * 1)::int AS period, COUNT(*) AS n / FROM "AL_D198_26260_20250115" / WHERE ("A4" LIKE '% 대연동' OR "A4" = '대연동') AND TRIM(COALESCE("A25"::text, '')) = '공동주택' A |
| Q242 | 사상구 공장 구조별 건수와 평균 연면적 상위 6 | FAIL/None | FAIL/None | FAIL/None | FAIL/None | FAIL/None | engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT. | SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%사상구%' AND b."A9" = '공장'; |
| Q243 | 중구 건물 중 높이 있는 건물의 평균·표준편차 높이 | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622] | SELECT AVG(b."A16"::float8) AS "avg_height_m" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%중구%'; |
| Q246 | 우동 건물 중 높이 50m 이상 비율과 20층 이상 비율 | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153] | SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A16"::float8 >= 50 AND b."A26"::float8 >= 20))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE (b."A4" LIKE '% 우동' OR b."A4" = '우동') AND b."A1 |
| Q251 | 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장) | FAIL/None | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[42.1833] | SELECT 100.0 * COUNT(*) FILTER (WHERE b."A9" = '공장')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE EXISTS (SELECT 1 FROM "AL_D060_00_20250804" ind WHERE ST_Intersects(b.geometry, ind |
| Q252 | 남구 숙박시설이 있는 법정동별 숙박시설 채수 | FAIL/building_usage_count | FAIL/building_usage_count | FAIL/building_usage_count | FAIL/building_usage_count | FAIL/building_usage_count | group-mismatch | SELECT COUNT(*) AS cnt / FROM "AL_D010_26_20250704" / WHERE "A4" LIKE '%남구%' AND "A9" = '숙박시설'; |
| Q254 | 부산 구별 위반건축물 수 상위 8개 구 | FAIL/semantic_plan_rank | FAIL/semantic_plan_rank | FAIL/semantic_plan_rank | FAIL/semantic_plan_rank | OK/semantic_plan_aggregate | group-label-missing | SELECT b."A24" AS "name", /        b."A4" AS "legal_dong", /        b."A5" AS "lot_address", /        b."A14"::float8 AS "gross_floor_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A20" = 'Y' / ORDER BY b."A14"::floa |
| Q256 | 사하구 공장 연면적 상위 10% 경계값(90백분위) | FAIL/building_rank_연면적 | FAIL/building_rank_연면적 | FAIL/building_rank_연면적 | FAIL/building_rank_연면적 | FAIL/building_rank_연면적 | scalar-mismatch hits=1 gold=[90.0, 2741.139, 2549.0] | SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", "A19", "A24", "A25", "A26" / FROM "AL_D010_26_20250704" WHERE "A4" LIKE '%사하구%' AND "A9" = '공장' AND "A14" > 0 AND "A14" <= 2e+06 / ORDER BY "A14" DESC NULLS LAST |
| Q261 | 수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14) | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[101.0, 0.2351] | SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        AVG(b."A12"::float8) AS "avg_building_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%수영구%' AND b."A9" = '숙박시설'; |
| Q265 | 해운대구 공동주택 높이 합계(1~500m만)와 건수 | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=0 gold=[2883.0, 80450.097] | SELECT SUM(b."A16"::float8) AS "sum_height_m", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%해운대구%' AND (b."A9" = '공동주택' AND b."A16"::float8 BETWEEN 1 AND 500) AND b."A16"::float8 > 0 AND  |
| Q286 | 대연3동 안 교육연구시설 대지면적 합계 | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | FAIL/semantic_plan_aggregate | scalar-mismatch hits=1 gold=[102.0, 4493737.873] | SELECT SUM(b."A15"::float8) AS "sum_site_area_m2" / FROM "AL_D010_26_20250704" b / JOIN "BND_ADM_DONG_PG" adm ON ST_Intersects(b.geometry, adm.geometry) / WHERE adm."ADM_NM" = '대연3동' AND adm."ADM_CD" LIKE '21%' AND b."A9 |
| Q298 | 북구 기초구역 면적 합계와 개수 | FAIL/bas_area_topn | FAIL/bas_area_topn | FAIL/bas_area_topn | FAIL/bas_area_topn | FAIL/bas_area_topn | scalar-mismatch hits=0 gold=[154.0, 39.7834] | SELECT "BAS_AR", "BAS_ID", "SIG_KOR_NM" / FROM "TL_KODIS_BAS_26_202507" / WHERE "SIG_KOR_NM" = '북구' / ORDER BY "BAS_AR" DESC NULLS LAST / LIMIT 1; |

## 상세

### Q200  해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이
- r0: pass=False route=building_profile reason=list-top-missing 마린시티두산위브포세이돈
- r3: pass=False route=building_profile reason=list-top-missing 마린시티두산위브포세이돈
- full28: pass=False route=building_profile reason=list-top-missing 마린시티두산위브포세이돈
- r3 sql: SELECT /   COUNT(*) AS cnt, /   ROUND(AVG("A14")::numeric, 1) AS avg_area, /   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area, /   ROUND(MIN("A14")::numeric, 1) AS min_area, /   ROUND(MAX("A14")::numeric, 1) AS max_area, /   ROUND(AVG("A16") FILTER (WHERE "A16" > 0 AND "A16" <= 600)::numeric, 1) AS avg_height, /   ROUND(MAX("A16") FILTER (WHERE "A16" > 0 AND "A16
- r3 answer: 해운대구 공동주택의 용적율 상위 10개 건물은 용적율 1422.2%까지 달하는 대형 단지가 포함되어 있으며, 이는 대지면적과 연면적의 비율이 매우 높은 구조로 보입니다. 용적율은 건물의 연면적을 대지면적으로 나눈 값으로, 건폐율은 건축면적을 대지면적으로 나눈 비율을 나타내며, 이는 대지면적·면적이 유효한 건물만 집계되었습니다. 전체 공동주택의 평균 용적율은

### Q201  수영구 건폐율 상위 8개 숙박시설의 이름·건폐율·연면적
- r0: pass=False route=building_profile reason=list-top-missing 호텔아쿠아펠리스
- r3: pass=False route=building_profile reason=list-top-missing 호텔아쿠아펠리스
- full28: pass=False route=building_profile reason=list-top-missing 호텔아쿠아펠리스
- r3 sql: SELECT /   COUNT(*) AS cnt, /   ROUND(AVG("A14")::numeric, 1) AS avg_area, /   ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "A14")::numeric, 1) AS med_area, /   ROUND(MIN("A14")::numeric, 1) AS min_area, /   ROUND(MAX("A14")::numeric, 1) AS max_area, /   ROUND(AVG("A16") FILTER (WHERE "A16" > 0 AND "A16" <= 600)::numeric, 1) AS avg_height, /   ROUND(MAX("A16") FILTER (WHERE "A16" > 0 AND "A16
- r3 answer: 수영구의 숙박시설 중 건폐율 상위 8개 건물은 대부분 철근콘크리트구조로 되어 있으며, 최대 건폐율은 1304.9%에 달합니다. 평균 건폐율은 397.7%로, 일부 건물에서는 대지면적 대비 매우 높은 건축면적을 보이고 있습니다. 연면적은 평균 1612.4㎡로, 최대 18,228.2㎡에 이르는 규모의 건물도 포함되어 있어 면적 차이가 크다는 점을 고려해야 합니

### Q220  동구 지하층 합계와 지하층이 있는 건물 수
- r0: pass=False route=building_place_count reason=scalar-mismatch hits=0 gold=[2344.0, 2682.0]
- r3: pass=False route=building_place_count reason=scalar-mismatch hits=0 gold=[2344.0, 2682.0]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=1 gold=[2344.0, 2682.0]
- r3 sql: SELECT COUNT(*) AS cnt / FROM "AL_D010_26_20250704" / WHERE "A4" LIKE '%동구%';
- r3 answer: 동구 건물은 모두 19,562채입니다.

### Q221  남구 건물동명에 '상가'가 들어가는 건물 수와 평균 연면적
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[73.0, 2129.7754]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[73.0, 2129.7754]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[73.0, 2129.7754]
- r3 sql: SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%남구%' AND b."A25" IS NOT NULL;
- r3 answer: 남구의 집계 결과입니다. 평균 연면적 3033.9318, 건수 2,587.

### Q222  사하구 위반건축물 비율(위반/(위반+N))
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[1.5357]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[1.5357]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[1.5357]
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE b."A20" = 'Y')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%사하구%';
- r3 answer: 사하구의 집계 결과입니다. ratio_pct 0.928.

### Q223  금정구 산지 비율(산 / 전체) %
- r0: pass=False route=meta_catalog reason=scalar-mismatch hits=0 gold=[3.7068]
- r3: pass=False route=semantic_plan_clarify reason=scalar-mismatch hits=0 gold=[3.7068]
- full28: pass=False route=semantic_plan_clarify reason=scalar-mismatch hits=0 gold=[3.7068]
- r3 sql: 
- r3 answer: 확인이 필요합니다. 질문을 완전히 해석하지 못해 확인이 필요합니다

### Q227  수영구 건물 용도별 평균 연면적 상위 10개 용도
- r0: pass=False route=None reason=engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.
- r3: pass=True route=semantic_plan_aggregate reason=group-nums
- full28: pass=True route=semantic_plan_aggregate reason=group-nums
- r3 sql: SELECT b."A9" AS "usage", /        AVG(b."A14"::float8) AS "avg_gross_floor_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%수영구%' / GROUP BY b."A9" / ORDER BY "avg_gross_floor_area_m2" DESC NULLS LAST / ...
- r3 answer: 수영구의 집계 결과입니다. 용도 의료시설, 평균 연면적 5934.3053.

### Q230  남구에서 공동주택이 전체 건물에서 차지하는 비율 %
- r0: pass=False route=meta_catalog reason=scalar-mismatch hits=0 gold=[9.0305]
- r3: pass=True route=semantic_plan_aggregate reason=scalar-nums 1/1
- full28: pass=True route=semantic_plan_aggregate reason=scalar-nums 1/1
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE b."A9" = '공동주택')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%남구%';
- r3 answer: 남구의 집계 결과입니다. ratio_pct 9.0305.

### Q231  영도구 15층 이상 건물 중 공동주택 비율 %
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[91.716]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[91.716]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[91.716]
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A9" = '공동주택' AND b."A26"::float8 >= 15))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%영도구%';
- r3 answer: 영도구의 집계 결과입니다. ratio_pct 0.6051.

### Q232  부산진구 용도별 평균 높이(높이 있는 건물만) 상위 8
- r0: pass=False route=None reason=engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.
- r3: pass=True route=semantic_plan_aggregate reason=group-nums
- full28: pass=True route=semantic_plan_aggregate reason=group-nums
- r3 sql: SELECT b."A9" AS "usage", /        AVG(b."A16"::float8) AS "avg_height_m" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%부산진구%' / GROUP BY b."A9" / ORDER BY "avg_height_m" DESC NULLS LAST;
- r3 answer: 부산진구의 집계 결과입니다. 용도 장례식장, 평균 높이 38.6.

### Q237  광안동 숙박시설 연면적 합계·평균·최대 높이
- r0: pass=False route=None reason=engine-fail:too many aggregations
- r3: pass=True route=semantic_plan_aggregate reason=scalar-nums 3/4
- full28: pass=True route=semantic_plan_aggregate reason=scalar-nums 3/4
- r3 sql: SELECT AVG(b."A16"::float8) AS "avg_height_m", /        AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        SUM(b."A16"::float8) AS "sum_height_m", /        SUM(b."A14"::float8) AS "sum_gross_floor_area_m2", /...
- r3 answer: 광안동의 집계 결과입니다. 평균 높이 18.9738, 평균 연면적 2075.2302, sum_height_m 948.69, sum_gross_floor_area_m2 103761.5099, max_height_m 73.8, max_gross_floor_area_m2 18228.2.

### Q238  장림동 공장 중 연면적 1000㎡ 이상 비율 %
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[24.7444]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[24.7444]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[24.7444]
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A9" = '공장' AND b."A14"::float8 >= 1000))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE (b."A4" LIKE '% 장림동' OR b."A4" = '장림동');
- r3 answer: 장림동의 집계 결과입니다. ratio_pct 3.5889.

### Q239  대연동 공동주택 층수 구간별 건수(1-5, 6-10, 11-20, 21+)
- r0: pass=False route=d198_value_bins reason=group-mismatch
- r3: pass=False route=d198_value_bins reason=group-mismatch
- full28: pass=False route=d198_value_bins reason=group-mismatch
- r3 sql: SELECT period, SUM(n) AS n / FROM ( / SELECT (FLOOR("A31" / 1) * 1)::int AS period, COUNT(*) AS n / FROM "AL_D198_26260_20250115" / WHERE ("A4" LIKE '% 대연동' OR "A4" = '대연동') AND TRIM(COALESCE("A25"::text, '')) = '공동주택' AND "A31" > 0 AND "A31" <= 80 / GROUP BY 1 / UNION ALL / SELECT (FLOOR("A31" / 1) * 1)::int AS period, COUNT(*) AS n / FROM "AL_D198_26410_20250115" / WHERE ("A4" LIKE '% 대연동' OR "A
- r3 answer: 안내: 면적·높이 구간 통계는 현재 동래구·금정구 용도별건물 자료입니다. /  / 대연동 공동주택에 해당하는 데이터를 찾지 못했습니다. 조건을 바꿔 다시 질문해 주세요.

### Q242  사상구 공장 구조별 건수와 평균 연면적 상위 6
- r0: pass=False route=None reason=engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.
- r3: pass=False route=None reason=engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.
- full28: pass=False route=None reason=engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.
- r3 sql: SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%사상구%' AND b."A9" = '공장';
- r3 answer: 요청하신 「사상구 공장 구조별 건수와 평균 연면적 상위 6」에는 지금은 답하지 못했습니다. / 이유: - Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT. / 시도한 SQL: SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /     

### Q243  중구 건물 중 높이 있는 건물의 평균·표준편차 높이
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622]
- r3 sql: SELECT AVG(b."A16"::float8) AS "avg_height_m" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%중구%';
- r3 answer: 중구의 집계 결과입니다. 평균 높이 5.5195.

### Q246  우동 건물 중 높이 50m 이상 비율과 20층 이상 비율
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153]
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE (b."A16"::float8 >= 50 AND b."A26"::float8 >= 20))::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE (b."A4" LIKE '% 우동' OR b."A4" = '우동') AND b."A16"::float8 > 0 AND b."A16"::float8 <= 600 AND (b."A26" IS NULL OR b."A16"::float8 <= (b."A26"::float8 * 8 + 30));
- r3 answer: 우동의 집계 결과입니다. ratio_pct 7.803.

### Q251  사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)
- r0: pass=False route=None reason=engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[42.1833]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[42.1833]
- r3 sql: SELECT 100.0 * COUNT(*) FILTER (WHERE b."A9" = '공장')::float8 / NULLIF(COUNT(*), 0) AS "ratio_pct" / FROM "AL_D010_26_20250704" b / WHERE EXISTS (SELECT 1 FROM "AL_D060_00_20250804" ind WHERE ST_Intersects(b.geometry, ind.geometry)) AND b."A4" LIKE '%사상구%';
- r3 answer: 사상구의 집계 결과입니다. ratio_pct 40.6885.

### Q252  남구 숙박시설이 있는 법정동별 숙박시설 채수
- r0: pass=False route=building_usage_count reason=group-mismatch
- r3: pass=False route=building_usage_count reason=group-mismatch
- full28: pass=False route=building_usage_count reason=group-mismatch
- r3 sql: SELECT COUNT(*) AS cnt / FROM "AL_D010_26_20250704" / WHERE "A4" LIKE '%남구%' AND "A9" = '숙박시설';
- r3 answer: 남구 숙박시설은 모두 67채입니다.

### Q254  부산 구별 위반건축물 수 상위 8개 구
- r0: pass=False route=semantic_plan_rank reason=group-label-missing
- r3: pass=False route=semantic_plan_rank reason=group-label-missing
- full28: pass=True route=semantic_plan_aggregate reason=group-labels 6
- r3 sql: SELECT b."A24" AS "name", /        b."A4" AS "legal_dong", /        b."A5" AS "lot_address", /        b."A14"::float8 AS "gross_floor_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A20" = 'Y' / ORDER BY b."A14"::float8 DESC NULLS LAST / LIMIT 8;
- r3 answer: 부산광역시의 상위 건물 8건을 조회했습니다. / 1. 더#해운대아델리스 · 부산광역시 해운대구 우동 1436-1 · 연면적 162286.38㎡ / 2. 트럼프월드센텀 · 부산광역시 해운대구 우동 1498 · 연면적 125513.59㎡ / 3. 엘시티 · 부산광역시 해운대구 중동 1829 · 연면적 121396.5881㎡ / 4. 부산광역시 해운대구 우동 1

### Q256  사하구 공장 연면적 상위 10% 경계값(90백분위)
- r0: pass=False route=building_rank_연면적 reason=scalar-mismatch hits=1 gold=[90.0, 2741.139, 2549.0]
- r3: pass=False route=building_rank_연면적 reason=scalar-mismatch hits=1 gold=[90.0, 2741.139, 2549.0]
- full28: pass=False route=building_rank_연면적 reason=scalar-mismatch hits=1 gold=[90.0, 2741.139, 2549.0]
- r3 sql: SELECT "A0", "A4", "A5", "A9", "A12", "A14", "A15", "A16", "A19", "A24", "A25", "A26" / FROM "AL_D010_26_20250704" WHERE "A4" LIKE '%사하구%' AND "A9" = '공장' AND "A14" > 0 AND "A14" <= 2e+06 / ORDER BY "A14" DESC NULLS LAST / LIMIT 10;
- r3 answer: 사하구 공장 중 연면적 상위 10곳은 다음과 같습니다. / 1) 지번 90 건물 — 부산광역시 사하구 구평동, 공장, 연면적 55,254.03㎡, 지상 2층 / 2) 「한국주철관공업(주)」 — 부산광역시 사하구 신평동, 공장, 연면적 36,727.37㎡, 지상 1층 / 3) 「다대동 1559 공장 (대선조선주식회사)」 — 부산광역시 사하구 다대동, 공장, 

### Q261  수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[101.0, 0.2351]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[101.0, 0.2351]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[101.0, 0.2351]
- r3 sql: SELECT AVG(b."A14"::float8) AS "avg_gross_floor_area_m2", /        AVG(b."A12"::float8) AS "avg_building_area_m2" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%수영구%' AND b."A9" = '숙박시설';
- r3 answer: 수영구의 집계 결과입니다. 평균 연면적 1612.3925, avg_building_area_m2 226.564.

### Q265  해운대구 공동주택 높이 합계(1~500m만)와 건수
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[2883.0, 80450.097]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[2883.0, 80450.097]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=0 gold=[2883.0, 80450.097]
- r3 sql: SELECT SUM(b."A16"::float8) AS "sum_height_m", /        COUNT(*) AS "n" / FROM "AL_D010_26_20250704" b / WHERE b."A4" LIKE '%해운대구%' AND (b."A9" = '공동주택' AND b."A16"::float8 BETWEEN 1 AND 500) AND b."A16"::float8 > 0 AND b."A16"::float8 <= 600 AND (b."A26" IS NULL OR b."A16"::float8 <= (b."A26"::float8 * 8 + 30));
- r3 answer: 해운대구의 집계 결과입니다. sum_height_m 80009.717, 건수 2,876.

### Q286  대연3동 안 교육연구시설 대지면적 합계
- r0: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=1 gold=[102.0, 4493737.873]
- r3: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=1 gold=[102.0, 4493737.873]
- full28: pass=False route=semantic_plan_aggregate reason=scalar-mismatch hits=1 gold=[102.0, 4493737.873]
- r3 sql: SELECT SUM(b."A15"::float8) AS "sum_site_area_m2" / FROM "AL_D010_26_20250704" b / JOIN "BND_ADM_DONG_PG" adm ON ST_Intersects(b.geometry, adm.geometry) / WHERE adm."ADM_NM" = '대연3동' AND adm."ADM_CD" LIKE '21%' AND b."A9" = '교육연구시설' / LIMIT 3;
- r3 answer: 대연3동의 집계 결과입니다. sum_site_area_m2 4493737.873.

### Q298  북구 기초구역 면적 합계와 개수
- r0: pass=False route=bas_area_topn reason=scalar-mismatch hits=0 gold=[154.0, 39.7834]
- r3: pass=False route=bas_area_topn reason=scalar-mismatch hits=0 gold=[154.0, 39.7834]
- full28: pass=False route=bas_area_topn reason=scalar-mismatch hits=0 gold=[154.0, 39.7834]
- r3 sql: SELECT "BAS_AR", "BAS_ID", "SIG_KOR_NM" / FROM "TL_KODIS_BAS_26_202507" / WHERE "SIG_KOR_NM" = '북구' / ORDER BY "BAS_AR" DESC NULLS LAST / LIMIT 1;
- r3 answer: 북구 기초구역의 면적 합계는 5.768㎡이며, 기초구역번호는 46535입니다. 총 1개의 기초구역이 있습니다.
