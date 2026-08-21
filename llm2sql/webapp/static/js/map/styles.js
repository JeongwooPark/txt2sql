/** 분석 레이어 테마 · 벡터 스타일 / WMS 투명도. */

export const THEMES = {
  default: { stroke: "#ff4d4d", fill: "#ffcccc", width: 2, opacity: 0.82 },
  colorful: { stroke: "#FF5722", fill: "#FFEBEE", width: 3, opacity: 0.88 },
  earth: { stroke: "#D84315", fill: "#FFCCBC", width: 2, opacity: 0.75 },
  modern: { stroke: "#E91E63", fill: "#FCE4EC", width: 2, opacity: 0.9 },
};

export function vectorStyle(theme) {
  const t = THEMES[theme] || THEMES.default;
  return new ol.style.Style({
    stroke: new ol.style.Stroke({ color: t.stroke, width: t.width }),
    fill: new ol.style.Fill({ color: hexAlpha(t.fill, 0.45) }),
    image: new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color: t.stroke }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1 }),
    }),
  });
}

export function applyThemeToLayer(olLayer, theme, custom) {
  const t = { ...(THEMES[theme] || THEMES.default), ...(custom || {}) };
  olLayer.setOpacity(t.opacity);
  if (olLayer instanceof ol.layer.Vector) {
    olLayer.setStyle(vectorStyleFrom(t));
  }
}

function vectorStyleFrom(t) {
  return new ol.style.Style({
    stroke: new ol.style.Stroke({ color: t.stroke, width: Number(t.width) || 2 }),
    fill: new ol.style.Fill({ color: hexAlpha(t.fill, 0.45) }),
    image: new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color: t.stroke }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1 }),
    }),
  });
}

function hexAlpha(hex, alpha) {
  const h = String(hex || "#ffffff").replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r},${g},${b},${alpha})`;
}
