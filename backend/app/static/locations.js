const state = { locations: [], observations: [], activeLocationId: null, editingLocationId: null };
const byId = (id) => document.getElementById(id);
const locationFormDialog = byId("location-form-dialog");
const locationDetailDialog = byId("location-detail-dialog");
const locationLinkDialog = byId("location-link-dialog");
const locationForm = byId("location-form");

const locationTypes = {
  wetland_park: "湿地公园", forest_park: "森林公园", urban_park: "城市公园",
  nature_reserve: "自然保护区", reservoir: "水库", farmland: "农田",
  coast: "海岸", other: "其他",
};

async function loadLocations() {
  [state.locations, state.observations] = await Promise.all([
    Yuhen.api("/api/locations"), Yuhen.api("/api/observations"),
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
        ? `<img src="${item.cover_url}" alt="${Yuhen.escapeHtml(item.name)}" loading="lazy" />`
        : `<span class="location-card-placeholder">⌖</span>`}
      <span class="location-card-body"><span class="card-number">${item.catalog_number}</span>
        <strong>${Yuhen.escapeHtml(item.name)}</strong><small>${locationTypes[item.location_type]} · ${Yuhen.escapeHtml(item.admin1_name)}</small>
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
    for (const name of ["name", "country_code", "country_name", "admin1_code", "admin1_name", "city", "district", "center_latitude", "center_longitude", "radius_meters", "notes"]) {
      locationForm.elements[name].value = location[name] ?? "";
    }
  } else {
    locationForm.elements.country_code.value = "CN";
    locationForm.elements.country_name.value = "中国";
    locationForm.elements.link_matching_records.checked = true;
  }
  byId("location-form-status").textContent = "";
  locationFormDialog.showModal();
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
    radius_meters: data.get("radius_meters") ? Number(data.get("radius_meters")) : null,
    notes: data.get("notes") || null,
    link_matching_records: state.editingLocationId ? false : data.has("link_matching_records"),
  };
}

function monthLabel(value) {
  return `${value.slice(0, 4)}年${Number(value.slice(5, 7))}月`;
}

async function openLocationDetail(locationId) {
  const detail = await Yuhen.api(`/api/locations/${locationId}`);
  state.activeLocationId = detail.id;
  const maxDays = Math.max(1, ...detail.monthly_activity.map((item) => item.visit_day_count));
  const cover = detail.cover_url
    ? `<img src="${detail.cover_url.replace("thumbnail=true", "thumbnail=false")}" alt="${Yuhen.escapeHtml(detail.name)}" />`
    : `<span class="location-detail-placeholder">⌖</span>`;
  byId("location-detail-content").innerHTML = `
    <section class="detail-hero location-detail-hero"><div class="location-detail-cover">${cover}</div>
      <div class="detail-title"><p class="eyebrow">${detail.catalog_number}</p><h2>${Yuhen.escapeHtml(detail.name)}</h2>
        <p>${locationTypes[detail.location_type]} · ${Yuhen.escapeHtml(detail.country_name)} ${Yuhen.escapeHtml(detail.admin1_name)} ${Yuhen.escapeHtml(detail.city || "")} ${Yuhen.escapeHtml(detail.district || "")}</p>
        <div class="detail-classification">中心点 ${detail.center_latitude}, ${detail.center_longitude}${detail.radius_meters ? ` · 建议半径 ${detail.radius_meters} 米` : ""}</div></div>
    </section>
    <div class="detail-body">
      <div class="location-summary-stats"><article><strong>${detail.species_count}</strong><span>记录物种</span></article><article><strong>${detail.observation_count}</strong><span>观察记录</span></article><article><strong>${detail.visit_day_count}</strong><span>到访日</span></article><article><strong>${detail.trip_count}</strong><span>观鸟行程</span></article></div>
      <section class="detail-section"><h3>地点档案</h3><p>${Yuhen.escapeHtml(detail.notes || "暂无地点备注")}</p><p class="section-note">${detail.first_observed_at ? `初次记录 ${detail.first_observed_at.replace("T", " ")} · 最近记录 ${detail.last_observed_at.replace("T", " ")}` : "尚未关联观察记录"}</p></section>
      <section class="detail-section"><h3>时间频率</h3><div class="location-month-chart">${detail.monthly_activity.length ? detail.monthly_activity.map((item) => `<div class="month-bar-row"><span>${monthLabel(item.month)}</span><i><b style="width:${item.visit_day_count / maxDays * 100}%"></b></i><em>${item.visit_day_count} 到访日 · ${item.observation_count} 记录</em></div>`).join("") : `<p class="preview-empty">暂无时间记录</p>`}</div></section>
      <section class="detail-section"><h3>地点物种</h3><div class="location-species-list">${detail.species.length ? detail.species.map((item) => `<a href="/dex?species=${item.id}"><img src="${item.thumbnail_url}" alt="" /><span><strong>${Yuhen.escapeHtml(item.chinese_name)}</strong><small>${Yuhen.escapeHtml(item.scientific_name)} · ${item.observation_count} 笔</small></span></a>`).join("") : `<p class="preview-empty">尚未记录物种</p>`}</div></section>
      <section class="detail-section"><h3>观察记录</h3><div class="record-grid">${detail.observations.map((item) => `<a class="record-tile" href="/observations?observation=${item.id}"><img src="${item.thumbnail_url}" alt="" /><span class="record-tile-body"><strong>${Yuhen.escapeHtml(item.species_name)}</strong><span>${item.observed_at.replace("T", " ")}</span><span>${Yuhen.escapeHtml(item.locality)}</span></span></a>`).join("")}</div></section>
      <div class="location-detail-actions"><button class="secondary-button" data-upload-location-cover="${detail.id}">${detail.cover_source === "custom" ? "更换自定义封面" : "上传自定义封面"}</button><button class="secondary-button" data-edit-location="${detail.id}">修改地点</button><button class="secondary-button" data-link-location="${detail.id}">关联已有观察</button><span id="location-cover-status"></span><button class="danger-outline-button" data-delete-location="${detail.id}">删除地点</button></div>
    </div>`;
  if (!locationDetailDialog.open) locationDetailDialog.showModal();
}

