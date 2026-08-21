/** WMS GetFeatureInfo · WFS hit → 속성 모달. */

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
            showProps(entry.title, feat.properties);
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
          showProps(entry.title, hits[0].getProperties());
          if (hint) hint.textContent = "맵을 클릭하여 속성을 확인하세요";
          return;
        }
      }
    }
    const pixelHits = map.getFeaturesAtPixel(evt.pixel) || [];
    if (pixelHits[0]) {
      const props = { ...pixelHits[0].getProperties() };
      delete props.geometry;
      showProps("피처", props);
    }
    if (hint) hint.textContent = "맵을 클릭하여 속성을 확인하세요";
  });
}

export function renderProperties(target, props) {
  const skip = new Set(["geometry", "boundedBy"]);
  const rows = Object.entries(props || {}).filter(
    ([k, v]) => !skip.has(k) && v != null && typeof v !== "object"
  );
  if (!rows.length) {
    target.innerHTML = "<p class='layer-empty'>표시할 속성이 없습니다.</p>";
    return;
  }
  const table = document.createElement("table");
  table.className = "attr-table";
  for (const [key, value] of rows) {
    const tr = document.createElement("tr");
    const th = document.createElement("th");
    th.textContent = key;
    const td = document.createElement("td");
    td.textContent = String(value);
    tr.append(th, td);
    table.appendChild(tr);
  }
  target.innerHTML = "";
  target.appendChild(table);
}
