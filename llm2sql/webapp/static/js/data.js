(function () {
  const el = document.getElementById("dataset-list");
  if (!el) return;

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }

  fetch("/api/map/layers")
    .then((res) => res.json())
    .then((data) => {
      const layers = data.layers || [];
      if (!data.online) {
        el.innerHTML =
          '<p class="layer-empty">GeoServer에 연결되지 않았습니다.</p>';
        return;
      }
      if (!layers.length) {
        el.innerHTML = '<p class="layer-empty">등록된 레이어가 없습니다.</p>';
        return;
      }
      el.innerHTML = layers
        .map((layer) => {
          const name = escapeHtml(layer.name || "");
          const title = escapeHtml(layer.title || layer.display_name || layer.name || "");
          return `<div class="dataset-item" title="${name}"><strong>${title}</strong><span>${name}</span></div>`;
        })
        .join("");
    })
    .catch(() => {
      el.innerHTML = '<p class="layer-empty">목록을 불러오지 못했습니다.</p>';
    });
})();
