# 평가 lineage audit (Phase 0)

기록 시각: 2026-08-24  
Git HEAD: `2bd714fb84c866104de483517db9668abd0032b6` (`master`)  
질문 파일: `docs/평가문항_500.json`  
SHA256: `73786531eac4188bdaa328c2674e9db1c01fb26f5d7afaf612d1fa0bdad03788`

## 500 숫자 기준선

`artifacts/evaluation/q500_gold_eval.json`을 **현재 500문항 숫자 기준선**으로 채택한다.

| 항목 | 값 |
|---|---|
| 시각 | 2026-08-24 12:53:09 |
| 총문항 | 500 |
| 성공 | 198 |
| 실패 | 302 |
| 정확도 | 39.6% |
| timeout | 60s |
| full-500 재실행 | 하지 않음 |

과거 `baseline_summary.json` / `d6fc4af3` 수치는 역사 기록이며 현재 HEAD 기준선이 아니다.

## 질문 파일 구조

- 총 500문항
- `N001`–`N100` (앞 100) + `Q101`–`Q500` (뒤 400)
- gold SQL에 `A9` 등장 338건, D198 테이블 언급 57건

## 용도 정책 (가능성 B)

문서의 “용도는 D198만”과 실제 gold의 전 구 `AL_D010.A9` 사용이 불일치한다.

제품 정책은 다음과 같이 고정한다.

- 전 구 주용도 조건은 `building.usage` → `AL_D010.A9`를 사용한다.
- D198 전용 속성(세부용도·허가일 등 D198에만 있는 슬롯)만 D198 범위(금정·동래)로 제한한다.
- gold 숫자/문항 ID를 production 코드에 하드코딩하지 않는다.

## pytest

`uv run pytest -q` → **137 passed**.

full-500은 lineage가 바뀌거나 Phase 16 구조 게이트 이후에만 재실행한다.
