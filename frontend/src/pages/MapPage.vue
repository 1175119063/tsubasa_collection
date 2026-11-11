<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIconUrl from "leaflet/dist/images/marker-icon.png";
import markerShadowUrl from "leaflet/dist/images/marker-shadow.png";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { api, errorMessage } from "@/api/client";
import type { LocationSummary } from "@/api/types";
import type { BaseMapHandle, MapServiceConfig } from "@/maps/base-map";
import { toDisplay, type CoordinateSystem } from "@/maps/coords";

const router = useRouter();
const mapElement = ref<HTMLElement>();
const locations = ref<LocationSummary[]>([]);
const query = ref("");
const locationType = ref("");
const status = ref("正在展开地图……");
const baseMapStatus = ref("正在加载底图……");
let map: L.Map | null = null;
let markers: L.MarkerClusterGroup | null = null;
let baseMapHandle: BaseMapHandle | null = null;
// 资料库存的是 WGS-84；首选的高德瓦片是 GCJ-02，图钉要跟着底图换算。
const mapSystem = ref<CoordinateSystem>("gcj02");

const DEFAULT_CENTER: L.LatLngExpression = [35, 105];
const DEFAULT_ZOOM = 4;

// Leaflet 默认图标按页面相对路径去找 /marker-icon.png，打包后一定是 404。
// 这里显式绑定随构建一起产出的图片，标记才会显示真实图钉。
const locationIcon = L.icon({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  tooltipAnchor: [16, -28],
  shadowSize: [41, 41],
});

const labels: Record<string, string> = {
  urban_park: "城市公园", campus: "校园", wetland: "湿地", forest: "森林",
  grassland: "草原", nature_reserve: "自然保护区", reservoir: "水库",
  farmland: "农田", coast: "海岸", other: "其他",
};

const types = computed(() => [...new Set(locations.value.map((item) => item.location_type))].sort());
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return locations.value.filter((item) =>
    `${item.name} ${item.city || ""} ${item.district || ""} ${item.admin1_name}`.toLocaleLowerCase().includes(needle)
    && (!locationType.value || item.location_type === locationType.value));
});

function popupFor(item: LocationSummary): HTMLElement {
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = item.name;
  const details = document.createElement("span");
  details.textContent = `${labels[item.location_type] || item.location_type} · ${item.species_count} 种 · ${item.observation_count} 笔记录`;
  const link = document.createElement("a");
  link.href = `/locations?location=${item.id}`;
  link.textContent = "打开区域档案";
  content.append(title, document.createElement("br"), details, document.createElement("br"), link);
  return content;
}

function displayPoint(item: LocationSummary): L.LatLngTuple {
  return toDisplay(item.center_latitude, item.center_longitude, mapSystem.value);
}

function boundsOf(items: LocationSummary[]): L.LatLngBounds {
  return L.latLngBounds(items.map(displayPoint));
}

// 首屏视野必须同步落地：Leaflet 的动画缩放要等 transitionend 才提交，
// 期间地图停在占位视图（先请求低层级瓦片），一旦被打断就会一直停在那里。
function fitToLocations(): void {
  if (!map) return;
  if (!filtered.value.length) {
    map.setView(DEFAULT_CENTER, DEFAULT_ZOOM, { animate: false });
    return;
  }
  map.fitBounds(boundsOf(filtered.value), { padding: [35, 35], maxZoom: 13, animate: false });
}

function renderMarkers(fit = false): void {
  if (!map || !markers) return;
  markers.clearLayers();
  for (const item of filtered.value) {
    const marker = L.marker(displayPoint(item), { icon: locationIcon });
    marker.bindPopup(popupFor(item));
    markers.addLayer(marker);
  }
  status.value = filtered.value.length
    ? `地图显示 ${filtered.value.length} 处区域档案。`
    : "没有符合条件的地图点位。";
  if (fit) fitToLocations();
}

function focusLocation(item: LocationSummary): void {
  map?.setView(displayPoint(item), 13);
}

function reset(): void {
  query.value = "";
  locationType.value = "";
  void nextTick(() => renderMarkers(true));
}

async function initialize(): Promise<void> {
  if (!mapElement.value) return;
  // 创建时故意不给初始视野：占位视图会先请求一整屏低层级瓦片，
  // 而首屏真正要显示的是下面的自适应视野。
  map = L.map(mapElement.value, { zoomControl: true });
  let config: MapServiceConfig | null = null;
  let dataLoaded = true;
  try {
    config = await api<MapServiceConfig>("/api/map/config");
  } catch (error) {
    baseMapStatus.value = errorMessage(error);
  }
  try {
    locations.value = await api<LocationSummary[]>("/api/locations");
    await nextTick();
  } catch (error) {
    dataLoaded = false;
    status.value = errorMessage(error);
  }
  // 先落定视野，再挂底图：这样瓦片从一开始就按最终的缩放层级请求。
  fitToLocations();
  const { addBaseMap } = await import("@/maps/base-map");
  baseMapHandle = addBaseMap(
    map,
    config,
    (message) => { baseMapStatus.value = message; },
    (_id, system) => {
      if (system === mapSystem.value) return;
      // 底图坐标系变了，图钉与视野都得按新坐标系重算，否则整体偏三四百米。
      mapSystem.value = system;
      renderMarkers();
      fitToLocations();
    },
  );
  markers = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 55 });
  map.addLayer(markers);
  if (dataLoaded) renderMarkers();
}

watch([query, locationType], () => renderMarkers(locationType.value !== ""));
onMounted(initialize);
onBeforeUnmount(() => {
  baseMapHandle?.destroy();
  map?.remove();
  map = null;
  markers = null;
});
</script>

<template>
  <main class="v2-map-layout">
    <aside class="v2-map-sidebar">
      <p class="v2-kicker">REGION EXPLORATION MAP</p><h1>探索地图</h1>
      <p>在同一张地图上查看全部区域档案。相邻点位会自动聚合，缩放后展开。</p>
      <label for="vue-map-location-search">检索区域</label>
      <input id="vue-map-location-search" v-model="query" class="v2-search" type="search" placeholder="地点、城市或行政区" />
      <label for="vue-map-location-type">区域类型</label>
      <select id="vue-map-location-type" v-model="locationType">
        <option value="">全部类型</option>
        <option v-for="type in types" :key="type" :value="type">{{ labels[type] || type }}</option>
      </select>
      <button class="v2-filter-reset" type="button" @click="reset">清除地图筛选</button>
      <div class="v2-book-count"><strong>{{ filtered.length }}</strong><span>处地图据点</span></div>
      <div class="v2-map-location-list">
        <button v-for="item in filtered" :key="item.id" type="button" @click="focusLocation(item)">
          <strong>{{ item.name }}</strong><span>{{ item.admin1_name }} · {{ item.species_count }} 种</span>
        </button>
        <p v-if="!filtered.length">没有符合条件的区域。</p>
      </div>
      <button class="v2-filter-reset" type="button" @click="router.push('/locations')">返回区域档案</button>
    </aside>
    <section class="v2-map-stage"><div ref="mapElement" :data-base-map-system="mapSystem" aria-label="区域档案地图"></div><p>{{ status }} · {{ baseMapStatus }}</p></section>
  </main>
</template>
