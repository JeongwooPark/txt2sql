function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

async function dataJson(url, options) {
  const res = await fetch(url, options);
  let body = {};
  try {
    body = await res.json();
  } catch {
    body = {};
  }
  if (!res.ok) {
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg || item).join("; ")
          : body.message || `요청 실패 (${res.status})`;
    throw new Error(message);
  }
  return body;
}

async function loadSpatialTables() {
  const data = await dataJson("/api/data/tables");
  return data.tables || [];
}

function renderTableList(el, tables, onSelect) {
  if (!el) return;
  if (!tables.length) {
    el.innerHTML = '<p class="layer-empty">공간 테이블이 없습니다.</p>';
    return;
  }
  el.innerHTML = "";
  tables.forEach((table) => {
    const item = document.createElement("div");
    item.className = "dataset-item";
    item.dataset.fullName = table.full_name;
    item.innerHTML = `<strong>${escapeHtml(table.display_name || table.table_name)}</strong><span>${escapeHtml(table.full_name)}</span>`;
    item.addEventListener("click", () => {
      el.querySelectorAll(".dataset-item").forEach((node) => node.classList.remove("active"));
      item.classList.add("active");
      if (onSelect) onSelect(table);
    });
    el.appendChild(item);
  });
}
