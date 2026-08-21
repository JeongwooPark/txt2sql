/** OpenLayers 맵 코어 · 배경 타일. */

const BUSAN = [129.0756, 35.1796];

export const BG_SOURCES = {
  osm: {
    title: "OpenStreetMap",
    source: () => new ol.source.OSM(),
  },
  cartoDark: {
    title: "Carto Dark",
    source: () =>
      new ol.source.XYZ({
        url: "https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        attributions: "© OpenStreetMap © CARTO",
      }),
  },
  esri: {
    title: "ESRI Imagery",
    source: () =>
      new ol.source.XYZ({
        url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attributions: "Tiles © Esri",
      }),
  },
};

export function createMap(target) {
  const layers = {};
  for (const [id, spec] of Object.entries(BG_SOURCES)) {
    layers[id] = new ol.layer.Tile({
      source: spec.source(),
      visible: id === "cartoDark",
      zIndex: 0,
    });
  }
  const map = new ol.Map({
    target,
    layers: Object.values(layers),
    view: new ol.View({
      center: ol.proj.fromLonLat(BUSAN),
      zoom: 12,
      minZoom: 8,
      maxZoom: 19,
    }),
  });
  return { map, bgLayers: layers };
}

export function fitLonLatExtent(map, extent) {
  if (!extent || extent.length !== 4) return;
  const transformed = ol.proj.transformExtent(
    extent,
    "EPSG:4326",
    "EPSG:3857"
  );
  if (transformed.some((n) => !Number.isFinite(n))) return;
  map.getView().fit(transformed, {
    duration: 700,
    padding: [48, 48, 48, 48],
    maxZoom: 18,
  });
}

export function createTileWmsLayer(info) {
  const qualified = `${info.workspace}:${info.layer}`;
  return new ol.layer.Tile({
    source: new ol.source.TileWMS({
      url: info.wms_url,
      params: {
        LAYERS: qualified,
        TILED: true,
        TRANSPARENT: true,
        VERSION: "1.1.1",
      },
      serverType: "geoserver",
      transition: 0,
    }),
    opacity: 0.82,
    zIndex: 80,
  });
}

export function createWfsLayer(info) {
  const qualified = `${info.workspace}:${info.layer}`;
  const base = info.wfs_url.replace(/\/wms$/i, "/wfs");
  return new ol.layer.Vector({
    source: new ol.source.Vector({
      format: new ol.format.GeoJSON(),
      strategy: ol.loadingstrategy.bbox,
      url: (extent) => {
        const bbox = extent.join(",");
        return (
          `${base}?service=WFS&version=2.0.0&request=GetFeature` +
          `&typename=${encodeURIComponent(qualified)}` +
          `&outputFormat=application/json&srsName=EPSG:3857` +
          `&bbox=${bbox},EPSG:3857`
        );
      },
    }),
    zIndex: 90,
  });
}

export function createKordbWmsLayer(item) {
  return new ol.layer.Tile({
    source: new ol.source.TileWMS({
      url: item.wms_url,
      params: {
        LAYERS: item.qualified,
        TILED: true,
        TRANSPARENT: true,
        VERSION: "1.1.1",
      },
      serverType: "geoserver",
    }),
    visible: false,
    opacity: 0.7,
    zIndex: 20,
  });
}
