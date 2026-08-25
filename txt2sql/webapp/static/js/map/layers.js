/** 레이어 목록 UI · 출력/분석/KorDB 연동. */

let contextMenuEl = null;

export function hideLayerContextMenu() {
  contextMenuEl?.remove();
  contextMenuEl = null;
}

export function bindLayerContextMenu(row, items) {
  if (!row || !items?.length) return;
  row.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    e.stopPropagation();
    hideLayerContextMenu();
    const menu = document.createElement("div");
    menu.className = "layer-context-menu";
    menu.setAttribute("role", "menu");
    for (const item of items) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("role", "menuitem");
      btn.textContent = item.label;
      btn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        hideLayerContextMenu();
        item.action();
      });
      menu.appendChild(btn);
    }
    document.body.appendChild(menu);
    const pad = 8;
    const x = Math.min(e.clientX, window.innerWidth - menu.offsetWidth - pad);
    const y = Math.min(e.clientY, window.innerHeight - menu.offsetHeight - pad);
    menu.style.left = `${Math.max(pad, x)}px`;
    menu.style.top = `${Math.max(pad, y)}px`;
    contextMenuEl = menu;
  });
}

function onDocumentPointerDown(e) {
  if (contextMenuEl && !contextMenuEl.contains(e.target)) {
    hideLayerContextMenu();
  }
}

document.addEventListener("pointerdown", onDocumentPointerDown, true);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hideLayerContextMenu();
});
window.addEventListener("blur", hideLayerContextMenu);
window.addEventListener("resize", hideLayerContextMenu);

export function renderLayerItem(
  info,
  {
    onToggle,
    onTable,
    onRemove,
    onMoveUp,
    onMoveDown,
    draggable,
    contextMenu,
  } = {}
) {
  const row = document.createElement("div");
  row.className = "layer-item";
  row.dataset.id = info.id;
  if (draggable) {
    row.draggable = true;
    const handle = document.createElement("span");
    handle.className = "drag-handle";
    handle.title = "드래그하여 위계 이동";
    handle.textContent = "⋮⋮";
    row.appendChild(handle);
  }
  if (typeof onToggle === "function") {
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = Boolean(info.visible);
    check.addEventListener("change", () => onToggle(info.id, check.checked));
    row.appendChild(check);
  }
  const label = document.createElement("label");
  label.textContent = info.title || info.id;
  label.title = info.id && info.title && info.id !== info.title
    ? `${info.title} (${info.id})`
    : info.title || info.id;
  row.appendChild(label);
  if (onMoveUp || onMoveDown) {
    const order = document.createElement("span");
    order.className = "order-btns";
    if (onMoveUp) {
      const up = document.createElement("button");
      up.type = "button";
      up.className = "tiny-btn";
      up.title = "위로";
      up.textContent = "▲";
      up.addEventListener("click", () => onMoveUp(info.id));
      order.appendChild(up);
    }
    if (onMoveDown) {
      const down = document.createElement("button");
      down.type = "button";
      down.className = "tiny-btn";
      down.title = "아래로";
      down.textContent = "▼";
      down.addEventListener("click", () => onMoveDown(info.id));
      order.appendChild(down);
    }
    row.appendChild(order);
  }
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
  if (contextMenu?.length) {
    row.title = row.title || "오른쪽 클릭하여 메뉴 열기";
    bindLayerContextMenu(row, contextMenu);
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

export function bindReorder(listEl, { onDrop } = {}) {
  if (!listEl || typeof onDrop !== "function") return;
  listEl.addEventListener("dragstart", (e) => {
    const item = e.target.closest(".layer-item");
    if (!item || !listEl.contains(item)) return;
    e.dataTransfer.setData("text/plain", item.dataset.id || "");
    e.dataTransfer.effectAllowed = "move";
    item.classList.add("dragging");
  });
  listEl.addEventListener("dragend", (e) => {
    const item = e.target.closest(".layer-item");
    item?.classList.remove("dragging");
    listEl.querySelectorAll(".drag-over").forEach((n) => n.classList.remove("drag-over"));
  });
  listEl.addEventListener("dragover", (e) => {
    e.preventDefault();
    const item = e.target.closest(".layer-item");
    listEl.querySelectorAll(".drag-over").forEach((n) => n.classList.remove("drag-over"));
    if (item) item.classList.add("drag-over");
  });
  listEl.addEventListener("drop", (e) => {
    e.preventDefault();
    const draggedId = e.dataTransfer.getData("text/plain");
    const target = e.target.closest(".layer-item");
    listEl.querySelectorAll(".drag-over").forEach((n) => n.classList.remove("drag-over"));
    if (!draggedId || !target || target.dataset.id === draggedId) return;
    const ids = [...listEl.querySelectorAll(".layer-item")].map((n) => n.dataset.id);
    const from = ids.indexOf(draggedId);
    let to = ids.indexOf(target.dataset.id);
    if (from < 0 || to < 0) return;
    const rect = target.getBoundingClientRect();
    if (e.clientY > rect.top + rect.height / 2 && to < ids.length - 1) {
      to += 1;
    }
    if (from < to) to -= 1;
    onDrop(draggedId, to);
  });
  listEl.addEventListener("scroll", hideLayerContextMenu);
}
