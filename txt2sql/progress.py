"""파이프라인 단계 진행 기록."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


ProgressCallback = Callable[[str, str, dict[str, Any] | None], None]
TokenCallback = Callable[[str], None]


@dataclass
class ProgressTracker:
    """단계별 진행을 수집하고 선택적으로 실시간 콜백한다."""

    on_step: ProgressCallback | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: list[str] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def record_llm(self, purpose: str) -> None:
        self.llm_calls.append(purpose)
        self.emit("llm", f"LLM 호출: {purpose}", purpose=purpose)

    def emit(self, stage: str, message: str, **extra: Any) -> None:
        elapsed_ms = round((time.perf_counter() - self._t0) * 1000)
        item: dict[str, Any] = {
            "stage": stage,
            "message": message,
            "elapsed_ms": elapsed_ms,
        }
        if extra:
            from txt2sql.observability import mask_mapping

            item["detail"] = mask_mapping(
                {k: v for k, v in extra.items() if v is not None}
            )
        self.steps.append(item)
        if self.on_step is not None:
            self.on_step(stage, message, item.get("detail"))

    def stage_latency_ms(self) -> dict[str, int]:
        """단계별 구간 시간. emit의 elapsed_ms는 시작 시각 기준 누적값이다."""
        out: dict[str, int] = {}
        prev = 0
        for item in self.steps:
            elapsed = int(item.get("elapsed_ms") or 0)
            stage = str(item.get("stage") or "unknown")
            delta = max(0, elapsed - prev)
            out[stage] = out.get(stage, 0) + delta
            prev = elapsed
        return out
