# 500문항 실패 원인 진단

- 시각: 2026-08-25 13:00:18
- 현재: 383/500 (76.6%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 58
- `ENTITY_SELECTION_ERROR`: 41
- `FOLLOWUP_CONTEXT_LOST`: 13
- `RANGE_BOUND_DROPPED`: 10
- `BOOLEAN_NOT_DROPPED`: 1
- `SPATIAL_TARGET_DROPPED`: 1
- `BOOLEAN_OR_DROPPED`: 1

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`engine-fail:plan generation failed` route=`semantic_plan_fallback`
- `N029` 엘시티의 높이와 층수는?  
  gold=`1. A24=중동 18290000 숙박시설 (주식회사엘시티피이에프브이), A25=랜드마크타워동, A4=부산광역시 해운대구 중동, A5=1829, A16=411.6, A26=101, A14=249,374.4587 / 2. A24=엘시티, A25=타워에이동, A4=부산광역시 해운대구 중동, A5=1829, A16=339.1, A26=85, A14=145,181.8812 / 3. A24=엘시티, A25=타워비동, A4=부산광역시 해운대구 중동, A5=1829, A16=333.1, A26=85, A14=145,181.8812 / 4. A24=르씨엘시티, A25=없음, A4=부산광역시 동래구 온천동, A5=1248-8, A16=57, A26=20, A14=4,220.66 / 5. A24=엘시티, A25=포디움동, A4=부산광역시 해운대구 중동, A5=1829, A16=43, A26=6, A14=121,396.5881` reason=`engine-fail:plan generation failed` route=`semantic_plan_fallback`
- `N063` 광안동에서 연면적이 가장 큰 숙박시설은?  
  gold=`A24=호텔아쿠아펠리스; A4=부산광역시 수영구 광안동; A5=192-5; A14=18,228.2; A16=71.2` reason=`engine-fail:P06` route=`semantic_plan_fallback`
- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`engine-fail:plan generation failed` route=`semantic_plan_fallback`
- `N065` 남구에서 건물면적이 가장 큰 공동주택은?  
  gold=`A24=GS하이츠자이; A4=부산광역시 남구 용호동; A5=197; A12=30,636.6549; A14=103,795.1908` reason=`engine-fail:P06` route=`semantic_plan_fallback`
- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`name-missing GS하이츠자이` route=`meta_column_display`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`engine-fail:plan generation failed` route=`semantic_plan_fallback`
- `N079` 대연3동과 교차하는 기초구역은 몇 개야?  
  gold=`49개` reason=`engine-fail:- 기초구역 공간 질의는 ST_Intersects/ST_Within/ST_DWithin을 써야 합니다.` route=`semantic_plan_fallback`

### PREDICATE_DROPPED

- `N056` 광안동에서 높이가 20미터를 넘는 건물은?  
  gold=`1. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=105.55, A9=공동주택 / 2. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=81.25, A9=공동주택 / 3. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=78.5, A9=공동주택 / 4. A24=없음, A4=부산광역시 수영구 광안동, A5=744-32, A16=77.4, A9=공동주택 / 5. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=75.7, A9=공동주택 / 6. A24=부산광안대우아이빌, A4=부산광역시 수영구 광안동, A5=193-4, A16=74.45, A9=업무시설 / 7. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A5=193-1, A16=73.8, A9=숙박시설 / 8. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=73.15, A9=공동주택 / 9. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=745-2, A16=72.9, A9=공동주택 / 10. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A5=192-5, A16=71.2, A9=숙박시설 / 11. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=70.45, A9=공동주택 / 12. A24=베스테이 센트럴뷰, A4=부산광역시 수영구 광안동, A5=51-1, A16=69.9, A9=업무시설 / 13. A24=광원아파트, A4=부산광역시 수영구 광안동, A5=526-1, A16=68.8, A9=공동주택 / 14. A24=광안역 성원상떼빌, A4=부산광역시 수영구 광안동, A5=143-1, A16=67.91, A9=공동주택 / 15. A24=광안스윗팰리스, A4=부산광역시 수영구 광안동, A5=74-5, A16=67.9, A9=공동주택 외 15건` reason=`list-top-missing 광안동에스케이뷰` route=`semantic_plan_list`
- `N070` 부산대학교와 부경대학교 건물 수를 비교해줘  
  gold=`pusan_n=95; pukyong_n=89` reason=`compare-num-missing` route=`semantic_plan_count`
- `N097` 안락동에서 지어진지 30년 넘은 건물은 몇 채야?  
  gold=`3,021채` reason=`count-mismatch gold=3021 pred=[3004.0, 3004.0]` route=`semantic_plan_count`
- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[18.0, 18.0]` route=`semantic_plan_count`
- `Q158` 강서구 공장·창고를 제외한 건물 중 연면적 5000㎡ 이상인 채수  
  gold=`244채` reason=`count-mismatch gold=244 pred=[23.0, 23.0]` route=`semantic_plan_count`
- `Q177` 금정구 단독주택 중 사용승인 1970~1989년이고 건축면적 60~150㎡인 채수  
  gold=`5,872채` reason=`count-mismatch gold=5872 pred=[1989.0, 13218.0, 13218.0]` route=`d198_attr_count`
- `Q184` 해운대구 위반건축물이 아니면서 높이 80m 이상인 공동주택 채수  
  gold=`73채` reason=`count-mismatch gold=73 pred=[70.0, 70.0]` route=`semantic_plan_count`
- `Q206` 동래구 위반건축물이면서 지어진지 30년 넘은 단독주택 채수  
  gold=`151채` reason=`count-mismatch gold=151 pred=[148.0, 148.0]` route=`semantic_plan_count`

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`engine-fail:plan generation failed` route=`semantic_plan_fallback`
- `Q284` 우동과 교차하는 기초구역 개수와 그 중 면적 최대값  
  gold=`n=30; max_ar=6.2449` reason=`engine-fail:- 기초구역 공간 질의는 ST_Intersects/ST_Within/ST_DWithin을 써야 합니다.` route=`semantic_plan_fallback`
- `Q390` 그중 2000년 이후 사용승인만  
  gold=`265채` reason=`count-mismatch gold=265 pred=[100.0, 1.0, 723.0, 2.0, 329.0, -4.0]` route=`semantic_plan_list`
- `Q402` 그중 2000년 이후 사용승인만  
  gold=`248채` reason=`count-mismatch gold=248 pred=[100.0, 1.0, 345.0, -8.0, 2.0, 1069.0]` route=`semantic_plan_list`
- `Q403` 그 건물들 평균 높이  
  gold=`n=248; avg_h=70.2789` reason=`scalar-mismatch hits=0 gold=[248.0, 70.2789]` route=`semantic_plan_aggregate`
- `Q407` 그 건물들 지하층이 있는 것은 몇 채야?  
  gold=`14채` reason=`engine-fail:P06` route=`semantic_plan_fallback`
- `Q426` 그중 사용승인 2000년 이후만  
  gold=`320채` reason=`count-mismatch gold=320 pred=[380.0, 380.0]` route=`semantic_plan_count`
- `Q450` 그중 10층 이상만  
  gold=`115채` reason=`count-mismatch gold=115 pred=[114.0, 114.0]` route=`semantic_plan_count`

### RANGE_BOUND_DROPPED

- `Q105` 강서구 공장 중 일반철골구조이고 연면적 5000㎡ 이상인 건물명과 연면적  
  gold=`1. A24=？⑥?？댄?？？二？怨듭?, A4=부산광역시 강서구 화전동, A5=597-5, A11=일반철골구조, A14=1,094,925 / 2. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=74,540.74 / 3. A24=금성볼트공업(주) 제2공장, A4=부산광역시 강서구 화전동, A5=591-4, A11=일반철골구조, A14=74,445.88 / 4. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=69,736.75 / 5. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=69,623.17 / 6. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=51,095.44 / 7. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=39,503.43 / 8. A24=(주)성광벤드, A4=부산광역시 강서구 송정동, A5=1720, A11=일반철골구조, A14=37,014.07 / 9. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=30,053.22 / 10. A24=삼성전기(주), A4=부산광역시 강서구 송정동, A5=1623-2, A11=일반철골구조, A14=27,377.12 / 11. A24=없음, A4=부산광역시 강서구 송정동, A5=1635-2, A11=일반철골구조, A14=27,214.85 / 12. A24=르노코리아자동차(주), A4=부산광역시 강서구 신호동, A5=185, A11=일반철골구조, A14=27,139.62 / 13. A24=없음, A4=부산광역시 강서구 지사동, A5=1213, A11=일반철골구조, A14=25,814.7 / 14. A24=없음, A4=부산광역시 강서구 송정동, A5=1638-1, A11=일반철골구조, A14=24,231.98 / 15. A24=(주)삼공사 녹산공장, A4=부산광역시 강서구 송정동, A5=1464-2, A11=일반철골구조, A14=23,546.4` reason=`list-top-missing ？⑥?？댄?？？二？怨듭?` route=`semantic_plan_list`
- `Q209` 사하구 지하층이 있는 공장 중 연면적 3000㎡ 이상인 이름·지하층·연면적  
  gold=`1. A24=없음, A27=1, A14=55,254.03, A4=부산광역시 사하구 구평동 / 2. A24=없음, A27=1, A14=28,222.45, A4=부산광역시 사하구 신평동 / 3. A24=없음, A27=1, A14=21,944.46, A4=부산광역시 사하구 신평동 / 4. A24=없음, A27=1, A14=20,876.43, A4=부산광역시 사하구 신평동 / 5. A24=대한제강(주)신평공장, A27=1, A14=20,472.75, A4=부산광역시 사하구 신평동 / 6. A24=？쇱?？??(二？？？臾쇰?？쇳?, A27=1, A14=20,254.87, A4=부산광역시 사하구 구평동 / 7. A24=없음, A27=1, A14=18,863.59, A4=부산광역시 사하구 신평동 / 8. A24=없음, A27=1, A14=17,007.45, A4=부산광역시 사하구 신평동 / 9. A24=없음, A27=1, A14=16,776.12, A4=부산광역시 사하구 신평동 / 10. A24=(주)남청, A27=1, A14=16,326.42, A4=부산광역시 사하구 장림동 / 11. A24=CJ제일제당(주) 부산공장, A27=1, A14=15,736.09, A4=부산광역시 사하구 장림동 / 12. A24=없음, A27=1, A14=15,458.94, A4=부산광역시 사하구 신평동 / 13. A24=주식회사유영산업, A27=1, A14=14,684.28, A4=부산광역시 사하구 신평동 / 14. A24=없음, A27=1, A14=13,019.24, A4=부산광역시 사하구 구평동 / 15. A24=없음, A27=2, A14=12,302.19, A4=부산광역시 사하구 장림동` reason=`list-top-missing 대한제강(주)신평공장` route=`semantic_plan_list`
- `Q216` 서구 위반건축물 중 높이 20m 이상인 채수  
  gold=`10채` reason=`count-mismatch gold=10 pred=[20.0, 22.0, 22.0]` route=`d010_attr_count`
- `Q308` 금정구 일반건축물대장 중 건폐율 50% 이상 80% 이하인 채수  
  gold=`4,536채` reason=`count-mismatch gold=4536 pred=[5698.0, 5698.0]` route=`d198_attr_count`
- `Q311` 동래구 허가일과 사용승인일 연도 차이가 3년 이상인 집합건축물 채수  
  gold=`360채` reason=`count-mismatch gold=360 pred=[3.0, 19645.0, 19645.0]` route=`d010_attr_count`
- `Q317` 동래구 학원(세부용도) 중 건물대지면적 200㎡ 이상인 채수  
  gold=`153채` reason=`count-mismatch gold=153 pred=[200.0, 154.0, 154.0]` route=`d198_attr_count`
- `Q330` 금정구 허가일과 사용승인일의 연도 차이가 5년 이상인 건물 수  
  gold=`278채` reason=`count-mismatch gold=278 pred=[5.0, 23435.0, 23435.0]` route=`d010_attr_count`
- `Q358` 금정구 단독주택 경과 40년 이상 vs 10년 미만 채수  
  gold=`old40=6,495; young10=327` reason=`compare-num-missing` route=`semantic_plan_count`

### BOOLEAN_NOT_DROPPED

- `Q181` 기장군 공동주택을 제외하고 높이 25m 이상인 건물 용도 상위 8개  
  gold=`1. usage=제1종근린생활시설, n=43 / 2. usage=업무시설, n=22 / 3. usage=숙박시설, n=20 / 4. usage=제2종근린생활시설, n=18 / 5. usage=의료시설, n=5 / 6. usage=공장, n=5 / 7. usage=자동차관련시설, n=5 / 8. usage=운동시설, n=4` reason=`engine-fail:missing_output` route=`semantic_plan_fallback`

### SPATIAL_TARGET_DROPPED

- `Q251` 사상구 산업단지 안 공장 비율(단지내 공장 / 사상구 공장)  
  gold=`pct=42.1833` reason=`scalar-mismatch hits=0 gold=[42.1833]` route=`semantic_plan_aggregate`

### BOOLEAN_OR_DROPPED

- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`engine-fail:slot_below_threshold:fields` route=`semantic_plan_fallback`
