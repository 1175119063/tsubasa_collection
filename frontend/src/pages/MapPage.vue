<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { api, errorMessage } from "@/api/client";
import type { LocationSummary } from "@/api/types";

const router = useRouter();
const mapElement = ref<HTMLElement>();
const locations = ref<LocationSummary[]>([]);
const query = ref("");
const locationType = ref("");
const status = ref("正在展开地图……");
let map: L.Map | null = null;
let markers: L.MarkerClusterGroup | null = null;

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
  link.href = `/vue/locations?location=${item.id}`;
  link.textContent = "打开区域档案";
  content.append(title, document.createElement("br"), details, document.createElement("br"), link);
  return content;
}

function renderMarkers(fit = false): void {
  if (!map || !markers) return;
  markers.clearLayers();
  for (const item of filtered.value) {
    const marker = L.marker([item.center_latitude, item.center_longitude]);
    marker.bindPopup(popupFor(item));
    markers.addLayer(marker);
  }
  status.value = filtered.value.length
    ? `地图显示 ${filtered.value.length} 处区域档案。`
    : "没有符合条件的地图点位。";
  if (fit && filtered.value.length) {
    map.fitBounds(markers.getBounds(), { padding: [35, 35], maxZoom: 13 });
  }
}

function focusLocation(item: LocationSummary): void {
  map?.setView([item.center_latitude, item.center_longitude], 13);
}

function reset(): void {
  query.value = "";
  locationType.value = "";
  void nextTick(() => renderMarkers(true));
}

async function initialize(): Promise<void> {
  if (!mapElement.value) return;
  map = L.map(mapElement.value, { zoomControl: true }).setView([35, 105], 4);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  markers = L.markerClusterGroup({ showCoverageOnHover: false, maxClusterRadius: 55 });
  map.addLayer(markers);
  try {
    locations.value = await api<LocationSummary[]>("/api/locations");
    await nextTick();
    renderMarkers(true);
  } catch (error) {
    status.value = errorMessage(error);
  }
}

watch([query, locationType], () => renderMarkers(locationType.value !== ""));
onMounted(initialize);
onBeforeUnmount(() => {
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
    <section class="v2-map-stage"><div ref="mapElement" aria-label="区域档案地图"></div><p>{{ status }}</p></section>
  </main>
</template>
