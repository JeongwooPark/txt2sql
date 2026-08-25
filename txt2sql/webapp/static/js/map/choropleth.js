/** 단계구분도(구간별 색상) 모달 · 범례 · 벡터 스타일. */

export const PALETTE_NAMES = [
  "Blues",
  "Greens",
  "Oranges",
  "Reds",
  "Purples",
  "Viridis",
  "YlOrRd",
];

const METHOD_LABELS = {
  jenks: "자연구간(Jenks)",
  equal_interval: "등간격",
  quantile: "분위수",
  manual: "사용자 정의",
};

function $(id) {
  return document.getElementById(id);
}

function apiError(data, fallback) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  return data?.message || fallback;
}

function formatNum(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "–";
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4 }).format(n);
}

function featureValue(feature, field) {
  if (!feature || !field) return null;
  return (
    feature.get(field) ??
    feature.get(field.toLowerCase()) ??
    feature.get(field.toUpperCase()) ??
    null
  );
}

function classColor(classification, value) {
  if (value == null || value === "") {
    return classification.null_color || "#BDBDBD";
  }
  const num = Number(value);
  if (!Number.isFinite(num)) return classification.null_color || "#BDBDBD";
  const breaks = classification.breaks || [];
  const last = breaks.length - 1;
  for (let i = 0; i < breaks.length; i += 1) {
    const lo = Number(breaks[i].min);
    const hi = Number(breaks[i].max);
    if (i === last) {
      if (num >= lo && num <= hi) return breaks[i].color;
    } else if (num >= lo && num < hi) {
      return breaks[i].color;
    }
  }
  if (breaks.length && num === Number(breaks[last].max)) return breaks[last].color;
  return classification.null_color || "#BDBDBD";
}

export function choroplethVectorStyle(classification) {
  const stroke = new ol.style.Stroke({
    color: classification.stroke || "#666666",
    width: Number(classification.stroke_width) || 0.7,
  });
  const opacity = Number(classification.fill_opacity);
  const fillOpacity = Number.isFinite(opacity) ? opacity : 0.8;
  const cache = new Map();
  return (feature) => {
    const field = classification.field;
    const value = featureValue(feature, field);
    const color = classColor(classification, value);
    let style = cache.get(color);
    if (!style) {
      style = new ol.style.Style({
        fill: new ol.style.Fill({ color: hexAlpha(color, fillOpacity) }),
        stroke,
      });
      cache.set(color, style);
    }
    return style;
  };
}

function hexAlpha(hex, alpha) {
  const h = String(hex || "#ffffff").replace("#", "");
  const full =
    h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  const n = parseInt(full, 16);
  if (Number.isNaN(n)) return `rgba(189,189,189,${alpha})`;
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}

export function isPolygonLayer(item) {
  const g = String(
    item?.info?.geom_type || item?.info?.geomType || item?.info?.geometry_type || ""
  ).toUpperCase();
  if (!g || g === "GEOMETRY" || g === "GEOGRAPHY") return true;
  if (g.includes("POINT") || g.includes("LINE")) return false;
  return g.includes("POLYGON");
}

export function applyChoroplethToOlLayer(item, entry) {
  if (!item?.olLayer || !entry?.classification) return false;
  const olLayer = item.olLayer;
  const src = olLayer.getSource && olLayer.getSource();
  if (!src) return false;
  const opacity = Number(entry.classification.fill_opacity);
  if (Number.isFinite(opacity)) olLayer.setOpacity(opacity);
  if (typeof ol !== "undefined" && src instanceof ol.source.Vector) {
    olLayer.setStyle(choroplethVectorStyle(entry.classification));
    return true;
  }
  if (!entry.geoserverOk || !entry.styleName) return false;
  if (typeof src.updateParams === "function") {
    const params = { ...(src.getParams() || {}) };
    delete params.SLD_BODY;
    src.updateParams({
      ...params,
      SLD_BODY: undefined,
      STYLES: entry.styleName || "",
      _v: Date.now(),
    });
    return true;
  }
  return false;
}

