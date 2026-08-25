(function () {
  "use strict";

  const page = document.body.dataset.page;
  const byId = (id) => document.getElementById(id);
  const esc = (value) => Yuhen.escapeHtml(value == null ? "" : String(value));
  const locationTypes = {
    wetland_park: "湿地公园", forest_park: "森林公园", urban_park: "城市公园",
    nature_reserve: "自然保护区", reservoir: "水库", farmland: "农田",
    coast: "海岸", other: "其他",
  };
  const state = {
    observations: [], locations: [], trips: [], activeObservationSpecies: new Map(),
    observationTripId: null, observationSpeciesId: null, observationMultiSpeciesOnly: false,
    activeTripId: null, tripCoverChoices: [],
  };

  function dateTime(value) { return String(value || "").replace("T", " "); }
  function monthLabel(value) { return `${value.slice(0, 4)}年${Number(value.slice(5, 7))}月`; }
  function durationLabel(minutes) {
    const hours = Math.floor(minutes / 60); const rest = minutes % 60;
    return [hours ? `${hours}小时` : "", rest ? `${rest}分钟` : ""].filter(Boolean).join(" ") || "0分钟";
  }
  function fillSelect(select, values, placeholder, render = (value) => value) {
    const old = select.value;
    select.innerHTML = `<option value="">${placeholder}</option>${values.map((value) => `<option value="${esc(value)}">${esc(render(value))}</option>`).join("")}`;
    if (values.map(String).includes(old)) select.value = old;
  }
  function wireDialog(dialog) {
    dialog.querySelector(".v2-dossier-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
  }
  function detailStat(value, label) { return `<article><strong>${value}</strong><span>${label}</span></article>`; }
  function speciesTiles(items) {
    return items.length ? items.map((item) => `<a class="v2-mini-species" href="/dex?species=${item.id}"><img src="${esc(item.thumbnail_url)}" alt="" /><span><strong>${esc(item.chinese_name)}</strong><em>${esc(item.scientific_name)}</em><small>${item.observation_count} 次记录</small></span></a>`).join("") : "<p class=\"v2-detail-empty\">尚未获得物种情报。</p>";
  }
  function evidenceTiles(items) {
    return items.length ? items.map((item) => `<a class="v2-detail-evidence" href="/observations?observation=${item.id}"><img src="${esc(item.thumbnail_url)}" alt="" /><span><strong>${esc(item.species_name)}</strong><small>${dateTime(item.observed_at)}</small></span></a>`).join("") : "<p class=\"v2-detail-empty\">尚未关联观察记录。</p>";
  }
  function tripEvidenceTiles(items) {
    if (!items.length) return "<p class=\"v2-detail-empty\">尚未关联观察记录。</p>";
    const tiles = items.map((item) => `<a class="v2-detail-evidence" href="/observations?observation=${item.id}"><img src="${esc(item.thumbnail_url)}" alt="" /><span><strong>${esc(item.species_name)}</strong><small>${dateTime(item.observed_at)}</small></span></a>`).join("");
    return `${tiles}${items.moreHref ? `<a class="v2-detail-evidence v2-evidence-more" href="${items.moreHref}"><span><strong>查看更多</strong><small>检视本次远征全部 ${items.totalCount} 笔记录 →</small></span></a>` : ""}`;
  }

  function openTripCoverPicker(item) {
    const dialog = byId("v2-trip-cover-dialog");
    state.activeTripId = item.id;
    state.tripCoverChoices = item.observations;
    byId("v2-trip-cover-status").textContent = item.observations.length
      ? `从本次远征的 ${item.observations.length} 笔观察中选择一张照片。`
      : "本次远征尚未关联带照片的观察记录。";
    byId("v2-trip-cover-grid").innerHTML = item.observations.length
      ? item.observations.map((observation) => `<button class="v2-home-cover-card${observation.id === item.cover_observation_id ? " is-selected" : ""}" type="button" data-v2-trip-cover-choice="${observation.id}" ${observation.id === item.cover_observation_id ? "disabled" : ""}><img src="${esc(observation.thumbnail_url)}" alt="" /><span><b>${esc(observation.species_name)}</b><small>${dateTime(observation.observed_at)}</small></span><em>${observation.id === item.cover_observation_id ? "当前封面" : "选作封面"}</em></button>`).join("")
      : "<p class=\"v2-detail-empty\">暂无可供选择的照片。</p>";
    dialog.showModal();
  }

  function observationSpeciesEntries(item) {
    if (Array.isArray(item.species_entries) && item.species_entries.length) return item.species_entries;
    return [{
      id: null,
      species_id: item.species_id,
      species_name: item.species_name || "未命名物种",
      species_scientific_name: item.species_scientific_name || "",
      photo_type: item.photo_type,
      sex: item.sex,
      life_stage: item.life_stage,
      subspecies: item.subspecies,
      notes: null,
      is_primary: true,
    }];
  }

  function observationCard(item) {
    const entries = observationSpeciesEntries(item);
    const names = entries.map((entry) => entry.species_name);
    const title = names.length > 2 ? `${names.slice(0, 2).join("、")}等 ${names.length} 种` : names.join("、");
    const count = item.species_count || entries.length;
    return `<button class="v2-field-card" data-v2-observation="${item.id}"><span class="v2-field-photo"><img src="${esc(item.thumbnail_url)}" alt="${esc(title)}" loading="lazy" /><i>OBSERVATION ${item.id}</i></span><span class="v2-field-copy"><strong>${esc(title)}</strong><em>${count} 条物种记录</em><span>${dateTime(item.observed_at)}</span><small>${esc(item.location?.name || item.locality)}</small><b>${esc(Yuhen.labels[item.season] || item.season)} · ${count > 1 ? "多物种照片" : (item.photo_type === "group" ? "群体照片" : "个体照片")}</b></span></button>`;
  }

  function populateObservationFilters() {
    fillSelect(byId("v2-observation-year"), [...new Set(state.observations.map((item) => item.observed_at.slice(0, 4)))].sort(), "全部年份", (value) => `${value}年`);
    const locations = new Map(); state.observations.forEach((item) => { if (item.location) locations.set(String(item.location.id), item.location.name); });
    const select = byId("v2-observation-location"); const old = select.value;
    select.innerHTML = `<option value="">全部区域</option>${[...locations].map(([id, name]) => `<option value="${id}">${esc(name)}</option>`).join("")}`;
    if (locations.has(old)) select.value = old;
    populateObservationMonths();
  }
  function populateObservationMonths() {
    const year = byId("v2-observation-year").value;
    fillSelect(byId("v2-observation-month"), [...new Set(state.observations.filter((item) => !year || item.observed_at.startsWith(`${year}-`)).map((item) => item.observed_at.slice(5, 7)))].sort(), "全部月份", (value) => `${Number(value)}月`);
  }
  function renderObservations() {
    const year = byId("v2-observation-year").value; const month = byId("v2-observation-month").value;
    const location = byId("v2-observation-location").value; const direction = byId("v2-observation-sort").value === "desc" ? -1 : 1;
    const filtered = state.observations.filter((item) => {
      const entries = observationSpeciesEntries(item);
      return (!year || item.observed_at.slice(0, 4) === year)
        && (!month || item.observed_at.slice(5, 7) === month)
        && (!location || String(item.location?.id) === location)
        && (!state.observationTripId || item.trip?.id === state.observationTripId)
        && (!state.observationSpeciesId || entries.some((entry) => entry.species_id === state.observationSpeciesId))
        && (!state.observationMultiSpeciesOnly || entries.length > 1);
    }).sort((a, b) => a.observed_at.localeCompare(b.observed_at) * direction);
    const groups = new Map(); filtered.forEach((item) => { const key = item.observed_at.slice(0, 7); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(item); });
    byId("v2-observation-count").textContent = filtered.length === state.observations.length ? state.observations.length : `${filtered.length}/${state.observations.length}`;
    byId("v2-observation-groups").innerHTML = [...groups].map(([key, items]) => `<section class="v2-month-section"><header><div><span>${key.slice(0, 4)}</span><h3>${Number(key.slice(5, 7))}月调查记录</h3></div><b>${items.length} 页</b></header><div class="v2-field-grid">${items.map(observationCard).join("")}</div></section>`).join("");
    byId("v2-observation-empty").hidden = filtered.length !== 0;
    document.querySelectorAll("[data-v2-observation]").forEach((card) => card.addEventListener("click", () => openObservation(Number(card.dataset.v2Observation))));
  }
  function openObservation(id, requestedIndex) {
    const item = state.observations.find((entry) => entry.id === id); if (!item) return;
    const dialog = byId("v2-observation-dialog");
    const entries = observationSpeciesEntries(item);
    const storedIndex = state.activeObservationSpecies.get(id) || 0;
    const index = Math.max(0, Math.min(requestedIndex ?? storedIndex, entries.length - 1));
    const entry = entries[index];
    const sexLabel = entry.sex === "unknown" || !entry.sex ? "性别未知" : (Yuhen.labels[entry.sex] || entry.sex);
    const lifeStageLabel = entry.life_stage === "unknown" || !entry.life_stage ? "生命阶段未知" : (Yuhen.labels[entry.life_stage] || entry.life_stage);
    const individualInfo = entry.photo_type === "group" ? "群体照片" : `${sexLabel} · ${lifeStageLabel}`;
    const subspecies = entry.subspecies
      ? [entry.subspecies.chinese_name, entry.subspecies.scientific_name].filter(Boolean).join(" · ")
      : "未记录";
    const audio = Array.isArray(item.audio) ? item.audio : [];
    state.activeObservationSpecies.set(id, index);
    byId("v2-observation-detail").innerHTML = `<section class="v2-observation-hero"><div class="v2-observation-hero-photo"><img src="${esc(item.photo_url)}" alt="观察照片" /></div><div class="v2-observation-hero-copy"><p class="v2-kicker">田野记录 · OBSERVATION ${item.id}${entries.length > 1 ? ` · ${index + 1}/${entries.length}` : ""}</p><h2>${esc(entry.species_name)}</h2><em>${esc(entry.species_scientific_name)}</em><dl><div><dt>个体信息</dt><dd>${esc(individualInfo)}</dd></div><div><dt>亚种</dt><dd>${esc(subspecies)}</dd></div><div><dt>拍摄时间</dt><dd>${dateTime(item.observed_at)}</dd></div><div><dt>拍摄地点</dt><dd>${esc(item.country_name)} · ${esc(item.admin1_name)} · ${esc(item.locality)}</dd></div><div><dt>坐标</dt><dd>${item.latitude}, ${item.longitude}</dd></div><div><dt>所属远征</dt><dd>${item.trip ? `${esc(item.trip.catalog_number)} · ${esc(item.trip.name)}` : "未关联"}</dd></div>${entry.notes ? `<div><dt>物种备注</dt><dd>${esc(entry.notes)}</dd></div>` : ""}</dl><div class="v2-detail-actions v2-species-navigation"><button class="v2-button v2-button-primary" type="button" data-v2-edit-observation="${item.id}">修改记录</button><button class="v2-button v2-button-ghost" type="button" data-v2-species-nav="previous" data-observation-id="${item.id}" ${entries.length === 1 ? "disabled" : ""}>上一个物种</button><button class="v2-button v2-button-ghost" type="button" data-v2-species-nav="next" data-observation-id="${item.id}" ${entries.length === 1 ? "disabled" : ""}>下一个物种</button></div></div></section><section class="v2-observation-notes"><p class="v2-kicker">现场备注</p><h3>调查者记录</h3><p>${esc(item.notes || "本次观察没有附加备注。")}</p>${audio.length ? `<div class="v2-audio-list">${audio.map((audioItem) => `<audio controls src="${esc(audioItem.url)}"></audio>`).join("")}</div>` : ""}<div id="observation-edit-container"></div></section><section class="v2-archive-danger-zone v2-observation-danger-zone"><div><p class="v2-kicker">记录管理</p><span>永久删除会同时移除这笔观察的照片、录音与全部物种记录。</span></div><button class="v2-button v2-button-danger" type="button" data-v2-delete-observation="${item.id}">永久删除</button></section>`;
    if (!dialog.open) dialog.showModal();
  }
  async function loadObservations() {
    state.observations = await Yuhen.api("/api/observations"); populateObservationFilters();
    const requestedLocation = new URLSearchParams(location.search).get("location");
    state.observationTripId = Number(new URLSearchParams(location.search).get("trip")) || null;
    if (requestedLocation && [...byId("v2-observation-location").options].some((option) => option.value === requestedLocation)) byId("v2-observation-location").value = requestedLocation;
    renderObservations();
    byId("v2-observation-year").addEventListener("change", () => { populateObservationMonths(); renderObservations(); });
    ["v2-observation-month", "v2-observation-location", "v2-observation-sort"].forEach((id) => byId(id).addEventListener("change", renderObservations));
    byId("v2-observation-reset").addEventListener("click", () => { ["v2-observation-year", "v2-observation-month", "v2-observation-location"].forEach((id) => { byId(id).value = ""; }); byId("v2-observation-sort").value = "asc"; state.observationTripId = null; state.observationSpeciesId = null; state.observationMultiSpeciesOnly = false; history.replaceState(null, "", "/observations"); populateObservationMonths(); renderObservations(); });
    wireDialog(byId("v2-observation-dialog"));
    byId("v2-observation-dialog").addEventListener("click", async (event) => {
      const navigation = event.target.closest("[data-v2-species-nav]");
      if (navigation && !navigation.disabled) {
        const observationId = Number(navigation.dataset.observationId);
        const observation = state.observations.find((entry) => entry.id === observationId);
        const count = observationSpeciesEntries(observation).length;
        const current = state.activeObservationSpecies.get(observationId) || 0;
        const next = navigation.dataset.v2SpeciesNav === "previous" ? (current - 1 + count) % count : (current + 1) % count;
        openObservation(observationId, next);
        return;
      }
      const edit = event.target.closest("[data-v2-edit-observation]");
      if (edit) {
        if (!window.YuhenObservationEditor) return;
        edit.disabled = true;
        try {
          const observationId = Number(edit.dataset.v2EditObservation);
          const entries = observationSpeciesEntries(state.observations.find((entry) => entry.id === observationId));
          const selectedEntry = entries[state.activeObservationSpecies.get(observationId) || 0];
          await window.YuhenObservationEditor.showObservationEditor(observationId, selectedEntry?.id);
        }
        catch (error) { alert(error.message); }
        finally { edit.disabled = false; }
        return;
      }
      const remove = event.target.closest("[data-v2-delete-observation]");
      if (remove && confirm("这会永久删除该观察及其照片、录音；若它是物种的最后一笔记录，物种档案也会一并删除。确定继续吗？")) {
        await Yuhen.api(`/api/observations/${remove.dataset.v2DeleteObservation}`, { method: "DELETE" });
        window.location.href = "/observations";
      }
      const removeEntry = event.target.closest("[data-v2-remove-species-entry]");
      if (removeEntry && confirm("只从这笔观察中移除该物种，不会删除照片或其他物种。确定继续吗？")) {
        await Yuhen.api(`/api/observations/${removeEntry.dataset.observationId}/species/${removeEntry.dataset.v2RemoveSpeciesEntry}`, { method: "DELETE" });
        state.observations = await Yuhen.api("/api/observations");
        populateObservationFilters();
        renderObservations();
        openObservation(Number(removeEntry.dataset.observationId));
      }
    });
    const requested = new URLSearchParams(location.search).get("observation"); if (requested) openObservation(Number(requested));
  }

  function locationCard(item) {
    return `<button class="v2-region-card" data-v2-location="${item.id}"><span class="v2-region-photo">${item.cover_url ? `<img src="${esc(item.cover_url)}" alt="${esc(item.name)}" loading="lazy" />` : "<i>⌖</i>"}<b>${esc(item.catalog_number)}</b></span><span class="v2-region-copy"><small>${esc(locationTypes[item.location_type] || item.location_type)}</small><strong>${esc(item.name)}</strong><em>${esc(item.admin1_name)} · ${esc(item.city || item.district || "")}</em><span class="v2-card-stat-grid">${detailStat(item.species_count, "物种")}${detailStat(item.observation_count, "记录")}${detailStat(item.visit_day_count, "到访日")}</span></span></button>`;
  }
  function renderLocations() {
    const query = byId("v2-location-search").value.trim().toLocaleLowerCase(); const type = byId("v2-location-type").value;
    const filtered = state.locations.filter((item) => `${item.name} ${item.country_name} ${item.admin1_name} ${item.city || ""} ${item.district || ""}`.toLocaleLowerCase().includes(query) && (!type || item.location_type === type));
    byId("v2-location-count").textContent = filtered.length === state.locations.length ? state.locations.length : `${filtered.length}/${state.locations.length}`;
    byId("v2-location-grid").innerHTML = filtered.map(locationCard).join(""); byId("v2-location-empty").hidden = filtered.length !== 0;
    document.querySelectorAll("[data-v2-location]").forEach((card) => card.addEventListener("click", () => openLocation(Number(card.dataset.v2Location))));
  }
  async function openLocation(id) {
    const dialog = byId("v2-location-dialog"); if (!dialog.open) dialog.showModal(); byId("v2-location-detail").innerHTML = "<p class=\"v2-loading v2-dossier-loading\">正在调取区域档案…</p>";
    try {
      const item = await Yuhen.api(`/api/locations/${id}`); const max = Math.max(1, ...item.monthly_activity.map((entry) => entry.visit_day_count));
      const observations = [...item.observations].reverse().slice(0, 8);
      const moreObservations = item.observations.length ? `<a class="v2-detail-evidence v2-evidence-more" href="/observations?location=${item.id}"><span><strong>查看更多</strong><small>检视该区域全部 ${item.observation_count} 笔记录 →</small></span></a>` : "";
      const trips = item.trips.length ? item.trips.map((trip) => `<a class="v2-location-trip" href="/trips?trip=${trip.id}"><small>${esc(trip.catalog_number)}${trip.is_primary_location ? " · 主要地点" : " · 途经地点"}</small><strong>${esc(trip.name)}</strong><span>${dateTime(trip.started_at)} — ${dateTime(trip.ended_at)}</span><em>${trip.observation_count} 笔观察</em></a>`).join("") : "<p class=\"v2-detail-empty\">尚未关联远征记录。</p>";
      byId("v2-location-detail").innerHTML = `<section class="v2-archive-detail-hero"><div class="v2-archive-cover">${item.cover_url ? `<img src="${esc(item.cover_url.replace("thumbnail=true", "thumbnail=false"))}" alt="${esc(item.name)}" />` : "<i>⌖</i>"}</div><div class="v2-archive-hero-copy"><p class="v2-kicker">区域档案 · ${esc(item.catalog_number)}</p><h2>${esc(item.name)}</h2><em>${esc(locationTypes[item.location_type] || item.location_type)} · ${esc(item.admin1_name)} ${esc(item.city || "")} ${esc(item.district || "")}</em><div class="v2-hero-stat-grid">${detailStat(item.species_count, "记录物种")}${detailStat(item.observation_count, "观察记录")}${detailStat(item.visit_day_count, "到访日")}${detailStat(item.trip_count, "远征")}</div><p>中心坐标 ${item.center_latitude}, ${item.center_longitude}</p><div class="v2-detail-actions"><button class="v2-button v2-button-primary" type="button" data-v2-edit-location="${item.id}">修改区域</button><button class="v2-button v2-button-ghost" type="button" data-v2-location-cover="${item.id}">${item.cover_source === "custom" ? "更换封面" : "上传封面"}</button><button class="v2-button v2-button-ghost" type="button" data-v2-link-location="${item.id}">关联观察</button></div></div></section><section class="v2-archive-detail-paper"><article><p class="v2-kicker">区域手记</p><h3>地点简介</h3><p class="v2-long-copy">${esc(item.notes || "尚未填写地点简介。")}</p></article><article><p class="v2-kicker">到访频率</p><h3>时间轨迹</h3><div class="v2-month-bars">${item.monthly_activity.map((entry) => `<div><span>${monthLabel(entry.month)}</span><i><b style="width:${entry.visit_day_count / max * 100}%"></b></i><small>${entry.visit_day_count} 到访日 · ${entry.observation_count} 条记录</small></div>`).join("") || "<p>暂无记录</p>"}</div></article><article><p class="v2-kicker">区域物种</p><h3>已经确认的飞羽</h3><div class="v2-mini-species-grid">${speciesTiles(item.species)}</div></article><article><p class="v2-kicker">远征记录</p><h3>与本区域关联的远征</h3><div class="v2-location-trip-list">${trips}</div></article><article class="v2-location-observations"><p class="v2-kicker">照片凭证</p><h3>区域观察记录</h3><div class="v2-detail-evidence-grid">${evidenceTiles(observations)}${moreObservations}</div></article></section><section class="v2-archive-danger-zone"><div><p class="v2-kicker">档案管理</p><span>删除区域只会解除其中观察记录的关联，不会删除观察记录本身。</span></div><button class="v2-button v2-button-danger" type="button" data-v2-delete-location="${item.id}">删除区域</button></section>`;
      const coordinateText = byId("v2-location-detail").querySelector(".v2-archive-hero-copy > p:last-of-type");
      if (coordinateText) coordinateText.append(` · ${item.coordinate_system === "gcj02" ? "GCJ-02" : "WGS-84"}`);
      const observationSection = byId("v2-location-detail").querySelector(".v2-location-observations");
      const tripSection = observationSection?.previousElementSibling;
      if (observationSection && tripSection) {
        const recordColumn = document.createElement("div");
        recordColumn.className = "v2-location-record-column";
        tripSection.before(recordColumn);
        recordColumn.append(tripSection, observationSection);
      }
    } catch (error) { byId("v2-location-detail").innerHTML = `<p class="v2-loading v2-dossier-loading">${esc(error.message)}</p>`; }
  }
  async function loadLocations() {
    state.locations = await Yuhen.api("/api/locations");
    byId("v2-location-type").innerHTML = `<option value="">全部类型</option>${Object.entries(locationTypes).map(([value, label]) => `<option value="${value}">${label}</option>`).join("")}`; renderLocations();
    byId("v2-location-search").addEventListener("input", renderLocations); byId("v2-location-type").addEventListener("change", renderLocations);
    byId("v2-location-reset").addEventListener("click", () => { byId("v2-location-search").value = ""; byId("v2-location-type").value = ""; renderLocations(); }); wireDialog(byId("v2-location-dialog"));
    byId("v2-location-dialog").addEventListener("click", async (event) => {
      const editor = window.YuhenLocationEditor;
      const edit = event.target.closest("[data-v2-edit-location]"); if (edit && editor) { await editor.editLocation(Number(edit.dataset.v2EditLocation)); return; }
      const cover = event.target.closest("[data-v2-location-cover]"); if (cover && editor) { editor.uploadCover(Number(cover.dataset.v2LocationCover)); return; }
      const link = event.target.closest("[data-v2-link-location]"); if (link && editor) { editor.openLocationLink(Number(link.dataset.v2LinkLocation)); return; }
      const remove = event.target.closest("[data-v2-delete-location]");
      if (remove && confirm("删除区域只会解除观察关联，不会删除任何观察记录。确定删除吗？")) { await Yuhen.api(`/api/locations/${remove.dataset.v2DeleteLocation}`, { method: "DELETE" }); window.location.href = "/locations"; }
    });
    const requested = new URLSearchParams(location.search).get("location"); if (requested) openLocation(Number(requested));
  }

  function tripCard(item) {
    return `<button class="v2-expedition-card" data-v2-trip="${item.id}"><span class="v2-expedition-photo">${item.cover_url ? `<img src="${esc(item.cover_url)}" alt="" loading="lazy" />` : "<i>⌁</i>"}<b>${esc(item.catalog_number)}</b></span><span class="v2-expedition-copy"><small>${esc(item.location.name)}</small><strong>${esc(item.name)}</strong><em>${dateTime(item.started_at)} — ${dateTime(item.ended_at)}</em><p>${esc(item.notes || "本次远征没有附加备注。")}</p><span class="v2-card-stat-grid">${detailStat(item.species_count, "种")}${detailStat(item.genus_count, "属")}${detailStat(item.family_count, "科")}${detailStat(item.observation_count, "记录")}</span></span></button>`;
  }
  function populateTripFilters() {
    fillSelect(byId("v2-trip-year"), [...new Set(state.trips.map((item) => item.started_at.slice(0, 4)))].sort(), "全部年份", (value) => `${value}年`); populateTripMonths();
    const locations = new Map(); state.trips.forEach((item) => (item.locations || [item.location]).forEach((location) => locations.set(String(location.id), location.name))); const select = byId("v2-trip-location"); select.innerHTML = `<option value="">全部区域</option>${[...locations].map(([id, name]) => `<option value="${id}">${esc(name)}</option>`).join("")}`;
  }
  function populateTripMonths() { const year = byId("v2-trip-year").value; fillSelect(byId("v2-trip-month"), [...new Set(state.trips.filter((item) => !year || item.started_at.startsWith(`${year}-`)).map((item) => item.started_at.slice(5, 7)))].sort(), "全部月份", (value) => `${Number(value)}月`); }
  function renderTrips() {
    const year = byId("v2-trip-year").value; const month = byId("v2-trip-month").value; const locationId = byId("v2-trip-location").value; const direction = byId("v2-trip-sort").value === "desc" ? -1 : 1;
    const filtered = state.trips.filter((item) => (!year || item.started_at.slice(0, 4) === year) && (!month || item.started_at.slice(5, 7) === month) && (!locationId || (item.locations || [item.location]).some((location) => String(location.id) === locationId))).sort((a, b) => a.started_at.localeCompare(b.started_at) * direction);
    const groups = new Map(); filtered.forEach((item) => { const key = item.started_at.slice(0, 7); if (!groups.has(key)) groups.set(key, []); groups.get(key).push(item); });
    byId("v2-trip-count").textContent = filtered.length === state.trips.length ? state.trips.length : `${filtered.length}/${state.trips.length}`;
    byId("v2-trip-groups").innerHTML = [...groups].map(([key, items]) => `<section class="v2-month-section"><header><div><span>${key.slice(0, 4)}</span><h3>${Number(key.slice(5, 7))}月远征卷宗</h3></div><b>${items.length} 卷</b></header><div class="v2-expedition-grid">${items.map(tripCard).join("")}</div></section>`).join(""); byId("v2-trip-empty").hidden = filtered.length !== 0;
    document.querySelectorAll("[data-v2-trip]").forEach((card) => card.addEventListener("click", () => openTrip(Number(card.dataset.v2Trip))));
  }
  async function openTrip(id) {
    const dialog = byId("v2-trip-dialog"); if (!dialog.open) dialog.showModal(); byId("v2-trip-detail").innerHTML = "<p class=\"v2-loading v2-dossier-loading\">正在调取远征卷宗…</p>";
    try {
      const item = await Yuhen.api(`/api/trips/${id}`);
      const allObservations = item.observations;
      state.activeTripId = item.id;
      state.tripCoverChoices = allObservations;
      item.observations = [...allObservations].reverse().slice(0, 8);
      item.observations.moreHref = allObservations.length ? `/observations?trip=${item.id}` : null;
      item.observations.totalCount = allObservations.length;
      const route = (item.locations || [item.location]).map((location) => `<a class="v2-trip-route-stop" href="/locations?location=${location.id}"><b>${String(location.visit_order || 1).padStart(2, "0")}</b><span>${esc(location.name)}</span>${location.is_primary ? "<small>主要地点</small>" : ""}</a>`).join("");
      byId("v2-trip-detail").innerHTML = `<section class="v2-archive-detail-hero"><div class="v2-archive-cover">${item.cover_url ? `<img src="${esc(item.cover_url.replace("thumbnail=true", "thumbnail=false"))}" alt="" />` : "<i>⌁</i>"}</div><div class="v2-archive-hero-copy"><p class="v2-kicker">远征日志 · ${esc(item.catalog_number)}</p><h2>${esc(item.name)}</h2><em>${esc(item.location.name)} · ${dateTime(item.started_at)} — ${dateTime(item.ended_at)}</em><div class="v2-hero-stat-grid">${detailStat(item.species_count, "种")}${detailStat(item.location_count, "地点")}${detailStat(item.observation_count, "记录")}${detailStat(durationLabel(item.duration_minutes), "持续")}</div><div class="v2-detail-actions"><button class="v2-button v2-button-primary" type="button" data-v2-edit-trip="${item.id}">修改远征</button><button class="v2-button v2-button-ghost" type="button" data-v2-link-trip="${item.id}">关联观察</button><button class="v2-button v2-button-ghost" type="button" data-v2-edit-trip-observations="${item.id}">编辑观察</button></div></div></section><section class="v2-trip-route"><p class="v2-kicker">行程路线</p><h3>本次远征到访地点</h3><div>${route}</div></section><section class="v2-archive-detail-paper"><article><p class="v2-kicker">远征手记</p><h3>行程备注</h3><p class="v2-long-copy">${esc(item.notes || "本次远征没有附加备注。")}</p></article><article><p class="v2-kicker">物种成果</p><h3>本次确认的飞羽</h3><div class="v2-mini-species-grid">${speciesTiles(item.species)}</div></article><article><p class="v2-kicker">田野凭证</p><h3>本次远征记录</h3><div class="v2-detail-evidence-grid">${tripEvidenceTiles(item.observations)}</div></article></section><section class="v2-archive-danger-zone"><div><p class="v2-kicker">档案管理</p><span>删除远征只会解除其中观察记录的关联，不会删除观察记录本身。</span></div><div class="v2-archive-danger-actions"><button class="v2-button v2-button-ghost" type="button" data-v2-change-trip-cover="${item.id}" ${allObservations.length ? "" : "disabled"}>更换封面</button><button class="v2-button v2-button-danger" type="button" data-v2-delete-trip="${item.id}">删除远征</button></div></section>`;
      const detailPaper = byId("v2-trip-detail").querySelector(".v2-archive-detail-paper");
      const routeSection = byId("v2-trip-detail").querySelector(".v2-trip-route");
      const sections = detailPaper ? [...detailPaper.children] : [];
      if (detailPaper && routeSection && sections.length >= 3) {
        const leftColumn = document.createElement("div");
        const rightColumn = document.createElement("div");
        leftColumn.className = "v2-trip-detail-column v2-trip-detail-left";
        rightColumn.className = "v2-trip-detail-column v2-trip-detail-right";
        detailPaper.append(leftColumn, rightColumn);
        leftColumn.append(sections[0], sections[1]);
        rightColumn.append(routeSection, sections[2]);
      }
    } catch (error) { byId("v2-trip-detail").innerHTML = `<p class="v2-loading v2-dossier-loading">${esc(error.message)}</p>`; }
  }
  async function loadTrips() {
    state.trips = await Yuhen.api("/api/trips"); populateTripFilters(); renderTrips();
    byId("v2-trip-year").addEventListener("change", () => { populateTripMonths(); renderTrips(); }); ["v2-trip-month", "v2-trip-location", "v2-trip-sort"].forEach((id) => byId(id).addEventListener("change", renderTrips));
    byId("v2-trip-reset").addEventListener("click", () => { ["v2-trip-year", "v2-trip-month", "v2-trip-location"].forEach((id) => { byId(id).value = ""; }); byId("v2-trip-sort").value = "asc"; populateTripMonths(); renderTrips(); }); wireDialog(byId("v2-trip-dialog"));
    byId("v2-trip-dialog").addEventListener("click", async (event) => {
      const editor = window.YuhenTripEditor;
      const edit = event.target.closest("[data-v2-edit-trip]"); if (edit && editor) { await editor.editTrip(Number(edit.dataset.v2EditTrip)); return; }
      const link = event.target.closest("[data-v2-link-trip]"); if (link && editor) { await editor.linkTrip(Number(link.dataset.v2LinkTrip)); return; }
      const editObservations = event.target.closest("[data-v2-edit-trip-observations]"); if (editObservations && editor) { await editor.editObservations(Number(editObservations.dataset.v2EditTripObservations)); return; }
      const changeCover = event.target.closest("[data-v2-change-trip-cover]"); if (changeCover) { const item = await Yuhen.api(`/api/trips/${changeCover.dataset.v2ChangeTripCover}`); openTripCoverPicker(item); return; }
      const remove = event.target.closest("[data-v2-delete-trip]"); if (remove && confirm("删除远征只会解除观察关联，不会删除任何观察记录。确定删除吗？")) { await Yuhen.api(`/api/trips/${remove.dataset.v2DeleteTrip}`, { method: "DELETE" }); window.location.href = "/trips"; }
    });
    const coverDialog = byId("v2-trip-cover-dialog"); wireDialog(coverDialog);
    byId("v2-trip-cover-grid").addEventListener("click", async (event) => {
      const choice = event.target.closest("[data-v2-trip-cover-choice]"); if (!choice || choice.disabled) return;
      byId("v2-trip-cover-status").textContent = "正在更换远征封面……";
      try {
        await Yuhen.api(`/api/trips/${state.activeTripId}/cover`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_id: Number(choice.dataset.v2TripCoverChoice) }) });
        coverDialog.close(); state.trips = await Yuhen.api("/api/trips"); populateTripFilters(); renderTrips(); await openTrip(state.activeTripId);
      } catch (error) { byId("v2-trip-cover-status").textContent = error.message; }
    });
    const requested = new URLSearchParams(location.search).get("trip"); if (requested) openTrip(Number(requested));
  }

  if (page === "observations") {
    document.addEventListener("feather:apply-observation-search", (event) => {
      const filters = event.detail || {};
      const year = filters.year ? String(filters.year) : "";
      if (year && ![...byId("v2-observation-year").options].some((option) => option.value === year)) {
        byId("v2-observation-year").add(new Option(`${year}年`, year));
      }
      byId("v2-observation-year").value = year;
      populateObservationMonths();
      const month = filters.month ? String(filters.month).padStart(2, "0") : "";
      if (month && ![...byId("v2-observation-month").options].some((option) => option.value === month)) {
        byId("v2-observation-month").add(new Option(`${Number(month)}月`, month));
      }
      byId("v2-observation-month").value = month;
      const locationId = filters.location_id ? String(filters.location_id) : "";
      if (locationId && ![...byId("v2-observation-location").options].some((option) => option.value === locationId)) {
        byId("v2-observation-location").add(new Option(filters.location_name || `地点 ${locationId}`, locationId));
      }
      byId("v2-observation-location").value = locationId;
      if (filters.sort) byId("v2-observation-sort").value = filters.sort;
      state.observationSpeciesId = filters.species_id || null;
      state.observationTripId = filters.trip_id || null;
      state.observationMultiSpeciesOnly = filters.multi_species_only === true;
      renderObservations();
    });
  }

  async function start() {
    try {
      if (page === "observations") await loadObservations();
      if (page === "locations") await loadLocations();
      if (page === "trips") await loadTrips();
    } catch (error) {
      const target = document.querySelector(".v2-archive-content .v2-loading"); if (target) target.textContent = error.message;
    }
  }
  start();
}());
