# 500문항 실패 원인 진단

- 시각: 2026-08-24 16:19:09
- 현재: 207/500 (41.4%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `ENTITY_SELECTION_ERROR`: 149
- `PREDICATE_DROPPED`: 96
- `RANGE_BOUND_DROPPED`: 33
- `FOLLOWUP_CONTEXT_LOST`: 27
- `BOOLEAN_OR_DROPPED`: 13
- `SPATIAL_TARGET_DROPPED`: 3
- `BOOLEAN_NOT_DROPPED`: 2
- `OUTPUT_SHAPE_MISMATCH`: 2

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N004` 내일 부산 강수량 예보 알려줘  
  gold=`범위 외. 기상 예보는 보유 데이터에 없다.` reason=`meta-mismatch` route=`guide_unscoped`
- `N005` 김해공항 항공편 지연 현황은?  
  gold=`범위 외. 항공편 현황은 보유 데이터에 없다.` reason=`meta-mismatch` route=`clarify_unknown_term`
- `N010` 용도별건물공간정보는 어디 구까지 있어?  
  gold=`1. table_name=AL_D198_26260_20250115 / 2. table_name=AL_D198_26410_20250115` reason=`group-label-missing` route=`clarify_unknown_term`
- `N018` 문현동에는 건물이 얼마나 있어?  
  gold=`9,080채` reason=`count-mismatch gold=9080 pred=[]` route=`semantic_plan_clarify`
- `N032` 강서구 건물은 얼마나 되나요?  
  gold=`49,373채` reason=`count-mismatch gold=49373 pred=[2000.0, 5.0]` route=`clarify_unknown_term`
- `N036` 부산시 전체 건물 수는?  
  gold=`472,620채` reason=`count-mismatch gold=472620 pred=[10.0, 26.0, 20250704.0, 2025.0, 7.0, 4.0]` route=`meta_catalog`
- `N037` 부산광역시 공동주택은 몇 채야?  
  gold=`30,773채` reason=`count-mismatch gold=30773 pred=[]` route=`semantic_plan_clarify`
- `N040` 광안동 숙박시설은 몇 채야?  
  gold=`50채` reason=`count-mismatch gold=50 pred=[2000.0, 5.0]` route=`clarify_unknown_term`

### PREDICATE_DROPPED

- `N016` 법정동명과 행정동명의 차이가 뭐야?  
  gold=`diff=법정동명(A4)은 토지·건물 대장 주소, 행정동명(ADM_NM)은 센서스 행정구역 경계` reason=`scalar-mismatch hits=0 gold=[4.0]` route=`building_name_lookup`
- `N026` 중앙동 건물 몇 채야?  
  gold=`확인 필요. 중앙동은 여러 구에 있어 구를 지정해야 한다.` reason=`meta-mismatch` route=`building_in_dong_spatial`
- `N046` 강서구 자동차관련시설은 몇 채야?  
  gold=`97채` reason=`count-mismatch gold=97 pred=[]` route=`building_name_lookup`
- `N056` 광안동에서 높이가 20미터를 넘는 건물은?  
  gold=`1. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=105.55, A9=공동주택 / 2. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=81.25, A9=공동주택 / 3. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=78.5, A9=공동주택 / 4. A24=없음, A4=부산광역시 수영구 광안동, A5=744-32, A16=77.4, A9=공동주택 / 5. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=742-2, A16=75.7, A9=공동주택 / 6. A24=부산광안대우아이빌, A4=부산광역시 수영구 광안동, A5=193-4, A16=74.45, A9=업무시설 / 7. A24=호메르스관광호텔, A4=부산광역시 수영구 광안동, A5=193-1, A16=73.8, A9=숙박시설 / 8. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=73.15, A9=공동주택 / 9. A24=협성엠파이어아파트, A4=부산광역시 수영구 광안동, A5=745-2, A16=72.9, A9=공동주택 / 10. A24=호텔아쿠아펠리스, A4=부산광역시 수영구 광안동, A5=192-5, A16=71.2, A9=숙박시설 / 11. A24=광안동에스케이뷰, A4=부산광역시 수영구 광안동, A5=473-2, A16=70.45, A9=공동주택 / 12. A24=베스테이 센트럴뷰, A4=부산광역시 수영구 광안동, A5=51-1, A16=69.9, A9=업무시설 / 13. A24=광원아파트, A4=부산광역시 수영구 광안동, A5=526-1, A16=68.8, A9=공동주택 / 14. A24=광안역 성원상떼빌, A4=부산광역시 수영구 광안동, A5=143-1, A16=67.91, A9=공동주택 / 15. A24=광안스윗팰리스, A4=부산광역시 수영구 광안동, A5=74-5, A16=67.9, A9=공동주택 외 15건` reason=`list-top-missing 광안동에스케이뷰` route=`semantic_plan_list`
- `N066` 지번 알려줘  
  gold=`lot=197; A24=GS하이츠자이; A4=부산광역시 남구 용호동` reason=`name-missing GS하이츠자이` route=`semantic_plan_list`
- `N070` 부산대학교와 부경대학교 건물 수를 비교해줘  
  gold=`pusan_n=95; pukyong_n=89` reason=`compare-num-missing` route=`semantic_plan_count`
- `N085` 북구 기초구역 면적이 가장 큰 것은?  
  gold=`BAS_ID=46535; SIG_KOR_NM=북구; BAS_AR=5.768` reason=`scalar-mismatch hits=0 gold=[46535.0, 5.768]` route=`building_rank_연면적`
- `N086` 사하구 산업단지는 몇 개야?  
  gold=`6개` reason=`count-mismatch gold=6 pred=[0.0, 0.0]` route=`industrial_count`

### FOLLOWUP_CONTEXT_LOST

- `N064` 그 건물 높이는?  
  gold=`height_m=71.2; A24=호텔아쿠아펠리스; A5=192-5` reason=`name-missing 호텔아쿠아펠리스` route=`semantic_plan_clarify`
- `Q210` 중구 위반건축물 전체 채수와 그 중 제2종근린생활시설 채수  
  gold=`violate_n=264; near_n=53` reason=`scalar-mismatch hits=0 gold=[264.0, 53.0]` route=`meta_catalog`
- `Q284` 우동과 교차하는 기초구역 개수와 그 중 면적 최대값  
  gold=`n=30; max_ar=6.2449` reason=`scalar-mismatch hits=1 gold=[30.0, 6.2449]` route=`spatial_bas_dong_count`
- `Q382` 그중 연면적 8000㎡ 이상만  
  gold=`530채` reason=`count-mismatch gold=530 pred=[100.0, 1.0, 887.0, -1.0, 96.6, 2.0]` route=`semantic_plan_list`
- `Q383` 그 건물들의 평균 높이와 평균 연면적  
  gold=`n=530; avg_h=72.4683; avg_gfa=19,764.5394` reason=`scalar-mismatch hits=0 gold=[530.0, 72.4683, 19764.5394]` route=`semantic_plan_clarify`
- `Q384` 그중 가장 높은 건물의 이름과 지번  
  gold=`A24=엘시티; A4=부산광역시 해운대구 중동; A5=1829; A16=339.1` reason=`name-missing 엘시티` route=`semantic_plan_clarify`
- `Q387` 그 건물들 연면적 합계  
  gold=`n=29; sum_gfa=106,135.2449` reason=`scalar-mismatch hits=0 gold=[29.0, 106135.2449]` route=`semantic_plan_clarify`
- `Q390` 그중 2000년 이후 사용승인만  
  gold=`265채` reason=`count-mismatch gold=265 pred=[]` route=`semantic_plan_clarify`

### SPATIAL_TARGET_DROPPED

- `N092` 명지국가산업단지 안에 있는 건물은 몇 채야?  
  gold=`709채` reason=`count-mismatch gold=709 pred=[18679.0, 18679.0]` route=`buildings_in_industrial`
- `Q185` 사상구 공장 또는 자동차관련시설이면서 산업단지와 교차하는 건물 수  
  gold=`2,143채` reason=`count-mismatch gold=2143 pred=[]` route=`semantic_plan_clarify`
- `Q272` 명지·녹산 국가산업단지 안 공장 또는 창고시설 채수  
  gold=`2,375채` reason=`count-mismatch gold=2375 pred=[]` route=`semantic_plan_clarify`

### RANGE_BOUND_DROPPED

- `Q103` 금정구에서 연면적 5000㎡ 이상이고 15층 이상인 철근콘크리트 공동주택 수  
  gold=`285채` reason=`count-mismatch gold=285 pred=[100.0, 1.0, 607.0, -7.0, 13964.7192, 2.0]` route=`semantic_plan_list`
- `Q104` 사하구 창고시설 중 연면적 3000㎡ 이상이면서 건축면적 1000㎡ 이상인 채수  
  gold=`40채` reason=`count-mismatch gold=40 pred=[3000.0, 59.0, 59.0]` route=`building_area_threshold_count`
- `Q116` 사상구 자동차관련시설 중 연면적 1000㎡ 이상이고 건축면적 400㎡ 이상인 채수  
  gold=`43채` reason=`count-mismatch gold=43 pred=[1000.0, 2699.0, 2699.0]` route=`building_area_threshold_count`
- `Q118` 영도구 공동주택 중 1990년대 사용승인이고 지상 10층 이상인 채수  
  gold=`99채` reason=`count-mismatch gold=99 pred=[10.0, 1990.0]` route=`d198_year_stats`
- `Q134` 용호동 교육연구시설 중 대지면적 3000㎡ 이상이고 연면적 2000㎡ 이상인 채수  
  gold=`12채` reason=`count-mismatch gold=12 pred=[3000.0, 15.0, 15.0]` route=`building_area_threshold_count`
- `Q136` 사상구 공장 중 경량철골구조이고 연면적 1500㎡ 이상인 채수  
  gold=`12채` reason=`count-mismatch gold=12 pred=[100.0, 1.0, 946.0, -20.0, 946.0, -20.0]` route=`semantic_plan_list`
- `Q144` 안락동 공동주택 중 지어진지 30년 넘고 연면적 2000㎡ 이상인 채수  
  gold=`30채` reason=`count-mismatch gold=30 pred=[2000.0, 107.0, 107.0]` route=`building_area_threshold_count`
- `Q145` 사직동 공동주택 중 대지면적 1000㎡ 이상이고 연면적 2000㎡ 이상인 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[1000.0, 129.0, 129.0]` route=`building_area_threshold_count`

### BOOLEAN_OR_DROPPED

- `Q152` 수영구 숙박시설 또는 위락시설 중 연면적 1000㎡ 이상인 채수  
  gold=`44채` reason=`count-mismatch gold=44 pred=[]` route=`semantic_plan_clarify`
- `Q154` 금정구 교육연구시설 또는 노유자시설 중 대지면적 1500㎡ 이상인 채수  
  gold=`105채` reason=`count-mismatch gold=105 pred=[]` route=`semantic_plan_clarify`
- `Q155` 해운대구에서 업무시설이거나 판매시설이면서 높이 30m 이상인 채수  
  gold=`94채` reason=`count-mismatch gold=94 pred=[]` route=`semantic_plan_clarify`
- `Q169` 북구에서 의료시설 또는 노유자시설이면서 연면적 1500㎡ 이상인 이름과 용도  
  gold=`1. A24=부민병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=12,278.8 / 2. A24=센트럴병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=12,110.63 / 3. A24=미래로 병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=9,957.51 / 4. A24=베스티안빌딩, A4=부산광역시 북구 화명동, A9=의료시설, A14=9,491.38 / 5. A24=없음, A4=부산광역시 북구 금곡동, A9=의료시설, A14=8,354.55 / 6. A24=일신기독병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=8,089.46 / 7. A24=구포성심병원, A4=부산광역시 북구 구포동, A9=의료시설, A14=7,957.75 / 8. A24=더청명빌딩, A4=부산광역시 북구 덕천동, A9=의료시설, A14=5,723.41 / 9. A24=구포 p 요양병원, A4=부산광역시 북구 구포동, A9=노유자시설, A14=5,671.21 / 10. A24=부산시노인전문병원, A4=부산광역시 북구 만덕동, A9=의료시설, A14=5,489.76 / 11. A24=덕천동 요양병원, A4=부산광역시 북구 덕천동, A9=의료시설, A14=4,968.85 / 12. A24=구포부민병원, A4=부산광역시 북구 구포동, A9=의료시설, A14=4,939.02 / 13. A24=덕천동 응급의료센타, A4=부산광역시 북구 덕천동, A9=의료시설, A14=4,706.6 / 14. A24=화명동대림타운, A4=부산광역시 북구 화명동, A9=의료시설, A14=4,486.05 / 15. A24=환희교회, A4=부산광역시 북구 만덕동, A9=노유자시설, A14=4,051.1` reason=`list-top-missing 부민병원` route=`guide_out_of_scope`
- `Q170` 연제구 문화및집회시설 또는 운동시설 중 대지면적 2000㎡ 이상인 채수  
  gold=`4채` reason=`count-mismatch gold=4 pred=[]` route=`semantic_plan_clarify`
- `Q175` 동래구 철근콘크리트 또는 철골철근콘크리트 구조이면서 높이 50m 이상인 채수  
  gold=`241채` reason=`count-mismatch gold=241 pred=[]` route=`semantic_plan_clarify`
- `Q176` 남구 아파트 또는 업무시설 중 지하 1층 이상이면서 지상 10층 이상인 채수  
  gold=`338채` reason=`count-mismatch gold=338 pred=[]` route=`semantic_plan_clarify`
- `Q179` 부산진구 위험물저장및처리시설 또는 분뇨쓰레기처리시설 중 연면적 500㎡ 이상 채수  
  gold=`2채` reason=`count-mismatch gold=2 pred=[]` route=`semantic_plan_clarify`

### BOOLEAN_NOT_DROPPED

- `Q193` 사하구 일반지번이 아닌 건물 중 공장인 채수  
  gold=`7채` reason=`count-mismatch gold=7 pred=[2000.0, 5.0]` route=`clarify_unknown_term`
- `Q276` 문현1동 안 건물 중 높이 25m 이상이면서 공동주택이 아닌 채수  
  gold=`1채` reason=`count-mismatch gold=1 pred=[]` route=`semantic_plan_clarify`

### OUTPUT_SHAPE_MISMATCH

- `Q231` 영도구 15층 이상 건물 중 공동주택 비율 %  
  gold=`pct=91.716` reason=`scalar-mismatch hits=0 gold=[91.716]` route=`building_floor_count`
- `Q238` 장림동 공장 중 연면적 1000㎡ 이상 비율 %  
  gold=`pct=24.7444` reason=`scalar-mismatch hits=0 gold=[24.7444]` route=`building_area_threshold_count`
