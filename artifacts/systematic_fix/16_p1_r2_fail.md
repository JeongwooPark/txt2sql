# 500문항 실패 원인 진단

- 시각: 2026-08-25 02:01:50
- 현재: 13/23 (56.5%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 6
- `ENTITY_SELECTION_ERROR`: 2
- `FOLLOWUP_CONTEXT_LOST`: 2
- `RANGE_BOUND_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q206` 동래구 위반건축물이면서 지어진지 30년 넘은 단독주택 채수  
  gold=`151채` reason=`count-mismatch gold=151 pred=[148.0, 148.0]` route=`semantic_plan_count`
- `Q449` 영도구 지어진지 25년 넘은 공동주택 채수  
  gold=`610채` reason=`count-mismatch gold=610 pred=[593.0, 593.0]` route=`semantic_plan_count`
- `Q451` 평균 연면적  
  gold=`avg_gfa=11,510.4952; n=115` reason=`scalar-mismatch hits=1 gold=[11510.4952, 115.0]` route=`semantic_plan_aggregate`
- `Q495` 법정동별 건수  
  gold=`1. dong=부산광역시 기장군 정관읍 모전리, n=64 / 2. dong=부산광역시 기장군 정관읍 달산리, n=23 / 3. dong=부산광역시 기장군 정관읍 용수리, n=19 / 4. dong=부산광역시 기장군 정관읍 매학리, n=16 / 5. dong=부산광역시 기장군 일광읍 삼성리, n=15 / 6. dong=부산광역시 기장군 철마면 고촌리, n=12 / 7. dong=부산광역시 기장군 기장읍 교리, n=10 / 8. dong=부산광역시 기장군 정관읍 방곡리, n=7 / 9. dong=부산광역시 기장군 일광읍 이천리, n=5 / 10. dong=부산광역시 기장군 기장읍 대라리, n=5 / 11. dong=부산광역시 기장군 기장읍 청강리, n=3 / 12. dong=부산광역시 기장군 정관읍 예림리, n=1` reason=`group-mismatch` route=`semantic_plan_count`
- `Q496` 가장 높은 건물 이름과 법정동  
  gold=`A24=가화 일광타워; A4=부산광역시 기장군 일광읍 이천리; A16=95.05; A26=33` reason=`scalar-mismatch hits=1 gold=[24.0, 4.0, 16.0, 95.05]` route=`semantic_plan_rank`

### ENTITY_SELECTION_ERROR

- `Q372` 금정구 사용승인 연도 구간별 공동주택 수(1970s~2010s)  
  gold=`1. decade=1,970, n=157 / 2. decade=1,980, n=352 / 3. decade=1,990, n=795 / 4. decade=2,000, n=796 / 5. decade=2,010, n=595` reason=`group-mismatch` route=`semantic_plan_clarify`
- `Q452` 가장 오래된(사용승인 빠른) 건물명과 사용승인일  
  gold=`A24=대동대교맨션아파트; A13=1980-08-30; A4=부산광역시 영도구 대평동1가` reason=`name-missing 대동대교맨션아파트` route=`semantic_plan_clarify`

### FOLLOWUP_CONTEXT_LOST

- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[113.0, 113.0]` route=`semantic_plan_count`
- `Q494` 그중 15층 이상만  
  gold=`180채` reason=`count-mismatch gold=180 pred=[2010.0, 15.0, 406.0, 406.0]` route=`semantic_plan_count`

### RANGE_BOUND_DROPPED

- `Q494` 그중 15층 이상만  
  gold=`180채` reason=`count-mismatch gold=180 pred=[2010.0, 15.0, 406.0, 406.0]` route=`semantic_plan_count`
