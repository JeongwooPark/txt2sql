import {
  BG_SOURCES,
  createKordbWmsLayer,
  createMap,
  createTileWmsLayer,
  createWfsLayer,
  fitLonLatExtent,
} from "./core.js";
import { fillList, renderLayerItem } from "./layers.js";
import { bindIdentify, renderProperties } from "./identify.js";
import { applyThemeToLayer } from "./styles.js";

const state = {
  map: null,
  bgLayers: {},
  analysis: [],
  output: new Set(),
  kordb: [],
  theme: "default",
  tableLayer: null,
  tableOffset: 0,
};

function renderingMode() {
  const sel = document.getElementById("rendering-mode-select");
  return sel && sel.value === "wfs" ? "wfs" : "wms";
}

function showBanner(message) {
  const el = document.getElementById("map-banner");
  if (!el) return;
  if (!message) {
    el.hidden = true;
    el.textContent = "";
    return;
  }
  el.hidden = false;
  el.textContent = message;
}

function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = false;
}

function closeModals() {
  document.querySelectorAll(".modal").forEach((m) => {
    m.hidden = true;
  });
}

function showProps(title, props) {
  const heading = document.getElementById("attr-modal-title");
  const body = document.getElementById("attr-modal-body");
  if (heading) heading.textContent = title || "속성 정보";
  if (body) renderProperties(body, props);
  openModal("attr-modal");
}

function refreshLists() {
  const analysisEl = document.getElementById("analysis-layers-list");
  const outputEl = document.getElementById("output-layers-list");
  const kordbEl = document.getElementById("kordb-layers-list");
  if (analysisEl) {
    fillList(analysisEl, state.analysis, (info) =>
      renderLayerItem(info, {
        onToggle: toggleAnalysis,
        onTable: openAttributeTable,
        onRemove: removeAnalysis,
      })
    );
  }
  const outputs = state.analysis.filter((a) => state.output.has(a.id));
  if (outputEl) {
    fillList(outputEl, outputs, (info) =>
      renderLayerItem(info, { onToggle: toggleAnalysis })
    );
  }
  if (kordbEl) {
    fillList(kordbEl, state.kordb, (info) =>
      renderLayerItem(info, { onToggle: toggleKordb })
    );
  }
}

function toggleAnalysis(id, visible) {
  const item = state.analysis.find((a) => a.id === id);
  if (!item) return;
  item.visible = visible;
  item.olLayer.setVisible(visible);
  if (visible) state.output.add(id);
  else state.output.delete(id);
  refreshLists();
}

function toggleKordb(id, visible) {
  const item = state.kordb.find((a) => a.id === id);
  if (!item) return;
  item.visible = visible;
  item.olLayer.setVisible(visible);
}

function removeAnalysis(id) {
  const idx = state.analysis.findIndex((a) => a.id === id);
  if (idx < 0) return;
  const item = state.analysis[idx];
  state.map.removeLayer(item.olLayer);
  state.analysis.splice(idx, 1);
  state.output.delete(id);
  if (item.layer) {
    fetch(`/api/map/layer/${encodeURIComponent(item.layer)}`, {
      method: "DELETE",
    }).catch(() => {});
  }
  refreshLists();
}

function addAnalysisLayer(info) {
  if (!state.map || !info || !info.available) {
    if (info && info.error) showBanner(info.error);
    return;
  }
  showBanner("");
  const mode =
    renderingMode() === "wfs" && info.wfs_allowed !== false ? "wfs" : "wms";
  const olLayer =
    mode === "wfs" ? createWfsLayer(info) : createTileWmsLayer(info);
  applyThemeToLayer(olLayer, state.theme);
  olLayer.setVisible(true);
  state.map.addLayer(olLayer);
  const entry = {
    id: info.layer,
    layer: info.layer,
    title: info.title || info.layer,
    workspace: info.workspace,
    visible: true,
    olLayer,
    info,
  };
  state.analysis.push(entry);
  state.output.add(entry.id);
  refreshLists();
  fitLonLatExtent(state.map, info.extent);
}

async function loadKordb() {
  const listEl = document.getElementById("kordb-layers-list");
  try {
    const res = await fetch("/api/map/layers");
    const data = await res.json();
    state.kordb.forEach((item) => state.map.removeLayer(item.olLayer));
    state.kordb = [];
    for (const layer of data.layers || []) {
      const olLayer = createKordbWmsLayer(layer);
      state.map.addLayer(olLayer);
      state.kordb.push({
        id: layer.name,
        title: layer.name,
        visible: false,
        olLayer,
      });
    }
    refreshLists();
  } catch {
    if (listEl) {
      listEl.innerHTML =
        '<p class="layer-empty">KorDB 레이어를 불러오지 못했습니다.</p>';
    }
  }
}

async function checkStatus() {
  try {
    const res = await fetch("/api/map/status");
    const data = await res.json();
    if (!data.online) {
      showBanner(data.message || "지도를 사용할 수 없습니다.");
    } else {
      showBanner("");
    }
  } catch {
    showBanner("지도 상태를 확인할 수 없습니다. 채팅은 사용할 수 있습니다.");
  }
}

