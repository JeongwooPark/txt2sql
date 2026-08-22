"""두 평가 런 비교."""

from __future__ import annotations

from typing import Any


def compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    sa = a.get("summary") or a
    sb = b.get("summary") or b
    keys = sorted(set(sa.get("metrics", {})) | set(sb.get("metrics", {})))
    metrics = {}
    for key in keys:
        va = float((sa.get("metrics") or {}).get(key, 0))
        vb = float((sb.get("metrics") or {}).get(key, 0))
        metrics[key] = {"a": va, "b": vb, "delta": vb - va}
    return {
        "a": {
            "name": sa.get("name"),
            "mode": sa.get("mode"),
            "passed": sa.get("passed"),
            "n": sa.get("n"),
            "env_blocked": sa.get("env_blocked"),
        },
        "b": {
            "name": sb.get("name"),
            "mode": sb.get("mode"),
            "passed": sb.get("passed"),
            "n": sb.get("n"),
            "env_blocked": sb.get("env_blocked"),
        },
        "metrics": metrics,
        "error_counts": {
            "a": sa.get("error_counts") or {},
            "b": sb.get("error_counts") or {},
        },
    }


def to_markdown(cmp: dict[str, Any]) -> str:
    lines = [
        "# eval comparison",
        "",
        "| metric | A | B | delta |",
        "|---|---:|---:|---:|",
    ]
    for key, row in cmp["metrics"].items():
        lines.append(
            f"| {key} | {row['a']:.4f} | {row['b']:.4f} | {row['delta']:+.4f} |"
        )
    lines.append("")
    lines.append(
        f"A mode={cmp['a']['mode']} passed={cmp['a']['passed']}/{cmp['a']['n']} "
        f"blocked={cmp['a']['env_blocked']}"
    )
    lines.append(
        f"B mode={cmp['b']['mode']} passed={cmp['b']['passed']}/{cmp['b']['n']} "
        f"blocked={cmp['b']['env_blocked']}"
    )
    return "\n".join(lines) + "\n"
