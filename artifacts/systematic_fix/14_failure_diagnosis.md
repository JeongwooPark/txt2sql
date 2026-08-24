# 500문항 실패 원인 진단

- 시각: 2026-08-25 01:17:54
- 현재: 283/500 (56.6%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 89
- `ENTITY_SELECTION_ERROR`: 85
- `RANGE_BOUND_DROPPED`: 35
- `FOLLOWUP_CONTEXT_LOST`: 20
- `BOOLEAN_OR_DROPPED`: 2
- `SPATIAL_TARGET_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`building_name_lookup`
- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`scalar-mismatch hits=1 gold=[197.0, 24.0, 4.0]` route=`semantic_plan_list`
- `N096` 금정구 주거용 연면적 크기별 수는?  
  gold=`1. bin=130㎡이상, n=9,343 / 2. bin=60-85㎡, n=1,732 / 3. bin=60㎡미만, n=1,825 / 4. bin=85-130㎡, n=3,762` reason=`group-mismatch` route=`building_name_lookup`
- `N097` 안락동에서 지어진지 30년 넘은 건물은 몇 채야?  
  gold=`3,021채` reason=`count-mismatch gold=3021 pred=[2866.0, 2866.0]` route=`building_age_count`
- `N100` 동래구 집합건축물 중 허가일자가 1990년대인 것은 몇 채야?  
  gold=`581채` reason=`count-mismatch gold=581 pred=[1990.0, 553.0, 100.0, 553.0, 100.0, 1990.0]` route=`d198_year_stats`
- `Q151` 연제구에서 공동주택 또는 단독주택이면서 높이 20m 이상인 건물 수  
  gold=`449채` reason=`count-mismatch gold=449 pred=[447.0, 447.0]` route=`semantic_plan_count`
- `Q156` 동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수  
  gold=`98채` reason=`count-mismatch gold=98 pred=[91.0, 91.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1035.0, 1035.0]` route=`semantic_plan_count`

### ENTITY_SELECTION_ERROR

- `N037` 부산광역시 공동주택은 몇 채야?  
  gold=`30,773채` reason=`count-mismatch gold=30773 pred=[]` route=`semantic_plan_clarify`
- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[]` route=`semantic_plan_clarify`
- `Q108` 남구 공동주택 중 2000년 이후 사용승인이고 지상 15층 이상인 채수  
  gold=`248채` reason=`engine-fail:numeric operator on text field: approval_date` route=`None`
- `Q118` 영도구 공동주택 중 1990년대 사용승인이고 지상 10층 이상인 채수  
  gold=`99채` reason=`engine-fail:numeric operator on text field: approval_date` route=`None`
- `Q124` 구서동 공동주택 중 2000년 이후 사용승인·철근콘크리트·15층 이상인 채수  
  gold=`111채` reason=`engine-fail:numeric operator on text field: approval_date` route=`None`
- `Q130` 정관읍 공동주택 중 높이 35m 이상이고 2000년 이후 사용승인인 채수  
  gold=`203채` reason=`engine-fail:numeric operator on text field: approval_date` route=`None`

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 1.0, 2.0, 3.0, 2.0]` route=`semantic_plan_list`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=1 gold=[29.0, 106135.2449]` route=`semantic_plan_aggregate`
- `Q396` 그 중 연면적 합계  
  gold=`sum_gfa=528,749.885; n=44` reason=`scalar-mismatch hits=1 gold=[528749.885, 44.0]` route=`semantic_plan_aggregate`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=1 gold=[248.0, 70.2789]` route=`building_floor_count`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`count-mismatch gold=14 pred=[1.0, 1.0, 71.2, 71.2]` route=`semantic_plan_list`

### RANGE_BOUND_DROPPED

- `Q105` 강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적  
  gold=`1. A24=？⑥?？댄?？？二？怨듭?, A4=부산광역시 강서구 화전동, A5=597-5, A11=일반철골구조, A14=1,094,925 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=74,540.74 / 3. A24=금성볼트공업(주) 제2공장, A4=부산광역시 강서구 화전동, A5=591-4, A11=일반철골구조, A14=74,445.88 / 4. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=69,736.75 / 5. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=69,623.17 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=51,095.44 / 7. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=39,503.43 / 8. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A5=1720, A11=일반철골구조, A14=37,014.07 / 9. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=30,053.22 / 10. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=27,377.12 / 11. A24=없음, A4=부산광역시 강서구 송정동, A5=1635-2, A11=일반철골구조, A14=27,214.85 / 12. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=27,139.62 / 13. A24=없음, A4=부산광역시 강서구 지사동, A5=1213, A11=일반철골구조, A14=25,814.7 / 14. A24=없음, A4=부산광역시 강서구 송정동, A5=1638-1, A11=일반철골구조, A14=24,231.98 / 15. A24=(주)삼공사 녹산공장, A4=부산광역시 강서구 송정동, A5=1464-2, A11=일반철골구조, A14=23,546.4` reason=`list-top-missing ？⑥?？댄?？？二？怨듭?` route=`semantic_plan_list`
- `Q173` 사상구 건물 건폐율 20% 이상 70% 이하이면서 연면적 2000㎡ 이상인 채수  
  gold=`431채` reason=`count-mismatch gold=431 pred=[485.0, 485.0]` route=`semantic_plan_count`
- `Q174` 해운대구 공동주택 용적율 100% 이상 400% 이하이고 15층 이상인 채수  
  gold=`166채` reason=`count-mismatch gold=166 pred=[190.0, 190.0]` route=`semantic_plan_count`
- `Q178` 강서구 동식물관련시설이 아니면서 산지(특수지)인 건물 중 연면적 500㎡ 이상 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[500.0, 0.0, 0.0]` route=`building_area_threshold_count`
- `Q190` 해운대구 지하 2층 이상이면서 지상 15층 이상인 공동주택 수  
  gold=`55채` reason=`count-mismatch gold=55 pred=[15.0, 856.0, 856.0]` route=`building_floor_count`
