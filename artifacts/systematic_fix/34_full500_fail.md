# 500문항 실패 원인 진단

- 시각: 2026-08-25 11:06:40
- 현재: 367/500 (73.4%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 58
- `ENTITY_SELECTION_ERROR`: 48
- `RANGE_BOUND_DROPPED`: 17
- `FOLLOWUP_CONTEXT_LOST`: 13
- `BOOLEAN_NOT_DROPPED`: 1
- `SPATIAL_TARGET_DROPPED`: 1
- `BOOLEAN_OR_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`semantic_plan_clarify`
- `N029` 엘시티의 높이와 층수는?  
  gold=`1. A24=중동 18290000 숙박시설 (주식회사엘시티피이에프브이), A25=랜드마크타워동, A4=부산광역시 해운대구 중동, A5=1829, A16=411.6, A26=101, A14=249,374.4587 / 2. A24=엘시티, A25=타워에이동, A4=부산광역시 해운대구 중동, A5=1829, A16=339.1, A26=85, A14=145,181.8812 / 3. A24=엘시티, A25=타워비동, A4=부산광역시 해운대구 중동, A5=1829, A16=333.1, A26=85, A14=145,181.8812 / 4. A24=르씨엘시티, A25=없음, A4=부산광역시 동래구 온천동, A5=1248-8, A16=57, A26=20, A14=4,220.66 / 5. A24=엘시티, A25=포디움동, A4=부산광역시 해운대구 중동, A5=1829, A16=43, A26=6, A14=121,396.5881` reason=`list-top-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N079` 대연3동과 교차하는 기초구역은 몇 개야?  
  gold=`49개` reason=`engine-fail:- 기초구역 공간 질의는 ST_Intersects/ST_Within/ST_DWithin을 써야 합니다.` route=`None`
- `N082` 좌표(129.12, 35.15)에서 200미터 이내 건물 건수  
  gold=`0채` reason=`count-mismatch gold=0 pred=[]` route=`semantic_plan_clarify`
- `N083` 반여동에 있는 건물이 반여1동과 반여2동에 몇 퍼센트씩 있는가?  
  gold=`1. ADM_NM=반여1동, n=2,966, pct=46.49 / 2. ADM_NM=반여2동, n=1,743, pct=27.32 / 3. ADM_NM=반여3동, n=1,108, pct=17.37 / 4. ADM_NM=반여4동, n=563, pct=8.82` reason=`group-mismatch` route=`semantic_plan_clarify`
- `N087` 강서구 산업단지 이름을 알려줘  
  gold=`1. name=강서보고일반산업단지 / 2. name=강서해성일반산업단지 / 3. name=명지,녹산국가산업단지 / 4. name=명지국가산업단지 / 5. name=부산과학지방산업단지 / 6. name=부산신항 국제산업물류도시(1단계)일반산업단지 / 7. name=부산신항배후 국제물류도시(1단계)일반산업단지 / 8. name=성우일반산업단지 / 9. name=신호지방산업단지 / 10. name=정주일반산업단지 / 11. name=지사2일반산업단지 / 12. name=지사글로벌일반산업단지` reason=`list-top-missing 강서보고일반산업단지` route=`meta_table`
- `Q181` 기장군 공동주택을 제외하고 높이 25m 이상인 건물 용도 상위 8개  
  gold=`1. usage=제1종근린생활시설, n=43 / 2. usage=업무시설, n=22 / 3. usage=숙박시설, n=20 / 4. usage=제2종근린생활시설, n=18 / 5. usage=의료시설, n=5 / 6. usage=공장, n=5 / 7. usage=자동차관련시설, n=5 / 8. usage=운동시설, n=4` reason=`group-mismatch` route=`semantic_plan_clarify`

### PREDICATE_DROPPED

- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`scalar-mismatch hits=1 gold=[197.0, 24.0, 4.0]` route=`semantic_plan_list`
- `N097` 안락동에서 지어진지 30년 넘은 건물은 몇 채야?  
  gold=`3,021채` reason=`count-mismatch gold=3021 pred=[3004.0, 3004.0]` route=`semantic_plan_count`
- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q158` 강서구 공장·창고를 제외한 건물 중 연면적 5000㎡ 이상인 채수  
  gold=`244채` reason=`count-mismatch gold=244 pred=[23.0, 23.0]` route=`semantic_plan_count`
- `Q165` 사하구 공장 연면적 1000㎡ 이상 8000㎡ 이하이고 일반철골인 채수  
  gold=`304채` reason=`count-mismatch gold=304 pred=[1000.0, 8000.0, 733.0, 733.0]` route=`building_area_threshold_count`
- `Q177` 금정구 단독주택 중 사용승인 1970~1989년이고 건축면적 60~150㎡인 채수  
  gold=`5,872채` reason=`count-mismatch gold=5872 pred=[1989.0, 13218.0, 13218.0]` route=`d198_attr_count`
- `Q184` 해운대구 위반건축물이 아니면서 높이 80m 이상인 공동주택 채수  
  gold=`73채` reason=`count-mismatch gold=73 pred=[70.0, 70.0]` route=`semantic_plan_count`
- `Q188` 부산진구 위반건축물(A20=Y) 중 공동주택은 몇 채야?  
  gold=`44채` reason=`count-mismatch gold=44 pred=[20.0, 652.0, 652.0]` route=`d010_attr_count`

### RANGE_BOUND_DROPPED

- `Q110` 기장군 단독주택 중 건축면적 200㎡ 이상이면서 벽돌구조인 채수  
  gold=`54채` reason=`count-mismatch gold=54 pred=[200.0, 269.0, 269.0]` route=`building_area_threshold_count`
- `Q125` 괴정동 단독주택 중 건축면적 150㎡ 이상이면서 블록구조인 채수  
  gold=`8채` reason=`count-mismatch gold=8 pred=[150.0, 66.0, 66.0]` route=`building_area_threshold_count`
- `Q136` 사상구 공장 중 경량철골구조이고 연면적 1500㎡ 이상인 채수  
  gold=`12채` reason=`count-mismatch gold=12 pred=[1500.0, 310.0, 310.0]` route=`building_area_threshold_count`
- `Q146` 남산동 단독주택 중 목구조이고 건축면적 80㎡ 이상인 채수  
  gold=`2채` reason=`count-mismatch gold=2 pred=[80.0, 1160.0, 1160.0]` route=`building_area_threshold_count`
- `Q186` 해운대구 공동주택 중 건폐율이 30% 이상인 건물 수  
  gold=`1,850채` reason=`count-mismatch gold=1850 pred=[30.0, 11476.0, 11476.0]` route=`d010_attr_count`
- `Q207` 해운대구 건물동명이 비어 있지 않은 아파트 중 20층 이상인 채수  
  gold=`589채` reason=`count-mismatch gold=589 pred=[]` route=`d010_attr_lookup`
- `Q271` 장림동 산업단지 안 공장 중 연면적 3000㎡ 이상인 채수  
  gold=`35채` reason=`count-mismatch gold=35 pred=[3000.0, 68.0, 68.0]` route=`building_area_threshold_count`
- `Q279` 남구 기초구역 중 면적(BAS_AR) 0.3 이상인 개수  
  gold=`16개` reason=`count-mismatch gold=16 pred=[0.3, 3.0, 1.64269819016635, 48562.0, 1.592911, 48481.0]` route=`bas_area_topn`

### BOOLEAN_NOT_DROPPED

- `Q181` 기장군 공동주택을 제외하고 높이 25m 이상인 건물 용도 상위 8개  
  gold=`1. usage=제1종근린생활시설, n=43 / 2. usage=업무시설, n=22 / 3. usage=숙박시설, n=20 / 4. usage=제2종근린생활시설, n=18 / 5. usage=의료시설, n=5 / 6. usage=공장, n=5 / 7. usage=자동차관련시설, n=5 / 8. usage=운동시설, n=4` reason=`group-mismatch` route=`semantic_plan_clarify`

### FOLLOWUP_CONTEXT_LOST

- `Q210` 중구 위반건축물 전체 채수와 그 중 제2종근린생활시설 채수  
  gold=`violate_n=264; near_n=53` reason=`scalar-mismatch hits=1 gold=[264.0, 53.0]` route=`d010_attr_count`
- `Q284` 우동과 교차하는 기초구역 개수와 그 중 면적 최대값  
  gold=`n=30; max_ar=6.2449` reason=`scalar-mismatch hits=0 gold=[30.0, 6.2449]` route=`semantic_plan_clarify`
- `Q390` 그중 2000년 이후 사용승인만  
  gold=`265채` reason=`count-mismatch gold=265 pred=[100.0, 1.0, 90.0, -31.0, 2.0, 1033.0]` route=`semantic_plan_list`
- `Q402` 그중 2000년 이후 사용승인만  
  gold=`248채` reason=`count-mismatch gold=248 pred=[100.0, 1.0, 482.0, -1.0, 2.0, 486.0]` route=`semantic_plan_list`
- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=0 gold=[248.0, 70.2789]` route=`semantic_plan_aggregate`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[380.0, 380.0]` route=`semantic_plan_count`
- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[114.0, 114.0]` route=`semantic_plan_count`

### SPATIAL_TARGET_DROPPED

- `Q251` 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)  
  gold=`pct=42.1833` reason=`scalar-mismatch hits=0 gold=[42.1833]` route=`semantic_plan_clarify`

### BOOLEAN_OR_DROPPED

- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`
