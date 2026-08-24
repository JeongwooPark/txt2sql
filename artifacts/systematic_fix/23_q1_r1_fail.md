# 500문항 실패 원인 진단

- 시각: 2026-08-25 07:25:35
- 현재: 7/18 (38.9%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `ENTITY_SELECTION_ERROR`: 6
- `PREDICATE_DROPPED`: 3
- `RANGE_BOUND_DROPPED`: 2
- `EXECUTION_TIMEOUT`: 1

## 대표 실패 사례 (원인별 최대 8건)

### EXECUTION_TIMEOUT

- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`timeout>40s` route=`None`

### PREDICATE_DROPPED

- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[162.0, 162.0]` route=`semantic_plan_count`
- `Q274` 사하구 산업단지와 교차하는 기초구역 개수  
  gold=`35개` reason=`count-mismatch gold=35 pred=[162.0, 162.0]` route=`semantic_plan_count`
- `Q288` 모라도시첨단산업단지 안 건물 수와 평균 연면적  
  gold=`n=22; avg_gfa=876.0655` reason=`scalar-mismatch hits=1 gold=[22.0, 876.0655]` route=`semantic_plan_aggregate`

### ENTITY_SELECTION_ERROR

- `Q244` 서구 공동주택 연면적 합계가 단독주택 연면적 합계보다 얼마나 큰가  
  gold=`apt_sum=1,953,917.88; detached_sum=819,131.1875; diff_sum=1,134,786.6925` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q245` 동구 용도 종류 수(distinct A9)와 가장 많은 용도 건수  
  gold=`n_usage=27; max_usage_n=9,360` reason=`scalar-mismatch hits=0 gold=[27.0, 9360.0]` route=`clarify_column`
- `Q255` 금정구 2000년 이후 사용승인 공동주택 평균 층수가 1990년대보다 얼마나 높은가  
  gold=`avg_fl_2000=7.6913; avg_fl_1990s=6.4428; diff_fl=1.2486` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q257` 해운대구 아파트 중 높이 결측 비율 %  
  gold=`pct_null_h=0` reason=`scalar-mismatch hits=0 gold=[0.0]` route=`semantic_plan_clarify`
- `Q273` 센텀2지구 도시첨단산업단지와 교차하는 건물 용도별 건수  
  gold=`1. usage=없음, n=612 / 2. usage=단독주택, n=63 / 3. usage=판매시설, n=18 / 4. usage=제2종근린생활시설, n=9 / 5. usage=제1종근린생활시설, n=7 / 6. usage=창고시설, n=4 / 7. usage=공동주택, n=2 / 8. usage=공장, n=2 / 9. usage=교육연구시설, n=2 / 10. usage=분뇨.쓰레기처리시설, n=2` reason=`engine-fail:heuristic_plan` route=`None`
- `Q300` 명지동 건물 중 산업단지 안에 있으면서 연면적 2000㎡ 이상인 채수  
  gold=`173채` reason=`engine-fail:- EXPLAIN failed: DuplicateAlias: 테이블 이름 "a" 가 한번 이상 명시되어 있습니다.` route=`None`

### RANGE_BOUND_DROPPED

- `Q271` 장림동 산업단지 안 공장 중 연면적 3000㎡ 이상인 채수  
  gold=`35채` reason=`count-mismatch gold=35 pred=[76.0, 76.0]` route=`semantic_plan_count`
- `Q300` 명지동 건물 중 산업단지 안에 있으면서 연면적 2000㎡ 이상인 채수  
  gold=`173채` reason=`engine-fail:- EXPLAIN failed: DuplicateAlias: 테이블 이름 "a" 가 한번 이상 명시되어 있습니다.` route=`None`
