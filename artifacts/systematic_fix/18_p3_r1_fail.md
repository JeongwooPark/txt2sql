# 500문항 실패 원인 진단

- 시각: 2026-08-25 02:33:20
- 현재: 43/124 (34.7%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 33
- `ENTITY_SELECTION_ERROR`: 25
- `FOLLOWUP_CONTEXT_LOST`: 20
- `RANGE_BOUND_DROPPED`: 10

## 대표 실패 사례 (원인별 최대 8건)

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 1.0, 2.0, 3.0, 4.0]` route=`semantic_plan_list`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=1 gold=[29.0, 106135.2449]` route=`semantic_plan_aggregate`
- `Q396` 그 중 연면적 합계  
  gold=`sum_gfa=528,749.885; n=44` reason=`scalar-mismatch hits=1 gold=[528749.885, 44.0]` route=`semantic_plan_aggregate`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=1 gold=[248.0, 70.2789]` route=`semantic_plan_aggregate`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[1.0, 1.0, 71.2, 71.2]` route=`semantic_plan_list`

### ENTITY_SELECTION_ERROR

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q388` 연면적이 가장 큰 것의 법정동과 지번  
  gold=`A24=호텔아쿠아펠리스; A4=부산광역시 수영구 광안동; A5=192-5; A14=18,228.2` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q400` 연면적이 가장 큰 공장 이름  
  gold=`A24=르노코리아자동차(주); A4=부산광역시 강서구 신호동; A14=74,540.74` reason=`name-missing 르노코리아자동차(주)` route=`semantic_plan_clarify`
- `Q408` 남은 건물 평균 연면적  
  gold=`avg_gfa=5,399.9514; n=14` reason=`scalar-mismatch hits=0 gold=[5399.9514, 14.0]` route=`semantic_plan_clarify`
- `Q423` 평균 지상층  
  gold=`n=405; avg_fl=18.2667` reason=`scalar-mismatch hits=0 gold=[405.0, 18.2667]` route=`semantic_plan_clarify`
- `Q424` 가장 높은 건물명  
  gold=`name=벽산아스타; h=162.5; A4=부산광역시 동래구 온천동` reason=`name-missing 벽산아스타` route=`semantic_plan_clarify`

### PREDICATE_DROPPED

- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`scalar-mismatch hits=1 gold=[197.0, 24.0, 4.0]` route=`semantic_plan_list`
- `Q391` 그 집합의 평균 층수  
  gold=`n=265; avg_fl=19.3132` reason=`scalar-mismatch hits=1 gold=[265.0, 19.3132]` route=`semantic_plan_count`
- `Q392` 층수가 가장 많은 건물 이름  
  gold=`A24=부곡동 푸르지오; A4=부산광역시 금정구 부곡동; A26=43; A16=131.2` reason=`name-missing 부곡동 푸르지오` route=`building_rank_지상층`
- `Q399` 그 공장들 평균 연면적  
  gold=`n=360; avg_gfa=8,261.8981` reason=`scalar-mismatch hits=0 gold=[360.0, 8261.8981]` route=`semantic_plan_aggregate`
- `Q404` 가장 높은 것의 이름과 층수  
  gold=`A24=오륙도 에스케이뷰 아파트; A4=부산광역시 남구 용호동; A16=141.79; A26=47` reason=`name-missing 오륙도 에스케이뷰 아파트` route=`building_rank_높이`
- `Q412` 연면적 합계  
  gold=`sum_gfa=200,589.738; n=50` reason=`scalar-mismatch hits=0 gold=[200589.738, 50.0]` route=`semantic_plan_aggregate`
- `Q415` 그 아파트들의 평균 층수  
  gold=`avg_fl=45.125; n=24` reason=`scalar-mismatch hits=0 gold=[45.125, 24.0]` route=`semantic_plan_aggregate`
- `Q416` 가장 높은 아파트 지번  
  gold=`A24=해운대 두산위브더제니스; A5=1407; A4=부산광역시 해운대구 우동; A16=299.9` reason=`name-missing 해운대 두산위브더제니스` route=`semantic_plan_rank`

### RANGE_BOUND_DROPPED

- `Q425` 금정구 세부용도 아파트 중 10층 이상  
  gold=`470채` reason=`count-mismatch gold=470 pred=[10.0, 2007.0, 8.0, 16.0, 2013.0, 4.0]` route=`d198_attr_list`