function fillBackgroundList() {
  const el = document.getElementById("background-layers-list");
  if (!el) return;
  el.innerHTML = "";
  for (const [id, spec] of Object.entries(BG_SOURCES)) {
    const row = document.createElement("div");
    row.className = "layer-item";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = id === "cartoDark";
    check.addEventListener("change", () => {
      const layer = state.bgLayers[id];
      if (layer) layer.setVisible(check.checked);
    });
    const label = document.createElement("label");
    label.textContent = spec.title;
    row.append(check, label);
    el.appendChild(row);
  }
}

async function openAttributeTable(id) {
  const item = state.analysis.find((a) => a.id === id);
  if (!item || !item.layer) return;
  state.tableLayer = item.layer;
  state.tableOffset = 0;
  document.getElementById("table-modal-title").textContent =
    item.title || "속성 테이블";
  openModal("table-modal");
  await loadTablePage();
}

async function loadTablePage() {
  if (!state.tableLayer) return;
  const limit = Number(document.getElementById("table-limit")?.value || 50);
  const res = await fetch("/api/map/attributes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      layer: state.tableLayer,
      limit,
      offset: state.tableOffset,
    }),
  });
  const data = await res.json();
  const body = document.getElementById("table-modal-body");
  const info = document.getElementById("table-page-info");
  if (!data.ok) {
    body.textContent = data.detail || "속성을 불러오지 못했습니다.";
    return;
  }
  const cols = data.columns || [];
  const rows = data.rows || [];
  const table = document.createElement("table");
  table.className = "attr-table";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  for (const col of cols) {
    const th = document.createElement("th");
    th.textContent = col;
    hr.appendChild(th);
  }
  thead.appendChild(hr);
  table.appendChild(thead);
  const tbody = document.createElement("tbody");
  for (const row of rows) {
    const tr = document.createElement("tr");
    for (const col of cols) {
      const td = document.createElement("td");
      td.textContent = row[col] == null ? "" : String(row[col]);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  body.innerHTML = "";
  body.appendChild(table);
  const total = data.total || 0;
  const from = total ? state.tableOffset + 1 : 0;
  const to = Math.min(state.tableOffset + rows.length, total);
  if (info) info.textContent = `${from}–${to} / ${total}`;
}

function bindUi() {
  document.getElementById("apply-theme-btn")?.addEventListener("click", () => {
    const theme = document.getElementById("theme-select")?.value || "default";
    state.theme = theme;
    for (const item of state.analysis) {
      applyThemeToLayer(item.olLayer, theme);
    }
  });
  document.getElementById("style-editor-btn")?.addEventListener("click", () => {
    openModal("style-modal");
  });
  document.getElementById("style-apply-btn")?.addEventListener("click", () => {
    const custom = {
      fill: document.getElementById("style-fill")?.value,
      stroke: document.getElementById("style-stroke")?.value,
      width: Number(document.getElementById("style-width")?.value || 2),
      opacity: Number(document.getElementById("style-opacity")?.value || 0.8),
    };
    for (const item of state.analysis) {
      if (item.visible) applyThemeToLayer(item.olLayer, state.theme, custom);
    }
    closeModals();
  });
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", closeModals);
  });
  document.querySelectorAll(".modal").forEach((modal) => {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) closeModals();
    });
  });
  document.getElementById("table-prev")?.addEventListener("click", async () => {
    const limit = Number(document.getElementById("table-limit")?.value || 50);
    state.tableOffset = Math.max(0, state.tableOffset - limit);
    await loadTablePage();
  });
  document.getElementById("table-next")?.addEventListener("click", async () => {
    const limit = Number(document.getElementById("table-limit")?.value || 50);
    state.tableOffset += limit;
    await loadTablePage();
  });
  document.getElementById("table-limit")?.addEventListener("change", async () => {
    state.tableOffset = 0;
    await loadTablePage();
  });

  const handle = document.getElementById("chat-resize");
  const workspace = document.querySelector(".workspace");
  if (handle && workspace) {
    let dragging = false;
    handle.addEventListener("mousedown", (e) => {
      dragging = true;
      e.preventDefault();
    });
    window.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      const rect = workspace.getBoundingClientRect();
      const width = Math.min(560, Math.max(300, rect.right - e.clientX));
      workspace.style.setProperty("--chat-w", `${width}px`);
      state.map?.updateSize();
    });
    window.addEventListener("mouseup", () => {
      if (dragging) {
        dragging = false;
        state.map?.updateSize();
      }
    });
  }
}

function init() {
  if (typeof ol === "undefined") {
    showBanner("OpenLayers를 불러오지 못했습니다.");
    return;
  }
  const { map, bgLayers } = createMap("map");
  state.map = map;
  state.bgLayers = bgLayers;
  fillBackgroundList();
  bindIdentify(map, () => {
    const analysis = state.analysis.map((a) => ({
      title: a.title,
      olLayer: a.olLayer,
    }));
    const kordb = state.kordb
      .filter((k) => k.visible)
      .map((k) => ({ title: k.title, olLayer: k.olLayer }));
    return [...analysis].reverse().concat(kordb);
  }, showProps);
  bindUi();
  checkStatus();
  loadKordb();
  window.addEventListener("resize", () => map.updateSize());
}

window.Llm2SqlMap = {
  addAnalysisLayer,
  showBanner,
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
