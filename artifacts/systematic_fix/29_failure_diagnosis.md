# 500문항 실패 원인 진단

- 시각: 2026-08-25 08:38:45
- 현재: 392/500 (78.4%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 67
- `ENTITY_SELECTION_ERROR`: 27
- `FOLLOWUP_CONTEXT_LOST`: 8
- `RANGE_BOUND_DROPPED`: 7
- `SPATIAL_TARGET_DROPPED`: 1
- `EXECUTION_TIMEOUT`: 1

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`meta_column_display`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `Q223` 금정구 산지 비율(산 / 전체) %  
  gold=`pct_mountain=3.7068` reason=`scalar-mismatch hits=0 gold=[3.7068]` route=`semantic_plan_clarify`
- `Q242` 사상구 공장 구조별 건수와 평균 연면적 상위 6  
  gold=`1. structure=일반철골구조, n=3,063, avg_gfa=587.5672 / 2. structure=철근콘크리트구조, n=1,066, avg_gfa=893.2194 / 3. structure=블록구조, n=290, avg_gfa=189.182 / 4. structure=경량철골구조, n=278, avg_gfa=412.658 / 5. structure=벽돌구조, n=35, avg_gfa=105.9127 / 6. structure=기타조적구조, n=22, avg_gfa=99.1427` reason=`engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.` route=`None`
- `Q244` 서구 공동주택 연면적 합계가 단독주택 연면적 합계보다 얼마나 큰가  
  gold=`apt_sum=1,953,917.88; detached_sum=819,131.1875; diff_sum=1,134,786.6925` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q245` 동구 용도 종류 수(distinct A9)와 가장 많은 용도 건수  
  gold=`n_usage=27; max_usage_n=9,360` reason=`scalar-mismatch hits=0 gold=[27.0, 9360.0]` route=`semantic_plan_clarify`
- `Q255` 금정구 2000년 이후 사용승인 공동주택 평균 층수가 1990년대보다 얼마나 높은가  
  gold=`avg_fl_2000=7.6913; avg_fl_1990s=6.4428; diff_fl=1.2486` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q257` 해운대구 아파트 중 높이 결측 비율 %  
  gold=`pct_null_h=0` reason=`scalar-mismatch hits=0 gold=[0.0]` route=`semantic_plan_clarify`

### PREDICATE_DROPPED

- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`scalar-mismatch hits=1 gold=[197.0, 24.0, 4.0]` route=`semantic_plan_list`
- `N097` 안락동에서 지어진지 30년 넘은 건물은 몇 채야?  
  gold=`3,021채` reason=`count-mismatch gold=3021 pred=[3004.0, 3004.0]` route=`semantic_plan_count`
- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q151` 연제구에서 공동주택 또는 단독주택이면서 높이 20m 이상인 건물 수  
  gold=`449채` reason=`count-mismatch gold=449 pred=[447.0, 447.0]` route=`semantic_plan_count`
- `Q156` 동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수  
  gold=`98채` reason=`count-mismatch gold=98 pred=[91.0, 91.0]` route=`semantic_plan_count`
- `Q158` 강서구 공장·창고를 제외한 건물 중 연면적 5000㎡ 이상인 채수  
  gold=`244채` reason=`count-mismatch gold=244 pred=[23.0, 23.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1035.0, 1035.0]` route=`semantic_plan_count`
- `Q171` 수영구에서 공동주택·단독주택을 제외한 높이 35m 이상 건물 수  
  gold=`100채` reason=`count-mismatch gold=100 pred=[94.0, 94.0]` route=`semantic_plan_count`

### RANGE_BOUND_DROPPED

- `Q231` 영도구 15층 이상 건물 중 공동주택 비율 %  
  gold=`pct=91.716` reason=`scalar-mismatch hits=0 gold=[91.716]` route=`semantic_plan_aggregate`
- `Q238` 장림동 공장 중 연면적 1000㎡ 이상 비율 %  
  gold=`pct=24.7444` reason=`scalar-mismatch hits=0 gold=[24.7444]` route=`semantic_plan_aggregate`
- `Q267` 구서1동 안에 있는 공동주택 중 지상 15층 이상인 이름과 층수  
  gold=`1. A24=구서동 유림 노르웨이 아침, A26=32, A16=99.3, A14=43,452.52 / 2. A24=금강부광아파트, A26=26, A16=69.8, A14=27,618.374 / 3. A24=금강부광아파트, A26=26, A16=69.8, A14=27,390.646 / 4. A24=구서벽산메가트리움, A26=26, A16=79.2, A14=20,460.11 / 5. A24=구서시티타워, A26=25, A16=79.7, A14=26,139.023 / 6. A24=구서동 쌍용예가, A26=25, A16=73.6, A14=11,958.3765 / 7. A24=구서동 쌍용예가, A26=25, A16=70.8, A14=14,331.744 / 8. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=11,426.6965 / 9. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=12,301.6763 / 10. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=11,251.2689 / 11. A24=구서동 쌍용예가, A26=22, A16=62.4, A14=12,259.7756 / 12. A24=구서동 쌍용예가, A26=22, A16=62.4, A14=7,158.7122 / 13. A24=경보아파트, A26=22, A16=59.2, A14=21,742.92 / 14. A24=구서동 쌍용예가, A26=21, A16=59.6, A14=12,840.8016 / 15. A24=구서동 쌍용예가, A26=21, A16=59.6, A14=10,187.3876` reason=`list-top-missing 구서동 유림 노르웨이 아침` route=`semantic_plan_list`
- `Q317` 동래구 학원(세부용도) 중 건물대지면적 200㎡ 이상인 채수  
  gold=`153채` reason=`count-mismatch gold=153 pred=[200.0, 154.0, 154.0]` route=`d198_attr_count`
- `Q358` 금정구 단독주택 경과 40년 이상 vs 10년 미만 채수  
  gold=`old40=6,495; young10=327` reason=`compare-num-missing` route=`semantic_plan_count`
- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 2004.0, 12.0]` route=`d198_attr_list`
- `Q481` 전포동 제2종근린생활시설 중 연면적 400㎡ 이상  
  gold=`181채` reason=`count-mismatch gold=181 pred=[100.0, 1.0, 337.0, -8.0, 2.0, 307.0]` route=`semantic_plan_list`

### SPATIAL_TARGET_DROPPED

- `Q251` 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)  
  gold=`pct=42.1833` reason=`scalar-mismatch hits=0 gold=[42.1833]` route=`semantic_plan_aggregate`

### FOLLOWUP_CONTEXT_LOST

- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=0 gold=[248.0, 70.2789]` route=`semantic_plan_aggregate`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[380.0, 380.0]` route=`semantic_plan_count`
- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[114.0, 114.0]` route=`semantic_plan_count`
- `Q458` 그중 공동주택 또는 숙박시설만  
  gold=`3채` reason=`count-mismatch gold=3 pred=[2.0, 2.0]` route=`semantic_plan_count`
- `Q474` 그중 건물높이 15m 이상만  
  gold=`313채` reason=`count-mismatch gold=313 pred=[100.0, 1.0, 256.0, 17.2, 2.0, 60.0]` route=`semantic_plan_list`
- `Q478` 그중 연면적 6000㎡ 이상만  
  gold=`362채` reason=`count-mismatch gold=362 pred=[1.0, 2077.0, 2.0, 334.0, 1.0, 1.0]` route=`clarify_place`
- `Q490` 그중 이동사유가 최초생성인 것만  
  gold=`29개` reason=`engine-fail:ReadTimeout: timed out` route=`None`

### EXECUTION_TIMEOUT

- `Q490` 그중 이동사유가 최초생성인 것만  
  gold=`29개` reason=`engine-fail:ReadTimeout: timed out` route=`None`
