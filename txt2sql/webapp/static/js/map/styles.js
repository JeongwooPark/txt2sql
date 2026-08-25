/** 분석/KorDB 레이어 테마 · 벡터 스타일 · WMS SLD. */

export const THEMES = {
  default: {
    analysis: { stroke: "#ff4d4d", fill: "#ffcccc", width: 2, opacity: 0.82 },
    kordb: { stroke: "#333333", fill: "#f4f4f4", width: 1, opacity: 0.7 },
  },
  colorful: {
    analysis: { stroke: "#FF5722", fill: "#FFEBEE", width: 3, opacity: 0.88 },
    kordb: { stroke: "#2196F3", fill: "#E3F2FD", width: 2, opacity: 0.8 },
  },
  earth: {
    analysis: { stroke: "#D84315", fill: "#FFCCBC", width: 2, opacity: 0.75 },
    kordb: { stroke: "#8D6E63", fill: "#D7CCC8", width: 1, opacity: 0.65 },
  },
  modern: {
    analysis: { stroke: "#E91E63", fill: "#FCE4EC", width: 2, opacity: 0.9 },
    kordb: { stroke: "#424242", fill: "#FAFAFA", width: 1, opacity: 0.8 },
  },
};

/** 이 건수 이하면 건물명 등 라벨을 그린다. */
export const LABEL_FEATURE_LIMIT = 80;

const LABEL_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/;

export function themeColors(theme, kind = "analysis") {
  const pack = THEMES[theme] || THEMES.default;
  return { ...(pack[kind] || pack.analysis) };
}

export function vectorStyle(theme) {
  return vectorStyleFrom(themeColors(theme, "analysis"));
}

export function geomKind(geomType) {
  const g = String(geomType || "").toUpperCase();
  if (g.includes("POINT")) return "point";
  if (g.includes("LINE")) return "line";
  return "polygon";
}

export function applyThemeToLayer(olLayer, theme, custom, kind = "analysis", opts = {}) {
  if (!olLayer) return false;
  const t = densityAdjust(
    { ...themeColors(theme, kind), ...(custom || {}) },
    opts
  );
  olLayer.setOpacity(Number(t.opacity) || 0.8);
  const src = olLayer.getSource && olLayer.getSource();
  if (!src) return false;
  if (typeof ol !== "undefined" && src instanceof ol.source.Vector) {
    olLayer.setStyle(vectorStyleFrom(t, opts));
    return true;
  }
  if (typeof src.updateParams === "function") {
    const layers = (src.getParams() || {}).LAYERS || "layer";
    src.updateParams({
      SLD_BODY: sldBody(layers, t, opts),
      STYLES: "",
    });
    return true;
  }
  return false;
}

export function densityAdjust(t, opts = {}) {
  const out = { ...t };
  const n = Number(opts.featureCount);
  const kind = opts.kind || "";
  if (kind === "boundary") {
    out.opacity = Math.min(Number(out.opacity) || 0.8, 0.55);
  }
  if (Number.isFinite(n) && n > 0 && n <= 20) {
    out.width = Math.max(Number(out.width) || 2, 3);
  } else if (Number.isFinite(n) && n > 200) {
    out.width = Math.min(Number(out.width) || 2, 1.5);
    out.opacity = Math.min(Number(out.opacity) || 0.8, 0.72);
  }
  return out;
}

export function shouldLabel(opts = {}) {
  const field = String(opts.labelField || "").trim();
  if (!LABEL_NAME_RE.test(field)) return false;
  const n = Number(opts.featureCount);
  if (!Number.isFinite(n) || n <= 0 || n > LABEL_FEATURE_LIMIT) return false;
  return true;
}

