const state = { trips: [], locations: [], observations: [], activeTripId: null, editingTripId: null };
const byId = (id) => document.getElementById(id);
const tripFormDialog = byId("trip-form-dialog");
const tripDetailDialog = byId("trip-detail-dialog");
const tripLinkDialog = byId("trip-link-dialog");
const tripForm = byId("trip-form");

async function loadTrips() {
  [state.trips, state.locations, state.observations] = await Promise.all([
    Yuhen.api("/api/trips"), Yuhen.api("/api/locations"), Yuhen.api("/api/observations"),
  ]);
  populateTripFilters(); renderTrips();
}

function locationOptions(selected = "") {
  if (!state.locations.length) return `<option value="">请先在地点浏览中建立地点</option>`;
  return state.locations.map((item) => `<option value="${item.id}" ${String(item.id) === String(selected) ? "selected" : ""}>${Yuhen.escapeHtml(item.name)} · ${Yuhen.escapeHtml(item.admin1_name)}</option>`).join("");
}

function populateTripFilters() {
  const yearSelect = byId("trip-year-filter"); const oldYear = yearSelect.value;
  const years = [...new Set(state.trips.map((item) => item.started_at.slice(0, 4)))].sort();
  yearSelect.innerHTML = `<option value="">全部年份</option>${years.map((item) => `<option value="${item}">${item} 年</option>`).join("")}`;
  if (years.includes(oldYear)) yearSelect.value = oldYear;
  populateTripMonths();
  const locationSelect = byId("trip-location-filter"); const oldLocation = locationSelect.value;
  locationSelect.innerHTML = `<option value="">全部地点</option>${locationOptions(oldLocation)}`;
  if ([...locationSelect.options].some((item) => item.value === oldLocation)) locationSelect.value = oldLocation;
}

function populateTripMonths() {
  const year = byId("trip-year-filter").value; const select = byId("trip-month-filter"); const old = select.value;
  const months = [...new Set(state.trips.filter((item) => !year || item.started_at.startsWith(`${year}-`)).map((item) => item.started_at.slice(5, 7)))].sort();
  select.innerHTML = `<option value="">全部月份</option>${months.map((item) => `<option value="${item}">${Number(item)} 月</option>`).join("")}`;
  if (months.includes(old)) select.value = old;
}

function durationLabel(minutes) {
  const hours = Math.floor(minutes / 60); const rest = minutes % 60;
  return `${hours ? `${hours} 小时` : ""}${rest ? ` ${rest} 分钟` : ""}`.trim() || "0 分钟";
}

function renderTrips() {
  const year = byId("trip-year-filter").value; const month = byId("trip-month-filter").value; const location = byId("trip-location-filter").value; const direction = byId("trip-sort").value === "desc" ? -1 : 1;
  const filtered = state.trips.filter((item) => (!year || item.started_at.slice(0, 4) === year) && (!month || item.started_at.slice(5, 7) === month) && (!location || String(item.location.id) === location)).sort((a, b) => a.started_at.localeCompare(b.started_at) * direction);
  const groups = new Map(); for (const item of filtered) { const key = item.started_at.slice(0, 7); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(item); }
  byId("trip-total").textContent = filtered.length === state.trips.length ? `${state.trips.length} 次行程` : `显示 ${filtered.length} / ${state.trips.length} 次行程`;
  byId("trip-empty").hidden = state.trips.length !== 0; byId("trip-filter-empty").hidden = state.trips.length === 0 || filtered.length !== 0;
  byId("trip-groups").innerHTML = [...groups.entries()].map(([key, items]) => `<section class="observation-month-group"><header class="month-heading"><h2>${key.slice(0, 4)}年${Number(key.slice(5, 7))}月</h2><span>${items.length} 次</span></header><div class="trip-grid">${items.map((item) => `<button class="trip-card" data-trip-id="${item.id}">${item.cover_url ? `<img src="${item.cover_url}" alt="" />` : `<span class="trip-card-placeholder">⌁</span>`}<span class="trip-card-body"><span class="card-number">${item.catalog_number}</span><strong>${Yuhen.escapeHtml(item.location.name)}</strong><small>${item.started_at.replace("T", " ")}—${item.ended_at.slice(11)}</small><span class="trip-card-stats"><span><b>${item.species_count}</b> 种</span><span><b>${item.genus_count}</b> 属</span><span><b>${item.family_count}</b> 科</span><span><b>${item.observation_count}</b> 记录</span></span></span></button>`).join("")}</div></section>`).join("");
}