- `Q191` 금정구 산지(특수지 산) 단독주택 중 건축면적 80㎡ 이상인 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[80.0, 5282.0, 5282.0]` route=`building_area_threshold_count`
- `Q194` 동래구 건물동명이 있는 공동주택 중 높이 40m 이상인 이름·동명·높이  
  gold=`1. A24=벽산아스타, A25=101동, A16=162.5, A14=82,698.6 / 2. A24=벽산아스타, A25=102동, A16=158.95, A14=33,084.734 / 3. A24=벽산아스타, A25=103동, A16=155.9, A14=30,324.93 / 4. A24=온천동반도보라스카이뷰, A25=108, A16=113.1, A14=24,317.35 / 5. A24=온천동반도보라스카이뷰, A25=107, A16=113.1, A14=30,723.46 / 6. A24=온천동반도보라스카이뷰, A25=106, A16=113.1, A14=19,731.16 / 7. A24=낙민동 한일유앤아이아파트, A25=110동, A16=110.7, A14=19,627.9052 / 8. A24=낙민동 한일유앤아이아파트, A25=109동, A16=110.7, A14=19,128.17 / 9. A24=낙민동 한일유앤아이아파트, A25=108동, A16=102.1, A14=18,172.62 / 10. A24=온천동반도보라스카이뷰, A25=104, A16=99.1, A14=16,734.2657 / 11. A24=온천동반도보라스카이뷰, A25=103, A16=99.1, A14=17,145.6647 / 12. A24=온천동반도보라스카이뷰, A25=102, A16=99.1, A14=17,243.6116 / 13. A24=온천동반도보라스카이뷰, A25=101, A16=96.3, A14=16,618.712 / 14. A24=동래 센트럴파크 하이츠 1차, A25=103동, A16=84.8, A14=22,759.5631 / 15. A24=온천동반도보라스카이뷰, A25=105, A16=82.3, A14=9,535.89` reason=`list-top-missing 벽산아스타` route=`d010_attr_lookup`
- `Q198` 북구 지하층이 있고 지상 5층 이상인 제2종근린생활시설 채수  
  gold=`168채` reason=`count-mismatch gold=168 pred=[2.0, 5.0, 219.0, 219.0]` route=`building_floor_count`

### BOOLEAN_OR_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`

### SPATIAL_TARGET_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
