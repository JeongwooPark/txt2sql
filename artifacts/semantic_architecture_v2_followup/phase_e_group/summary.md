# Phase E — Group / Distribution

Implemented in `txt2sql/planner/semantic_executor.py` (`build_sqp`):
- Preserve group dimensions on Logical→SQP
- Stable order: `ORDER BY agg DESC, key ASC`

Covered by `tests/planner/test_semantic_v2_operators.py::test_group_stable_order`.
