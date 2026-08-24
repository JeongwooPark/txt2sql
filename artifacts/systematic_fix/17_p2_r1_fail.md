# 500문항 실패 원인 진단

- 시각: 2026-08-25 02:15:32
- 현재: 27/92 (29.3%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `ENTITY_SELECTION_ERROR`: 40
- `FOLLOWUP_CONTEXT_LOST`: 14
- `PREDICATE_DROPPED`: 12
- `RANGE_BOUND_DROPPED`: 6
- `BOOLEAN_OR_DROPPED`: 2
- `SPATIAL_TARGET_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 2.0, 3.0, 1.0, 4.0]` route=`semantic_plan_list`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=1 gold=[29.0, 106135.2449]` route=`semantic_plan_aggregate`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[1.0, 1.0, 71.2, 71.2]` route=`semantic_plan_list`
- `Q422` 그중 주요용도가 공동주택인 것만  
  gold=`405채` reason=`count-mismatch gold=405 pred=[25.0, 2268.0, 12.5, 10301.0, 56.8, 2.0]` route=`usage_overview`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[10.0, 2000.0, 2007.0, 8.0, 16.0, 2013.0]` route=`d198_attr_list`

### ENTITY_SELECTION_ERROR

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[]` route=`semantic_plan_clarify`
- `Q188` 부산진구 위반건축물(A20=Y) 중 공동주택은 몇 채야?  
  gold=`44채` reason=`count-mismatch gold=44 pred=[20.0, 10.0, 20.0]` route=`clarify_column`
- `Q237` 광안동 숙박시설 연면적 합계·평균·최대 높이  
  gold=`n=50; sum_gfa=103,761.5099; avg_gfa=2,075.2302; max_h=73.8` reason=`engine-fail:too many aggregations` route=`None`
- `Q244` 서구 공동주택 연면적 합계가 단독주택 연면적 합계보다 얼마나 큰가  
  gold=`apt_sum=1,953,917.88; detached_sum=819,131.1875; diff_sum=1,134,786.6925` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q245` 동구 용도 종류 수(distinct A9)와 가장 많은 용도 건수  
  gold=`n_usage=27; max_usage_n=9,360` reason=`scalar-mismatch hits=0 gold=[27.0, 9360.0]` route=`clarify_column`
- `Q257` 해운대구 아파트 중 높이 결측 비율 %  
  gold=`pct_null_h=0` reason=`scalar-mismatch hits=0 gold=[0.0]` route=`semantic_plan_clarify`

### PREDICATE_DROPPED

- `Q208` 기장군 용적율이 0보다 크고 80% 미만인 공장 채수  
  gold=`593채` reason=`count-mismatch gold=593 pred=[0.0, 0.0]` route=`semantic_plan_count`
- `Q211` 연제구 건폐율이 기록된 공동주택의 평균 건폐율과 건수  
  gold=`n=1,216; avg_cov=59.7314` reason=`scalar-mismatch hits=0 gold=[1216.0, 59.7314]` route=`semantic_plan_aggregate`
- `Q219` 해운대구 공동주택 중 용적율과 건폐율이 모두 있는 건물의 평균 용적율·평균 건폐율  
  gold=`n=2,355; avg_far=247.399; avg_cov=59.3335` reason=`scalar-mismatch hits=0 gold=[2355.0, 247.399, 59.3335]` route=`semantic_plan_aggregate`
- `Q254` 부산 구별 위반건축물 수 상위 8개 구  
  gold=`1. gu_name=강서구, n=1,288 / 2. gu_name=금정구, n=762 / 3. gu_name=사상구, n=716 / 4. gu_name=부산진구, n=652 / 5. gu_name=동래구, n=519 / 6. gu_name=기장군, n=483 / 7. gu_name=해운대구, n=473 / 8. gu_name=남구, n=430` reason=`group-label-missing` route=`semantic_plan_rank`
- `Q399` 그 공장들 평균 연면적  
  gold=`n=360; avg_gfa=8,261.8981` reason=`scalar-mismatch hits=0 gold=[360.0, 8261.8981]` route=`semantic_plan_aggregate`
- `Q449` 영도구 지어진지 25년 넘은 공동주택 채수  
  gold=`610채` reason=`count-mismatch gold=610 pred=[601.0, 601.0]` route=`semantic_plan_count`
- `Q451` 평균 연면적  
  gold=`avg_gfa=11,510.4952; n=115` reason=`scalar-mismatch hits=1 gold=[11510.4952, 115.0]` route=`semantic_plan_aggregate`
- `Q459` 평균 층수  
  gold=`avg_fl=90.3333; n=3` reason=`scalar-mismatch hits=1 gold=[90.3333, 3.0]` route=`semantic_plan_aggregate`

### BOOLEAN_OR_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`

### SPATIAL_TARGET_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`

### RANGE_BOUND_DROPPED

- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 2013.0, 4.0]` route=`d198_attr_list`
- `Q437` 연제구 공동주택 중 건폐율 30% 이상  
  gold=`1,139채` reason=`count-mismatch gold=1139 pred=[100.0, 1.0, 1293.0, -2.0, 2.0, 1050.0]` route=`semantic_plan_list`
- `Q438` 그중 용적율 200% 이상만  
  gold=`769채` reason=`count-mismatch gold=769 pred=[100.0, 1.0, 1876.0, -235.0, 2.0, 676.0]` route=`semantic_plan_list`
- `Q466` 그중 높이 40m 이상만  
  gold=`118채` reason=`count-mismatch gold=118 pred=[40.0, 2000.0, 241.0, 241.0]` route=`d198_attr_count`
- `Q489` 남구 기초구역 중 면적(BAS_AR) 0.2 이상 개수  
  gold=`32개` reason=`count-mismatch gold=32 pred=[0.2, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`
- `Q494` 그중 15층 이상만  
  gold=`180채` reason=`count-mismatch gold=180 pred=[2010.0, 15.0, 406.0, 406.0]` route=`semantic_plan_count`
