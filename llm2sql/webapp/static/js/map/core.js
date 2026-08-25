/** OpenLayers 맵 코어 · 배경 타일. */

const BUSAN = [129.0756, 35.1796];

export const DEFAULT_BG = "osm";

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
      visible: id === DEFAULT_BG,
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
  const padded = padLonLatExtent(extent);
  const transformed = ol.proj.transformExtent(
    padded,
    "EPSG:4326",
    "EPSG:3857"
  );
  if (transformed.some((n) => !Number.isFinite(n))) return;
  map.getView().fit(transformed, {
    duration: 800,
    padding: [56, 56, 56, 56],
    maxZoom: 18,
    constrainResolution: false,
  });
}

/** 단일 건물처럼 작은 bbox는 ~330m 이상으로 키운다. */
export function padLonLatExtent(extent, minSpan = 0.003, margin = 0.15) {
  if (!extent || extent.length !== 4) return extent;
  let [minx, miny, maxx, maxy] = extent.map(Number);
  if ([minx, miny, maxx, maxy].some((n) => !Number.isFinite(n))) return extent;
  if (maxx < minx) [minx, maxx] = [maxx, minx];
  if (maxy < miny) [miny, maxy] = [maxy, miny];
  if (maxx - minx < minSpan) {
    const mid = (minx + maxx) / 2;
    minx = mid - minSpan / 2;
    maxx = mid + minSpan / 2;
  }
  if (maxy - miny < minSpan) {
    const mid = (miny + maxy) / 2;
    miny = mid - minSpan / 2;
    maxy = mid + minSpan / 2;
  }
  const padX = (maxx - minx) * margin;
  const padY = (maxy - miny) * margin;
  return [minx - padX, miny - padY, maxx + padX, maxy + padY];
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

/** 분석 결과 WMS. SLD_BODY·소수 피처에 TileWMS보다 ImageWMS가 안정적이다. */
export function createAnalysisWmsLayer(info, opts = {}) {
  const qualified = `${info.workspace}:${info.layer}`;
  const params = {
    LAYERS: qualified,
    TRANSPARENT: true,
    VERSION: "1.1.1",
  };
  if (opts.styleName) {
    params.STYLES = opts.styleName;
    params._v = Date.now();
  }
  return new ol.layer.Image({
    source: new ol.source.ImageWMS({
      url: info.wms_url,
      params,
      ratio: 1,
      serverType: "geoserver",
    }),
    opacity: 0.82,
    zIndex: 80,
  });
}

export function createWfsLayer(info) {
  const qualified =
    info.qualified || `${info.workspace}:${info.layer}`;
  const base = String(info.wfs_url || info.wms_url || "").replace(
    /\/wms$/i,
    "/wfs"
  );
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

export function createKordbWmsLayer(item, opts = {}) {
  const params = {
    LAYERS: item.qualified,
    TILED: true,
    TRANSPARENT: true,
    VERSION: "1.1.1",
  };
  if (opts.styleName) {
    params.STYLES = opts.styleName;
    params._v = Date.now();
  }
  return new ol.layer.Tile({
    source: new ol.source.TileWMS({
      url: item.wms_url,
      params,
      serverType: "geoserver",
      transition: 0,
    }),
    visible: false,
    opacity: 0.7,
    zIndex: 20,
  });
}
