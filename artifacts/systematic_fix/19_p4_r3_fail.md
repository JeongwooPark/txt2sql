# 500문항 실패 원인 진단

- 시각: 2026-08-25 03:04:37
- 현재: 36/93 (38.7%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 34
- `RANGE_BOUND_DROPPED`: 17
- `ENTITY_SELECTION_ERROR`: 6
- `FOLLOWUP_CONTEXT_LOST`: 4

## 대표 실패 사례 (원인별 최대 8건)

### PREDICATE_DROPPED

- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q156` 동래구 건물 중 공동주택을 제외하고 높이 40m 이상인 채수  
  gold=`98채` reason=`count-mismatch gold=98 pred=[91.0, 91.0]` route=`semantic_plan_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1035.0, 1035.0]` route=`semantic_plan_count`
- `Q160` 영도구에서 단독주택이 아니고 벽돌·블록구조도 아닌 건물 중 연면적 1000㎡ 이상 채수  
  gold=`805채` reason=`count-mismatch gold=805 pred=[8.0, 8.0]` route=`semantic_plan_count`
- `Q165` 사하구 공장 연면적 1000㎡ 이상 8000㎡ 이하이고 일반철골인 채수  
  gold=`304채` reason=`count-mismatch gold=304 pred=[378.0, 378.0]` route=`semantic_plan_count`
- `Q171` 수영구에서 공동주택·단독주택을 제외한 높이 35m 이상 건물 수  
  gold=`100채` reason=`count-mismatch gold=100 pred=[94.0, 94.0]` route=`semantic_plan_count`
- `Q172` 장림동 공장 중 경량철골이 아닌 연면적 2500㎡ 이상 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[0.0, 0.0]` route=`semantic_plan_count`
- `Q183` 연제구 업무시설 연면적 800㎡ 이상 5000㎡ 이하이고 높이 15~45m인 채수  
  gold=`110채` reason=`count-mismatch gold=110 pred=[800.0, 5000.0, 137.0, 137.0]` route=`building_area_threshold_count`

### RANGE_BOUND_DROPPED

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
- `Q283` 강서구 산업단지 안 공장 중 연면적 5000㎡ 이상 이름  
  gold=`1. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=74,540.74 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=69,736.75 / 3. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=69,623.17 / 4. A24=없음, A4=부산광역시 강서구 송정동, A14=54,595.54 / 5. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=51,095.44 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=39,503.43 / 7. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A14=37,014.07 / 8. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=33,453.95 / 9. A24=농심 녹산공장, A4=부산광역시 강서구 송정동, A14=31,388.84 / 10. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=30,053.22 / 11. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A14=27,377.12 / 12. A24=없음, A4=부산광역시 강서구 송정동, A14=27,214.85 / 13. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A14=27,139.62 / 14. A24=없음, A4=부산광역시 강서구 지사동, A14=25,814.7 / 15. A24=없음, A4=부산광역시 강서구 송정동, A14=24,231.98` reason=`engine-fail:- Industrial-park questions must use "AL_D060_00_20250804".` route=`None`

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
