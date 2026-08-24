# 20차 실패 → 수정 패턴 (분류기 라벨이 아님)

기준: `artifacts/systematic_fix/20_post_fix500.json` 162실패. 문항 ID는 평가 집합이며 production에 넣지 않는다.
기존 `05`–`21` 산출은 덮지 않는다.

각 패턴은 **진단 → 수정 → 해당 문항만 평가**를 3회 반복한다. 마지막에 full-500.

| 키 | 구멍 | 20차 규모 | 1회차 수정 단위 |
|---|---|---:|---|
| `Q1_clarify_spatial` | 산업단지·기초구역·POI 비교가 clarify로 실행이 끊기거나 D060 가드가 건물∩산단 SQL을 거절 | 18 | 이름 있는 산단/구 전역 산단은 실행, 건물 질의는 D010∩D060 허용 |
| `Q2_followup` | 후속 필터·집계·순위가 부모 술어/공간/표시를 잃거나 1건 오차 | 62 | 후속 델타가 부모 filters·spatial·select를 유지 |
| `Q3_agg_rank` | 용도별 상위 집계에 ORDER BY 누락, 다중 집계 거절, 비율이 meta/레거시로 새김 | 24 | group-rank SQL에 ORDER BY LIMIT, 다중 집계 허용, 비율은 plan |
| `Q4_legacy_predicate` | 레거시 라우트가 복합 술어를 훔침, NOT/특수지/구간이 0건·과다건 | 35 | 복합은 plan에 양보, 특수지·NOT 컴파일 |
| `Q5_d198` | 세부용도/용도분류/허가일·주요용도가 D010 A9 또는 레거시 카운트로 새김 | 23 | D198 테이블+컬럼, 가드가 D010 A9를 막지 않고 D198로 보냄 |

평가: `scripts/eval_q500_gold.py --pattern-ids artifacts/systematic_fix/22_pattern_ids.json --pattern KEY --out ... --fail-report ... --fail-md ... --no-full-copy`
세션 부모 문항은 컨텍스트로만 같이 돌리고, `pattern_passed`는 패턴 ID만 센다.
`05`–`21`은 덮지 않는다.
