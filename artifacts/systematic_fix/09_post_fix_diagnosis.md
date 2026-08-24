# 500문항 실패 원인 진단 (구조 개선 후)

- 시각: 2026-08-24 21:21:25
- 현재: 263/500 (52.6%)
- 직전 비교 기준: 207/500 (41.4%)
- 초기 기준선: 198/500 (39.6%)
- timeout: 1건 (한도 40s 유지). p95 15687ms.

## 구조 원인 빈도

- `PREDICATE_DROPPED`: 118
- `ENTITY_SELECTION_ERROR`: 65
- `RANGE_BOUND_DROPPED`: 35
- `FOLLOWUP_CONTEXT_LOST`: 23
- `BOOLEAN_OR_DROPPED`: 6
- `SPATIAL_TARGET_DROPPED`: 2
- `EXECUTION_TIMEOUT`: 1

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N004` 내일 부산 강수량 예보 알려줘  
  gold=`범위 외. 기상 예보는 보유 데이터에 없다.` reason=`meta-mismatch` route=`guide_unscoped`
- `N010` 용도별건물공간정보는 어디 구까지 있어?  
  gold=`1. table_name=AL_D198_26260_20250115 / 2. table_name=AL_D198_26410_20250115` reason=`group-label-missing` route=`semantic_plan_clarify`
- `N036` 부산시 전체 건물 수는?  
  gold=`472,620채` reason=`count-mismatch gold=472620 pred=[10.0, 26.0, 20250704.0, 2025.0, 7.0, 4.0]` route=`meta_catalog`
- `N037` 부산광역시 공동주택은 몇 채야?  
  gold=`30,773채` reason=`count-mismatch gold=30773 pred=[]` route=`semantic_plan_clarify`
- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `N090` 사하구 산업단지와 교차하는 기초구역은 몇 개야?  
  gold=`35개` reason=`count-mismatch gold=35 pred=[]` route=`semantic_plan_clarify`
- `Q124` 구서동 공동주택 중 2000년 이후 사용승인·철근콘크리트·15층 이상인 채수  
  gold=`111채` reason=`count-mismatch gold=111 pred=[2000.0, 5.0]` route=`clarify_unknown_term`

### EXECUTION_TIMEOUT

- `N005` 김해공항 항공편 지연 현황은?  
  gold=`범위 외. 항공편 현황은 보유 데이터에 없다.` reason=`timeout>40s` route=`None`

### PREDICATE_DROPPED

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`building_name_lookup`
- `N026` 중앙동 건물 몇 채야?  
  gold=`확인 필요. 중앙동은 여러 구에 있어 구를 지정해야 한다.` reason=`meta-mismatch` route=`building_in_dong_spatial`
- `N056` 광안동에서 높이가 20미터를 넘는 건물은?  
  gold=`1. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=105.55, A9=공동주택 / 2. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=81.25, A9=공동주택 / 3. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=78.5, A9=공동주택 / 4. A24=없음, A4=부산광역시 수영구 광안동, A5=744-32, A16=77.4, A9=공동주택 / 5. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=75.7, A9=공동주택 / 6. A24=부산광안대우아이빌, A4=부산광역시 수영구 광안동, A5=193-4, A16=74.45, A9=업무시설 / 7. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A5=193-1, A16=73.8, A9=숙박시설 / 8. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=73.15, A9=공동주택 / 9. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=745-2, A16=72.9, A9=공동주택 / 10. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A5=192-5, A16=71.2, A9=숙박시설 / 11. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=70.45, A9=공동주택 / 12. A24=베스테이 센트럴뷰, A4=부산광역시 수영구 광안동, A5=51-1, A16=69.9, A9=업무시설 / 13. A24=광원아파트, A4=부산광역시 수영구 광안동, A5=526-1, A16=68.8, A9=공동주택 / 14. A24=광안역 성원상떼빌, A4=부산광역시 수영구 광안동, A5=143-1, A16=67.91, A9=공동주택 / 15. A24=광안스윗팰리스, A4=부산광역시 수영구 광안동, A5=74-5, A16=67.9, A9=공동주택 외 15건` reason=`list-top-missing 광안동에스케이뷰` route=`semantic_plan_list`
- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`name-missing GS하이츠자이` route=`semantic_plan_list`
- `N070` 부산대학교와 부경대학교 건물 수를 비교해줘  
  gold=`pusan_n=95; pukyong_n=89` reason=`compare-num-missing` route=`semantic_plan_count`
- `N085` 북구 기초구역 면적이 가장 큰 것은?  
  gold=`BAS_ID=46535; SIG_KOR_NM=북구; BAS_AR=5.768` reason=`scalar-mismatch hits=1 gold=[46535.0, 5.768]` route=`bas_area_topn_value`
- `N086` 사하구 산업단지는 몇 개야?  
  gold=`6개` reason=`count-mismatch gold=6 pred=[0.0, 0.0]` route=`industrial_count`
- `N096` 금정구 주거용 연면적 크기별 수는?  
  gold=`1. bin=130㎡이상, n=9,343 / 2. bin=60-85㎡, n=1,732 / 3. bin=60㎡미만, n=1,825 / 4. bin=85-130㎡, n=3,762` reason=`group-mismatch` route=`building_name_lookup`

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q210` 중구 위반건축물 전체 채수와 그 중 제2종근린생활시설 채수  
  gold=`violate_n=264; near_n=53` reason=`scalar-mismatch hits=0 gold=[264.0, 53.0]` route=`meta_catalog`
