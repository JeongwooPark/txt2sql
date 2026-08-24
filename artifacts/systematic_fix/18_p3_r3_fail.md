# 500문항 실패 원인 진단

- 시각: 2026-08-25 02:54:32
- 현재: 58/124 (46.8%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 37
- `FOLLOWUP_CONTEXT_LOST`: 13
- `ENTITY_SELECTION_ERROR`: 10
- `RANGE_BOUND_DROPPED`: 7

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

- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`count-mismatch gold=360 pred=[361.0, 361.0]` route=`semantic_plan_count`
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

### RANGE_BOUND_DROPPED

- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 34.0, 2013.0]` route=`d198_attr_list`
- `Q437` 연제구 공동주택 중 건폐율 30% 이상  
  gold=`1,139채` reason=`count-mismatch gold=1139 pred=[100.0, 1.0, 1503.0, -34.0, 2.0, 894.0]` route=`semantic_plan_list`
- `Q441` 해운대구 지하 2층 이상 건물 채수  
  gold=`389채` reason=`count-mismatch gold=389 pred=[15655.0, 15655.0]` route=`building_floor_count`
- `Q445` 북구 교육연구시설 중 대지면적 1500㎡ 이상  
  gold=`1. A24=부산과학기술대학교, A15=97,998, A16=31.85, A4=부산광역시 북구 구포동 / 2. A24=부산과학기술대학교, A15=97,998, A16=18.85, A4=부산광역시 북구 구포동 / 3. A24=부산과학기술대학교, A15=97,998, A16=19.5, A4=부산광역시 북구 구포동 / 4. A24=부산광역시 건설기술교육원, A15=57,142, A16=15.9, A4=부산광역시 북구 덕천동 / 5. A24=한국폴리텍대학 부산캠퍼스, A15=56,788, A16=11.2, A4=부산광역시 북구 덕천동 / 6. A24=신천초등학교 다목적강당, A15=30,886, A16=16.56, A4=부산광역시 북구 구포동 / 7. A24=신천초등학교, A15=30,886, A16=21, A4=부산광역시 북구 구포동 / 8. A24=백양초등학교, A15=26,593.9, A16=22.3, A4=부산광역시 북구 만덕동 / 9. A24=경혜여자고등학교, A15=25,974, A16=21.7, A4=부산광역시 북구 구포동 / 10. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=10, A4=부산광역시 북구 금곡동 / 11. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=43.2, A4=부산광역시 북구 금곡동 / 12. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=5.65, A4=부산광역시 북구 금곡동 / 13. A24=성도고등학교, A15=23,657, A16=0, A4=부산광역시 북구 구포동 / 14. A24=만덕초등학교, A15=20,459, A16=13.65, A4=부산광역시 북구 만덕동 / 15. A24=양천초등학교, A15=20,414, A16=18.15, A4=부산광역시 북구 덕천동` reason=`list-top-missing 부산과학기술대학교` route=`building_area_threshold_count`
- `Q461` 대연동 연면적 4000㎡ 이상 공동주택  
  gold=`1. A24=대연극동아파트, A14=46,326.96, A26=25, A16=67.6 / 2. A24=리마크빌 대연, A14=41,046.41, A26=20, A16=65.27 / 3. A24=삼성아파트, A14=29,899.51, A26=25, A16=68.88 / 4. A24=대우그린2차아파트, A14=27,880.9, A26=24, A16=66 / 5. A24=대연 힐스테이트푸르지오, A14=27,871.7, A26=38, A16=111.5 / 6. A24=대연 힐스테이트푸르지오, A14=27,789.3, A26=38, A16=111.5 / 7. A24=장백장미타워, A14=26,447.5, A26=25, A16=69.9 / 8. A24=대연2차동원로얄듀크, A14=24,498.528, A26=25, A16=67.8 / 9. A24=대연동동일스위트, A14=23,591.96, A26=20, A16=78.4 / 10. A24=대연 힐스테이트푸르지오, A14=23,293.68, A26=35, A16=102.15 / 11. A24=대연 힐스테이트푸르지오, A14=23,124.27, A26=35, A16=102.15 / 12. A24=대연 힐스테이트푸르지오, A14=23,103.51, A26=35, A16=102.15 / 13. A24=대연 힐스테이트푸르지오, A14=22,706.3, A26=38, A16=111.5 / 14. A24=대연 힐스테이트푸르지오, A14=22,143.02, A26=36, A16=105 / 15. A24=대연 힐스테이트푸르지오, A14=22,126.48, A26=36, A16=105` reason=`list-top-missing 대연극동아파트` route=`building_area_threshold_count`
- `Q489` 남구 기초구역 중 면적(BAS_AR) 0.2 이상 개수  
  gold=`32개` reason=`count-mismatch gold=32 pred=[0.2, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`
- `Q497` 서구 의료시설 중 연면적 1500㎡ 이상  
  gold=`1. A24=동아대학교 의료원, A14=58,753.15, A16=48.1, A4=부산광역시 서구 동대신동3가 / 2. A24=부산대학교병원 본관, A14=26,399.08, A16=38.5, A4=부산광역시 서구 아미동1가 / 3. A24=종합의료시설, A14=18,737.52, A16=43.2, A4=부산광역시 서구 동대신동3가 / 4. A24=대신병원, A14=15,020.64, A16=44.26, A4=부산광역시 서구 동대신동3가 / 5. A24=종합의료시설, A14=13,390.54, A16=43.8, A4=부산광역시 서구 동대신동3가 / 6. A24=종합의료시설, A14=13,032.381, A16=10.86, A4=부산광역시 서구 동대신동3가 / 7. A24=부산대학교병원, A14=11,359.89, A16=41.4, A4=부산광역시 서구 아미동1가 / 8. A24=부산지역 암센터, A14=11,359.89, A16=41.4, A4=부산광역시 서구 아미동2가 / 9. A24=없음, A14=10,436.605, A16=24.7, A4=부산광역시 서구 암남동 / 10. A24=없음, A14=8,104.89, A16=0, A4=부산광역시 서구 암남동 / 11. A24=삼육부산병원, A14=7,153.555, A16=40.4, A4=부산광역시 서구 서대신동2가 / 12. A24=바른빌딩, A14=6,139.62, A16=47.9, A4=부산광역시 서구 충무동1가 / 13. A24=삼육부산병원, A14=4,941.35, A16=23.9, A4=부산광역시 서구 서대신동2가 / 14. A24=이동, A14=4,705.97, A16=11.2, A4=부산광역시 서구 동대신동3가 / 15. A24=없음, A14=4,222.44, A16=17.8, A4=부산광역시 서구 아미동2가` reason=`list-top-missing 동아대학교 의료원` route=`building_area_threshold_count`

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
