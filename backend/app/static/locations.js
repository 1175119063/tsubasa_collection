const state = { locations: [], observations: [], activeLocationId: null, editingLocationId: null, locationMap: null, locationMarker: null, mapResults: [] };
const byId = (id) => document.getElementById(id);
const locationFormDialog = byId("location-form-dialog");
const locationDetailDialog = byId("location-detail-dialog");
const locationLinkDialog = byId("location-link-dialog");
const locationForm = byId("location-form");
const isV2Editor = document.body.classList.contains("v2-page");

const locationTypes = {
  wetland_park: "湿地公园", forest_park: "森林公园", urban_park: "城市公园",
  nature_reserve: "自然保护区", reservoir: "水库", farmland: "农田",
  coast: "海岸", other: "其他",
};

const provinceCodes = {
  "北京市": "CN-BJ", "天津市": "CN-TJ", "河北省": "CN-HE", "山西省": "CN-SX", "内蒙古自治区": "CN-NM",
  "辽宁省": "CN-LN", "吉林省": "CN-JL", "黑龙江省": "CN-HL", "上海市": "CN-SH", "江苏省": "CN-JS",
  "浙江省": "CN-ZJ", "安徽省": "CN-AH", "福建省": "CN-FJ", "江西省": "CN-JX", "山东省": "CN-SD",
  "河南省": "CN-HA", "湖北省": "CN-HB", "湖南省": "CN-HN", "广东省": "CN-GD", "广西壮族自治区": "CN-GX",
  "海南省": "CN-HI", "重庆市": "CN-CQ", "四川省": "CN-SC", "贵州省": "CN-GZ", "云南省": "CN-YN",
  "西藏自治区": "CN-XZ", "陕西省": "CN-SN", "甘肃省": "CN-GS", "青海省": "CN-QH", "宁夏回族自治区": "CN-NX",
  "新疆维吾尔自治区": "CN-XJ", "台湾省": "CN-TW", "香港特别行政区": "CN-HK", "澳门特别行政区": "CN-MO",
};
let leafletLoadPromise = null;
let mapSearchEnabled = false;

function setMapStatus(message) {
  const target = byId("location-map-status");
  if (target) target.textContent = message;
}

async function loadLeaflet() {
  if (window.L) return window.L;
  if (leafletLoadPromise) return leafletLoadPromise;
  leafletLoadPromise = (async () => {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
    document.head.append(stylesheet);
    await new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
      script.onload = resolve;
      script.onerror = () => reject(new Error("地图组件加载失败，请检查网络后重试。"));
      document.head.append(script);
    });
    return window.L;
  })();
  try { return await leafletLoadPromise; } catch (error) { leafletLoadPromise = null; throw error; }
}

function outsideChina(latitude, longitude) {
  return !(latitude >= 0.8293 && latitude <= 55.8271 && longitude >= 72.004 && longitude <= 137.8347);
}

function coordinateOffset(latitude, longitude) {
  const x = longitude - 105; const y = latitude - 35;
  let dLat = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * Math.sqrt(Math.abs(x));
  dLat += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
  dLat += (20 * Math.sin(y * Math.PI) + 40 * Math.sin(y / 3 * Math.PI)) * 2 / 3;
  dLat += (160 * Math.sin(y / 12 * Math.PI) + 320 * Math.sin(y / 30 * Math.PI)) * 2 / 3;
  let dLng = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * Math.sqrt(Math.abs(x));
  dLng += (20 * Math.sin(6 * x * Math.PI) + 20 * Math.sin(2 * x * Math.PI)) * 2 / 3;
  dLng += (20 * Math.sin(x * Math.PI) + 40 * Math.sin(x / 3 * Math.PI)) * 2 / 3;
  dLng += (150 * Math.sin(x / 12 * Math.PI) + 300 * Math.sin(x / 30 * Math.PI)) * 2 / 3;
  const radLat = latitude / 180 * Math.PI;
  const magic = 1 - .006693421622965943 * Math.sin(radLat) ** 2;
  const sqrtMagic = Math.sqrt(magic);
  return [dLat * 180 / ((6335552.717000426 / (magic * sqrtMagic)) * Math.PI), dLng * 180 / ((6378245 / sqrtMagic) * Math.cos(radLat) * Math.PI)];
}

