"""파이프라인 단계 진행 기록."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


ProgressCallback = Callable[[str, str, dict[str, Any] | None], None]


@dataclass
class ProgressTracker:
    """단계별 진행을 수집하고 선택적으로 실시간 콜백한다."""

    on_step: ProgressCallback | None = None
    steps: list[dict[str, Any]] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def emit(self, stage: str, message: str, **extra: Any) -> None:
        elapsed_ms = round((time.perf_counter() - self._t0) * 1000)
        item: dict[str, Any] = {
            "stage": stage,
            "message": message,
            "elapsed_ms": elapsed_ms,
        }
        if extra:
            item["detail"] = {k: v for k, v in extra.items() if v is not None}
        self.steps.append(item)
        if self.on_step is not None:
            self.on_step(stage, message, item.get("detail"))
