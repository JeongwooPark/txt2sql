# 맵 UI 신규 500 — 이번 회차(Round1–3) 문제사항 (v0.3.1)

작성일: 2026-08-26  
캠페인: 맵 UI 신규 정답표 500문항 정확도 개선  
제품 버전(이 브랜치): **0.3.1** (main은 **0.3.0** 유지)

## 배경·목표

신규 자연어 테스트셋 500문항을 맵 UI 경로로 평가했을 때 초기 정답률이 **36.0%(180/500)** 에 머물렀다.  
목표는 실패 패턴(count/list/group/scalar·라우팅 오탐)을 라운드별로 고레버리지 수정해 정답률을 끌어올리고, 잔여 이슈를 다음 라운드 백로그로 정리하는 것이다.

정답표: `docs/llm2sql_신규_자연어질의_테스트셋_500건_정답표.json`  
평가 러너: `tests/map_ui_gold500/`

## 전후 정확도

| 시점 | 결과 파일 | 통과 | 정답률 | Δ(직전 대비) |
|------|-----------|------|--------|--------------|
| 초기 | `mapui_newset500_20260825_1759.json` | 180/500 | **36.0%** | — |
| Round1 | `mapui_newset500_fixed_20260826_095513.json` | 208/500 | **41.6%** | +28 · +5.6%p |
| Round2 | `mapui_newset500_round2_20260826_111602.json` | 222/500 | **44.4%** | +14 · +2.8%p |
| Round3 | `mapui_newset500_round3_20260826_120607.json` | 244/500 | **48.8%** | +22 · +4.4%p |

누적: **36.0% → 48.8%** (+64 · +12.8%p). Round3 소요 약 745.5초, 평균 지연 약 1,337ms.

## Round별 상위 수정과 효과

### Round1 (36.0% → 41.6%)

1. **지역 필터·행정코드** (`domain.py`, `catalog_attrs.py`, `intent_router.py`, `spatial_templates.py`)  
   - 구·군 `A4 LIKE '%서구%'`류를 행정코드 접두 술어로 통일.  
   - count-mismatch 85→70, 기본 구·군 건수 회복.
2. **Contract→Plan→SQL 불변식** (`contract_verifier.py`, `validator.py`, `plan_sql_verifier.py`, `sql_equivalence.py`)  
   - group/aggregation/predicate 누락 hard-fail.  
   - group 13→26(+13), list 60→75(+15).
3. **D198 동적 allowlist** (`catalog.py`, `compiler.py`)  
   - rejected physical identifier 12→0.

### Round2 (41.6% → 44.4%)

1. **meta 「알려줘」 오탐** (`meta_qa.py`)  
   - 장소/구 + 건물·기초구역이면서 스키마 키워드 없을 때 meta=False.  
   - meta_table count-mismatch 16→0, count 42.2%→52.2%(+18).
2. **건물명 컬럼 → name-lookup 오탐** (`domain.py`)  
   - name_lookup list-top-missing 10→2.
3. **age unsupported_coverage** (`validator.py`, `generator.py`)  
   - approval_date order/select/agg/group 허용. unsupported 19→14.

순증 +14 = 획득 39 − 회귀 25. list·cat7은 골드 재생성·비결정 정렬로 하락.

### Round3 (44.4% → 48.8%)

1. **list ORDER BY + rank 「많은」** (`generator.py`)  
   - list-top-missing 40→28, list 정답률 50.0%→65.6%(+20).
2. **detail_usage · IS DISTINCT FROM · 범위** (`compiler.py`, `domain.py`, `d198_attrs.py`, `intent_router.py`)  
   - count-mismatch 63→51, cat4 22%→35%(+13).
3. **cat4 용도×장소 평균(부분)** (`generator.py` d198_ledger)  
   - scalar-mismatch 표기 36→25이나 scalar 통과 수는 8 유지(slot/P03 fallback).

순증 +22 = 획득 26 − 회귀 4.

## 잔여 주요 문제사항 (Round3 실측)