function openLocationLink(locationId) {
  state.activeLocationId = Number(locationId);
  byId("location-link-list").innerHTML = state.observations.map((item) => {
    const checked = item.location?.id === state.activeLocationId ? "checked" : "";
    const elsewhere = item.location && item.location.id !== state.activeLocationId
      ? `当前：${Yuhen.escapeHtml(item.location.name)}` : "";
    return `<label class="location-link-item"><input type="checkbox" name="observation_id" value="${item.id}" ${checked} /><img src="${item.thumbnail_url}" alt="" /><span><strong>${Yuhen.escapeHtml(item.species_name)}</strong><small>${item.observed_at.replace("T", " ")} · ${Yuhen.escapeHtml(item.locality)}</small><em>${elsewhere}</em></span></label>`;
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
    const detail = await Yuhen.api(url, { method: state.editingLocationId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(locationPayload()) });
    locationFormDialog.close(); await loadLocations(); await openLocationDetail(detail.id);
  } catch (error) { status.textContent = error.message; }
});

byId("location-link-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const ids = [...new FormData(event.currentTarget).getAll("observation_id")].map(Number);
  const status = byId("location-link-status"); status.textContent = "正在保存关联…";
  try {
    await Yuhen.api(`/api/locations/${state.activeLocationId}/observations`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_ids: ids }) });
    locationLinkDialog.close(); await loadLocations(); await openLocationDetail(state.activeLocationId);
  } catch (error) { status.textContent = error.message; }
});

byId("location-grid").addEventListener("click", (event) => { const card = event.target.closest("[data-location-id]"); if (card) openLocationDetail(card.dataset.locationId); });
byId("new-location-button").addEventListener("click", () => openLocationForm());
byId("empty-new-location").addEventListener("click", () => openLocationForm());
byId("location-search").addEventListener("input", renderLocations);
byId("location-type-filter").addEventListener("change", renderLocations);
byId("location-filter-reset").addEventListener("click", () => { byId("location-search").value = ""; byId("location-type-filter").value = ""; renderLocations(); });
byId("use-location-center").addEventListener("click", () => navigator.geolocation.getCurrentPosition(({ coords }) => { locationForm.elements.center_latitude.value = coords.latitude; locationForm.elements.center_longitude.value = coords.longitude; }, () => { byId("location-form-status").textContent = "无法读取设备位置，请手动填写中心经纬度"; }));
document.querySelectorAll("[data-close-location-form]").forEach((item) => item.addEventListener("click", () => locationFormDialog.close()));
document.querySelectorAll("[data-close-location-detail]").forEach((item) => item.addEventListener("click", () => locationDetailDialog.close()));
document.querySelectorAll("[data-close-location-link]").forEach((item) => item.addEventListener("click", () => locationLinkDialog.close()));
locationDetailDialog.addEventListener("click", async (event) => {
  const cover = event.target.closest("[data-upload-location-cover]");
  if (cover) { state.activeLocationId = Number(cover.dataset.uploadLocationCover); byId("location-cover-input").click(); return; }
  const edit = event.target.closest("[data-edit-location]"); if (edit) { const detail = await Yuhen.api(`/api/locations/${edit.dataset.editLocation}`); openLocationForm(detail); return; }
  const link = event.target.closest("[data-link-location]"); if (link) { openLocationLink(link.dataset.linkLocation); return; }
  const remove = event.target.closest("[data-delete-location]");
  if (remove && confirm("删除地点只会解除观察关联，不会删除任何观察记录。确定删除吗？")) { await Yuhen.api(`/api/locations/${remove.dataset.deleteLocation}`, { method: "DELETE" }); locationDetailDialog.close(); await loadLocations(); }
});

byId("location-cover-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file || !state.activeLocationId) return;
  const status = byId("location-cover-status");
  if (status) status.textContent = "正在上传封面…";
  const body = new FormData(); body.append("photo", file);
  try {
    await Yuhen.api(`/api/locations/${state.activeLocationId}/cover`, { method: "POST", body });
    event.target.value = ""; await loadLocations(); await openLocationDetail(state.activeLocationId);
  } catch (error) { if (status) status.textContent = error.message; event.target.value = ""; }
});

loadLocations().then(() => { const id = Number(new URLSearchParams(location.search).get("location")); if (id) openLocationDetail(id); }).catch((error) => { byId("location-filter-empty").hidden = false; byId("location-filter-empty").textContent = error.message; });
