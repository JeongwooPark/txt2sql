# 500문항 실패 원인 진단

- 시각: 2026-08-25 03:22:31
- 현재: 338/500 (67.6%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 99
- `ENTITY_SELECTION_ERROR`: 37
- `RANGE_BOUND_DROPPED`: 17
- `FOLLOWUP_CONTEXT_LOST`: 13
- `BOOLEAN_OR_DROPPED`: 1
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
- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q151` 연제구에서 공동주택 또는 단독주택이면서 높이 20m 이상인 건물 수  
  gold=`449채` reason=`count-mismatch gold=449 pred=[447.0, 447.0]` route=`semantic_plan_count`
- `Q156` 동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수  
  gold=`98채` reason=`count-mismatch gold=98 pred=[91.0, 91.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1035.0, 1035.0]` route=`semantic_plan_count`

### ENTITY_SELECTION_ERROR

- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[]` route=`semantic_plan_clarify`
- `Q188` 부산진구 위반건축물(A20=Y) 중 공동주택은 몇 채야?  
  gold=`44채` reason=`count-mismatch gold=44 pred=[20.0, 10.0, 20.0]` route=`clarify_column`
- `Q223` 금정구 산지 비율(산 / 전체) %  
  gold=`pct_mountain=3.7068` reason=`scalar-mismatch hits=0 gold=[3.7068]` route=`meta_catalog`
- `Q227` 수영구 건물 용도별 평균 연면적 상위 10개 용도  
  gold=`1. usage=의료시설, n=24, avg_gfa=5,934.3053 / 2. usage=판매시설, n=25, avg_gfa=4,649.8398 / 3. usage=방송통신시설, n=7, avg_gfa=4,410.2471 / 4. usage=업무시설, n=200, avg_gfa=3,499.542 / 5. usage=운동시설, n=4, avg_gfa=2,451.7425 / 6. usage=교육연구시설, n=129, avg_gfa=2,153.9953 / 7. usage=공동주택, n=2,303, avg_gfa=1,999.5602 / 8. usage=숙박시설, n=102, avg_gfa=1,612.3925 / 9. usage=위락시설, n=5, avg_gfa=1,238.308 / 10. usage=종교시설, n=94, avg_gfa=1,131.4029` reason=`engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.` route=`None`
- `Q230` 남구에서 공동주택이 전체 건물에서 차지하는 비율 %  
  gold=`pct=9.0305` reason=`scalar-mismatch hits=0 gold=[9.0305]` route=`meta_catalog`
- `Q232` 부산진구 용도별 평균 높이(높이 있는 건물만) 상위 8  
  gold=`1. usage=업무시설, n=349, avg_h=37.1618 / 2. usage=판매시설, n=25, avg_h=33.8296 / 3. usage=의료시설, n=37, avg_h=32.4727 / 4. usage=공동주택, n=2,356, avg_h=25.449 / 5. usage=숙박시설, n=151, avg_h=23.4296 / 6. usage=교육연구시설, n=222, avg_h=18.8559 / 7. usage=자동차관련시설, n=88, avg_h=14.9837 / 8. usage=제1종근린생활시설, n=1,200, avg_h=12.9815` reason=`engine-fail:- Ranking questions require ORDER BY ... DESC NULLS LAST and LIMIT.` route=`None`
- `Q237` 광안동 숙박시설 연면적 합계·평균·최대 높이  
  gold=`n=50; sum_gfa=103,761.5099; avg_gfa=2,075.2302; max_h=73.8` reason=`engine-fail:too many aggregations` route=`None`

### RANGE_BOUND_DROPPED

- `Q105` 강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적  
  gold=`1. A24=？⑥?？댄?？？二？怨듭?, A4=부산광역시 강서구 화전동, A5=597-5, A11=일반철골구조, A14=1,094,925 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=74,540.74 / 3. A24=금성볼트공업(주) 제2공장, A4=부산광역시 강서구 화전동, A5=591-4, A11=일반철골구조, A14=74,445.88 / 4. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=69,736.75 / 5. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=69,623.17 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=51,095.44 / 7. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=39,503.43 / 8. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A5=1720, A11=일반철골구조, A14=37,014.07 / 9. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=30,053.22 / 10. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=27,377.12 / 11. A24=없음, A4=부산광역시 강서구 송정동, A5=1635-2, A11=일반철골구조, A14=27,214.85 / 12. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=27,139.62 / 13. A24=없음, A4=부산광역시 강서구 지사동, A5=1213, A11=일반철골구조, A14=25,814.7 / 14. A24=없음, A4=부산광역시 강서구 송정동, A5=1638-1, A11=일반철골구조, A14=24,231.98 / 15. A24=(주)삼공사 녹산공장, A4=부산광역시 강서구 송정동, A5=1464-2, A11=일반철골구조, A14=23,546.4` reason=`list-top-missing ？⑥?？댄?？？二？怨듭?` route=`semantic_plan_list`
- `Q178` 강서구 동식물관련시설이 아니면서 산지(특수지)인 건물 중 연면적 500㎡ 이상 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[0.0, 0.0]` route=`semantic_plan_count`
- `Q198` 북구 지하층이 있고 지상 5층 이상인 제2종근린생활시설 채수  
  gold=`168채` reason=`count-mismatch gold=168 pred=[219.0, 219.0]` route=`semantic_plan_count`
- `Q231` 영도구 15층 이상 건물 중 공동주택 비율 %  
  gold=`pct=91.716` reason=`scalar-mismatch hits=0 gold=[91.716]` route=`semantic_plan_aggregate`
- `Q238` 장림동 공장 중 연면적 1000㎡ 이상 비율 %  
  gold=`pct=24.7444` reason=`scalar-mismatch hits=0 gold=[24.7444]` route=`semantic_plan_aggregate`
- `Q267` 구서1동 안에 있는 공동주택 중 지상 15층 이상인 이름과 층수  
  gold=`1. A24=구서동 유림 노르웨이 아침, A26=32, A16=99.3, A14=43,452.52 / 2. A24=금강부광아파트, A26=26, A16=69.8, A14=27,618.374 / 3. A24=금강부광아파트, A26=26, A16=69.8, A14=27,390.646 / 4. A24=구서벽산메가트리움, A26=26, A16=79.2, A14=20,460.11 / 5. A24=구서시티타워, A26=25, A16=79.7, A14=26,139.023 / 6. A24=구서동 쌍용예가, A26=25, A16=73.6, A14=11,958.3765 / 7. A24=구서동 쌍용예가, A26=25, A16=70.8, A14=14,331.744 / 8. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=11,426.6965 / 9. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=12,301.6763 / 10. A24=구서동 쌍용예가, A26=23, A16=65.2, A14=11,251.2689 / 11. A24=구서동 쌍용예가, A26=22, A16=62.4, A14=12,259.7756 / 12. A24=구서동 쌍용예가, A26=22, A16=62.4, A14=7,158.7122 / 13. A24=경보아파트, A26=22, A16=59.2, A14=21,742.92 / 14. A24=구서동 쌍용예가, A26=21, A16=59.6, A14=12,840.8016 / 15. A24=구서동 쌍용예가, A26=21, A16=59.6, A14=10,187.3876` reason=`list-top-missing 구서동 유림 노르웨이 아침` route=`semantic_plan_list`
- `Q271` 장림동 산업단지 안 공장 중 연면적 3000㎡ 이상인 채수  
  gold=`35채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q279` 남구 기초구역 중 면적(BAS_AR) 0.3 이상인 개수  
  gold=`16개` reason=`count-mismatch gold=16 pred=[0.3, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`

### BOOLEAN_OR_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`

### SPATIAL_TARGET_DROPPED

- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`

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
