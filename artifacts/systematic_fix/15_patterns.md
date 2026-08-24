# 13차 실패 → 수정 패턴 (분류기 라벨이 아님)

기준: `artifacts/systematic_fix/13_post_fix500.json` 217실패. 문항 ID는 평가 집합이며 production에 넣지 않는다.

각 패턴은 **진단 → 수정 → 해당 문항만 평가**를 3회 반복한다. 마지막에 full-500.

| 키 | 구멍 | 13차 규모 | 1회차 수정 단위 |
|---|---|---:|---|
| `P1_year_text_field` | 사용승인 연도를 `approval_date` 텍스트에 gte/between → validator가 거절, RAG 금지 후 engine-fail | 17 | validator·predicate가 연도 SQL(`A13`)을 허용 |
| `P2_over_clarify` | 시 전역·D198 OR·산업단지·POI가 clarify로 실행을 죽임 | 54 | heuristic 완성 시 LLM/clarify 금지, sido·D198 슬롯 |
| `P3_followup` | OVER 목록 dump가 list, 앵커 손실, 후속 합계 n 탈락 | 83 | count 강제, 앵커, 합계 n 유지 |
| `P5_range_attr` | 건폐·용적 BETWEEN, 지하+지상, 특수지, 레거시 라우트가 복합 질의를 훔침 | 64 | 힌트 구간·레거시 양보 |
| `P6_d198` | 세부용도/용도분류/허가일 슬롯 또는 D198 가드가 D010을 막음 | 29 | D198 테이블+컬럼, 가드 범위 |

`P4_boolean`·`P7_legacy_steal`·`P8_spatial`은 위 패턴에 겹친다. 독립 루프는 돌리지 않고 해당 루프에서 같이 본다.

평가: `scripts/eval_q500_gold.py --pattern KEY --out ... --fail-report ... --fail-md ... --no-full-copy`
세션 부모 문항은 컨텍스트로만 같이 돌리고, `pattern_passed`는 패턴 ID만 센다.
13/14는 덮지 않는다.