function openTripForm(trip = null) {
  state.editingTripId = trip?.id || null; tripForm.reset();
  byId("trip-form-title").textContent = trip ? "修改观鸟行程" : "创建观鸟行程";
  tripForm.elements.location_id.innerHTML = locationOptions(trip?.location.id);
  if (trip) { tripForm.elements.started_at.value = trip.started_at; tripForm.elements.ended_at.value = trip.ended_at; tripForm.elements.notes.value = trip.notes || ""; }
  byId("trip-form-status").textContent = state.locations.length ? "" : "请先建立至少一个观鸟地点。";
  tripFormDialog.showModal();
}

function tripPayload() {
  const data = new FormData(tripForm); return { location_id: Number(data.get("location_id")), started_at: data.get("started_at"), ended_at: data.get("ended_at"), notes: data.get("notes") || null };
}

async function openTripDetail(tripId) {
  const detail = await Yuhen.api(`/api/trips/${tripId}`); state.activeTripId = detail.id;
  const cover = detail.cover_url ? `<img src="${detail.cover_url.replace("thumbnail=true", "thumbnail=false")}" alt="" />` : `<span class="trip-detail-placeholder">⌁</span>`;
  byId("trip-detail-content").innerHTML = `<section class="detail-hero trip-detail-hero"><div class="trip-detail-cover">${cover}</div><div class="detail-title"><p class="eyebrow">${detail.catalog_number}</p><h2>${Yuhen.escapeHtml(detail.location.name)}</h2><p>${detail.started_at.replace("T", " ")}—${detail.ended_at.replace("T", " ")}</p><div class="detail-classification">持续 ${durationLabel(detail.duration_minutes)} · <a href="/locations?location=${detail.location.id}">查看地点档案</a></div></div></section><div class="detail-body">
    <div class="trip-summary-stats"><article><strong>${detail.species_count}</strong><span>种</span></article><article><strong>${detail.genus_count}</strong><span>属</span></article><article><strong>${detail.family_count}</strong><span>科</span></article><article><strong>${detail.observation_count}</strong><span>观察记录</span></article></div>
    <section class="detail-section"><h3>行程备注</h3><p>${Yuhen.escapeHtml(detail.notes || "暂无备注")}</p></section>
    <section class="detail-section"><h3>本次拍摄物种</h3><div class="location-species-list">${detail.species.length ? detail.species.map((item) => `<a href="/dex?species=${item.id}"><img src="${item.thumbnail_url}" alt="" /><span><strong>${Yuhen.escapeHtml(item.chinese_name)}</strong><small>${Yuhen.escapeHtml(item.scientific_name)} · ${item.observation_count} 笔</small></span></a>`).join("") : `<p class="preview-empty">尚未关联观察</p>`}</div></section>
    <section class="detail-section"><h3>观察记录与封面</h3><p class="section-note">默认使用拍摄时间最早的照片，也可以改选行程中的其他照片。</p><div class="observation-list">${detail.observations.map((item) => { const current = item.id === detail.cover_observation_id; return `<article class="observation-card ${current ? "is-current-cover" : ""}"><img src="${item.thumbnail_url}" alt="" /><div class="observation-info">${Yuhen.escapeHtml(item.species_name)}<br />${item.observed_at.replace("T", " ")}<span class="observation-card-actions"><button class="cover-button" data-trip-cover-observation="${item.id}" ${current ? "disabled" : ""}>${current ? "当前行程封面" : "设为行程封面"}</button><a class="observation-preview-link" href="/observations?observation=${item.id}">预览观察</a></span></div></article>`; }).join("")}</div></section>
    <div class="location-detail-actions"><button class="secondary-button" data-edit-trip="${detail.id}">修改行程</button><button class="primary-button" data-link-trip="${detail.id}">关联观察</button><button class="danger-outline-button" data-delete-trip="${detail.id}">删除行程</button></div></div>`;
  if (!tripDetailDialog.open) tripDetailDialog.showModal();
}

