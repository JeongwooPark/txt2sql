# 500문항 실패 원인 진단

- 시각: 2026-08-25 10:48:31
- 현재: 10/24 (41.7%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `ENTITY_SELECTION_ERROR`: 10
- `PREDICATE_DROPPED`: 4
- `SPATIAL_TARGET_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `Q200` 해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이  
  gold=`1. A24=마린시티두산위브포세이돈, A4=부산광역시 해운대구 우동, A18=989.25, A16=162.58, A14=129,393.97 / 2. A24=해운대 경보이리스오션, A4=부산광역시 해운대구 중동, A18=977.47, A16=71.7, A14=23,328.42 / 3. A24=마린시티자이, A4=부산광역시 해운대구 우동, A18=953.79, A16=156.45, A14=48,627.2614 / 4. A24=현대아쿠아팰리스동백섬, A4=부산광역시 해운대구 우동, A18=935.71, A16=63.3, A14=14,205.42 / 5. A24=해운대 한솔 솔파크, A4=부산광역시 해운대구 우동, A18=916.03, A16=96.6, A14=42,892.436 / 6. A24=현대아파트, A4=부산광역시 해운대구 우동, A18=912.09, A16=52.3, A14=11,179.41 / 7. A24=해운대 비치베르빌, A4=부산광역시 해운대구 중동, A18=907.94, A16=99.15, A14=41,150.786 / 8. A24=현대 아쿠아팰리스 해운대, A4=부산광역시 해운대구 중동, A18=874.45, A16=95.7, A14=28,119.22 / 9. A24=아크로뷰, A4=부산광역시 해운대구 중동, A18=816.44, A16=56.02, A14=10,673.41 / 10. A24=삼영일리아, A4=부산광역시 해운대구 우동, A18=801.68, A16=46.7, A14=5,410.21` reason=`list-top-missing 마린시티두산위브포세이돈` route=`semantic_plan_clarify`
- `Q201` 수영구 건폐율 상위 8개 숙박시설의 이름·건폐율·연면적  
  gold=`1. A24=없음, A4=부산광역시 수영구 광안동, A17=90.72, A14=585.92 / 2. A24=없음, A4=부산광역시 수영구 민락동, A17=83.1, A14=474.01 / 3. A24=없음, A4=부산광역시 수영구 광안동, A17=82.92, A14=1,216.99 / 4. A24=없음, A4=부산광역시 수영구 광안동, A17=79.86, A14=683.13 / 5. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A17=78.54, A14=18,228.2 / 6. A24=메종 드 센텀, A4=부산광역시 수영구 광안동, A17=77.86, A14=1,281.74 / 7. A24=골든벨모텔, A4=부산광역시 수영구 남천동, A17=77.09, A14=1,042.47 / 8. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A17=76.59, A14=16,992.61` reason=`list-top-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q222` 사하구 위반건축물 비율(위반/(위반+N))  
  gold=`pct_violate=1.5357` reason=`scalar-mismatch hits=0 gold=[1.5357]` route=`semantic_plan_clarify`
- `Q223` 금정구 산지 비율(산 / 전체) %  
  gold=`pct_mountain=3.7068` reason=`scalar-mismatch hits=0 gold=[3.7068]` route=`semantic_plan_clarify`
- `Q238` 장림동 공장 중 연면적 1000㎡ 이상 비율 %  
  gold=`pct=24.7444` reason=`scalar-mismatch hits=0 gold=[24.7444]` route=`semantic_plan_clarify`
- `Q239` 대연동 공동주택 층수 구간별 건수(1-5, 6-10, 11-20, 21+)  
  gold=`1. bin=1-5층, n=1,046 / 2. bin=11-20층, n=37 / 3. bin=21층이상, n=48 / 4. bin=6-10층, n=291` reason=`group-mismatch` route=`semantic_plan_clarify`
- `Q246` 우동 건물 중 높이 50m 이상 비율과 20층 이상 비율  
  gold=`pct_h50=2.3586; pct_fl20=1.7153` reason=`scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153]` route=`semantic_plan_clarify`
- `Q251` 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)  
  gold=`pct=42.1833` reason=`scalar-mismatch hits=0 gold=[42.1833]` route=`semantic_plan_clarify`

### PREDICATE_DROPPED

- `Q243` 중구 건물 중 높이 있는 건물의 평균·표준편차 높이  
  gold=`n=3,081; avg_h=13.8696; sd_h=9.8622` reason=`scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622]` route=`semantic_plan_aggregate`
- `Q256` 사하구 공장 연면적 상위 10% 경계값(90백분위)  
  gold=`p90_gfa=2,741.139; n=2,549` reason=`scalar-mismatch hits=1 gold=[90.0, 2741.139, 2549.0]` route=`semantic_plan_aggregate`
- `Q261` 수영구 숙박시설 중 연면적 대비 건축면적 비(평균 A12/A14)  
  gold=`n=101; avg_ratio=0.2351` reason=`scalar-mismatch hits=1 gold=[101.0, 0.2351]` route=`semantic_plan_aggregate`
- `Q286` 대연3동 안 교육연구시설 대지면적 합계  
  gold=`n=102; sum_land=4,493,737.873` reason=`scalar-mismatch hits=1 gold=[102.0, 4493737.873]` route=`semantic_plan_aggregate`

### SPATIAL_TARGET_DROPPED

- `Q251` 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)  
  gold=`pct=42.1833` reason=`scalar-mismatch hits=0 gold=[42.1833]` route=`semantic_plan_clarify`
