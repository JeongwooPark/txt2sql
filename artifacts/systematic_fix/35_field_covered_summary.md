# Field-Covered Pipeline — eval 35

브랜치: `contract-capability-sqp-20260825`  
기준: `32_post_fix500` / `34_full500`

## 한 줄

필드 단위 Capability + 실행 shape 검증 + SQP 연산자 + Bind를 넣었다. full-500 367→379 (73.4%→75.8%). 32의 393 (78.6%)에는 14건 부족. Q3 10→15/24. pytest 258 passed.

## 평가

| | 32 | 34 | 35 |
|---|---|---|---|
| pytest | 246 | 254 | 258 |
| Q3_agg_rank 24 | 10 | 10 | **15** |
| full-500 | 393 (78.6%) | 367 (73.4%) | **379 (75.8%)** |
| p95 ms | 12344 | 13969 | **2332** |

산출: `35_pytest.json`, `35_q3_agg_rank.json`, `35_full500.json`, `35_vs_32_34_compare.json`. 05–29는 덮지 않음.
