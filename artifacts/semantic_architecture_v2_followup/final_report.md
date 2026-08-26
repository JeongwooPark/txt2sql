# Semantic Architecture v2 Follow-up — Final Gold

- Round3: 244/500 (48.8%)
- Follow-up: 248/500 (49.6%)
- Delta: +4 (+0.8%p)
- Migration: fixed=4 regressed=0 still_pass=244 still_fail=252
- Execution sources: {'legacy_router': 193, 'semantic_plan': 263, 'semantic_v2': 44}
- Share %: {'legacy_router': 38.6, 'semantic_plan': 52.6, 'semantic_v2': 8.8}

## by_kind
- compare: 8/18 (44.4%)
- count: 98/180 (54.4%)
- group: 31/93 (33.3%)
- list: 84/128 (65.6%)
- meta: 16/19 (84.2%)
- scalar: 11/62 (17.7%)

## Gates
- overall>48.8: True
- scalar: 17.7%
- group: 33.3%
- cat5: 13.3%
- regressed<=fixed: True
- count-mismatch concrete: 98.0%

- gold: `mapui_newset500_followup_20260826_152056.json`
