/** WMS GetFeatureInfo · WFS hit → 속성 모달. */

const SKIP_KEYS = new Set([
  "geometry",
  "boundedby",
  "bbox",
  "the_geom",
  "geom",
  "shape",
  "wkt",
  "fid",
  "gml_id",
  "id",
]);

function flattenProps(props) {
  const out = {};
  for (const [key, value] of Object.entries(props || {})) {
    if (value && typeof value === "object" && !Array.isArray(value) && !(value instanceof Date)) {
      if ("coordinates" in value || "type" in value) continue;
      Object.assign(out, flattenProps(value));
      continue;
    }
    out[key] = value;
  }
  return out;
}

function lookupLabel(fields, key) {
  if (!key) return key;
  if (fields[key]) return fields[key];
  const upper = key.toUpperCase();
  if (fields[upper]) return fields[upper];
  const stripped = key.split(/[.:]/).pop() || key;
  if (fields[stripped]) return fields[stripped];
  if (fields[stripped.toUpperCase()]) return fields[stripped.toUpperCase()];
  const want = stripped.toLowerCase();
  for (const [name, label] of Object.entries(fields || {})) {
    if (name.toLowerCase() === want) return label;
  }
  return key;
}

async function labelsForProps(layer, props) {
  if (!layer) return {};
  const columns = Object.keys(props || {});
  try {
    const res = await fetch("/api/map/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layer, columns }),
    });
    const data = await res.json();
    if (data.ok && data.fields) return data.fields;
  } catch {
    /* keep empty */
  }
  return {};
}

export function bindIdentify(map, getQueryable, showProps) {
  const hint = document.getElementById("click-info");
  map.on("singleclick", async (evt) => {
    if (hint) hint.textContent = "속성 조회 중…";
    const view = map.getView();
    const layers = getQueryable();
    for (const entry of layers) {
      const olLayer = entry.olLayer;
      if (!olLayer.getVisible()) continue;
      const source = olLayer.getSource();
      if (source && typeof source.getFeatureInfoUrl === "function") {
        const url = source.getFeatureInfoUrl(
          evt.coordinate,
          view.getResolution(),
          view.getProjection(),
          { INFO_FORMAT: "application/json", FEATURE_COUNT: 8 }
        );
        if (!url) continue;
        try {
          const res = await fetch(url);
          if (!res.ok) continue;
          const data = await res.json();
          const feat = (data.features || [])[0];
          if (feat && feat.properties) {
            const props = flattenProps(feat.properties);
            const fields = await labelsForProps(entry.layer, props);
            showProps(entry.title, props, fields, { layer: entry.layer });
            if (hint) hint.textContent = "맵을 클릭하여 속성을 확인하세요";
            return;
          }
        } catch {
          /* next layer */
        }
      }
      if (source && source.getFeaturesAtCoordinate) {
        const hits = source.getFeaturesAtCoordinate(evt.coordinate);
        if (hits && hits[0]) {
          const raw = { ...hits[0].getProperties() };
          delete raw.geometry;
          const props = flattenProps(raw);
          const fields = await labelsForProps(entry.layer, props);
          showProps(entry.title, props, fields, { layer: entry.layer });
          if (hint) hint.textContent = "맵을 클릭하여 속성을 확인하세요";
          return;
        }
      }
    }
    const pixelHits = map.getFeaturesAtPixel(evt.pixel) || [];
    if (pixelHits[0]) {
      const raw = { ...pixelHits[0].getProperties() };
      delete raw.geometry;
      const props = flattenProps(raw);
      const top = (getQueryable() || [])[0];
      const fields = await labelsForProps(top?.layer, props);
      showProps(top?.title || "피처", props, fields, { layer: top?.layer });
    }
    if (hint) hint.textContent = "맵을 클릭하여 속성을 확인하세요";
  });
}

export function renderProperties(target, props, fields = {}) {
  const rows = Object.entries(props || {}).filter(([k, v]) => {
    const key = String(k);
    if (SKIP_KEYS.has(key.toLowerCase())) return false;
    if (key.toLowerCase().includes("geom")) return false;
    return v != null && typeof v !== "object";
  });
  if (!rows.length) {
    target.innerHTML = "<p class='layer-empty'>표시할 속성이 없습니다.</p>";
    return;
  }
  const table = document.createElement("table");
  table.className = "attr-table";
  for (const [key, value] of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = lookupLabel(fields, key);
    th.title = key;
    const td = document.createElement("td");
    td.textContent = String(value);
    tr.append(th, td);
    table.appendChild(tr);
  }
  target.innerHTML = "";
  target.appendChild(table);
}

const explainSeq = new WeakMap();
const MAX_EXPLAIN_COLUMNS = 40;
const MAX_EXPLAIN_ROWS = 8;

function slimExplainPayload(payload) {
  const src = payload || {};
  const rawCols = Array.isArray(src.columns) ? src.columns : null;
  const columns = rawCols
    ? rawCols.map((c) => String(c)).filter(Boolean).slice(0, MAX_EXPLAIN_COLUMNS)
    : src.columns;
  let rows = src.rows;
  if (Array.isArray(rows)) {
    const keep = Array.isArray(columns) ? columns : null;
    rows = rows.slice(0, MAX_EXPLAIN_ROWS).map((row) => {
      if (!row || typeof row !== "object" || Array.isArray(row) || !keep) return row;
      const slim = {};
      for (const col of keep) {
        if (Object.prototype.hasOwnProperty.call(row, col)) slim[col] = row[col];
      }
      return slim;
    });
  }
  let properties = src.properties;
  if (properties && typeof properties === "object" && !Array.isArray(properties)) {
    const keys = Object.keys(properties);
    if (keys.length > MAX_EXPLAIN_COLUMNS) {
      properties = Object.fromEntries(
        keys.slice(0, MAX_EXPLAIN_COLUMNS).map((k) => [k, properties[k]])
      );
    }
  }
  let fields = src.fields;
  if (fields && typeof fields === "object" && Array.isArray(columns)) {
    const slimFields = {};
    for (const col of columns) {
      if (fields[col] != null) slimFields[col] = String(fields[col]);
    }
    if (Object.keys(slimFields).length) fields = slimFields;
  }
  return { ...src, columns, rows, properties, fields };
}

export function attachExplain(el, payload) {
  if (!el) return;
  const token = (explainSeq.get(el) || 0) + 1;
  explainSeq.set(el, token);
  el.hidden = false;
  el.className = "attr-explain loading";
  el.textContent = "설명을 작성하는 중…";
  fetch("/api/map/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(slimExplainPayload(payload)),
  })
    .then(async (res) => {
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error("explain failed");
      }
      return data;
    })
    .then((data) => {
      if (explainSeq.get(el) !== token) return;
      const text = (data && data.explanation) || "";
      el.className = "attr-explain";
      if (!text) {
        el.className = "attr-explain error";
        el.textContent =
          "설명을 불러오지 못했습니다. 아래 표에서 값을 확인할 수 있습니다.";
        return;
      }
      el.textContent = text;
    })
    .catch(() => {
      if (explainSeq.get(el) !== token) return;
      el.className = "attr-explain error";
      el.textContent = "설명을 불러오지 못했습니다. 아래 표에서 값을 확인할 수 있습니다.";
    });
}