- `Q284` 우동과 교차하는 기초구역 개수와 그 중 면적 최대값  
  gold=`n=30; max_ar=6.2449` reason=`scalar-mismatch hits=0 gold=[30.0, 6.2449]` route=`bas_area_topn_value`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 1662.0, 59.75, 2.0, 1407.0]` route=`semantic_plan_list`
- `Q383` 그 건물들의 평균 높이와 평균 연면적  
  gold=`n=530; avg_h=72.4683; avg_gfa=19,764.5394` reason=`scalar-mismatch hits=0 gold=[530.0, 72.4683, 19764.5394]` route=`building_profile`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=0 gold=[29.0, 106135.2449]` route=`semantic_plan_aggregate`
- `Q396` 그 중 연면적 합계  
  gold=`sum_gfa=528,749.885; n=44` reason=`scalar-mismatch hits=1 gold=[528749.885, 44.0]` route=`semantic_plan_aggregate`
- `Q398` 그중 산업단지 안에 있는 것만  
  gold=`360채` reason=`count-mismatch gold=360 pred=[3000.0, 0.0]` route=`None`

### RANGE_BOUND_DROPPED

- `Q103` 금정구에서 연면적 5000㎡ 이상이고 15층 이상인 철근콘크리트 공동주택 수  
  gold=`285채` reason=`count-mismatch gold=285 pred=[100.0, 1.0, 607.0, -7.0, 13964.7192, 2.0]` route=`semantic_plan_list`
- `Q118` 영도구 공동주택 중 1990년대 사용승인이고 지상 10층 이상인 채수  
  gold=`99채` reason=`count-mismatch gold=99 pred=[10.0, 1990.0]` route=`d198_year_stats`
- `Q136` 사상구 공장 중 경량철골구조이고 연면적 1500㎡ 이상인 채수  
  gold=`12채` reason=`count-mismatch gold=12 pred=[180.0, 180.0]` route=`semantic_plan_count`
- `Q137` 동구 공동주택 중 지어진지 20년 넘고 지상 10층 이상인 채수  
  gold=`19채` reason=`count-mismatch gold=19 pred=[10.0, 46.0, 46.0]` route=`building_floor_count`
- `Q144` 안락동 공동주택 중 지어진지 30년 넘고 연면적 2000㎡ 이상인 채수  
  gold=`30채` reason=`count-mismatch gold=30 pred=[2000.0, 107.0, 107.0]` route=`building_area_threshold_count`
