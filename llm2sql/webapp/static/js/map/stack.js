/** 출력 레이어 스택: 추가·삭제·위계 이동. index 0 = 맨 위 = 높은 zIndex. */

export const ANALYSIS_Z_BASE = 100;
export const ANALYSIS_Z_STEP = 10;
export const KORDB_Z_BASE = 20;
export const KORDB_Z_STEP = 5;
export const BG_Z = 0;

export class LayerStack {
  constructor() {
    this._ids = [];
  }

  ids() {
    return [...this._ids];
  }

  has(layerId) {
    return this._ids.includes(layerId);
  }

  get length() {
    return this._ids.length;
  }

  add(layerId, { onTop = true } = {}) {
    if (!layerId || this._ids.includes(layerId)) return false;
    if (onTop) this._ids.unshift(layerId);
    else this._ids.push(layerId);
    return true;
  }

  remove(layerId) {
    const i = this._ids.indexOf(layerId);
    if (i < 0) return false;
    this._ids.splice(i, 1);
    return true;
  }

  moveUp(layerId) {
    const i = this._ids.indexOf(layerId);
    if (i <= 0) return false;
    [this._ids[i - 1], this._ids[i]] = [this._ids[i], this._ids[i - 1]];
    return true;
  }

  moveDown(layerId) {
    const i = this._ids.indexOf(layerId);
    if (i < 0 || i >= this._ids.length - 1) return false;
    [this._ids[i + 1], this._ids[i]] = [this._ids[i], this._ids[i + 1]];
    return true;
  }

  moveTo(layerId, index) {
    const current = this._ids.indexOf(layerId);
    if (current < 0 || !this._ids.length) return false;
    const target = Math.max(0, Math.min(Number(index) || 0, this._ids.length - 1));
    if (current === target) return false;
    const [item] = this._ids.splice(current, 1);
    this._ids.splice(target, 0, item);
    return true;
  }

  zIndices({ base = ANALYSIS_Z_BASE, step = ANALYSIS_Z_STEP } = {}) {
    const count = this._ids.length;
    const out = {};
    this._ids.forEach((id, index) => {
      out[id] = base + (count - index) * step;
    });
    return out;
  }
}
