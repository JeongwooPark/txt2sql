import {
  BG_SOURCES,
  DEFAULT_BG,
  createAnalysisWmsLayer,
  createKordbWmsLayer,
  createMap,
  createWfsLayer,
  fitLonLatExtent,
} from "./core.js?v=25";
import {
  bindReorder,
  fillList,
  hideLayerContextMenu,
  renderLayerItem,
} from "./layers.js?v=25";
import { attachExplain, bindIdentify, renderProperties } from "./identify.js?v=26";
import { applyThemeToLayer, themeColors } from "./styles.js?v=25";
import {
  ANALYSIS_Z_BASE,
  ANALYSIS_Z_STEP,
  BG_Z,
  LayerStack,
} from "./stack.js?v=25";
import {
  applyChoroplethToOlLayer,
  bindChoroplethUi,
  isPolygonLayer,
  renderChoroplethLegend,
  topmostVisibleChoropleth,
} from "./choropleth.js?v=26";

const MAX_ANALYSIS_LAYERS = 8;

const state = {
  map: null,
  bgLayers: {},
  byId: {},
  stack: new LayerStack(),
  kordbById: {},
  kordbOrder: [],
  outputStack: new LayerStack(),
  theme: "default",
  customStyle: null,
  choroplethByLayer: {},
  tableLayer: null,
  tableOffset: 0,
  tableExplainKey: "",
};

let choroplethUi = null;

function openChoropleth(id) {
  choroplethUi?.openFor(id);
}

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

function showProps(title, props, fields, meta = {}) {
  const heading = document.getElementById("attr-modal-title");
  const body = document.getElementById("attr-modal-body");
  if (heading) heading.textContent = title || "속성 정보";
  if (body) renderProperties(body, props, fields || {});
  openModal("attr-modal");
  attachExplain(document.getElementById("attr-explain"), {
    kind: "identify",
    title: title || "",
    layer: meta.layer || "",
    properties: props || {},
    fields: fields || {},
  });
}

function getLayer(id) {
  return state.byId[id] || state.kordbById[id] || null;
}

function orderedAnalysis() {
  return state.stack.ids().map((id) => state.byId[id]).filter(Boolean);
}

function orderedKordb() {
  return state.kordbOrder.map((id) => state.kordbById[id]).filter(Boolean);
}

function orderedOutput() {
  return state.outputStack.ids().map((id) => getLayer(id)).filter(Boolean);
}

function applyZOrder() {
  const zMap = state.outputStack.zIndices({
    base: ANALYSIS_Z_BASE,
    step: ANALYSIS_Z_STEP,
  });
  for (const item of [...Object.values(state.byId), ...Object.values(state.kordbById)]) {
    item.olLayer?.setZIndex(zMap[item.id] ?? 1);
  }
  for (const layer of Object.values(state.bgLayers)) {
    layer.setZIndex(BG_Z);
  }
}

function styleOpts(item) {
  const info = item?.info || {};
  const geomType = info.geom_type || info.geomType || "";
  if (item?.source === "kordb") {
    return { kind: "kordb", geomType };
  }
  return {
    kind: info.kind || "analysis",
    labelField: info.label_field || "",
    featureCount: info.feature_count,
    geomType,
  };
}

function applyItemStyle(item) {
  if (!item?.olLayer) return;
  const choro = state.choroplethByLayer[item.id];
  if (choro?.classification) {
    applyChoroplethToOlLayer(item, choro);
    refreshLegend();
    return;
  }
  const kind = item.source === "kordb" ? "kordb" : "analysis";
  applyThemeToLayer(item.olLayer, state.theme, state.customStyle, kind, styleOpts(item));
}

function applyAllStyles() {
  for (const item of Object.values(state.byId)) applyItemStyle(item);
  for (const item of Object.values(state.kordbById)) applyItemStyle(item);
  refreshLegend();
}