function gcj02ToWgs84(latitude, longitude) {
  if (outsideChina(latitude, longitude)) return [latitude, longitude];
  const [dLat, dLng] = coordinateOffset(latitude, longitude);
  return [latitude - dLat, longitude - dLng];
}

function showMapMarker(latitude, longitude, zoom = 15) {
  if (!state.locationMap) return;
  if (!state.locationMarker) {
    state.locationMarker = window.L.marker([latitude, longitude], { draggable: true }).addTo(state.locationMap);
    state.locationMarker.on("dragend", (event) => {
      const point = event.target.getLatLng();
      selectWgsPoint(point.lat, point.lng);
    });
  } else state.locationMarker.setLatLng([latitude, longitude]);
  state.locationMap.setView([latitude, longitude], zoom);
}

function fillAddressFields(component = {}) {
  const province = component.province;
  const adcode = String(component.adcode || "");
  if (province) {
    locationForm.elements.country_code.value = "CN";
    locationForm.elements.country_name.value = "中国";
    locationForm.elements.admin1_name.value = province;
    locationForm.elements.admin1_code.value = provinceCodes[province] || (adcode ? `CN-${adcode.slice(0, 2)}` : "");
  }
  if (component.city) locationForm.elements.city.value = component.city;
  else if (province && /^(北京市|天津市|上海市|重庆市)$/.test(province)) locationForm.elements.city.value = province;
  if (component.district) locationForm.elements.district.value = component.district;
}

async function reverseMapPoint(latitude, longitude) {
  if (!mapSearchEnabled) return;
  try {
    const result = await Tsubasa.api(`/api/map/reverse?latitude=${latitude}&longitude=${longitude}`);
    fillAddressFields(result);
    setMapStatus(`已选择：${result.formatted_address || `${latitude}, ${longitude}`}（WGS-84）`);
  } catch (error) { setMapStatus(`${error.message} 坐标已经写入，可以手动补充行政区。`); }
}

function selectWgsPoint(latitude, longitude, name = "", address = null, shouldReverse = true) {
  locationForm.elements.center_latitude.value = Number(latitude).toFixed(6);
  locationForm.elements.center_longitude.value = Number(longitude).toFixed(6);
  locationForm.elements.coordinate_system.value = "wgs84";
  if (name) locationForm.elements.name.value = name;
  if (address) fillAddressFields(address);
  showMapMarker(Number(latitude), Number(longitude));
  if (shouldReverse) reverseMapPoint(Number(latitude), Number(longitude));
  else setMapStatus(`已选择：${name}（已转换为 WGS-84）`);
}

function syncMapFromForm({ reverse = false } = {}) {
  if (!state.locationMap) return;
  const latitude = Number(locationForm.elements.center_latitude.value);
  const longitude = Number(locationForm.elements.center_longitude.value);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || !locationForm.elements.center_latitude.value || !locationForm.elements.center_longitude.value) return;
  const point = locationForm.elements.coordinate_system.value === "gcj02" ? gcj02ToWgs84(latitude, longitude) : [latitude, longitude];
  showMapMarker(point[0], point[1]);
  if (reverse) reverseMapPoint(point[0], point[1]);
}

async function initializeLocationMap() {
  if (!byId("location-map")) return;
  setMapStatus("正在加载地图……");
  try {
    const [L, config] = await Promise.all([loadLeaflet(), Tsubasa.api("/api/map/config")]);
    mapSearchEnabled = Boolean(config.enabled);
    if (!state.locationMap) {
      state.locationMap = L.map("location-map").setView([36.6, 117.06], 11);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(state.locationMap);
      state.locationMap.on("click", (event) => selectWgsPoint(event.latlng.lat, event.latlng.lng));
    } else state.locationMap.invalidateSize();
    setMapStatus(mapSearchEnabled ? "可以搜索地点，也可以直接点击地图或拖动标记选择中心点。" : "地图可以正常选点，但尚未配置高德 Web 服务 Key。 ");
    syncMapFromForm();
  } catch (error) { setMapStatus(error.message); }
}

