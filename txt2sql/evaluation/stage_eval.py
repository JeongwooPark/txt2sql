"""Stage-level semantic evaluation records."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

StageStatus = Literal["PASS", "FAIL", "SKIP"]


@dataclass
class StageResult:
    understanding: StageStatus = "SKIP"
    binding: StageStatus = "SKIP"
    logical_plan: StageStatus = "SKIP"
    physical_plan: StageStatus = "SKIP"
    compile: StageStatus = "SKIP"
    execution: StageStatus = "SKIP"
    interaction: StageStatus = "SKIP"
    presentation: StageStatus = "SKIP"
    policy: StageStatus = "SKIP"

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CaseStageEval:
    id: str
    final_pass: bool
    stages: StageResult = field(default_factory=StageResult)
    root_cause: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "final_pass": self.final_pass,
            "stages": self.stages.as_dict(),
            "root_cause": self.root_cause,
            "extras": self.extras,
        }


_REASON_STAGE: list[tuple[str, str, str]] = [
    ("slot_below_threshold", "understanding", "SEMANTIC_SLOT_THRESHOLD"),
    ("plan generation failed", "logical_plan", "PLAN_GENERATION_FAILED"),
    ("unsupported_coverage", "binding", "SEMANTIC_UNSUPPORTED_COVERAGE"),
    ("missing_aggregation", "logical_plan", "SEMANTIC_INCOMPLETE_AGGREGATION"),
    ("missing_predicate", "logical_plan", "SEMANTIC_UNBOUND_PREDICATE"),
    ("missing_order", "logical_plan", "SEMANTIC_MISSING_ORDER"),
    ("missing_limit", "logical_plan", "SEMANTIC_MISSING_LIMIT"),
    ("p03", "policy", "SEMANTIC_POLICY_P03"),
    ("p07", "policy", "SEMANTIC_POLICY_P07"),
    ("p06", "policy", "SEMANTIC_POLICY_P06"),
    ("p04", "policy", "SEMANTIC_POLICY_P04"),
    ("count-mismatch", "execution", "COUNT_MISMATCH"),
    ("list-top-missing", "execution", "LIST_TOP_MISSING"),
    ("scalar-mismatch", "execution", "SCALAR_MISMATCH"),
    ("group-mismatch", "execution", "GROUP_MISMATCH"),
    ("compare-num-missing", "execution", "COMPARE_MISMATCH"),
    ("meta-mismatch", "presentation", "META_MISMATCH"),
    ("timeout", "execution", "EXECUTION_TIMEOUT"),
]


def taxonomy_from_reason(reason: str) -> str:
    text = (reason or "").strip()
    if not text:
        return "unknown"
    lower = text.lower()
    for needle, _stage, code in _REASON_STAGE:
        if needle in lower:
            return code if not text.startswith("engine-fail") else f"engine:{needle}"
    if text.startswith("engine-fail:"):
        rest = text[len("engine-fail:") :].strip()
        head = rest.split(":", 1)[0].strip() or rest[:40]
        return f"engine:{head[:60]}"
    head = text.split(":", 1)[0].strip()
    return head[:60] if head else "unknown"


def evaluate_stages(
    *,
    case_id: str,
    final_pass: bool,
    understanding_ok: bool | None = None,
    binding_ok: bool | None = None,
    logical_ok: bool | None = None,
    physical_ok: bool | None = None,
    compile_ok: bool | None = None,
    execution_ok: bool | None = None,
    interaction_ok: bool | None = None,
    presentation_ok: bool | None = None,
    policy_ok: bool | None = None,
    root_cause: str | None = None,
) -> CaseStageEval:
    def _st(v: bool | None) -> StageStatus:
        if v is None:
            return "SKIP"
        return "PASS" if v else "FAIL"

    stages = StageResult(
        understanding=_st(understanding_ok),
        binding=_st(binding_ok),
        logical_plan=_st(logical_ok),
        physical_plan=_st(physical_ok),
        compile=_st(compile_ok),
        execution=_st(execution_ok),
        interaction=_st(interaction_ok),
        presentation=_st(presentation_ok),
        policy=_st(policy_ok),
    )
    if root_cause is None and not final_pass:
        for name, status in stages.as_dict().items():
            if status == "FAIL":
                root_cause = f"STAGE_{name.upper()}"
                break
        root_cause = root_cause or "UNKNOWN"
    return CaseStageEval(id=case_id, final_pass=final_pass, stages=stages, root_cause=root_cause)


def stages_from_reason(*, case_id: str, final_pass: bool, reason: str) -> CaseStageEval:
    """Map a map-ui fail reason into stage PASS/FAIL record."""
    if final_pass:
        return evaluate_stages(
            case_id=case_id,
            final_pass=True,
            understanding_ok=True,
            binding_ok=True,
            logical_ok=True,
            physical_ok=True,
            compile_ok=True,
            execution_ok=True,
            root_cause=None,
        )
    lower = (reason or "").lower()
    flags: dict[str, bool | None] = {
        "understanding_ok": True,
        "binding_ok": True,
        "logical_ok": True,
        "physical_ok": True,
        "compile_ok": True,
        "execution_ok": True,
        "interaction_ok": None,
        "presentation_ok": None,
        "policy_ok": True,
    }
    root = "UNKNOWN"
    matched = False
    for needle, stage, code in _REASON_STAGE:
        if needle in lower:
            matched = True
            root = code
            key = {
                "understanding": "understanding_ok",
                "binding": "binding_ok",
                "logical_plan": "logical_ok",
                "physical_plan": "physical_ok",
                "compile": "compile_ok",
                "execution": "execution_ok",
                "interaction": "interaction_ok",
                "presentation": "presentation_ok",
                "policy": "policy_ok",
            }[stage]
            flags[key] = False
            break
    if not matched and reason:
        root = taxonomy_from_reason(reason)
        flags["execution_ok"] = False
    return evaluate_stages(case_id=case_id, final_pass=False, root_cause=root, **flags)


def migrate_failures(
    before: dict[str, bool],
    after: dict[str, bool],
) -> dict[str, list[str]]:
    """Compare case_id -> passed maps for failure migration.

    Only cases present in both maps contribute to the four buckets.
    """
    fixed: list[str] = []
    regressed: list[str] = []
    still_fail: list[str] = []
    still_pass: list[str] = []
    for cid in sorted(set(before) & set(after)):
        b = before[cid]
        a = after[cid]
        if (not b) and a:
            fixed.append(cid)
        elif b and (not a):
            regressed.append(cid)
        elif (not b) and (not a):
            still_fail.append(cid)
        else:
            still_pass.append(cid)
    return {
        "fixed": fixed,
        "regressed": regressed,
        "still_fail": still_fail,
        "still_pass": still_pass,
    }


def annotate_doc_stages(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Attach stage evaluation to each scored case row."""
    from txt2sql.evaluation.case_map import case_id, case_passed, case_rows

    out: list[dict[str, Any]] = []
    for case in case_rows(doc):
        cid = case_id(case)
        passed = bool(case_passed(case))
        reason = str(case.get("reason") or case.get("fail_reason") or case.get("error") or "")
        ev = stages_from_reason(case_id=cid, final_pass=passed, reason=reason)
        out.append(ev.as_dict())
    return out