function refreshLegend() {
  const show = (entry) => entry?.showLegend !== false;
  const ordered = orderedOutput().filter((item) => {
    const entry = state.choroplethByLayer[item.id];
    return item.visible && entry?.classification && show(entry);
  });
  const cls = topmostVisibleChoropleth(ordered, state.choroplethByLayer);
  const entry = ordered[0] ? state.choroplethByLayer[ordered[0].id] : null;
  if (cls && entry?.showNullLegend === false) {
    const copy = {
      ...cls,
      null_color: "",
    };
    renderChoroplethLegend(copy, { visible: true });
    return;
  }
  renderChoroplethLegend(cls, { visible: Boolean(cls) });
}

function fillStyleForm() {
  const t = {
    ...themeColors(state.theme, "analysis"),
    ...(state.customStyle || {}),
  };
  const fill = document.getElementById("style-fill");
  const stroke = document.getElementById("style-stroke");
  const width = document.getElementById("style-width");
  const opacity = document.getElementById("style-opacity");
  if (fill) fill.value = t.fill || "#ffcccc";
  if (stroke) stroke.value = t.stroke || "#ff4d4d";
  if (width) width.value = String(t.width ?? 2);
  if (opacity) opacity.value = String(t.opacity ?? 0.8);
}

function wfsInfoFor(item) {
  if (item.source === "kordb") {
    const qualified = item.info?.qualified || "";
    const [workspace, layer] = qualified.includes(":")
      ? qualified.split(":")
      : ["korDB", item.layer || item.id];
    return {
      workspace,
      layer: layer || item.layer || item.id,
      qualified,
      wms_url: item.info?.wms_url,
      wfs_url: item.info?.wfs_url || item.info?.wms_url,
    };
  }
  return item.info;
}

function recreateOlLayer(item) {
  if (!state.map || !item) return;
  const visible = item.visible;
  const z = item.olLayer?.getZIndex() ?? 100;
  if (item.olLayer) state.map.removeLayer(item.olLayer);
  const mode = renderingMode();
  const choro = state.choroplethByLayer[item.id];
  const styleName = choro?.styleName;
  const useWfs =
    mode === "wfs" &&
    (item.source === "kordb" || item.info?.wfs_allowed !== false);
  let olLayer;
  if (useWfs) {
    olLayer = createWfsLayer(wfsInfoFor(item));
  } else if (item.source === "kordb") {
    olLayer = createKordbWmsLayer(item.info, { styleName });
  } else {
    olLayer = createAnalysisWmsLayer(item.info, { styleName });
  }
  olLayer.setVisible(visible);
  olLayer.setZIndex(z);
  state.map.addLayer(olLayer);
  item.olLayer = olLayer;
  applyItemStyle(item);
}

function rebuildAnalysisLayers() {
  if (!state.map) return;
  const mode = renderingMode();
  let skipped = 0;
  for (const item of Object.values(state.byId)) {
    if (!item.info) continue;
    if (mode === "wfs" && item.info.wfs_allowed === false) skipped += 1;
    recreateOlLayer(item);
  }
  for (const item of Object.values(state.kordbById)) {
    const inOutput = state.outputStack.has(item.id);
    const hasChoro = Boolean(state.choroplethByLayer[item.id]);
    if (mode === "wfs" && (inOutput || hasChoro)) {
      recreateOlLayer(item);
    } else if (item.olLayer) {
      applyItemStyle(item);
    }
  }
  applyZOrder();
  refreshLegend();
  if (skipped) {
    showBanner(
      "일부 분석 레이어는 건수가 많아 WMS로 유지했습니다."
    );
  } else {
    showBanner("");
  }
}

function addToOutput(id) {
  const item = getLayer(id);
  if (!item) return false;
  applyItemStyle(item);
  item.visible = true;
  item.olLayer.setVisible(true);
  state.outputStack.add(id, { onTop: true });
  applyZOrder();
  refreshLists();
  fitLonLatExtent(state.map, item.info?.extent);
  return true;
}

function removeFromOutput(id) {
  const item = getLayer(id);
  if (!item) return false;
  item.visible = false;
  item.olLayer.setVisible(false);
  state.outputStack.remove(id);
  applyZOrder();
  refreshLists();
  refreshLegend();
  return true;
}