async function searchLocationMap() {
  const query = byId("location-map-search")?.value.trim();
  if (!query) { setMapStatus("请输入地点名称后再搜索。"); return; }
  if (!mapSearchEnabled) { setMapStatus("尚未配置可用的高德 Web 服务 Key。"); return; }
  setMapStatus("正在通过高德搜索地点……");
  try {
    const city = locationForm.elements.city.value.trim();
    const result = await Tsubasa.api(`/api/map/search?query=${encodeURIComponent(query)}${city ? `&city=${encodeURIComponent(city)}` : ""}`);
    state.mapResults = result.items || [];
    byId("location-map-results").innerHTML = state.mapResults.map((item, index) => `<button type="button" class="location-map-result" data-location-map-result="${index}"><strong>${Tsubasa.escapeHtml(item.name)}</strong><small>${Tsubasa.escapeHtml([item.province, item.city, item.district, item.address].filter(Boolean).join(" · "))}</small></button>`).join("");
    setMapStatus(state.mapResults.length ? `找到 ${state.mapResults.length} 个结果，请选择一个地点。` : "没有找到匹配地点，可以换个关键词或直接点击地图。");
  } catch (error) { setMapStatus(error.message); }
}

async function loadLocations() {
  [state.locations, state.observations] = await Promise.all([
    Tsubasa.api("/api/locations"), Tsubasa.api("/api/observations"),
  ]);
  populateTypeFilter();
  renderLocations();
}

