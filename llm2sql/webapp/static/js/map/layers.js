/** 레이어 목록 UI · 출력/분석/KorDB 연동. */

export function renderLayerItem(info, { onToggle, onTable, onRemove }) {
  const row = document.createElement("div");
  row.className = "layer-item";
  row.dataset.id = info.id;
  const check = document.createElement("input");
  check.type = "checkbox";
  check.checked = Boolean(info.visible);
  check.addEventListener("change", () => onToggle(info.id, check.checked));
  const label = document.createElement("label");
  label.textContent = info.title || info.id;
  label.title = info.title || info.id;
  row.append(check, label);
  if (onTable) {
    const tableBtn = document.createElement("button");
    tableBtn.type = "button";
    tableBtn.className = "tiny-btn";
    tableBtn.textContent = "속성";
    tableBtn.addEventListener("click", () => onTable(info.id));
    row.appendChild(tableBtn);
  }
  if (onRemove) {
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "tiny-btn";
    rm.textContent = "삭제";
    rm.addEventListener("click", () => onRemove(info.id));
    row.appendChild(rm);
  }
  return row;
}

export function fillList(el, items, factory) {
  el.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "layer-empty";
    empty.textContent = "없음";
    el.appendChild(empty);
    return;
  }
  for (const item of items) {
    el.appendChild(factory(item));
  }
}