function refreshLists() {
  hideLayerContextMenu();
  const analysisEl = document.getElementById("analysis-layers-list");
  const outputEl = document.getElementById("output-layers-list");
  const kordbEl = document.getElementById("kordb-layers-list");
  if (analysisEl) {
    fillList(analysisEl, orderedAnalysis(), (info) =>
      renderLayerItem(
        { ...info, visible: state.outputStack.has(info.id) },
        {
          onToggle: toggleAnalysis,
          onRemove: (id) => removeAnalysis(id),
        }
      )
    );
  }
  if (outputEl) {
    fillList(outputEl, orderedOutput(), (info) =>
      renderLayerItem(info, {
        onToggle: toggleOutputVisibility,
        onMoveUp: moveOutputUp,
        onMoveDown: moveOutputDown,
        draggable: true,
        contextMenu: [
          {
            label: "레이어 삭제",
            action: () => deleteOutputLayer(info.id),
          },
          {
            label: "속성 테이블 보기",
            action: () => openAttributeTable(info.id),
          },
          ...(isPolygonLayer(info)
            ? [
                {
                  label: "구간별 색상...",
                  action: () => openChoropleth(info.id),
                },
              ]
            : []),
        ],
      })
    );
  }
  if (kordbEl) {
    fillList(kordbEl, orderedKordb(), (info) =>
      renderLayerItem(
        { ...info, visible: state.outputStack.has(info.id) },
        {
          onToggle: toggleKordb,
        }
      )
    );
  }
}

function toggleOutputVisibility(id, visible) {
  const item = getLayer(id);
  if (!item) return;
  item.visible = visible;
  item.olLayer.setVisible(visible);
  refreshLegend();
}

function toggleAnalysis(id, visible) {
  const item = state.byId[id];
  if (!item) return;
  if (visible) addToOutput(id);
  else removeFromOutput(id);
}

function toggleKordb(id, visible) {
  const item = state.kordbById[id];
  if (!item) return;
  if (visible) addToOutput(id);
  else removeFromOutput(id);
}

function deleteOutputLayer(id) {
  if (state.byId[id]) {
    removeAnalysis(id);
    return;
  }
  if (state.kordbById[id]) {
    removeFromOutput(id);
  }
}

function removeAnalysis(id, { dropServer = true } = {}) {
  const item = state.byId[id];
  if (!item) return false;
  state.map.removeLayer(item.olLayer);
  state.stack.remove(id);
  state.outputStack.remove(id);
  delete state.byId[id];
  delete state.choroplethByLayer[id];
  if (dropServer && item.layer) {
    fetch(`/api/map/layer/${encodeURIComponent(item.layer)}`, {
      method: "DELETE",
    }).catch(() => {});
  }
  applyZOrder();
  refreshLists();
  return true;
}

