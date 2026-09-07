<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { LocationDetail } from "@/api/types";
import type { BaseMapHandle, MapServiceConfig } from "@/maps/base-map";

const props = defineProps<{ location: LocationDetail | null }>();
const emit = defineEmits<{ close: []; saved: [location: LocationDetail] }>();

const locationTypes: Record<string, string> = { wetland_park: "湿地公园", forest_park: "森林公园", urban_park: "城市公园", nature_reserve: "自然保护区", reservoir: "水库", farmland: "农田", coast: "海岸", other: "其他" };
const provinceCodes: Record<string, string> = { "北京市": "CN-BJ", "天津市": "CN-TJ", "河北省": "CN-HE", "山西省": "CN-SX", "内蒙古自治区": "CN-NM", "辽宁省": "CN-LN", "吉林省": "CN-JL", "黑龙江省": "CN-HL", "上海市": "CN-SH", "江苏省": "CN-JS", "浙江省": "CN-ZJ", "安徽省": "CN-AH", "福建省": "CN-FJ", "江西省": "CN-JX", "山东省": "CN-SD", "河南省": "CN-HA", "湖北省": "CN-HB", "湖南省": "CN-HN", "广东省": "CN-GD", "广西壮族自治区": "CN-GX", "海南省": "CN-HI", "重庆市": "CN-CQ", "四川省": "CN-SC", "贵州省": "CN-GZ", "云南省": "CN-YN", "西藏自治区": "CN-XZ", "陕西省": "CN-SN", "甘肃省": "CN-GS", "青海省": "CN-QH", "宁夏回族自治区": "CN-NX", "新疆维吾尔自治区": "CN-XJ", "台湾省": "CN-TW", "香港特别行政区": "CN-HK", "澳门特别行政区": "CN-MO" };
interface MapResult { name: string; latitude: number; longitude: number; province?: string; city?: string; district?: string; address?: string; adcode?: string }

const form = reactive({ name: props.location?.name || "", location_type: props.location?.location_type || "urban_park", radius_meters: props.location?.radius_meters ?? null as number | null, country_code: props.location?.country_code || "CN", country_name: props.location?.country_name || "中国", admin1_code: props.location?.admin1_code || "", admin1_name: props.location?.admin1_name || "", city: props.location?.city || "", district: props.location?.district || "", center_latitude: props.location?.center_latitude ?? null as number | null, center_longitude: props.location?.center_longitude ?? null as number | null, coordinate_system: props.location?.coordinate_system || "wgs84", notes: props.location?.notes || "", link_matching_records: !props.location });
const mapElement = ref<HTMLElement>(); const search = ref(props.location?.name || ""); const mapStatus = ref("正在加载地图……"); const baseMapStatus = ref("正在加载底图……"); const status = ref(""); const results = ref<MapResult[]>([]);
let map: L.Map | null = null; let marker: L.Marker | null = null; let searchEnabled = false; let baseMapHandle: BaseMapHandle | null = null;

function fillAddress(item: MapResult): void { if (item.province) { form.country_code = "CN"; form.country_name = "中国"; form.admin1_name = item.province; form.admin1_code = provinceCodes[item.province] || (item.adcode ? `CN-${item.adcode.slice(0, 2)}` : ""); } form.city = item.city || (/^(北京市|天津市|上海市|重庆市)$/.test(item.province || "") ? item.province || "" : form.city); form.district = item.district || form.district; }
function showPoint(latitude: number, longitude: number): void { form.center_latitude = Number(latitude.toFixed(6)); form.center_longitude = Number(longitude.toFixed(6)); form.coordinate_system = "wgs84"; if (!map) return; if (!marker) { marker = L.marker([latitude, longitude], { draggable: true }).addTo(map); marker.on("dragend", () => { const point = marker?.getLatLng(); if (point) void selectPoint(point.lat, point.lng); }); } else marker.setLatLng([latitude, longitude]); map.setView([latitude, longitude], 15); }
async function selectPoint(latitude: number, longitude: number, result?: MapResult): Promise<void> { showPoint(latitude, longitude); if (result) { form.name = result.name || form.name; fillAddress(result); mapStatus.value = `已选择：${result.name}（WGS-84）`; return; } if (!searchEnabled) { mapStatus.value = `已选择坐标 ${latitude.toFixed(6)}, ${longitude.toFixed(6)}，请手动填写行政区。`; return; } try { const address = await api<MapResult & { formatted_address?: string }>(`/api/map/reverse?latitude=${latitude}&longitude=${longitude}`); fillAddress(address); mapStatus.value = `已选择：${address.formatted_address || `${latitude}, ${longitude}`}（WGS-84）`; } catch (caught) { mapStatus.value = `${errorMessage(caught)} 坐标已经写入，可以手动补充行政区。`; } }
async function searchMap(): Promise<void> { const query = search.value.trim(); if (!query) { mapStatus.value = "请输入地点名称后再搜索。"; return; } if (!searchEnabled) { mapStatus.value = "尚未配置可用的高德 Web 服务 Key。"; return; } mapStatus.value = "正在通过高德搜索地点……"; try { const response = await api<{ items: MapResult[] }>(`/api/map/search?query=${encodeURIComponent(query)}${form.city ? `&city=${encodeURIComponent(form.city)}` : ""}`); results.value = response.items || []; mapStatus.value = results.value.length ? `找到 ${results.value.length} 个结果，请选择一个地点。` : "没有找到匹配地点，可以直接点击地图。"; } catch (caught) { mapStatus.value = errorMessage(caught); } }
function useDeviceLocation(): void { navigator.geolocation.getCurrentPosition(({ coords }) => { void selectPoint(coords.latitude, coords.longitude); mapStatus.value = "已读取设备位置（WGS-84）。"; }, () => { status.value = "无法读取设备位置，请手动填写中心经纬度"; }); }
async function submit(): Promise<void> { status.value = "正在保存…"; try { const payload = { ...form, city: form.city || null, district: form.district || null, radius_meters: form.radius_meters || null, notes: form.notes || null, link_matching_records: props.location ? false : form.link_matching_records }; const saved = await api<LocationDetail>(props.location ? `/api/locations/${props.location.id}` : "/api/locations", jsonRequest(props.location ? "PUT" : "POST", payload)); emit("saved", saved); } catch (caught) { status.value = errorMessage(caught); } }
async function initializeMap(): Promise<void> {
  if (!mapElement.value) return;
  map = L.map(mapElement.value).setView([36.6, 117.06], 11);
  map.on("click", (event) => void selectPoint(event.latlng.lat, event.latlng.lng));
  let config: MapServiceConfig | null = null;
  try {
    config = await api<MapServiceConfig>("/api/map/config");
    searchEnabled = config.enabled;
    mapStatus.value = searchEnabled ? "可以搜索地点，也可以直接点击地图或拖动标记选择中心点。" : "地图可以正常选点，但尚未配置高德 Web 服务 Key。";
  } catch (caught) { mapStatus.value = errorMessage(caught); }
  const { addBaseMap } = await import("@/maps/base-map");
  baseMapHandle = addBaseMap(map, config, (message) => { baseMapStatus.value = message; });
  if (form.center_latitude !== null && form.center_longitude !== null) showPoint(form.center_latitude, form.center_longitude);
  await nextTick();
  setTimeout(() => map?.invalidateSize(), 0);
}
onMounted(initializeMap); onBeforeUnmount(() => { baseMapHandle?.destroy(); map?.remove(); map = null; });
</script>

