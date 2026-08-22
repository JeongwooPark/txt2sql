"""출력 레이어 스택: 추가·삭제·위계(zIndex) 이동. 지도 z-index의 기준은 출력 목록이다."""

from __future__ import annotations

from dataclasses import dataclass

ANALYSIS_Z_BASE = 100
ANALYSIS_Z_STEP = 10
KORDB_Z_BASE = 20
KORDB_Z_STEP = 5
BG_Z = 0


@dataclass(frozen=True)
class LayerRef:
    layer_id: str
    z_index: int


class LayerStack:
    """index 0 = 목록 맨 위 = 지도에서 가장 위 (높은 zIndex)."""

    def __init__(self) -> None:
        self._ids: list[str] = []

    def ids(self) -> list[str]:
        return list(self._ids)

    def __contains__(self, layer_id: str) -> bool:
        return layer_id in self._ids

    def __len__(self) -> int:
        return len(self._ids)

    def add(self, layer_id: str, *, on_top: bool = True) -> bool:
        """새 레이어를 넣는다. 기본은 맨 위(최신 질의가 위에 보이게)."""
        if not layer_id or layer_id in self._ids:
            return False
        if on_top:
            self._ids.insert(0, layer_id)
        else:
            self._ids.append(layer_id)
        return True

    def remove(self, layer_id: str) -> bool:
        if layer_id not in self._ids:
            return False
        self._ids.remove(layer_id)
        return True

    def move_up(self, layer_id: str) -> bool:
        """목록에서 한 칸 위(zIndex 증가). 이미 맨 위면 False."""
        try:
            index = self._ids.index(layer_id)
        except ValueError:
            return False
        if index == 0:
            return False
        self._ids[index - 1], self._ids[index] = (
            self._ids[index],
            self._ids[index - 1],
        )
        return True

    def move_down(self, layer_id: str) -> bool:
        """목록에서 한 칸 아래(zIndex 감소). 이미 맨 아래면 False."""
        try:
            index = self._ids.index(layer_id)
        except ValueError:
            return False
        if index >= len(self._ids) - 1:
            return False
        self._ids[index + 1], self._ids[index] = (
            self._ids[index],
            self._ids[index + 1],
        )
        return True

    def move_to(self, layer_id: str, index: int) -> bool:
        """드래그 드롭: 목표 위치(0=맨 위)로 이동."""
        try:
            current = self._ids.index(layer_id)
        except ValueError:
            return False
        if not self._ids:
            return False
        target = max(0, min(int(index), len(self._ids) - 1))
        if current == target:
            return False
        item = self._ids.pop(current)
        self._ids.insert(target, item)
        return True

    def z_indices(
        self,
        *,
        base: int = ANALYSIS_Z_BASE,
        step: int = ANALYSIS_Z_STEP,
    ) -> dict[str, int]:
        """맨 위 항목이 가장 큰 zIndex."""
        count = len(self._ids)
        return {
            layer_id: base + (count - index) * step
            for index, layer_id in enumerate(self._ids)
        }

    def snapshot(self) -> list[LayerRef]:
        zmap = self.z_indices()
        return [LayerRef(layer_id=lid, z_index=zmap[lid]) for lid in self._ids]