async function clearAnalysis(sessionId) {
  const ids = [...state.stack.ids()];
  for (const id of ids) {
    removeAnalysis(id, { dropServer: false });
  }
  if (sessionId) {
    try {
      await fetch("/api/map/session/cleanup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch {
      /* ignore */
    }
  }
  refreshLists();
}

function addAnalysisLayer(info) {
  if (!state.map || !info || !info.available) {
    if (info && info.error) showBanner(info.error);
    return false;
  }
  showBanner("");
  const id = info.layer;
  if (info.reused && id && state.stack.has(id)) {
    return false;
  }
  if (!id || state.stack.has(id)) return false;
  for (const evicted of info.evicted || []) {
    removeAnalysis(evicted, { dropServer: false });
  }
  while (state.stack.length >= MAX_ANALYSIS_LAYERS) {
    const oldest = state.stack.ids().at(-1);
    if (!oldest) break;
    removeAnalysis(oldest, { dropServer: true });
  }
  const mode =
    renderingMode() === "wfs" && info.wfs_allowed !== false ? "wfs" : "wms";
  const olLayer =
    mode === "wfs" ? createWfsLayer(info) : createAnalysisWmsLayer(info);
  applyThemeToLayer(olLayer, state.theme, state.customStyle, "analysis", {
    kind: info.kind || "features",
    labelField: info.label_field || "",
    featureCount: info.feature_count,
    geomType: info.geom_type || "",
  });
  olLayer.setVisible(true);
  state.map.addLayer(olLayer);
  const entry = {
    id,
    layer: info.layer,
    title: info.title || info.layer,
    workspace: info.workspace,
    source: "analysis",
    visible: true,
    olLayer,
    info,
    fields: info.fields || {},
  };
  state.byId[id] = entry;
  state.stack.add(id, { onTop: true });
  state.outputStack.add(id, { onTop: true });
  applyZOrder();
  refreshLists();
  fitLonLatExtent(state.map, info.extent);
  ensureLabels(entry);
  return true;
}

function moveOutputUp(id) {
  if (!state.outputStack.moveUp(id)) return false;
  applyZOrder();
  refreshLists();
  return true;
}

function moveOutputDown(id) {
  if (!state.outputStack.moveDown(id)) return false;
  applyZOrder();
  refreshLists();
  return true;
}

function moveOutputTo(id, index) {
  if (!state.outputStack.moveTo(id, index)) return false;
  applyZOrder();
  refreshLists();
  return true;
}

async function loadKordb() {
  const listEl = document.getElementById("kordb-layers-list");
  try {
    const res = await fetch("/api/map/layers");
    const data = await res.json();
    for (const id of [...state.outputStack.ids()]) {
      if (state.kordbById[id]) state.outputStack.remove(id);
    }
    for (const item of Object.values(state.kordbById)) {
      state.map.removeLayer(item.olLayer);
    }
    state.kordbById = {};
    state.kordbOrder = [];
    for (const layer of data.layers || []) {
      const olLayer = createKordbWmsLayer(layer);
      olLayer.setVisible(false);
      state.map.addLayer(olLayer);
      state.kordbById[layer.name] = {
        id: layer.name,
        layer: layer.name,
        title: layer.title || layer.display_name || layer.name,
        source: "kordb",
        visible: false,
        olLayer,
        info: layer,
        fields: layer.fields || {},
      };
      state.kordbOrder.push(layer.name);
      applyItemStyle(state.kordbById[layer.name]);
    }
    applyZOrder();
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

function setBackgroundLayer(selectedId) {
  const checks = document.querySelectorAll(
    "#background-layers-list input[type=checkbox]"
  );
  for (const check of checks) {
    const id = check.dataset.id;
    const on = Boolean(selectedId) && id === selectedId;
    check.checked = on;
    state.bgLayers[id]?.setVisible(on);
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
    check.dataset.id = id;
    check.checked = id === DEFAULT_BG;
    check.addEventListener("change", () => {
      setBackgroundLayer(check.checked ? id : null);
    });
    const label = document.createElement("label");
    label.textContent = spec.title;
    row.append(check, label);
    el.appendChild(row);
  }
}

async function ensureLabels(item) {
  if (!item || !item.layer) return item?.fields || {};
  if (item.fields && Object.keys(item.fields).length) return item.fields;
  try {
    const res = await fetch(
      `/api/map/labels?layer=${encodeURIComponent(item.layer)}`
    );
    const data = await res.json();
    if (data.ok && data.fields) {
      item.fields = data.fields;
      if (data.title && item.source === "kordb") item.title = data.title;
      refreshLists();
    }
  } catch {
    item.fields = item.fields || {};
  }
  return item.fields || {};
}

async function openAttributeTable(id) {
  const item = getLayer(id);
  if (!item) return;
  await ensureLabels(item);
  state.tableLayer = item.layer || item.id;
  state.tableOffset = 0;
  state.tableExplainKey = "";
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
  if (data.title) {
    const heading = document.getElementById("table-modal-title");
    if (heading && data.title) heading.textContent = data.title;
  }
  const cols = data.columns || [];
  const names = data.display_names || {};
  const rows = data.rows || [];
  const table = document.createElement("table");
  table.className = "attr-table";
  const thead = document.createElement("thead");
  const hr = document.createElement("tr");
  for (const col of cols) {
    const th = document.createElement("th");
    th.textContent = names[col] || col;
    th.title = col;
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
  const explainKey = `${state.tableLayer}:${total}:${cols.join(",")}`;
  if (state.tableExplainKey !== explainKey) {
    state.tableExplainKey = explainKey;
    attachExplain(document.getElementById("table-explain"), {
      kind: "table",
      title: (document.getElementById("table-modal-title") || {}).textContent || "",
      layer: state.tableLayer,
      columns: cols,
      rows: rows.slice(0, 8),
      total,
      fields: names,
    });
  }
}

function bindUi() {
  document.getElementById("clear-analysis-btn")?.addEventListener(
    "click",
    () => {
      const sid =
        window.localStorage?.getItem("txt2sql_session_id") || "";
      clearAnalysis(sid);
    }
  );
  document.getElementById("rendering-mode-select")?.addEventListener(
    "change",
    () => {
      rebuildAnalysisLayers();
    }
  );
  document.getElementById("apply-theme-btn")?.addEventListener("click", () => {
    const theme = document.getElementById("theme-select")?.value || "default";
    state.theme = theme;
    state.customStyle = null;
    applyAllStyles();
  });
  document.getElementById("style-editor-btn")?.addEventListener("click", () => {
    fillStyleForm();
    const note = document.getElementById("style-choropleth-note");
    if (note) {
      note.hidden = !Object.keys(state.choroplethByLayer).length;
    }
    openModal("style-modal");
  });
  document.getElementById("style-apply-btn")?.addEventListener("click", () => {
    state.customStyle = {
      fill: document.getElementById("style-fill")?.value,
      stroke: document.getElementById("style-stroke")?.value,
      width: Number(document.getElementById("style-width")?.value || 2),
      opacity: Number(document.getElementById("style-opacity")?.value || 0.8),
    };
    applyAllStyles();
    if (Object.keys(state.choroplethByLayer).length) {
      showBanner("단계구분도 레이어는 단일 색상 스타일에서 제외했습니다.");
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

  bindReorder(document.getElementById("output-layers-list"), {
    onDrop: moveOutputTo,
  });

  choroplethUi = bindChoroplethUi({
    getLayer,
    getChoropleth: (id) => state.choroplethByLayer[id],
    setChoropleth: (id, value) => {
      if (!value) delete state.choroplethByLayer[id];
      else state.choroplethByLayer[id] = value;
    },
    applyToMap: (id) => {
      const item = getLayer(id);
      if (!item) return;
      recreateOlLayer(item);
      applyZOrder();
      refreshLegend();
    },
    resetOnMap: (id) => {
      const item = getLayer(id);
      if (!item) return;
      recreateOlLayer(item);
      applyZOrder();
      refreshLegend();
    },
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
      const width = Math.min(840, Math.max(300, rect.right - e.clientX));
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
  setBackgroundLayer(DEFAULT_BG);
  bindIdentify(map, () =>
    orderedOutput()
      .filter((item) => item.visible)
      .map((item) => ({
      title: item.title,
      layer: item.layer,
      olLayer: item.olLayer,
      fields: item.fields || {},
    })),
    showProps
  );
  bindUi();
  applyZOrder();
  checkStatus();
  loadKordb();
  window.addEventListener("resize", () => map.updateSize());
}

window.Txt2SqlMap = {
  addAnalysisLayer,
  removeAnalysis,
  clearAnalysis,
  moveOutputUp,
  moveOutputDown,
  moveOutputTo,
  getStack: () => {
    const z = state.outputStack.zIndices();
    return state.outputStack.ids().map((id) => ({
      id,
      zIndex: z[id],
      visible: Boolean(getLayer(id)?.visible),
    }));
  },
  showBanner,
  openChoropleth,
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
