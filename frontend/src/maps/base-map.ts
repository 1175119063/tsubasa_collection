import L from "leaflet";

export interface MapServiceConfig {
  provider: "amap";
  map_provider: "tianditu" | "openstreetmap";
  enabled: boolean;
  tianditu_key: string | null;
}

export interface BaseMapHandle {
  destroy: () => void;
}

function openStreetMapLayer(): L.TileLayer {
  return L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  });
}

function tiandituTileUrl(layer: "vec" | "cva", key: string): string {
  const token = encodeURIComponent(key);
  return `https://t{s}.tianditu.gov.cn/${layer}_w/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=${layer}&STYLE=default&TILEMATRIXSET=w&FORMAT=tiles&TILECOL={x}&TILEROW={y}&TILEMATRIX={z}&tk=${token}`;
}

export function addBaseMap(
  map: L.Map,
  config: MapServiceConfig | null,
  onStatus: (message: string) => void,
): BaseMapHandle {
  const osm = openStreetMapLayer();
  const key = config?.tianditu_key?.trim();
  if (!key) {
    osm.addTo(map);
    onStatus("使用 OpenStreetMap 底图；配置天地图 Key 后将优先使用国内底图。");
    return { destroy: () => undefined };
  }

  const vector = L.tileLayer(tiandituTileUrl("vec", key), {
    subdomains: "01234567",
    maxZoom: 18,
    attribution: '&copy; <a href="https://www.tianditu.gov.cn/">天地图</a>',
  });
  const labels = L.tileLayer(tiandituTileUrl("cva", key), {
    subdomains: "01234567",
    maxZoom: 18,
  });
  const tianditu = L.layerGroup([vector, labels]);
  const control = L.control.layers(
    { "天地图（国内）": tianditu, OpenStreetMap: osm },
    undefined,
    { collapsed: true },
  ).addTo(map);
  let loadedTiles = 0;
  let failedTiles = 0;
  let switchedToFallback = false;

  const useFallback = (message: string): void => {
    if (switchedToFallback || loadedTiles > 0) return;
    switchedToFallback = true;
    tianditu.removeFrom(map);
    osm.addTo(map);
    onStatus(message);
  };
  const onTileLoad = (): void => {
    loadedTiles += 1;
    if (loadedTiles === 1) onStatus("天地图底图已加载，可在图层按钮中切换备用底图。");
  };
  const onTileError = (): void => {
    failedTiles += 1;
    if (failedTiles >= 4) useFallback("天地图加载失败，已切换到 OpenStreetMap 备用底图。");
  };
  const onBaseLayerChange = (event: L.LayersControlEvent): void => {
    onStatus(event.name.startsWith("天地图") ? "已切换到天地图底图。" : "已切换到 OpenStreetMap 备用底图。");
  };
  vector.on("tileload", onTileLoad);
  vector.on("tileerror", onTileError);
  map.on("baselayerchange", onBaseLayerChange);
  tianditu.addTo(map);
  onStatus("正在加载天地图底图……");
  const timeout = window.setTimeout(
    () => useFallback("天地图响应超时，已切换到 OpenStreetMap 备用底图。"),
    8000,
  );

  return {
    destroy: () => {
      window.clearTimeout(timeout);
      vector.off("tileload", onTileLoad);
      vector.off("tileerror", onTileError);
      map.off("baselayerchange", onBaseLayerChange);
      control.remove();
    },
  };
}