function typeOptions(selected = "") {
  return Object.entries(locationTypes).map(([value, label]) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${label}</option>`
  ).join("");
}

function populateTypeFilter() {
  const select = byId("location-type-filter");
  const current = select.value;
  select.innerHTML = `<option value="">全部类型</option>${typeOptions(current)}`;
  if ([...select.options].some((item) => item.value === current)) select.value = current;
}

function renderLocations() {
  const query = byId("location-search").value.trim().toLocaleLowerCase();
  const type = byId("location-type-filter").value;
  const filtered = state.locations.filter((item) =>
    `${item.name} ${item.country_name} ${item.admin1_name} ${item.city || ""} ${item.district || ""}`
      .toLocaleLowerCase().includes(query) && (!type || item.location_type === type)
  );
  byId("location-total").textContent = filtered.length === state.locations.length
    ? `${state.locations.length} 个地点` : `显示 ${filtered.length} / ${state.locations.length} 个地点`;
  byId("location-empty").hidden = state.locations.length !== 0;
  byId("location-filter-empty").hidden = state.locations.length === 0 || filtered.length !== 0;
  byId("location-grid").innerHTML = filtered.map((item) => `
    <button class="location-card" data-location-id="${item.id}">
      ${item.cover_url
        ? `<img src="${item.cover_url}" alt="${Tsubasa.escapeHtml(item.name)}" loading="lazy" />`
        : `<span class="location-card-placeholder">⌖</span>`}
      <span class="location-card-body"><span class="card-number">${item.catalog_number}</span>
        <strong>${Tsubasa.escapeHtml(item.name)}</strong><small>${locationTypes[item.location_type]} · ${Tsubasa.escapeHtml(item.admin1_name)}</small>
        <span class="location-card-stats"><span><b>${item.species_count}</b> 物种</span><span><b>${item.observation_count}</b> 记录</span><span><b>${item.visit_day_count}</b> 到访日</span><span><b>${item.trip_count}</b> 行程</span></span>
      </span>
    </button>`).join("");
}

function openLocationForm(location = null) {
  state.editingLocationId = location?.id || null;
  locationForm.reset();
  byId("location-form-title").textContent = location ? "修改观鸟地点" : "新增观鸟地点";
  locationForm.elements.location_type.innerHTML = typeOptions(location?.location_type);
  byId("auto-link-field").hidden = Boolean(location);
  if (location) {
    for (const name of ["name", "country_code", "country_name", "admin1_code", "admin1_name", "city", "district", "center_latitude", "center_longitude", "coordinate_system", "radius_meters", "notes"]) {
      locationForm.elements[name].value = location[name] ?? "";
    }
  } else {
    locationForm.elements.country_code.value = "CN";
    locationForm.elements.country_name.value = "中国";
    locationForm.elements.coordinate_system.value = "wgs84";
    locationForm.elements.link_matching_records.checked = true;
  }
  byId("location-map-search").value = location?.name || "";
  byId("location-map-results").innerHTML = "";
  byId("location-form-status").textContent = "";
  locationFormDialog.showModal();
  initializeLocationMap();
}

function locationPayload() {
  const data = new FormData(locationForm);
  return {
    name: data.get("name"), location_type: data.get("location_type"),
    country_code: data.get("country_code"), country_name: data.get("country_name"),
    admin1_code: data.get("admin1_code"), admin1_name: data.get("admin1_name"),
    city: data.get("city") || null, district: data.get("district") || null,
    center_latitude: Number(data.get("center_latitude")),
    center_longitude: Number(data.get("center_longitude")),
    coordinate_system: data.get("coordinate_system") || "wgs84",
    radius_meters: data.get("radius_meters") ? Number(data.get("radius_meters")) : null,
    notes: data.get("notes") || null,
    link_matching_records: state.editingLocationId ? false : data.has("link_matching_records"),
  };
}

function monthLabel(value) {
  return `${value.slice(0, 4)}年${Number(value.slice(5, 7))}月`;
}

async function openLocationDetail(locationId) {
  const detail = await Tsubasa.api(`/api/locations/${locationId}`);
  state.activeLocationId = detail.id;
  const maxDays = Math.max(1, ...detail.monthly_activity.map((item) => item.visit_day_count));
  const cover = detail.cover_url
    ? `<img src="${detail.cover_url.replace("thumbnail=true", "thumbnail=false")}" alt="${Tsubasa.escapeHtml(detail.name)}" />`
    : `<span class="location-detail-placeholder">⌖</span>`;
  byId("location-detail-content").innerHTML = `
    <section class="detail-hero location-detail-hero"><div class="location-detail-cover">${cover}</div>
      <div class="detail-title"><p class="eyebrow">${detail.catalog_number}</p><h2>${Tsubasa.escapeHtml(detail.name)}</h2>
        <p>${locationTypes[detail.location_type]} · ${Tsubasa.escapeHtml(detail.country_name)} ${Tsubasa.escapeHtml(detail.admin1_name)} ${Tsubasa.escapeHtml(detail.city || "")} ${Tsubasa.escapeHtml(detail.district || "")}</p>
        <div class="detail-classification">中心点 ${detail.center_latitude}, ${detail.center_longitude} · ${detail.coordinate_system === "gcj02" ? "GCJ-02" : "WGS-84"}${detail.radius_meters ? ` · 建议半径 ${detail.radius_meters} 米` : ""}</div></div>
    </section>
    <div class="detail-body">
      <div class="location-summary-stats"><article><strong>${detail.species_count}</strong><span>记录物种</span></article><article><strong>${detail.observation_count}</strong><span>观察记录</span></article><article><strong>${detail.visit_day_count}</strong><span>到访日</span></article><article><strong>${detail.trip_count}</strong><span>观鸟行程</span></article></div>
      <section class="detail-section"><h3>地点档案</h3><p>${Tsubasa.escapeHtml(detail.notes || "暂无地点备注")}</p><p class="section-note">${detail.first_observed_at ? `初次记录 ${detail.first_observed_at.replace("T", " ")} · 最近记录 ${detail.last_observed_at.replace("T", " ")}` : "尚未关联观察记录"}</p></section>
      <section class="detail-section"><h3>时间频率</h3><div class="location-month-chart">${detail.monthly_activity.length ? detail.monthly_activity.map((item) => `<div class="month-bar-row"><span>${monthLabel(item.month)}</span><i><b style="width:${item.visit_day_count / maxDays * 100}%"></b></i><em>${item.visit_day_count} 到访日 · ${item.observation_count} 记录</em></div>`).join("") : `<p class="preview-empty">暂无时间记录</p>`}</div></section>
      <section class="detail-section"><h3>地点物种</h3><div class="location-species-list">${detail.species.length ? detail.species.map((item) => `<a href="/dex?species=${item.id}"><img src="${item.thumbnail_url}" alt="" /><span><strong>${Tsubasa.escapeHtml(item.chinese_name)}</strong><small>${Tsubasa.escapeHtml(item.scientific_name)} · ${item.observation_count} 笔</small></span></a>`).join("") : `<p class="preview-empty">尚未记录物种</p>`}</div></section>
      <section class="detail-section"><h3>观察记录</h3><div class="record-grid">${detail.observations.map((item) => `<a class="record-tile" href="/observations?observation=${item.id}"><img src="${item.thumbnail_url}" alt="" /><span class="record-tile-body"><strong>${Tsubasa.escapeHtml(item.species_name)}</strong><span>${item.observed_at.replace("T", " ")}</span><span>${Tsubasa.escapeHtml(item.locality)}</span></span></a>`).join("")}</div></section>
      <div class="location-detail-actions"><button class="secondary-button" data-upload-location-cover="${detail.id}">${detail.cover_source === "custom" ? "更换自定义封面" : "上传自定义封面"}</button><button class="secondary-button" data-edit-location="${detail.id}">修改地点</button><button class="secondary-button" data-link-location="${detail.id}">关联已有观察</button><span id="location-cover-status"></span><button class="danger-outline-button" data-delete-location="${detail.id}">删除地点</button></div>
    </div>`;
  if (!locationDetailDialog.open) locationDetailDialog.showModal();
}

function openLocationLink(locationId) {
  state.activeLocationId = Number(locationId);
  byId("location-link-list").innerHTML = state.observations.map((item) => {
    const checked = item.location?.id === state.activeLocationId ? "checked" : "";
    const elsewhere = item.location && item.location.id !== state.activeLocationId
      ? `当前：${Tsubasa.escapeHtml(item.location.name)}` : "";
    return `<label class="location-link-item"><input type="checkbox" name="observation_id" value="${item.id}" ${checked} /><img src="${item.thumbnail_url}" alt="" /><span><strong>${Tsubasa.escapeHtml(item.species_name)}</strong><small>${item.observed_at.replace("T", " ")} · ${Tsubasa.escapeHtml(item.locality)}</small><em>${elsewhere}</em></span></label>`;
  }).join("") || `<p class="compact-empty">尚无可关联的观察记录。</p>`;
  byId("location-link-status").textContent = "";
  locationLinkDialog.showModal();
}

locationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = byId("location-form-status");
  status.textContent = "正在保存…";
  try {
    const url = state.editingLocationId ? `/api/locations/${state.editingLocationId}` : "/api/locations";
    const detail = await Tsubasa.api(url, { method: state.editingLocationId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(locationPayload()) });
    locationFormDialog.close();
    if (isV2Editor) { window.location.href = `/locations?location=${detail.id}`; return; }
    await loadLocations(); await openLocationDetail(detail.id);
  } catch (error) { status.textContent = error.message; }
});

byId("location-link-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const ids = [...new FormData(event.currentTarget).getAll("observation_id")].map(Number);
  const status = byId("location-link-status"); status.textContent = "正在保存关联…";
  try {
    await Tsubasa.api(`/api/locations/${state.activeLocationId}/observations`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_ids: ids }) });
    locationLinkDialog.close();
    if (isV2Editor) { window.location.href = `/locations?location=${state.activeLocationId}`; return; }
    await loadLocations(); await openLocationDetail(state.activeLocationId);
  } catch (error) { status.textContent = error.message; }
});

byId("location-grid").addEventListener("click", (event) => { const card = event.target.closest("[data-location-id]"); if (card) openLocationDetail(card.dataset.locationId); });
byId("new-location-button").addEventListener("click", () => openLocationForm());
byId("empty-new-location").addEventListener("click", () => openLocationForm());
byId("location-search").addEventListener("input", renderLocations);
byId("location-type-filter").addEventListener("change", renderLocations);
byId("location-filter-reset").addEventListener("click", () => { byId("location-search").value = ""; byId("location-type-filter").value = ""; renderLocations(); });
byId("location-map-search-button").addEventListener("click", searchLocationMap);
byId("location-map-search").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); searchLocationMap(); } });
byId("location-map-results").addEventListener("click", (event) => {
  const choice = event.target.closest("[data-location-map-result]");
  if (!choice) return;
  const item = state.mapResults[Number(choice.dataset.locationMapResult)];
  if (item) selectWgsPoint(item.latitude, item.longitude, item.name, item, false);
});
for (const name of ["center_latitude", "center_longitude", "coordinate_system"]) locationForm.elements[name].addEventListener("change", () => syncMapFromForm());
byId("use-location-center").addEventListener("click", () => navigator.geolocation.getCurrentPosition(({ coords }) => {
  locationForm.elements.center_latitude.value = coords.latitude.toFixed(6);
  locationForm.elements.center_longitude.value = coords.longitude.toFixed(6);
  locationForm.elements.coordinate_system.value = "wgs84";
  syncMapFromForm({ reverse: true });
  setMapStatus("已读取设备位置（WGS-84）。");
}, () => { byId("location-form-status").textContent = "无法读取设备位置，请手动填写中心经纬度"; }));
document.querySelectorAll("[data-close-location-form]").forEach((item) => item.addEventListener("click", () => locationFormDialog.close()));
document.querySelectorAll("[data-close-location-detail]").forEach((item) => item.addEventListener("click", () => locationDetailDialog.close()));
document.querySelectorAll("[data-close-location-link]").forEach((item) => item.addEventListener("click", () => locationLinkDialog.close()));
locationDetailDialog.addEventListener("click", async (event) => {
  const cover = event.target.closest("[data-upload-location-cover]");
  if (cover) { state.activeLocationId = Number(cover.dataset.uploadLocationCover); byId("location-cover-input").click(); return; }
  const edit = event.target.closest("[data-edit-location]"); if (edit) { const detail = await Tsubasa.api(`/api/locations/${edit.dataset.editLocation}`); openLocationForm(detail); return; }
  const link = event.target.closest("[data-link-location]"); if (link) { openLocationLink(link.dataset.linkLocation); return; }
  const remove = event.target.closest("[data-delete-location]");
  if (remove && confirm("删除地点只会解除观察关联，不会删除任何观察记录。确定删除吗？")) { await Tsubasa.api(`/api/locations/${remove.dataset.deleteLocation}`, { method: "DELETE" }); locationDetailDialog.close(); await loadLocations(); }
});

byId("location-cover-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file || !state.activeLocationId) return;
  const status = byId("location-cover-status");
  if (status) status.textContent = "正在上传封面…";
  const body = new FormData(); body.append("photo", file);
  try {
    await Tsubasa.api(`/api/locations/${state.activeLocationId}/cover`, { method: "POST", body });
    event.target.value = "";
    if (isV2Editor) { window.location.href = `/locations?location=${state.activeLocationId}`; return; }
    await loadLocations(); await openLocationDetail(state.activeLocationId);
  } catch (error) { if (status) status.textContent = error.message; event.target.value = ""; }
});

window.TsubasaLocationEditor = {
  openLocationForm,
  async editLocation(locationId) {
    openLocationForm(await Tsubasa.api(`/api/locations/${locationId}`));
  },
  openLocationLink,
  uploadCover(locationId) {
    state.activeLocationId = Number(locationId);
    byId("location-cover-input").click();
  },
};

loadLocations().then(() => {
  const id = Number(new URLSearchParams(location.search).get("location"));
  if (id && !isV2Editor) openLocationDetail(id);
}).catch((error) => { byId("location-filter-empty").hidden = false; byId("location-filter-empty").textContent = error.message; });
