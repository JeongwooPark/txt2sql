# Phase I — Spatial executor

`query_ir_to_semantic_plan` maps SpatialIR → `spatial_relations`; missing target inherits scope place.
Compiler already emits PostGIS (`ST_Intersects` / `ST_DWithin`) via `_apply_spatial_relations`.
IR must not contain raw `ST_*` strings (enforced by `assert_no_physical_names`).
