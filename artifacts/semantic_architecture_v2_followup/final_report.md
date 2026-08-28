# Semantic Architecture v2 Follow-up — Final Gold (DE uplift)

- Round3: 244/500 (48.8%)
- Prior follow-up (scalar): 248/500 (49.6%)
- **DE uplift (temporal+group): 277/500 (55.4%)**
- vs Round3: **+33 (+6.6%p)**, fixed=33, regressed=0
- Execution sources (compare share): legacy_router=183, semantic_plan=243, semantic_v2=74

## by_kind
- compare: 11/18 (61.1%)
- count: 113/180 (62.8%)
- group: 40/93 (43.0%)
- list: 84/128 (65.6%)
- meta: 16/19 (84.2%)
- scalar: 13/62 (21.0%)

## Gates
- overall>48.8: True
- scalar: 21.0%
- group: 43.0%
- cat5: 41.7% (was 13.3%)
- regressed<=fixed: True (0 ≤ 33)

- gold: `mapui_newset500_de_uplift_20260826_162745.json`
- detail: `artifacts/semantic_architecture_v2_followup/phase_de_uplift/final_report.md`
