# 500문항 실패 원인 진단

- 시각: 2026-08-25 02:58:28
- 현재: 30/93 (32.3%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 35
- `RANGE_BOUND_DROPPED`: 22
- `ENTITY_SELECTION_ERROR`: 6
- `FOLLOWUP_CONTEXT_LOST`: 4

## 대표 실패 사례 (원인별 최대 8건)

### RANGE_BOUND_DROPPED

- `Q105` 강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적  
  gold=`1. A24=？⑥?？댄?？？二？怨듭?, A4=부산광역시 강서구 화전동, A5=597-5, A11=일반철골구조, A14=1,094,925 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=74,540.74 / 3. A24=금성볼트공업(주) 제2공장, A4=부산광역시 강서구 화전동, A5=591-4, A11=일반철골구조, A14=74,445.88 / 4. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=69,736.75 / 5. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=69,623.17 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=51,095.44 / 7. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=39,503.43 / 8. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A5=1720, A11=일반철골구조, A14=37,014.07 / 9. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=30,053.22 / 10. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=27,377.12 / 11. A24=없음, A4=부산광역시 강서구 송정동, A5=1635-2, A11=일반철골구조, A14=27,214.85 / 12. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=27,139.62 / 13. A24=없음, A4=부산광역시 강서구 지사동, A5=1213, A11=일반철골구조, A14=25,814.7 / 14. A24=없음, A4=부산광역시 강서구 송정동, A5=1638-1, A11=일반철골구조, A14=24,231.98 / 15. A24=(주)삼공사 녹산공장, A4=부산광역시 강서구 송정동, A5=1464-2, A11=일반철골구조, A14=23,546.4` reason=`list-top-missing ？⑥?？댄?？？二？怨듭?` route=`semantic_plan_list`
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
- `Q207` 해운대구 건물동명이 비어 있지 않은 아파트 중 20층 이상인 채수  
  gold=`589채` reason=`count-mismatch gold=589 pred=[]` route=`d010_attr_lookup`
- `Q231` 영도구 15층 이상 건물 중 공동주택 비율 %  
  gold=`pct=91.716` reason=`scalar-mismatch hits=0 gold=[91.716]` route=`semantic_plan_aggregate`

### PREDICATE_DROPPED

- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q156` 동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수  
  gold=`98채` reason=`count-mismatch gold=98 pred=[91.0, 91.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1035.0, 1035.0]` route=`semantic_plan_count`
- `Q160` 영도구에서 단독주택이 아니고 벽돌·블록구조도 아닌 건물 중 연면적 1000㎡ 이상 채수  
  gold=`805채` reason=`count-mismatch gold=805 pred=[8.0, 8.0]` route=`semantic_plan_count`
- `Q163` 금정구 건물 중 지상 8층 이상 20층 이하이면서 높이 25m 이상인 채수  
  gold=`441채` reason=`count-mismatch gold=441 pred=[1.0, 1.0]` route=`semantic_plan_count`
- `Q165` 사하구 공장 연면적 1000㎡ 이상 8000㎡ 이하이고 일반철골인 채수  
  gold=`304채` reason=`count-mismatch gold=304 pred=[378.0, 378.0]` route=`semantic_plan_count`
- `Q171` 수영구에서 공동주택·단독주택을 제외한 높이 35m 이상 건물 수  
  gold=`100채` reason=`count-mismatch gold=100 pred=[94.0, 94.0]` route=`semantic_plan_count`
- `Q172` 장림동 공장 중 경량철골이 아닌 연면적 2500㎡ 이상 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[0.0, 0.0]` route=`semantic_plan_count`

### ENTITY_SELECTION_ERROR

- `Q271` 장림동 산업단지 안 공장 중 연면적 3000㎡ 이상인 채수  
  gold=`35채` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q283` 강서구 산업단지 안 공장 중 연면적 5000㎡ 이상 이름  
  gold=`1. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=74,540.74 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=69,736.75 / 3. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=69,623.17 / 4. A24=없음, A4=부산광역시 강서구 송정동, A14=54,595.54 / 5. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=51,095.44 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=39,503.43 / 7. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A14=37,014.07 / 8. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=33,453.95 / 9. A24=농심 녹산공장, A4=부산광역시 강서구 송정동, A14=31,388.84 / 10. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=30,053.22 / 11. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=27,377.12 / 12. A24=없음, A4=부산광역시 강서구 송정동, A14=27,214.85 / 13. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=27,139.62 / 14. A24=없음, A4=부산광역시 강서구 지사동, A14=25,814.7 / 15. A24=없음, A4=부산광역시 강서구 송정동, A14=24,231.98` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`
- `Q309` 동래구 표제부 중 용적율 200% 이상인 공동주택(주요용도) 채수  
  gold=`936채` reason=`engine-fail:- 동래구 "주요용도명" kinds/count must use "AL_D198_26260_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q332` 금정구 철근콘크리트 구조이면서 주요용도가 공동주택이고 15층 이상인 채수  
  gold=`338채` reason=`engine-fail:- 금정구 "주요용도명" kinds/count must use "AL_D198_26410_20250115"."A25" with A25 IS NOT NULL, not AL_D010 "A9".` route=`None`
- `Q491` 면적 합계  
  gold=`sum_ar=12.7918; n=29` reason=`scalar-mismatch hits=0 gold=[12.7918, 29.0]` route=`semantic_plan_clarify`
- `Q492` 면적 최대 기초구역번호  
  gold=`BAS_ID=48481; BAS_AR=1.5929; MVMN_RESN=국가기초구역 최초생성` reason=`scalar-mismatch hits=0 gold=[48481.0, 1.5929]` route=`semantic_plan_clarify`

### FOLLOWUP_CONTEXT_LOST

- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[324.0, 324.0]` route=`semantic_plan_count`
- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[114.0, 114.0]` route=`semantic_plan_count`
- `Q490` 그중 이동사유가 최초생성인 것만  
  gold=`29개` reason=`count-mismatch gold=29 pred=[0.2, 1.0, 1.64269819016635, 48562.0]` route=`bas_area_topn`
- `Q498` 그중 높이 18m 이상만  
  gold=`14채` reason=`count-mismatch gold=14 pred=[19.0, 19.0]` route=`semantic_plan_count`