<template>
  <form @submit.prevent="submit"><header class="dialog-header"><div><p class="eyebrow">PLACE ARCHIVE</p><h2>{{ location ? "修改观鸟地点" : "新增观鸟地点" }}</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="$emit('close')">×</button></header><div class="form-scroll">
    <fieldset><legend><span>01</span> 基本资料</legend><div class="form-grid"><label class="full-field">地点名称<input v-model="form.name" required placeholder="例如 天坛公园" /></label><label>地点类型<select v-model="form.location_type" required><option v-for="(label, value) in locationTypes" :key="value" :value="value">{{ label }}</option></select></label><label>建议匹配半径（米）<input v-model.number="form.radius_meters" type="number" min="1" step="any" placeholder="可不填" /></label><label>国家代码<input v-model="form.country_code" required /></label><label>国家名称<input v-model="form.country_name" required /></label><label>一级行政区代码<input v-model="form.admin1_code" placeholder="例如 CN-BJ" required /></label><label>一级行政区名称<input v-model="form.admin1_name" placeholder="例如 北京市" required /></label><label>城市<input v-model="form.city" /></label><label>区县<input v-model="form.district" /></label></div></fieldset>
    <fieldset><legend><span>02</span> 中心位置</legend><div class="form-grid"><section class="location-map-picker full-field"><div class="location-map-search"><label><span>搜索地图地点</span><input v-model="search" type="search" placeholder="例如：山东大学兴隆山校区" @keydown.enter.prevent="searchMap" /></label><button type="button" class="secondary-button" @click="searchMap">搜索</button></div><p class="field-hint" role="status">{{ mapStatus }}</p><p class="field-hint">{{ baseMapStatus }}</p><div id="location-map" ref="mapElement" aria-label="地点选择地图"></div><div class="location-map-results"><button v-for="item in results" :key="`${item.name}-${item.latitude}`" type="button" class="location-map-result" @click="selectPoint(item.latitude, item.longitude, item)"><strong>{{ item.name }}</strong><small>{{ [item.province, item.city, item.district, item.address].filter(Boolean).join(" · ") }}</small></button></div></section><label>中心纬度<input v-model.number="form.center_latitude" type="number" min="-90" max="90" step="any" required /></label><label>中心经度<input v-model.number="form.center_longitude" type="number" min="-180" max="180" step="any" required /></label><label class="full-field">坐标系统<select v-model="form.coordinate_system"><option value="wgs84">WGS-84（设备定位、照片坐标）</option><option value="gcj02">GCJ-02（高德地图）</option></select></label><button type="button" class="secondary-button full-field" @click="useDeviceLocation">使用当前设备位置作为中心点</button><label class="full-field">地点备注<textarea v-model="form.notes" rows="4"></textarea></label><label v-if="!location" class="check-field full-field"><input v-model="form.link_matching_records" type="checkbox" /><span>自动关联同省份、地点名称完全相同的已有观察</span></label></div></fieldset>
  </div><footer class="dialog-footer"><span role="status">{{ status }}</span><button type="submit" class="primary-button">保存地点</button></footer></form>
</template>