export function renderChoroplethLegend(classification, { visible = true } = {}) {
  const box = $("choropleth-legend");
  if (!box) return;
  if (!classification || !visible) {
    box.hidden = true;
    return;
  }
  const title = $("choropleth-legend-title");
  const unit = $("choropleth-legend-unit");
  const list = $("choropleth-legend-items");
  if (title) {
    title.textContent =
      classification.field_display_name || classification.field || "단계구분도";
  }
  if (unit) {
    const u = classification.unit || "";
    unit.textContent = u ? `단위: ${u}` : "";
    unit.hidden = !u;
  }
  if (list) {
    list.innerHTML = "";
    for (const brk of classification.breaks || []) {
      list.appendChild(
        legendRow(brk.color, `${formatNum(brk.min)} – ${formatNum(brk.max)}`)
      );
    }
    if (classification.null_color) {
      list.appendChild(legendRow(classification.null_color, "데이터 없음"));
    }
  }
  box.hidden = false;
}

function legendRow(color, label) {
  const li = document.createElement("li");
  const sw = document.createElement("span");
  sw.className = "swatch";
  sw.style.background = color;
  const text = document.createElement("span");
  text.textContent = label;
  li.append(sw, text);
  return li;
}

export function topmostVisibleChoropleth(ordered, byLayer) {
  for (const item of ordered || []) {
    if (!item?.visible) continue;
    const hit = byLayer?.[item.id];
    if (hit?.classification) return hit.classification;
  }
  return null;
}

