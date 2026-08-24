# 500문항 실패 원인 진단

- 시각: 2026-08-25 07:33:07
- 현재: 13/18 (72.2%)
- 기준선: 198/500 (39.6%)

## 구조 원인 빈도

- `ENTITY_SELECTION_ERROR`: 5

## 대표 실패 사례 (원인별 최대 8건)

### ENTITY_SELECTION_ERROR

- `N069` 엘시티랑 엘크루 블루오션 중에 더 높은 건물은?  
  gold=`name=중동 18290000 숙박시설 (주식회사엘시티피이에프브이); height_m=411.6 | name=엘시티, height_m=339.1 / name=르씨엘시티, height_m=57 / name=엘크루 블루오션, height_m=35.45` reason=`compare-name-missing 중동 18290000 숙박시설 (주식회사엘시티피이에프브이)` route=`semantic_plan_clarify`
- `Q244` 서구 공동주택 연면적 합계가 단독주택 연면적 합계보다 얼마나 큰가  
  gold=`apt_sum=1,953,917.88; detached_sum=819,131.1875; diff_sum=1,134,786.6925` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q245` 동구 용도 종류 수(distinct A9)와 가장 많은 용도 건수  
  gold=`n_usage=27; max_usage_n=9,360` reason=`scalar-mismatch hits=0 gold=[27.0, 9360.0]` route=`semantic_plan_clarify`
- `Q255` 금정구 2000년 이후 사용승인 공동주택 평균 층수가 1990년대보다 얼마나 높은가  
  gold=`avg_fl_2000=7.6913; avg_fl_1990s=6.4428; diff_fl=1.2486` reason=`compare-num-missing` route=`semantic_plan_clarify`
- `Q257` 해운대구 아파트 중 높이 결측 비율 %  
  gold=`pct_null_h=0` reason=`scalar-mismatch hits=0 gold=[0.0]` route=`semantic_plan_clarify`
