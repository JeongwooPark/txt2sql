# 500문항 실패 원인 진단

- 시각: 2026-08-25 07:50:52
- 현재: 4/24 (16.7%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 16
- `ENTITY_SELECTION_ERROR`: 2
- `RANGE_BOUND_DROPPED`: 2

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `Q200` 해운대구 용적율 상위 10개 공동주택의 이름·용적율·높이  
  gold=`1. A24=마린시티두산위브포세이돈, A4=부산광역시 해운대구 우동, A18=989.25, A16=162.58, A14=129,393.97 / 2. A24=해운대 경보이리스오션, A4=부산광역시 해운대구 중동, A18=977.47, A16=71.7, A14=23,328.42 / 3. A24=마린시티자이, A4=부산광역시 해운대구 우동, A18=953.79, A16=156.45, A14=48,627.2614 / 4. A24=현대아쿠아팰리스동백섬, A4=부산광역시 해운대구 우동, A18=935.71, A16=63.3, A14=14,205.42 / 5. A24=해운대 한솔 솔파크, A4=부산광역시 해운대구 우동, A18=916.03, A16=96.6, A14=42,892.436 / 6. A24=현대아파트, A4=부산광역시 해운대구 우동, A18=912.09, A16=52.3, A14=11,179.41 / 7. A24=해운대 비치베르빌, A4=부산광역시 해운대구 중동, A18=907.94, A16=99.15, A14=41,150.786 / 8. A24=현대 아쿠아팰리스 해운대, A4=부산광역시 해운대구 중동, A18=874.45, A16=95.7, A14=28,119.22 / 9. A24=아크로뷰, A4=부산광역시 해운대구 중동, A18=816.44, A16=56.02, A14=10,673.41 / 10. A24=삼영일리아, A4=부산광역시 해운대구 우동, A18=801.68, A16=46.7, A14=5,410.21` reason=`list-top-missing 마린시티두산위브포세이돈` route=`building_profile`
- `Q201` 수영구 건폐율 상위 8개 숙박시설의 이름·건폐율·연면적  
  gold=`1. A24=없음, A4=부산광역시 수영구 광안동, A17=90.72, A14=585.92 / 2. A24=없음, A4=부산광역시 수영구 민락동, A17=83.1, A14=474.01 / 3. A24=없음, A4=부산광역시 수영구 광안동, A17=82.92, A14=1,216.99 / 4. A24=없음, A4=부산광역시 수영구 광안동, A17=79.86, A14=683.13 / 5. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A17=78.54, A14=18,228.2 / 6. A24=메종 드 센텀, A4=부산광역시 수영구 광안동, A17=77.86, A14=1,281.74 / 7. A24=골든벨모텔, A4=부산광역시 수영구 남천동, A17=77.09, A14=1,042.47 / 8. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A17=76.59, A14=16,992.61` reason=`list-top-missing 호텔아쿠아펠리스` route=`building_profile`
- `Q220` 동구 지하층 합계와 지하층이 있는 건물 수  
  gold=`n=2,344; sum_basement=2,682` reason=`scalar-mismatch hits=0 gold=[2344.0, 2682.0]` route=`building_place_count`
- `Q221` 남구 건물동명에 '상가'가 들어가는 건물 수와 평균 연면적  
  gold=`n=73; avg_gfa=2,129.7754` reason=`scalar-mismatch hits=0 gold=[73.0, 2129.7754]` route=`semantic_plan_aggregate`
- `Q222` 사하구 위반건축물 비율(위반/(위반+N))  
  gold=`pct_violate=1.5357` reason=`scalar-mismatch hits=0 gold=[1.5357]` route=`semantic_plan_aggregate`
- `Q239` 대연동 공동주택 층수 구간별 건수(1-5, 6-10, 11-20, 21+)  
  gold=`1. bin=1-5층, n=1,046 / 2. bin=11-20층, n=37 / 3. bin=21층이상, n=48 / 4. bin=6-10층, n=291` reason=`group-mismatch` route=`d198_value_bins`
- `Q243` 중구 건물 중 높이 있는 건물의 평균·표준편차 높이  
  gold=`n=3,081; avg_h=13.8696; sd_h=9.8622` reason=`scalar-mismatch hits=0 gold=[3081.0, 13.8696, 9.8622]` route=`semantic_plan_aggregate`
- `Q246` 우동 건물 중 높이 50m 이상 비율과 20층 이상 비율  
  gold=`pct_h50=2.3586; pct_fl20=1.7153` reason=`scalar-mismatch hits=0 gold=[50.0, 2.3586, 20.0, 1.7153]` route=`semantic_plan_aggregate`

### ENTITY_SELECTION_ERROR

- `Q223` 금정구 산지 비율(산 / 전체) %  
  gold=`pct_mountain=3.7068` reason=`scalar-mismatch hits=0 gold=[3.7068]` route=`semantic_plan_clarify`
- `Q242` 사상구 공장 구조별 건수와 평균 연면적 상위 6  
  gold=`1. structure=일반철골구조, n=3,063, avg_gfa=587.5672 / 2. structure=철근콘크리트구조, n=1,066, avg_gfa=893.2194 / 3. structure=블록구조, n=290, avg_gfa=189.182 / 4. structure=경량철골구조, n=278, avg_gfa=412.658 / 5. structure=벽돌구조, n=35, avg_gfa=105.9127 / 6. structure=기타조적구조, n=22, avg_gfa=99.1427` reason=`engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.` route=`None`

### RANGE_BOUND_DROPPED

- `Q231` 영도구 15층 이상 건물 중 공동주택 비율 %  
  gold=`pct=91.716` reason=`scalar-mismatch hits=0 gold=[91.716]` route=`semantic_plan_aggregate`
- `Q238` 장림동 공장 중 연면적 1000㎡ 이상 비율 %  
  gold=`pct=24.7444` reason=`scalar-mismatch hits=0 gold=[24.7444]` route=`semantic_plan_aggregate`
