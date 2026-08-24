# 500문항 실패 원인 진단

- 시각: 2026-08-25 08:20:52
- 현재: 7/23 (30.4%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 9
- `ENTITY_SELECTION_ERROR`: 4
- `RANGE_BOUND_DROPPED`: 3

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `Q307` 동래구 부속건축물 채수와 주건축물 채수  
  gold=`annex_n=109; main_n=18,039` reason=`compare-num-missing` route=`d198_attr_count`
- `Q319` 동래구 공공용 건물 이름과 주요용도  
  gold=`1. name=동래전화국, A25=방송통신시설, A4=부산광역시 동래구 명륜동 / 2. name=안락동 한국전력공사, A25=업무시설, A4=부산광역시 동래구 안락동 / 3. name=부산지방기상청, A25=업무시설, A4=부산광역시 동래구 명륜동 / 4. name=없음, A25=방송통신시설, A4=부산광역시 동래구 온천동 / 5. name=내성초등학교 강당동, A25=업무시설, A4=부산광역시 동래구 복천동 / 6. name=동래교육지원청, A25=업무시설, A4=부산광역시 동래구 복천동` reason=`list-top-missing 동래전화국` route=`usage_overview`
- `Q323` 동래구 사직동 상업용 중 허가 1990년대인 채수  
  gold=`163채` reason=`count-mismatch gold=163 pred=[174.0, 174.0]` route=`semantic_plan_count`
- `Q324` 금정구 장전동 문교사회용 건물연면적 합계  
  gold=`n=160; sum_gfa=559,127.324` reason=`scalar-mismatch hits=1 gold=[160.0, 559127.324]` route=`semantic_plan_aggregate`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[94.0, 94.0]` route=`d198_attr_count`
- `Q329` 동래구 집합 vs 일반건축물 평균 건물높이  
  gold=`jibhap_h=18.2192; general_h=6.0094; jibhap_n=2,592; general_n=15,556` reason=`compare-num-missing` route=`semantic_plan_aggregate`
- `Q334` 금정구 주거용 대비 상업용 건수 비  
  gold=`commercial_per_resi=0.2951; resi_n=15,942; com_n=4,705` reason=`compare-num-missing` route=`semantic_plan_count`
- `Q337` 동래구 명장동 다가구주택 평균 건물건축면적과 건수  
  gold=`n=524; avg_bldg_area=87.5702` reason=`scalar-mismatch hits=1 gold=[524.0, 87.5702]` route=`semantic_plan_aggregate`

### RANGE_BOUND_DROPPED

- `Q311` 동래구 허가일과 사용승인일 연도 차이가 3년 이상인 집합건축물 채수  
  gold=`360채` reason=`count-mismatch gold=360 pred=[18014.0, 18014.0]` route=`semantic_plan_count`
- `Q317` 동래구 학원(세부용도) 중 건물대지면적 200㎡ 이상인 채수  
  gold=`153채` reason=`count-mismatch gold=153 pred=[200.0, 154.0, 154.0]` route=`d198_attr_count`
- `Q330` 금정구 허가일과 사용승인일의 연도 차이가 5년 이상인 건물 수  
  gold=`278채` reason=`count-mismatch gold=278 pred=[20716.0, 20716.0]` route=`semantic_plan_count`

### ENTITY_SELECTION_ERROR

- `Q312` 금정구 사용승인이 2000년 이후인 아파트(세부용도) 채수  
  gold=`400채` reason=`count-mismatch gold=400 pred=[]` route=`semantic_plan_clarify`
- `Q322` 금정구 구서동 아파트(세부용도) 평균 건물높이와 건수  
  gold=`n=235; avg_h=38.1403` reason=`scalar-mismatch hits=0 gold=[235.0, 38.1403]` route=`semantic_plan_clarify`
- `Q328` 금정구 남산동 단독주택(세부용도) 중 지어진지 30년 넘은 채수(사용승인 기준)  
  gold=`648채` reason=`count-mismatch gold=648 pred=[]` route=`semantic_plan_clarify`
- `Q374` 동래구 명장동 vs 안락동 다세대·다가구(D198 세부용도) 채수  
  gold=`myeongjang_n=704; allak_n=743` reason=`compare-num-missing` route=`semantic_plan_clarify`