export function bindChoroplethUi({
  getLayer,
  getChoropleth,
  setChoropleth,
  applyToMap,
  resetOnMap,
}) {
  fillPaletteSelect();
  $("choro-classes-minus")?.addEventListener("click", () => bumpClasses(-1));
  $("choro-classes-plus")?.addEventListener("click", () => bumpClasses(1));
  $("choro-field")?.addEventListener("change", onFieldChange);
  $("choro-method")?.addEventListener("change", onMethodChange);
  $("choro-preview-btn")?.addEventListener("click", () => runPreview());
  $("choro-apply-btn")?.addEventListener("click", () => runApply());
  $("choro-reset-btn")?.addEventListener("click", () => runReset());
  $("choro-manual-toggle")?.addEventListener("click", () => {
    $("choro-method").value = "manual";
    onMethodChange();
  });

  async function openFor(layerId) {
    const item = getLayer(layerId);
    if (!item) return;
    const modal = $("choropleth-modal");
    if (!modal) return;
    setStatus("");
    $("choro-layer-name").textContent = item.title || item.id;
    $("choro-layer-id").textContent = item.layer || item.id;
    modal.dataset.layerId = item.id;
    modal.hidden = false;
    const existing = getChoropleth(item.id);
    try {
      const res = await fetch(
        `/api/map/choropleth/fields?layer=${encodeURIComponent(item.layer || item.id)}`
      );
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        fillFields([]);
        setStatus(apiError(data, "이 레이어에는 단계구분도에 사용할 수 있는 숫자 속성이 없습니다"));
        return;
      }
      fillFields(data.fields || [], existing?.classification?.field);
      if (!(data.fields || []).length) {
        setStatus("이 레이어에는 단계구분도에 사용할 수 있는 숫자 속성이 없습니다");
        return;
      }
      if (existing?.classification) {
        restoreForm(existing.classification);
        renderBreaks(existing.classification);
        fillStats(existing.classification);
      } else {
        await onFieldChange();
        await runPreview();
      }
    } catch {
      setStatus("단계구분도 설정을 불러오지 못했습니다.");
    }
  }

  function fillFields(fields, selected) {
    const sel = $("choro-field");
    if (!sel) return;
    sel.innerHTML = "";
    for (const field of fields) {
      const opt = document.createElement("option");
      opt.value = field.name;
      opt.textContent = field.display_name || field.name;
      opt.dataset.unit = field.unit || "";
      opt.dataset.type = field.data_type || "";
      sel.appendChild(opt);
    }
    if (selected) sel.value = selected;
    updateFieldMeta();
  }

  function updateFieldMeta() {
    const sel = $("choro-field");
    const opt = sel?.selectedOptions?.[0];
    $("choro-field-raw").textContent = opt?.value || "–";
    $("choro-field-unit").textContent = opt?.dataset.unit || "–";
  }

  async function onFieldChange() {
    updateFieldMeta();
    const payload = formPayload();
    if (!payload) return;
    try {
      const res = await fetch("/api/map/choropleth/stats", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ layer: payload.layer, field: payload.field }),
      });
      const data = await res.json();
      if (!res.ok) {
        fillStats(null);
        setStatus(apiError(data, "선택한 속성은 숫자형이 아닙니다"));
        return;
      }
      fillStats(data);
      setStatus("");
    } catch {
      fillStats(null);
      setStatus("통계를 불러오지 못했습니다.");
    }
  }

  function onMethodChange() {
    const manual = $("choro-method")?.value === "manual";
    const box = $("choro-manual-box");
    if (box) box.hidden = !manual;
  }

  function bumpClasses(delta) {
    const input = $("choro-classes");
    if (!input) return;
    const next = Math.min(9, Math.max(3, Number(input.value || 5) + delta));
    input.value = String(next);
  }

  function formPayload() {
    const modal = $("choropleth-modal");
    const layerId = modal?.dataset.layerId;
    const item = getLayer(layerId);
    if (!item) return null;
    const method = $("choro-method")?.value || "jenks";
    const payload = {
      layer: item.layer || item.id,
      field: $("choro-field")?.value,
      method,
      classes: Number($("choro-classes")?.value || 5),
      palette: $("choro-palette")?.value || "YlOrRd",
      reverse: Boolean($("choro-reverse")?.checked),
      null_color: $("choro-null-color")?.value || "#BDBDBD",
      stroke: $("choro-stroke")?.value || "#666666",
      stroke_width: Number($("choro-stroke-width")?.value || 0.7),
      fill_opacity: Number($("choro-opacity")?.value || 0.8),
    };
    if (method === "manual") {
      payload.manual_breaks = parseManualBreaks();
      payload.break_values = payload.manual_breaks;
    }
    return payload;
  }

  function parseManualBreaks() {
    const text = $("choro-manual-breaks")?.value || "";
    return text
      .split(/[, \n]+/)
      .map((part) => part.trim())
      .filter(Boolean)
      .map(Number)
      .filter((n) => Number.isFinite(n));
  }

  async function runPreview() {
    const payload = formPayload();
    if (!payload?.field) {
      setStatus("분류할 속성을 선택하세요.");
      return;
    }
    setStatus("미리보기 계산 중…");
    try {
      const res = await fetch("/api/map/choropleth/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus(apiError(data, "미리보기에 실패했습니다."));
        return;
      }
      const cls = data.classification || data;
      renderBreaks(cls);
      fillStats(cls);
      if ($("choro-show-legend")?.checked) {
        renderChoroplethLegend(cls, { visible: true });
      }
      setStatus(cls.message || "미리보기를 갱신했습니다. 적용을 누르면 지도에 반영됩니다.");
    } catch {
      setStatus("미리보기에 실패했습니다.");
    }
  }

  async function runApply() {
    const payload = formPayload();
    if (!payload?.field) {
      setStatus("분류할 속성을 선택하세요.");
      return;
    }
    const modal = $("choropleth-modal");
    const layerId = modal?.dataset.layerId;
    setStatus("GeoServer 스타일을 적용하는 중…");
    try {
      const res = await fetch("/api/map/choropleth/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus(apiError(data, "단계구분도를 적용하지 못했습니다."));
        return;
      }
      const classification = data.classification || data;
      if (!data.geoserver_ok) {
        setStatus(
          data.message ||
            "GeoServer 스타일을 적용하지 못했습니다. 기존 지도 스타일은 유지됩니다"
        );
      } else {
        setStatus("단계구분도를 적용했습니다.");
      }
      setChoropleth(layerId, {
        styleName: data.style_name,
        classification,
        geoserverOk: Boolean(data.geoserver_ok),
        showLegend: Boolean($("choro-show-legend")?.checked),
        showNullLegend: Boolean($("choro-show-null-legend")?.checked),
      });
      applyToMap(layerId);
      if (!data.geoserver_ok) {
        return;
      }
      modal.hidden = true;
    } catch {
      setStatus("GeoServer 스타일을 적용하지 못했습니다. 기존 지도 스타일은 유지됩니다");
    }
  }

  async function runReset() {
    const modal = $("choropleth-modal");
    const layerId = modal?.dataset.layerId;
    const item = getLayer(layerId);
    if (!item) return;
    const current = getChoropleth(layerId);
    setStatus("기본 스타일로 되돌리는 중…");
    try {
      await fetch("/api/map/choropleth/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          layer: item.layer || item.id,
          purge_style: true,
          style_name: current?.styleName || null,
        }),
      });
    } catch {
      /* keep local reset */
    }
    setChoropleth(layerId, null);
    resetOnMap(layerId);
    setStatus("단계구분도를 해제했습니다.");
    $("choropleth-modal").hidden = true;
  }

  function fillStats(stats) {
    const map = {
      "choro-stat-min": stats?.min,
      "choro-stat-max": stats?.max,
      "choro-stat-mean": stats?.mean,
      "choro-stat-median": stats?.median,
      "choro-stat-valid": stats?.valid_count,
      "choro-stat-null": stats?.null_count,
    };
    for (const [id, value] of Object.entries(map)) {
      const el = $(id);
      if (!el) continue;
      el.textContent = value == null ? "–" : formatNum(value);
    }
    if (stats?.display_name) {
      $("choro-field-unit").textContent = stats.unit || $("choro-field-unit").textContent;
    }
  }

  function renderBreaks(classification) {
    const list = $("choro-breaks");
    if (!list) return;
    list.innerHTML = "";
    for (const brk of classification.breaks || []) {
      list.appendChild(
        legendRow(brk.color, `${formatNum(brk.min)}  ~  ${formatNum(brk.max)}`)
      );
    }
    if (classification.method === "manual") {
      $("choro-manual-breaks").value = (classification.breaks || [])
        .slice(1)
        .map((brk) => brk.min)
        .join(", ");
    }
  }

  function restoreForm(cls) {
    if (cls.field) $("choro-field").value = cls.field;
    if (cls.method) $("choro-method").value = cls.method;
    if (cls.classes) $("choro-classes").value = String(cls.classes);
    if (cls.palette) $("choro-palette").value = cls.palette;
    $("choro-reverse").checked = Boolean(cls.reverse);
    if (cls.null_color) $("choro-null-color").value = cls.null_color;
    if (cls.stroke) $("choro-stroke").value = cls.stroke;
    if (cls.stroke_width != null) $("choro-stroke-width").value = String(cls.stroke_width);
    if (cls.fill_opacity != null) $("choro-opacity").value = String(cls.fill_opacity);
    updateFieldMeta();
    onMethodChange();
  }

  function setStatus(text) {
    const el = $("choro-status");
    if (el) el.textContent = text || "";
  }

  function fillPaletteSelect() {
    const sel = $("choro-palette");
    if (!sel || sel.options.length) return;
    for (const name of PALETTE_NAMES) {
      const opt = document.createElement("option");
      opt.value = name;
      opt.textContent = name;
      if (name === "YlOrRd") opt.selected = true;
      sel.appendChild(opt);
    }
  }

  return { openFor };
}

export { METHOD_LABELS };