- `Q159` 부산진구 제1·2종근린생활시설을 뺀 건물 중 높이 25m 이상인 채수  
  gold=`1,043채` reason=`count-mismatch gold=1043 pred=[1.0, 25.0, 91.0, 91.0]` route=`building_height_count`
- `Q166` 남구 공동주택 사용승인이 1980년 이상 1999년 이하이면서 10층 이상인 채수  
  gold=`88채` reason=`count-mismatch gold=88 pred=[1980.0, 0.0, 0.0]` route=`building_floor_count`
- `Q176` 남구 아파트 또는 업무시설 중 지하 1층 이상이면서 지상 10층 이상인 채수  
  gold=`338채` reason=`count-mismatch gold=338 pred=[451.0, 451.0]` route=`semantic_plan_count`

### BOOLEAN_OR_DROPPED

- `Q169` 북구에서 의료시설 또는 노유자시설이면서 연면적 1500㎡ 이상인 이름과 용도  
  gold=`1. A24=부민병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=12,278.8 / 2. A24=센트럴병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=12,110.63 / 3. A24=미래로 병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=9,957.51 / 4. A24=베스티안빌딩, A4=부산광역시 북구 화명동, A9=의료시설, A14=9,491.38 / 5. A24=없음, A4=부산광역시 북구 금곡동, A9=의료시설, A14=8,354.55 / 6. A24=일신기독병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=8,089.46 / 7. A24=구포성심병원, A4=부산광역시 북구 구포동, A9=의료시설, A14=7,957.75 / 8. A24=더청명빌딩, A4=부산광역시 북구 덕천동, A9=의료시설, A14=5,723.41 / 9. A24=구포 p 요양병원, A4=부산광역시 북구 구포동, A9=노유자시설, A14=5,671.21 / 10. A24=부산시노인전문병원, A4=부산광역시 북구 만덕동, A9=의료시설, A14=5,489.76 / 11. A24=덕천동 요양병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=4,968.85 / 12. A24=구포부민병원, A4=부산광역시 북구 구포동, A9=의료시설, A14=4,939.02 / 13. A24=덕천동 응급의료센타, A4=부산광역시 북구 덕천동, A9=의료시설, A14=4,706.6 / 14. A24=화명동대림타운, A4=부산광역시 북구 화명동, A9=의료시설, A14=4,486.05 / 15. A24=환희교회, A4=부산광역시 북구 만덕동, A9=노유자시설, A14=4,051.1` reason=`list-top-missing 부민병원` route=`guide_out_of_scope`
- `Q175` 동래구 철근콘크리트 또는 철골철근콘크리트 구조이면서 높이 50m 이상인 채수  
  gold=`241채` reason=`count-mismatch gold=241 pred=[]` route=`semantic_plan_clarify`
- `Q179` 부산진구 위험물저장및처리시설 또는 분뇨쓰레기처리시설 중 연면적 500㎡ 이상 채수  
  gold=`2채` reason=`count-mismatch gold=2 pred=[]` route=`semantic_plan_clarify`
- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
- `Q327` 동래구 명륜동 오피스텔 또는 사무소(세부용도) 채수  
  gold=`81채` reason=`count-mismatch gold=81 pred=[]` route=`semantic_plan_clarify`
- `Q336` 금정구 청룡동 문교사회용 또는 공공용 채수  
  gold=`64채` reason=`count-mismatch gold=64 pred=[]` route=`semantic_plan_clarify`

### SPATIAL_TARGET_DROPPED

- `Q185` 사상구 공장 또는 자동차관련시설이면서 산업단지와 교차하는 건물 수  
  gold=`2,143채` reason=`count-mismatch gold=2143 pred=[4791.0, 281.0, 17.0, 617.6, 187.0, 789.2]` route=`building_profile_compare`
- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`