function openTripLink(trip) {
  state.activeTripId = trip.id;
  const eligible = state.observations.filter((item) => trip.started_at <= item.observed_at && item.observed_at <= trip.ended_at && (!item.location || item.location.id === trip.location.id) && (!item.trip || item.trip.id === trip.id));
  byId("trip-link-list").innerHTML = eligible.map((item) => `<label class="location-link-item"><input type="checkbox" name="observation_id" value="${item.id}" ${item.trip?.id === trip.id ? "checked" : ""} /><img src="${item.thumbnail_url}" alt="" /><span><strong>${Yuhen.escapeHtml(item.species_name)}</strong><small>${item.observed_at.replace("T", " ")} · ${Yuhen.escapeHtml(item.locality)}</small><em>${item.location ? Yuhen.escapeHtml(item.location.name) : "尚未关联地点；加入后自动关联"}</em></span></label>`).join("") || `<p class="compact-empty">没有符合时间和地点条件的可关联观察。</p>`;
  byId("trip-link-status").textContent = ""; tripLinkDialog.showModal();
}

tripForm.addEventListener("submit", async (event) => { event.preventDefault(); const status = byId("trip-form-status"); status.textContent = "正在保存…"; try { const url = state.editingTripId ? `/api/trips/${state.editingTripId}` : "/api/trips"; const detail = await Yuhen.api(url, { method: state.editingTripId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(tripPayload()) }); tripFormDialog.close(); await loadTrips(); await openTripDetail(detail.id); } catch (error) { status.textContent = error.message; } });
byId("trip-link-form").addEventListener("submit", async (event) => { event.preventDefault(); const ids = new FormData(event.currentTarget).getAll("observation_id").map(Number); const status = byId("trip-link-status"); status.textContent = "正在保存关联…"; try { await Yuhen.api(`/api/trips/${state.activeTripId}/observations`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_ids: ids }) }); tripLinkDialog.close(); await loadTrips(); await openTripDetail(state.activeTripId); } catch (error) { status.textContent = error.message; } });

byId("trip-groups").addEventListener("click", (event) => { const card = event.target.closest("[data-trip-id]"); if (card) openTripDetail(card.dataset.tripId); });
byId("new-trip-button").addEventListener("click", () => openTripForm()); byId("empty-new-trip").addEventListener("click", () => openTripForm());
byId("trip-year-filter").addEventListener("change", () => { populateTripMonths(); renderTrips(); }); byId("trip-month-filter").addEventListener("change", renderTrips); byId("trip-location-filter").addEventListener("change", renderTrips); byId("trip-sort").addEventListener("change", renderTrips);
byId("trip-filter-reset").addEventListener("click", () => { byId("trip-year-filter").value = ""; populateTripMonths(); byId("trip-month-filter").value = ""; byId("trip-location-filter").value = ""; byId("trip-sort").value = "asc"; renderTrips(); });
document.querySelectorAll("[data-close-trip-form]").forEach((item) => item.addEventListener("click", () => tripFormDialog.close())); document.querySelectorAll("[data-close-trip-detail]").forEach((item) => item.addEventListener("click", () => tripDetailDialog.close())); document.querySelectorAll("[data-close-trip-link]").forEach((item) => item.addEventListener("click", () => tripLinkDialog.close()));
tripDetailDialog.addEventListener("click", async (event) => { const cover = event.target.closest("[data-trip-cover-observation]"); if (cover) { await Yuhen.api(`/api/trips/${state.activeTripId}/cover`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_id: Number(cover.dataset.tripCoverObservation) }) }); await loadTrips(); await openTripDetail(state.activeTripId); return; } const edit = event.target.closest("[data-edit-trip]"); if (edit) { openTripForm(await Yuhen.api(`/api/trips/${edit.dataset.editTrip}`)); return; } const link = event.target.closest("[data-link-trip]"); if (link) { openTripLink(await Yuhen.api(`/api/trips/${link.dataset.linkTrip}`)); return; } const remove = event.target.closest("[data-delete-trip]"); if (remove && confirm("删除行程只会解除观察关联，不会删除任何观察记录。确定删除吗？")) { await Yuhen.api(`/api/trips/${remove.dataset.deleteTrip}`, { method: "DELETE" }); tripDetailDialog.close(); await loadTrips(); } });

loadTrips().then(() => { const id = Number(new URLSearchParams(location.search).get("trip")); if (id) openTripDetail(id); }).catch((error) => { byId("trip-filter-empty").hidden = false; byId("trip-filter-empty").textContent = error.message; });
