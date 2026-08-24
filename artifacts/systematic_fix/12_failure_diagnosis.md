# 500문항 실패 원인 진단

- 시각: 2026-08-25 00:35:26
- 현재: 277/500 (55.4%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 90
- `ENTITY_SELECTION_ERROR`: 79
- `RANGE_BOUND_DROPPED`: 38
- `FOLLOWUP_CONTEXT_LOST`: 23
- `BOOLEAN_OR_DROPPED`: 4
- `EXECUTION_TIMEOUT`: 2
- `SPATIAL_TARGET_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### EXECUTION_TIMEOUT

- `N015` 산업단지 자료의 기준일은?  
  gold=`min_base=2025-08-01 00:00:00; max_base=2025-08-01 00:00:00; n=130` reason=`timeout>40s` route=`None`
- `Q108` 남구 공동주택 중 2000년 이후 사용승인이고 지상 15층 이상인 채수  
  gold=`248채` reason=`timeout>40s` route=`None`

### PREDICATE_DROPPED

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`building_name_lookup`
- `N056` 광안동에서 높이가 20미터를 넘는 건물은?  
  gold=`1. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=105.55, A9=공동주택 / 2. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=81.25, A9=공동주택 / 3. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=78.5, A9=공동주택 / 4. A24=없음, A4=부산광역시 수영구 광안동, A5=744-32, A16=77.4, A9=공동주택 / 5. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=75.7, A9=공동주택 / 6. A24=부산광안대우아이빌, A4=부산광역시 수영구 광안동, A5=193-4, A16=74.45, A9=업무시설 / 7. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A5=193-1, A16=73.8, A9=숙박시설 / 8. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=73.15, A9=공동주택 / 9. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=745-2, A16=72.9, A9=공동주택 / 10. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A5=192-5, A16=71.2, A9=숙박시설 / 11. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=70.45, A9=공동주택 / 12. A24=베스테이 센트럴뷰, A4=부산광역시 수영구 광안동, A5=51-1, A16=69.9, A9=업무시설 / 13. A24=광원아파트, A4=부산광역시 수영구 광안동, A5=526-1, A16=68.8, A9=공동주택 / 14. A24=광안역 성원상떼빌, A4=부산광역시 수영구 광안동, A5=143-1, A16=67.91, A9=공동주택 / 15. A24=광안스윗팰리스, A4=부산광역시 수영구 광안동, A5=74-5, A16=67.9, A9=공동주택 외 15건` reason=`list-top-missing 광안동에스케이뷰` route=`semantic_plan_list`
- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`name-missing GS하이츠자이` route=`semantic_plan_list`
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

### ENTITY_SELECTION_ERROR

- `N037` 부산광역시 공동주택은 몇 채야?  
  gold=`30,773채` reason=`count-mismatch gold=30773 pred=[]` route=`semantic_plan_clarify`
- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[]` route=`semantic_plan_clarify`
- `Q118` 영도구 공동주택 중 1990년대 사용승인이고 지상 10층 이상인 채수  
  gold=`99채` reason=`engine-fail:UndefinedColumn: "A34" 이름의 칼럼은 없습니다
LINE 5:   AND "A34" BETWEEN '1990-01-01' AND '1990-12-31'  
              ^` route=`None`
- `Q122` 중동 아파트 중 높이 100m 이상이면서 지상 30층 이상인 건물명과 높이·층수  
  gold=`1. A24=엘시티, A4=부산광역시 해운대구 중동, A16=339.1, A26=85, A14=145,181.8812 / 2. A24=엘시티, A4=부산광역시 해운대구 중동, A16=333.1, A26=85, A14=145,181.8812` reason=`list-top-missing 엘시티` route=`clarify_place`
- `Q124` 구서동 공동주택 중 2000년 이후 사용승인·철근콘크리트·15층 이상인 채수  
  gold=`111채` reason=`count-mismatch gold=111 pred=[2000.0, 5.0]` route=`clarify_unknown_term`
- `Q130` 정관읍 공동주택 중 높이 35m 이상이고 2000년 이후 사용승인인 채수  
  gold=`203채` reason=`engine-fail:UndefinedColumn: b.A30 칼럼 없음
LINE 1: ...A9", b."A12", b."A14", b."A16", b."A24", b."A26", b."A30", b...
                                                             ^` route=`None`

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q210` 중구 위반건축물 전체 채수와 그 중 제2종근린생활시설 채수  
  gold=`violate_n=264; near_n=53` reason=`scalar-mismatch hits=1 gold=[264.0, 53.0]` route=`semantic_plan_count`
- `Q284` 우동과 교차하는 기초구역 개수와 그 중 면적 최대값  
  gold=`n=30; max_ar=6.2449` reason=`scalar-mismatch hits=0 gold=[30.0, 6.2449]` route=`bas_area_topn`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 887.0, -1.0, 96.6, 2.0]` route=`semantic_plan_list`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=1 gold=[29.0, 106135.2449]` route=`semantic_plan_aggregate`
- `Q396` 그 중 연면적 합계  
  gold=`sum_gfa=528,749.885; n=44` reason=`scalar-mismatch hits=1 gold=[528749.885, 44.0]` route=`semantic_plan_aggregate`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`count-mismatch gold=360 pred=[3000.0, 0.0]` route=`None`

### RANGE_BOUND_DROPPED

- `Q105` 강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적  
  gold=`1. A24=？⑥?？댄?？？二？怨듭?, A4=부산광역시 강서구 화전동, A5=597-5, A11=일반철골구조, A14=1,094,925 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=74,540.74 / 3. A24=금성볼트공업(주) 제2공장, A4=부산광역시 강서구 화전동, A5=591-4, A11=일반철골구조, A14=74,445.88 / 4. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=69,736.75 / 5. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=69,623.17 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=51,095.44 / 7. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=39,503.43 / 8. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A5=1720, A11=일반철골구조, A14=37,014.07 / 9. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=30,053.22 / 10. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=27,377.12 / 11. A24=없음, A4=부산광역시 강서구 송정동, A5=1635-2, A11=일반철골구조, A14=27,214.85 / 12. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=27,139.62 / 13. A24=없음, A4=부산광역시 강서구 지사동, A5=1213, A11=일반철골구조, A14=25,814.7 / 14. A24=없음, A4=부산광역시 강서구 송정동, A5=1638-1, A11=일반철골구조, A14=24,231.98 / 15. A24=(주)삼공사 녹산공장, A4=부산광역시 강서구 송정동, A5=1464-2, A11=일반철골구조, A14=23,546.4` reason=`list-top-missing ？⑥?？댄?？？二？怨듭?` route=`semantic_plan_list`
- `Q130` 정관읍 공동주택 중 높이 35m 이상이고 2000년 이후 사용승인인 채수  
  gold=`203채` reason=`engine-fail:UndefinedColumn: b.A30 칼럼 없음
LINE 1: ...A9", b."A12", b."A14", b."A16", b."A24", b."A26", b."A30", b...
                                                             ^` route=`None`
- `Q136` 사상구 공장 중 경량철골구조이고 연면적 1500㎡ 이상인 채수  
  gold=`12채` reason=`count-mismatch gold=12 pred=[180.0, 180.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1.0, 25.0, 91.0, 91.0]` route=`building_height_count`
- `Q173` 사상구 건물 건폐율 20% 이상 70% 이하이면서 연면적 2000㎡ 이상인 채수  
  gold=`431채` reason=`count-mismatch gold=431 pred=[485.0, 485.0]` route=`semantic_plan_count`
- `Q174` 해운대구 공동주택 용적율 100% 이상 400% 이하이고 15층 이상인 채수  
  gold=`166채` reason=`count-mismatch gold=166 pred=[190.0, 190.0]` route=`semantic_plan_count`
- `Q176` 남구 아파트 또는 업무시설 중 지하 1층 이상이면서 지상 10층 이상인 채수  
  gold=`338채` reason=`count-mismatch gold=338 pred=[451.0, 451.0]` route=`semantic_plan_count`
- `Q178` 강서구 동식물관련시설이 아니면서 산지(특수지)인 건물 중 연면적 500㎡ 이상 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[500.0, 0.0, 0.0]` route=`building_area_threshold_count`

### BOOLEAN_OR_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`
- `Q336` 금정구 청룡동 문교사회용 또는 공공용 채수  
  gold=`64채` reason=`count-mismatch gold=64 pred=[]` route=`semantic_plan_clarify`
- `Q458` 그중 공동주택 또는 숙박시설만  
  gold=`3채` reason=`count-mismatch gold=3 pred=[]` route=`clarify_place`

### SPATIAL_TARGET_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
