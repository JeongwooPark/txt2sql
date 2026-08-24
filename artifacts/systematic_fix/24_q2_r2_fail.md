# 500문항 실패 원인 진단

- 시각: 2026-08-25 07:41:54
- 현재: 49/106 (46.2%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 34
- `FOLLOWUP_CONTEXT_LOST`: 11
- `ENTITY_SELECTION_ERROR`: 10
- `RANGE_BOUND_DROPPED`: 3

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`scalar-mismatch hits=1 gold=[197.0, 24.0, 4.0]` route=`semantic_plan_list`
- `Q391` 그 집합의 평균 층수  
  gold=`n=265; avg_fl=19.3132` reason=`scalar-mismatch hits=0 gold=[265.0, 19.3132]` route=`semantic_plan_aggregate`
- `Q392` 층수가 가장 많은 건물 이름  
  gold=`A24=부곡동 푸르지오; A4=부산광역시 금정구 부곡동; A26=43; A16=131.2` reason=`scalar-mismatch hits=1 gold=[24.0, 4.0, 26.0, 43.0]` route=`semantic_plan_rank`
- `Q399` 그 공장들 평균 연면적  
  gold=`n=360; avg_gfa=8,261.8981` reason=`scalar-mismatch hits=0 gold=[360.0, 8261.8981]` route=`semantic_plan_aggregate`
- `Q400` 연면적이 가장 큰 공장 이름  
  gold=`A24=르노코리아자동차(주); A4=부산광역시 강서구 신호동; A14=74,540.74` reason=`name-missing 르노코리아자동차(주)` route=`semantic_plan_rank`
- `Q404` 가장 높은 것의 이름과 층수  
  gold=`A24=오륙도 에스케이뷰 아파트; A4=부산광역시 남구 용호동; A16=141.79; A26=47` reason=`name-missing 오륙도 에스케이뷰 아파트` route=`semantic_plan_rank`
- `Q408` 남은 건물 평균 연면적  
  gold=`avg_gfa=5,399.9514; n=14` reason=`scalar-mismatch hits=0 gold=[5399.9514, 14.0]` route=`semantic_plan_aggregate`
- `Q412` 연면적 합계  
  gold=`sum_gfa=200,589.738; n=50` reason=`scalar-mismatch hits=0 gold=[200589.738, 50.0]` route=`semantic_plan_aggregate`

### FOLLOWUP_CONTEXT_LOST

- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=0 gold=[248.0, 70.2789]` route=`semantic_plan_aggregate`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q410` 그중 철골구조만  
  gold=`50채` reason=`count-mismatch gold=50 pred=[47.0, 47.0]` route=`semantic_plan_count`
- `Q422` 그중 주요용도가 공동주택인 것만  
  gold=`405채` reason=`count-mismatch gold=405 pred=[408.0, 408.0]` route=`semantic_plan_count`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[324.0, 324.0]` route=`semantic_plan_count`
- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[114.0, 114.0]` route=`semantic_plan_count`
- `Q458` 그중 공동주택 또는 숙박시설만  
  gold=`3채` reason=`count-mismatch gold=3 pred=[2.0, 2.0]` route=`semantic_plan_count`
- `Q474` 그중 건물높이 15m 이상만  
  gold=`313채` reason=`count-mismatch gold=313 pred=[100.0, 1.0, 16.0, -7.0, 829.0, -5.0]` route=`semantic_plan_list`

### RANGE_BOUND_DROPPED

- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 2004.0, 12.0]` route=`d198_attr_list`
- `Q481` 전포동 제2종근린생활시설 중 연면적 400㎡ 이상  
  gold=`181채` reason=`count-mismatch gold=181 pred=[100.0, 1.0, 337.0, -8.0, 2.0, 307.0]` route=`semantic_plan_list`
- `Q489` 남구 기초구역 중 면적(BAS_AR) 0.2 이상 개수  
  gold=`32개` reason=`count-mismatch gold=32 pred=[0.2, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`

### ENTITY_SELECTION_ERROR

- `Q431` 용도별 건수 상위 6  
  gold=`1. usage=제2종근린생활시설, n=37 / 2. usage=공동주택, n=29 / 3. usage=제1종근린생활시설, n=26 / 4. usage=숙박시설, n=10 / 5. usage=교육연구시설, n=7 / 6. usage=업무시설, n=4` reason=`group-mismatch` route=`semantic_plan_clarify`
- `Q432` 연면적이 가장 큰 위반건축물 이름·용도  
  gold=`A24=대원플러스빌; A9=공동주택; A14=9,535.751; A4=부산광역시 부산진구 양정동` reason=`name-missing 대원플러스빌` route=`semantic_plan_clarify`
- `Q475` 세부용도 상위 5  
  gold=`1. detail=오피스텔, n=90 / 2. detail=사무소, n=39 / 3. detail=의원, n=38 / 4. detail=여관, n=32 / 5. detail=일반음식점, n=16` reason=`group-mismatch` route=`semantic_plan_clarify`
- `Q476` 가장 높은 건물명  
  gold=`name=없음; h=173.5; A27=오피스텔` reason=`scalar-mismatch hits=0 gold=[173.5, 27.0]` route=`semantic_plan_clarify`
- `Q477` 좌동 15층 이상 공동주택 이름과 층수  
  gold=`1. A24=해운대케이씨씨스위첸, A26=29, A16=88, A14=19,371.657 / 2. A24=해운대케이씨씨스위첸, A26=29, A16=88, A14=18,715.551 / 3. A24=해운대케이씨씨스위첸, A26=28, A16=87.7, A14=16,346.842 / 4. A24=대우2차, A26=27, A16=74.1, A14=12,575.496 / 5. A24=대우2차, A26=27, A16=74.1, A14=11,215.744 / 6. A24=대우2차, A26=27, A16=74.1, A14=13,024.212 / 7. A24=두산1차아파트, A26=27, A16=74.9, A14=16,001.8 / 8. A24=대우2차, A26=27, A16=74.1, A14=8,391.824 / 9. A24=대우2차, A26=27, A16=74.1, A14=8,391.824 / 10. A24=대우2차, A26=27, A16=74.1, A14=9,549.344 / 11. A24=두산1차아파트, A26=27, A16=74.9, A14=16,001.8 / 12. A24=두산1차아파트, A26=27, A16=74.9, A14=16,001.8 / 13. A24=대우2차, A26=27, A16=74.1, A14=9,549.344 / 14. A24=대림아파트, A26=26, A16=71.65, A14=11,401.212 / 15. A24=한라아파트, A26=26, A16=0, A14=10,558.56` reason=`list-top-missing 해운대케이씨씨스위첸` route=`clarify_place`
- `Q478` 그중 연면적 6000㎡ 이상만  
  gold=`362채` reason=`count-mismatch gold=362 pred=[1.0, 2077.0, 2.0, 334.0, 1.0, 1.0]` route=`clarify_place`
- `Q479` 평균 높이  
  gold=`avg_h=59.9616; n=362` reason=`scalar-mismatch hits=0 gold=[59.9616, 362.0]` route=`semantic_plan_clarify`
- `Q480` 지번 알려줘(연면적 1위)  
  gold=`A24=경남선경아파트; A5=1448; A4=부산광역시 해운대구 좌동; A14=49,777.696` reason=`name-missing 경남선경아파트` route=`semantic_plan_clarify`