export function vectorStyleFrom(t, opts = {}) {
  const kind = geomKind(opts.geomType);
  const stroke = new ol.style.Stroke({
    color: t.stroke,
    width: Number(t.width) || 2,
  });
  const parts = { stroke };
  if (kind === "polygon") {
    parts.fill = new ol.style.Fill({ color: hexAlpha(t.fill, 0.45) });
  }
  if (kind === "point") {
    parts.image = new ol.style.Circle({
      radius: Number(opts.featureCount) > 0 && Number(opts.featureCount) <= 20 ? 7 : 5,
      fill: new ol.style.Fill({ color: t.stroke }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1 }),
    });
  }
  const geomStyle = new ol.style.Style(parts);
  if (!shouldLabel(opts)) {
    return geomStyle;
  }
  const field = String(opts.labelField).trim();
  return (feature) => {
    const raw =
      feature.get(field) ??
      feature.get(field.toLowerCase()) ??
      feature.get(field.toUpperCase());
    const text = raw == null || raw === "" ? "" : String(raw);
    if (!text) return geomStyle;
    return [
      geomStyle,
      new ol.style.Style({
        text: new ol.style.Text({
          text,
          font: "600 13px 'IBM Plex Sans KR', sans-serif",
          fill: new ol.style.Fill({ color: "#1a1a1a" }),
          stroke: new ol.style.Stroke({ color: "#ffffff", width: 4 }),
          overflow: true,
          offsetY: -10,
        }),
      }),
    ];
  };
}

export function sldBody(layerName, t, opts = {}) {
  const fill = escapeXml(t.fill || "#ffcccc");
  const stroke = escapeXml(t.stroke || "#ff4d4d");
  const width = Number(t.width) || 2;
  const name = escapeXml(layerName || "layer");
  const kind = geomKind(opts.geomType);
  const symbolizers = [];
  if (kind === "polygon") {
    symbolizers.push(`          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">${fill}</CssParameter>
              <CssParameter name="fill-opacity">0.45</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">${stroke}</CssParameter>
              <CssParameter name="stroke-width">${width}</CssParameter>
            </Stroke>
          </PolygonSymbolizer>`);
  } else if (kind === "line") {
    symbolizers.push(`          <LineSymbolizer>
            <Stroke>
              <CssParameter name="stroke">${stroke}</CssParameter>
              <CssParameter name="stroke-width">${width}</CssParameter>
            </Stroke>
          </LineSymbolizer>`);
  } else {
    symbolizers.push(`          <PointSymbolizer>
            <Graphic>
              <Mark>
                <WellKnownName>circle</WellKnownName>
                <Fill>
                  <CssParameter name="fill">${stroke}</CssParameter>
                </Fill>
                <Stroke>
                  <CssParameter name="stroke">#ffffff</CssParameter>
                </Stroke>
              </Mark>
              <Size>8</Size>
            </Graphic>
          </PointSymbolizer>`);
  }
  const labelXml = textSymbolizerXml(opts);
  return `<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0"
  xmlns="http://www.opengis.net/sld"
  xmlns:ogc="http://www.opengis.net/ogc">
  <NamedLayer>
    <Name>${name}</Name>
    <UserStyle>
      <FeatureTypeStyle>
        <Rule>
${symbolizers.join("\n")}${labelXml}
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>`;
}

function textSymbolizerXml(opts = {}) {
  if (!shouldLabel(opts)) return "";
  const field = escapeXml(String(opts.labelField).trim());
  return `
          <TextSymbolizer>
            <Label>
              <ogc:PropertyName>${field}</ogc:PropertyName>
            </Label>
            <Font>
              <CssParameter name="font-family">SansSerif</CssParameter>
              <CssParameter name="font-size">13</CssParameter>
              <CssParameter name="font-weight">bold</CssParameter>
            </Font>
            <Halo>
              <Radius>2</Radius>
              <Fill>
                <CssParameter name="fill">#ffffff</CssParameter>
              </Fill>
            </Halo>
            <Fill>
              <CssParameter name="fill">#1a1a1a</CssParameter>
            </Fill>
            <VendorOption name="maxDisplacement">48</VendorOption>
            <VendorOption name="autoWrap">88</VendorOption>
          </TextSymbolizer>`;
}

function escapeXml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function hexAlpha(hex, alpha) {
  const h = String(hex || "#ffffff").replace("#", "");
  const full =
    h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  const n = parseInt(full, 16);
  if (Number.isNaN(n)) return `rgba(255,255,255,${alpha})`;
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}