| 패턴 | 건수(R3) | R2→R3 | 원인 가설 | 영향 카테고리 |
|------|----------|-------|-----------|---------------|
| count-mismatch | 51 | 63→51 (−12) | Q033 IS DISTINCT→P03 전이, 건폐율 D198 vs D010, ILIKE/= 잔차 | cat1·2·4 count |
| list-top-missing | 28 | 40→28 (−12) | 용도 목록·name_lookup·차트 가로채기, 골드 비결정 정렬 | list |
| scalar-mismatch | 25 | 36→25 (−11) | AVG SQL은 맞으나 slot/P03로 미통과 전이 | scalar · cat4 |
| plan generation failed | 22 | 21→22 (+1) | 휴리스틱/LLM 플랜 생성 실패 잔존 | 다수 |
| group-mismatch | 20 | 21→20 (−1) | group_by·라벨 정합 잔차 | group · cat3 |
| engine-fail:P03 | 18 | 4→18 (+14) | IS DISTINCT/AVG 정책 충돌 증가(회귀성) | count·scalar |
| unsupported_coverage | 15 | 14→15 (+1) | age gap/상관/분위 등 고급 temporal 미착수 | cat5 |
| slot_below_threshold | 14 | 8→14 (+6) | cat4 AVG plan fallback | scalar · cat4 |
| engine-fail:P07 | 10 | 10→10 (0) | 정책 차단 | 다수 |
| engine-fail:P06 | 5 | 15→5 (−10) | Round3 부수 감소 | — |

종류별 정답률(R3): meta 84.2%, list 65.6%, count 53.9%, compare 44.4%, group 33.3%, **scalar 12.9%**.  
카테고리: cat2 85.7%, cat1 68.6%, cat3 53.3%, cat7 48.3%, cat6 40.0%, cat4 35.0%, **cat5 13.3%**.

## 회귀·리스크

### Round2

- list 75→64(−11), cat7 70.0%→48.3%(−13): 골드 재생성·비결정 정렬·후속/차트 게이트.
- 순증 +14 대비 회귀 25건으로 획득 대비 회귀 비율이 높았음.

### Round3

- 회귀 lost 4: **Q214, Q281, Q288, Q470**.
- meta 17→16(−1).
- **P03 4→18(+14)**: IS DISTINCT/AVG 정책 충돌 — 모니터링·게이트 완화 필요.
- slot_below_threshold 8→14(+6): cat4 AVG가 SQL 정합이어도 통과로 안 넘어감.
- 평균 지연 1,252→1,337ms 소폭 증가.

## 다음 점검방안

| 우선 | 점검 | 기대 | 방법 |
|------|------|------|------|
| 1 | scalar AVG slot/P03 게이트 | scalar −8~12 통과 전환 | validator/policy + Q203 회귀 |
| 2 | cat7 chart_help·후속 게이트 | 회귀 회수·후속 안정 | pipeline 우선순위 + followup |
| 3 | Q033 P03 · 건폐율 D010 선호 | count −5~10 | policy / d198 vs d010 라우트 |
| 4 | age gap/상관/분위 temporal | unsupported −8~12 | temporal.py + validator |
| 5 | 잔여 list name_lookup·용도 | list-top −5~8 | router + ORDER 보조 |

## 관련 결과 파일·캔버스 경로

### 저장소 내 결과 JSON (`tests/map_ui_gold500/results/`)

- 초기: `mapui_newset500_20260825_1759.json`
- Round1: `mapui_newset500_fixed_20260826_095513.json`
- Round2: `mapui_newset500_round2_20260826_111602.json` (+ `.jsonl`)
- Round3: `mapui_newset500_round3_20260826_120607.json` (+ `.jsonl`)

### Cursor Canvas (저장소 밖 — git 미포함)

경로 루트: `C:\Users\polem\.cursor\projects\d-py-workspace-llm2sql\canvases\`

- `map-ui-newset500-error-analysis.canvas.tsx`
- `map-ui-newset500-fix-plan.canvas.tsx` / `map-ui-newset500-fix-results.canvas.tsx`
- `map-ui-newset500-round2-plan.canvas.tsx` / `map-ui-newset500-round2-results.canvas.tsx`
- `map-ui-newset500-round3-plan.canvas.tsx` / `map-ui-newset500-round3-results.canvas.tsx`

### 단위 테스트(라운드 가드)

- `tests/test_round2_high_leverage.py`
- `tests/test_round3_high_leverage.py`

## 버전·브랜치 메모

- 이 문서는 **0.3.1 안정화 브랜치**용 이슈 기록이다.
- **main은 0.3.0**으로 두고, 본 캠페인 코드·평가·문서는 feature/release 브랜치에서만 버전을 0.3.1로 올린다.
- Round3 에이전트는 평가·결과 캔버스까지 완료(244/500, 48.8%).
