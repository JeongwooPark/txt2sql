# 500문항 실패 원인 진단

- 시각: 2026-08-25 03:07:18
- 현재: 4/38 (10.5%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 20
- `RANGE_BOUND_DROPPED`: 7
- `ENTITY_SELECTION_ERROR`: 6
- `FOLLOWUP_CONTEXT_LOST`: 3
- `BOOLEAN_OR_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### RANGE_BOUND_DROPPED

- `Q302` 금정구 집합건축물 중 세부용도가 아파트이고 지상 15층 이상인 채수  
  gold=`337채` reason=`count-mismatch gold=337 pred=[15.0, 713.0, 713.0]` route=`d198_attr_count`
- `Q309` 동래구 표제부 중 용적율 200% 이상인 공동주택(주요용도) 채수  
  gold=`936채` reason=`engine-fail:- 동래구 "주요용도명" kinds/count must use "AL_D198_26260_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q311` 동래구 허가일과 사용승인일 연도 차이가 3년 이상인 집합건축물 채수  
  gold=`360채` reason=`count-mismatch gold=360 pred=[3.0, 19645.0, 19645.0]` route=`d010_attr_count`
- `Q317` 동래구 학원(세부용도) 중 건물대지면적 200㎡ 이상인 채수  
  gold=`153채` reason=`count-mismatch gold=153 pred=[200.0, 154.0, 154.0]` route=`d198_attr_count`
- `Q321` 동래구 온천동 집합건축물 중 지상 10층 이상인 채수  
  gold=`231채` reason=`count-mismatch gold=231 pred=[10.0, 943.0, 943.0]` route=`d198_attr_count`
- `Q332` 금정구 철근콘크리트 구조이면서 주요용도가 공동주택이고 15층 이상인 채수  
  gold=`338채` reason=`engine-fail:- 금정구 "주요용도명" kinds/count must use "AL_D198_26410_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 2013.0, 4.0]` route=`d198_attr_list`

### PREDICATE_DROPPED

- `Q306` 금정구 문교사회용 건물 수와 평균 건물연면적  
  gold=`n=780; avg_gfa=2,113.5119` reason=`scalar-mismatch hits=1 gold=[780.0, 2113.5119]` route=`semantic_plan_aggregate`
- `Q307` 동래구 부속건축물 채수와 주건축물 채수  
  gold=`annex_n=109; main_n=18,039` reason=`compare-num-missing` route=`d198_attr_count`
- `Q308` 금정구 일반건축물대장 중 건폐율 50% 이상 80% 이하인 채수  
  gold=`4,536채` reason=`count-mismatch gold=4536 pred=[6163.0, 6163.0]` route=`semantic_plan_count`
- `Q310` 금정구 오피스텔(세부용도) 이름과 지상층·건물높이  
  gold=`1. name=한진스카이뷰, A4=부산광역시 금정구 구서동, fl=21, h=75.1 / 2. name=장전동 현대성우오스타 오피스텔, A4=부산광역시 금정구 장전동, fl=22, h=71.99 / 3. name=온천장역 삼정 그린코아, A4=부산광역시 금정구 장전동, fl=22, h=67.95 / 4. name=인스타, A4=부산광역시 금정구 서동, fl=15, h=56.3 / 5. name=로얄캐슬, A4=부산광역시 금정구 구서동, fl=15, h=54.9 / 6. name=구서동센트리움, A4=부산광역시 금정구 구서동, fl=15, h=54.3 / 7. name=여전씨티빌, A4=부산광역시 금정구 구서동, fl=14, h=52 / 8. name=애플타워, A4=부산광역시 금정구 부곡동, fl=14, h=47.68 / 9. name=메트로폴리스9, A4=부산광역시 금정구 서동, fl=14, h=45.29 / 10. name=플러스 하이빌, A4=부산광역시 금정구 부곡동, fl=15, h=44 / 11. name=없음, A4=부산광역시 금정구 구서동, fl=14, h=44 / 12. name=까사펠리체 장전, A4=부산광역시 금정구 장전동, fl=14, h=44 / 13. name=우성 더리치, A4=부산광역시 금정구 서동, fl=14, h=43.8 / 14. name=남산동 효산 벨루스, A4=부산광역시 금정구 남산동, fl=14, h=43.7 / 15. name=티아이더코어, A4=부산광역시 금정구 부곡동, fl=14, h=43.15` reason=`list-top-missing 한진스카이뷰` route=`building_name_lookup`
- `Q312` 금정구 사용승인이 2000년 이후인 아파트(세부용도) 채수  
  gold=`400채` reason=`count-mismatch gold=400 pred=[2000.0, 713.0, 713.0]` route=`d198_attr_count`
- `Q319` 동래구 공공용 건물 이름과 주요용도  
  gold=`1. name=동래전화국, A25=방송통신시설, A4=부산광역시 동래구 명륜동 / 2. name=안락동 한국전력공사, A25=업무시설, A4=부산광역시 동래구 안락동 / 3. name=부산지방기상청, A25=업무시설, A4=부산광역시 동래구 명륜동 / 4. name=없음, A25=방송통신시설, A4=부산광역시 동래구 온천동 / 5. name=내성초등학교 강당동, A25=업무시설, A4=부산광역시 동래구 복천동 / 6. name=동래교육지원청, A25=업무시설, A4=부산광역시 동래구 복천동` reason=`list-top-missing 동래전화국` route=`building_name_lookup`
- `Q322` 금정구 구서동 아파트(세부용도) 평균 건물높이와 건수  
  gold=`n=235; avg_h=38.1403` reason=`scalar-mismatch hits=0 gold=[235.0, 38.1403]` route=`semantic_plan_aggregate`
- `Q323` 동래구 사직동 상업용 중 허가 1990년대인 채수  
  gold=`163채` reason=`count-mismatch gold=163 pred=[1990.0, 4374.0, 4374.0]` route=`building_place_count`

### ENTITY_SELECTION_ERROR

- `Q309` 동래구 표제부 중 용적율 200% 이상인 공동주택(주요용도) 채수  
  gold=`936채` reason=`engine-fail:- 동래구 "주요용도명" kinds/count must use "AL_D198_26260_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q315` 동래구 주요용도별 건수 상위 8  
  gold=`1. usage=단독주택, n=10,301 / 2. usage=제2종근린생활시설, n=2,572 / 3. usage=공동주택, n=2,268 / 4. usage=제1종근린생활시설, n=1,712 / 5. usage=교육연구시설, n=247 / 6. usage=업무시설, n=205 / 7. usage=숙박시설, n=146 / 8. usage=창고시설, n=127` reason=`engine-fail:- 동래구 "주요용도명" kinds/count must use "AL_D198_26260_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`
- `Q332` 금정구 철근콘크리트 구조이면서 주요용도가 공동주택이고 15층 이상인 채수  
  gold=`338채` reason=`engine-fail:- 금정구 "주요용도명" kinds/count must use "AL_D198_26410_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q475` 세부용도 상위 5  
  gold=`1. detail=오피스텔, n=90 / 2. detail=사무소, n=39 / 3. detail=의원, n=38 / 4. detail=여관, n=32 / 5. detail=일반음식점, n=16` reason=`group-mismatch` route=`semantic_plan_clarify`
- `Q476` 가장 높은 건물명  
  gold=`name=없음; h=173.5; A27=오피스텔` reason=`scalar-mismatch hits=0 gold=[173.5, 27.0]` route=`semantic_plan_clarify`

### BOOLEAN_OR_DROPPED

- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`

### FOLLOWUP_CONTEXT_LOST

- `Q422` 그중 주요용도가 공동주택인 것만  
  gold=`405채` reason=`count-mismatch gold=405 pred=[408.0, 408.0]` route=`semantic_plan_count`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[324.0, 324.0]` route=`semantic_plan_count`
- `Q474` 그중 건물높이 15m 이상만  
  gold=`313채` reason=`count-mismatch gold=313 pred=[100.0, 1.0, 112.0, -5.0, 17.6, 2.0]` route=`semantic_plan_list`
