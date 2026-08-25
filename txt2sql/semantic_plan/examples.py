"""Contract signature에 맞춘 소수 Plan 예제. 벡터 검색이 아니다."""

from __future__ import annotations

from txt2sql.query_understanding.contract import QueryContract

_EXAMPLES: dict[str, str] = {
    "ratio": (
        '{"query_kind":"aggregate","entity":"building","ratios":['
        '{"numerator_predicate":{"op":"cmp","operator":"eq","left":{"kind":"field","field":"usage"},'
        '"right":{"kind":"literal","value":"공동주택"}},'
        '"denominator_predicate":{"op":"cmp","operator":"gte","left":{"kind":"field","field":"ground_floors"},'
        '"right":{"kind":"literal","value":15}},"multiplier":100,"alias":"ratio_pct"}]}'
    ),
    "percentile": (
        '{"query_kind":"aggregate","entity":"building","aggregations":['
        '{"function":"percentile","field":"height_m","percentile":0.9,"alias":"pctl"}]}'
    ),
    "spatial": (
        '{"query_kind":"count","entity":"building","spatial_relations":['
        '{"relation":"intersects","target":{"entity":"basic_zone"}}]}'
    ),
    "count": (
        '{"query_kind":"count","entity":"building","scope":{"place":{"name":"해운대구","kind":"gu"}}}'
    ),
}


def examples_for_contract(contract: QueryContract | None) -> list[str]:
    if contract is None:
        return []
    keys: list[str] = []
    if contract.ratios:
        keys.append("ratio")
    if contract.percentile_requests:
        keys.append("percentile")
    if contract.wants_spatial or contract.spatial_path:
        keys.append("spatial")
    if contract.query_kind == "count":
        keys.append("count")
    return [_EXAMPLES[k] for k in keys if k in _EXAMPLES]
