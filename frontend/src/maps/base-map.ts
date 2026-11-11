import L from "leaflet";

import { toDisplay, toWgs84, type CoordinateSystem } from "./coords";

export type BaseMapId = "amap" | "tianditu" | "openstreetmap";

export interface MapServiceConfig {
  provider: "amap";
  map_provider: BaseMapId;
  enabled: boolean;
  tianditu_key: string | null;
}

export interface BaseMapHandle {
  destroy: () => void;
  /** 当前底图使用的坐标系，图钉渲染与点击取值都要按它换算。 */
  system: () => CoordinateSystem;
  id: () => BaseMapId;
}

interface LayerChoice {
  id: BaseMapId;
  /** 状态提示里用的简称，例如“天地图底图已加载”。 */
  label: string;
  /** 图层切换按钮上显示的名字。 */
  controlLabel: string;
  /** 作为备选被切换过去时的说法，例如“已切换到高德地图备用底图”。 */
  fallbackLabel: string;
  layer: L.Layer;
  /** 实际发瓦片请求的图层，用来监控加载成败。 */
  tiles: L.TileLayer[];
  system: CoordinateSystem;
}

/** 高德栅格瓦片用 GCJ-02，图钉必须先换算，否则整体偏移三四百米。 */
function amapLayer(): L.TileLayer {
  return L.tileLayer(
    "https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",
    {
      subdomains: "1234",
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.amap.com/">高德地图</a>',
    },
  );
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
  onBaseChange?: (id: BaseMapId, system: CoordinateSystem) => void,
): BaseMapHandle {
  const key = config?.tianditu_key?.trim();

  // 顺序即优先级。默认高德优先（国内直连最稳）；只有后端明确报 map_provider
  // 为 tianditu（说明用户配了天地图 Key）时才把天地图放到最前，失败再回落高德。
  const choices: LayerChoice[] = [];
  const amap = amapLayer();
  const amapChoice: LayerChoice = {
    id: "amap",
    label: "高德地图",
    controlLabel: "高德地图",
    fallbackLabel: "高德地图备用底图",
    layer: amap,
    tiles: [amap],
    system: "gcj02",
  };
  let tiandituChoice: LayerChoice | null = null;
  if (key) {
    const vector = L.tileLayer(tiandituTileUrl("vec", key), {
      subdomains: "01234567",
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.tianditu.gov.cn/">天地图</a>',
    });
    const labels = L.tileLayer(tiandituTileUrl("cva", key), {
      subdomains: "01234567",
      maxZoom: 18,
    });
    tiandituChoice = {
      id: "tianditu",
      label: "天地图",
      controlLabel: "天地图（国内）",
      fallbackLabel: "天地图备用底图",
      layer: L.layerGroup([vector, labels]),
      tiles: [vector, labels],
      system: "wgs84",
    };
  }
  if (tiandituChoice && config?.map_provider === "tianditu") {
    choices.push(tiandituChoice, amapChoice);
  } else {
    choices.push(amapChoice);
    if (tiandituChoice) choices.push(tiandituChoice);
  }
  const osm = openStreetMapLayer();
  choices.push({
    id: "openstreetmap",
    label: "OpenStreetMap",
    controlLabel: "OpenStreetMap",
    fallbackLabel: "OpenStreetMap 备用底图",
    layer: osm,
    tiles: [osm],
    system: "wgs84",
  });

  const layersControl: Record<string, L.Layer> = {};
  for (const choice of choices) layersControl[choice.controlLabel] = choice.layer;
  const control = L.control.layers(layersControl, undefined, { collapsed: true }).addTo(map);

  let current: LayerChoice = choices[0]!;
  let loadedTiles = 0;
  let failedTiles = 0;
  let detachTiles = (): void => {};
  let timeout = 0;

  // 换底图时视野要保持在地理上的同一处，否则会因为坐标系不同而跳几百米。
  const reprojectView = (from: CoordinateSystem, to: CoordinateSystem): void => {
    if (from === to) return;
    const center = map.getCenter();
    const [wgsLatitude, wgsLongitude] = toWgs84(center.lat, center.lng, from);
    const [displayLatitude, displayLongitude] = toDisplay(wgsLatitude, wgsLongitude, to);
    map.setView([displayLatitude, displayLongitude], map.getZoom(), { animate: false });
  };

  const monitor = (choice: LayerChoice): void => {
    detachTiles();
    window.clearTimeout(timeout);
    loadedTiles = 0;
    failedTiles = 0;

    const onTileLoad = (): void => {
      if (choice !== current) return;
      loadedTiles += 1;
      if (loadedTiles > 1) return;
      window.clearTimeout(timeout);
      onStatus(`${choice.label}底图已加载，可在图层按钮中切换备用底图。`);
    };
    const onTileError = (): void => {
      if (choice !== current) return;
      failedTiles += 1;
      // 已经出一块瓦片就说明网络是通的，个别瓦片失败不该触发整层回落。
      if (loadedTiles > 0 || failedTiles < 4) return;
      switchToNext(`${choice.label}加载失败`);
    };
    for (const tile of choice.tiles) {
      tile.on("tileload", onTileLoad);
      tile.on("tileerror", onTileError);
    }
    detachTiles = (): void => {
      for (const tile of choice.tiles) {
        tile.off("tileload", onTileLoad);
        tile.off("tileerror", onTileError);
      }
    };
    timeout = window.setTimeout(() => {
      if (choice !== current || loadedTiles > 0) return;
      switchToNext(`${choice.label}响应超时`);
    }, 10_000);
  };

  const activate = (next: LayerChoice, message: string): void => {
    const previous = current;
    current = next;
    monitor(next);
    // 先把视野挪到新坐标系，再通知页面重投影图钉：反之页面刚算好的视野会被覆盖。
    reprojectView(previous.system, next.system);
    onStatus(message);
    onBaseChange?.(next.id, next.system);
  };

  /** 一路往下换，换到最后仍失败就只剩如实汇报。 */
  const switchToNext = (reason: string): void => {
    const index = choices.indexOf(current);
    const next = choices[index + 1];
    if (!next) {
      onStatus("当前网络无法访问任何地图瓦片服务，地图可能显示为空白；请检查网络或代理设置。");
      return;
    }
    const fallbackLabel = next.fallbackLabel;
    current.layer.removeFrom(map);
    next.layer.addTo(map);
    activate(next, `${reason}，已切换到${fallbackLabel}。`);
  };

  const onBaseLayerChange = (event: L.LayersControlEvent): void => {
    const chosen = choices.find((choice) => choice.layer === event.layer);
    if (!chosen || chosen === current) return;
    activate(chosen, `已切换到${chosen.label}底图。`);
  };

  map.on("baselayerchange", onBaseLayerChange);
  current.layer.addTo(map);
  monitor(current);
  // 首层也要报一次：配置了天地图 Key 时首层是 WGS-84 的天地图，
  // 页面若按默认的 GCJ-02 投影图钉，整屏会偏三四百米。
  onBaseChange?.(current.id, current.system);
  onStatus(`正在加载${current.label}底图……`);

  return {
    destroy: () => {
      window.clearTimeout(timeout);
      detachTiles();
      map.off("baselayerchange", onBaseLayerChange);
      control.remove();
      for (const choice of choices) choice.layer.removeFrom(map);
    },
    system: () => current.system,
    id: () => current.id,
  };
}
