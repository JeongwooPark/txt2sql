# Phase F — Legacy router shrink

`should_try_semantic_v2` skips `FAST_SIMPLE_COUNT` / `FAST_THRESHOLD`.
READY aggregate/group/temporal/spatial/rank prefer semantic-v2 before `try_route`.
Pipeline entry: compile+exec → return `execution_source=semantic_v2`.