- `Q437` 연제구 공동주택 중 건폐율 30% 이상  
  gold=`1,139채` reason=`count-mismatch gold=1139 pred=[100.0, 1.0, 1827.0, -32.0, 2.0, 588.0]` route=`semantic_plan_list`
- `Q438` 그중 용적율 200% 이상만  
  gold=`769채` reason=`count-mismatch gold=769 pred=[100.0, 1.0, 1876.0, -235.0, 2.0, 676.0]` route=`semantic_plan_list`
- `Q441` 해운대구 지하 2층 이상 건물 채수  
  gold=`389채` reason=`count-mismatch gold=389 pred=[15655.0, 15655.0]` route=`building_floor_count`
- `Q445` 북구 교육연구시설 중 대지면적 1500㎡ 이상  
  gold=`1. A24=부산과학기술대학교, A15=97,998, A16=31.85, A4=부산광역시 북구 구포동 / 2. A24=부산과학기술대학교, A15=97,998, A16=18.85, A4=부산광역시 북구 구포동 / 3. A24=부산과학기술대학교, A15=97,998, A16=19.5, A4=부산광역시 북구 구포동 / 4. A24=부산광역시 건설기술교육원, A15=57,142, A16=15.9, A4=부산광역시 북구 덕천동 / 5. A24=한국폴리텍대학 부산캠퍼스, A15=56,788, A16=11.2, A4=부산광역시 북구 덕천동 / 6. A24=신천초등학교 다목적강당, A15=30,886, A16=16.56, A4=부산광역시 북구 구포동 / 7. A24=신천초등학교, A15=30,886, A16=21, A4=부산광역시 북구 구포동 / 8. A24=백양초등학교, A15=26,593.9, A16=22.3, A4=부산광역시 북구 만덕동 / 9. A24=경혜여자고등학교, A15=25,974, A16=21.7, A4=부산광역시 북구 구포동 / 10. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=10, A4=부산광역시 북구 금곡동 / 11. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=43.2, A4=부산광역시 북구 금곡동 / 12. A24=한국산업인력공단부산지역본부, A15=23,901.8, A16=5.65, A4=부산광역시 북구 금곡동 / 13. A24=성도고등학교, A15=23,657, A16=0, A4=부산광역시 북구 구포동 / 14. A24=만덕초등학교, A15=20,459, A16=13.65, A4=부산광역시 북구 만덕동 / 15. A24=양천초등학교, A15=20,414, A16=18.15, A4=부산광역시 북구 덕천동` reason=`list-top-missing 부산과학기술대학교` route=`building_area_threshold_count`
- `Q461` 대연동 연면적 4000㎡ 이상 공동주택  
  gold=`1. A24=대연극동아파트, A14=46,326.96, A26=25, A16=67.6 / 2. A24=리마크빌 대연, A14=41,046.41, A26=20, A16=65.27 / 3. A24=삼성아파트, A14=29,899.51, A26=25, A16=68.88 / 4. A24=대우그린2차아파트, A14=27,880.9, A26=24, A16=66 / 5. A24=대연 힐스테이트푸르지오, A14=27,871.7, A26=38, A16=111.5 / 6. A24=대연 힐스테이트푸르지오, A14=27,789.3, A26=38, A16=111.5 / 7. A24=장백장미타워, A14=26,447.5, A26=25, A16=69.9 / 8. A24=대연2차동원로얄듀크, A14=24,498.528, A26=25, A16=67.8 / 9. A24=대연동동일스위트, A14=23,591.96, A26=20, A16=78.4 / 10. A24=대연 힐스테이트푸르지오, A14=23,293.68, A26=35, A16=102.15 / 11. A24=대연 힐스테이트푸르지오, A14=23,124.27, A26=35, A16=102.15 / 12. A24=대연 힐스테이트푸르지오, A14=23,103.51, A26=35, A16=102.15 / 13. A24=대연 힐스테이트푸르지오, A14=22,706.3, A26=38, A16=111.5 / 14. A24=대연 힐스테이트푸르지오, A14=22,143.02, A26=36, A16=105 / 15. A24=대연 힐스테이트푸르지오, A14=22,126.48, A26=36, A16=105` reason=`list-top-missing 대연극동아파트` route=`building_area_threshold_count`
- `Q466` 그중 높이 40m 이상만  
  gold=`118채` reason=`count-mismatch gold=118 pred=[40.0, 2000.0, 241.0, 241.0]` route=`d198_attr_count`
- `Q489` 남구 기초구역 중 면적(BAS_AR) 0.2 이상 개수  
  gold=`32개` reason=`count-mismatch gold=32 pred=[0.2, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`
