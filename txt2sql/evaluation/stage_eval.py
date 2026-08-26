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


def migrate_failures(
    before: dict[str, bool],
    after: dict[str, bool],
) -> dict[str, list[str]]:
    """Compare case_id -> passed maps for failure migration."""
    fixed: list[str] = []
    regressed: list[str] = []
    still_fail: list[str] = []
    still_pass: list[str] = []
    for cid in sorted(set(before) | set(after)):
        b = before.get(cid)
        a = after.get(cid)
        if b is False and a is True:
            fixed.append(cid)
        elif b is True and a is False:
            regressed.append(cid)
        elif b is False and a is False:
            still_fail.append(cid)
        elif b is True and a is True:
            still_pass.append(cid)
    return {
        "fixed": fixed,
        "regressed": regressed,
        "still_fail": still_fail,
        "still_pass": still_pass,
    }
