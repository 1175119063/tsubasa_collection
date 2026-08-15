const state = { species: [], observations: [], taxonomy: [], locations: [] };
const byId = (id) => document.getElementById(id);
const form = byId("record-form");
const recordDialog = byId("record-dialog");
const observationDetailDialog = byId("observation-detail-dialog");

async function loadPage() {
  const [species, observations, taxonomy, locations] = await Promise.all([
    Yuhen.api("/api/species"),
    Yuhen.api("/api/observations"),
    Yuhen.api("/api/taxonomy/tree"),
    Yuhen.api("/api/locations"),
  ]);
  state.species = species;
  state.observations = observations;
  state.taxonomy = taxonomy;
  state.locations = locations;
  populateSpeciesSelect();
  populateTaxonomySelectors();
  populateLocationSelectors();
  populateTimeFilters();
  renderObservations();
}

function populateLocationSelectors() {
  const options = state.locations.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.name)} · ${Yuhen.escapeHtml(item.admin1_name)}</option>`
  ).join("");
  const recordSelect = byId("location-select");
  const currentRecord = recordSelect.value;
  recordSelect.innerHTML = `<option value="">暂不关联地点</option>${options}`;
  if ([...recordSelect.options].some((item) => item.value === currentRecord)) {
    recordSelect.value = currentRecord;
  }
  const filterSelect = byId("observation-location-filter");
  const currentFilter = filterSelect.value;
  filterSelect.innerHTML = `<option value="">全部地点</option><option value="unlinked">未关联地点</option>${options}`;
  if ([...filterSelect.options].some((item) => item.value === currentFilter)) {
    filterSelect.value = currentFilter;
  }
}

function populateTimeFilters() {
  const yearSelect = byId("observation-year-filter");
  const previousYear = yearSelect.value;
  const years = [...new Set(state.observations.map((item) => item.observed_at.slice(0, 4)))].sort();
  yearSelect.innerHTML = `<option value="">全部年份</option>${years.map((year) =>
    `<option value="${year}">${year} 年</option>`
  ).join("")}`;
  if (years.includes(previousYear)) yearSelect.value = previousYear;
  populateMonthFilter();
}

function populateMonthFilter() {
  const year = byId("observation-year-filter").value;
  const monthSelect = byId("observation-month-filter");
  const previousMonth = monthSelect.value;
  const months = [...new Set(state.observations
    .filter((item) => !year || item.observed_at.startsWith(`${year}-`))
    .map((item) => item.observed_at.slice(5, 7)))].sort();
  monthSelect.innerHTML = `<option value="">全部月份</option>${months.map((month) =>
    `<option value="${month}">${Number(month)} 月</option>`
  ).join("")}`;
  if (months.includes(previousMonth)) monthSelect.value = previousMonth;
}

function observationMatchesTime(item) {
  const year = byId("observation-year-filter").value;
  const month = byId("observation-month-filter").value;
  const location = byId("observation-location-filter").value;
  const locationMatches = !location
    || (location === "unlinked" ? !item.location : String(item.location?.id) === location);
  return (!year || item.observed_at.slice(0, 4) === year)
    && (!month || item.observed_at.slice(5, 7) === month) && locationMatches;
}

function renderObservations() {
  const direction = byId("observation-sort-order").value === "desc" ? -1 : 1;
  const filtered = state.observations
    .filter(observationMatchesTime)
    .sort((left, right) => left.observed_at.localeCompare(right.observed_at) * direction);
  const groups = new Map();
  for (const item of filtered) {
    const monthKey = item.observed_at.slice(0, 7);
    if (!groups.has(monthKey)) groups.set(monthKey, []);
    groups.get(monthKey).push(item);
  }

  byId("record-total").textContent = filtered.length === state.observations.length
    ? `${state.observations.length} 笔记录`
    : `显示 ${filtered.length} / ${state.observations.length} 笔记录`;
  const empty = byId("observation-empty");
  empty.hidden = filtered.length !== 0;
  empty.textContent = state.observations.length ? "当前时间条件下没有观察记录。" : "尚无观察记录。";
  byId("observation-groups").innerHTML = [...groups.entries()].map(([monthKey, items]) => `
    <section class="observation-month-group">
      <header class="month-heading">
        <h2>${monthKey.slice(0, 4)}年${Number(monthKey.slice(5, 7))}月</h2>
        <span>${items.length} 笔</span>
      </header>
      <div class="record-grid record-grid-large">${items.map((item) => `
    <button type="button" class="record-tile" data-observation-id="${item.id}">
      <img src="${item.thumbnail_url}" alt="${Yuhen.escapeHtml(item.species_name)}" loading="lazy" />
      <span class="record-tile-body">
        <strong>${Yuhen.escapeHtml(item.species_name)}</strong>
        <span>${Yuhen.escapeHtml(item.observed_at.replace("T", " "))}</span>
        <span>${Yuhen.escapeHtml(item.admin1_name)} · ${Yuhen.escapeHtml(item.locality)}</span>
        ${item.location ? `<span>地点档案 · ${Yuhen.escapeHtml(item.location.name)}</span>` : ""}
        <span>${Yuhen.labels[item.season] || Yuhen.escapeHtml(item.season)} · ${item.photo_type === "group" ? "群体" : "个体"}</span>
      </span>
    </button>`).join("")}</div>
    </section>`).join("");
}

function valueLabel(value, emptyLabel = "未知") {
  return value ? (Yuhen.labels[value] || value) : emptyLabel;
}

function openObservationDetail(observationId) {
  const item = state.observations.find((value) => value.id === Number(observationId));
  if (!item) return;
  const individual = item.photo_type === "individual";
  const subspecies = item.subspecies
    ? `${item.subspecies.chinese_name ? `${item.subspecies.chinese_name} · ` : ""}${item.subspecies.scientific_name}`
    : "未知 / 无亚种";
  const audio = item.audio.length
    ? item.audio.map((entry, index) => `<div class="preview-audio"><span>录音 ${index + 1}</span><audio controls preload="metadata" src="${entry.url}"></audio></div>`).join("")
    : `<span class="preview-empty">没有附带录音</span>`;
  byId("observation-detail-content").innerHTML = `
    <article class="observation-preview-layout">
      <div class="observation-preview-photo"><img src="${item.photo_url}" alt="${Yuhen.escapeHtml(item.species_name)}" /></div>
      <div class="observation-preview-info">
        <p class="eyebrow">${Yuhen.escapeHtml(item.catalog_number)} · OBSERVATION ${item.id}</p>
        <h2>${Yuhen.escapeHtml(item.species_name)}</h2>
        <p class="latin">${Yuhen.escapeHtml(item.species_scientific_name)}</p>
        <dl class="observation-facts">
          <div><dt>拍摄时间</dt><dd>${Yuhen.escapeHtml(item.observed_at.replace("T", " "))}</dd></div>
          <div><dt>拍摄地点</dt><dd>${Yuhen.escapeHtml(item.country_name)} · ${Yuhen.escapeHtml(item.admin1_name)} · ${Yuhen.escapeHtml(item.locality)}</dd></div>
          <div><dt>地点档案</dt><dd>${item.location ? `<a href="/locations?location=${item.location.id}">${Yuhen.escapeHtml(item.location.name)}</a>` : "未关联"}</dd></div>
          <div><dt>所属行程</dt><dd>${item.trip ? `<a href="/trips?trip=${item.trip.id}">${Yuhen.escapeHtml(item.trip.catalog_number)} · ${Yuhen.escapeHtml(item.trip.location_name)}</a>` : "未关联"}</dd></div>
          <div><dt>经纬度</dt><dd>${item.latitude}, ${item.longitude}</dd></div>
          <div><dt>季节</dt><dd>${Yuhen.escapeHtml(valueLabel(item.season))}</dd></div>
          <div><dt>照片类型</dt><dd>${individual ? "个体照片" : "群体照片"}</dd></div>
          ${individual ? `<div><dt>性别</dt><dd>${Yuhen.escapeHtml(valueLabel(item.sex))}</dd></div>
          <div><dt>生命阶段</dt><dd>${Yuhen.escapeHtml(valueLabel(item.life_stage))}</dd></div>
          <div><dt>亚种</dt><dd>${Yuhen.escapeHtml(subspecies)}</dd></div>` : ""}
        </dl>
        <section class="preview-notes"><h3>备注</h3><p>${Yuhen.escapeHtml(item.notes || "无备注")}</p></section>
        <section class="preview-audio-list"><h3>录音</h3>${audio}</section>
        <div class="preview-primary-actions">
          <button type="button" class="primary-button" data-edit-observation="${item.id}">修改记录</button>
          <a class="secondary-button button-link" href="/dex?species=${item.species_id}">查看该物种图鉴</a>
        </div>
        <div id="observation-edit-container"></div>
      </div>
    </article>`;
  if (!observationDetailDialog.open) observationDetailDialog.showModal();
}

function enumOptions(values, selected) {
  return values.map((value) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${Yuhen.escapeHtml(valueLabel(value))}</option>`
  ).join("");
}

async function showObservationEditor(observationId) {
  const item = state.observations.find((value) => value.id === Number(observationId));
  if (!item) return;
  const individual = item.photo_type === "individual";
  const speciesDetail = individual ? await Yuhen.api(`/api/species/${item.species_id}`) : null;
  const subspeciesOptions = speciesDetail
    ? speciesDetail.subspecies.map((entry) => {
      const selected = item.subspecies?.id === entry.id ? "selected" : "";
      const label = `${entry.chinese_name ? `${entry.chinese_name} · ` : ""}${entry.scientific_name}`;
      return `<option value="${entry.id}" ${selected}>${Yuhen.escapeHtml(label)}</option>`;
    }).join("")
    : "";
  const container = byId("observation-edit-container");
  container.innerHTML = `
    <form id="observation-edit-form" class="observation-edit-form">
      <header><h3>修改观察记录</h3><span>物种、照片、时间与地点不可修改</span></header>
      ${individual ? `<div class="observation-edit-grid">
        <label>性别<select name="sex">${enumOptions(["unknown", "male", "female"], item.sex)}</select></label>
        <label>生命阶段<select name="life_stage">${enumOptions(["unknown", "egg", "chick", "subadult", "adult"], item.life_stage)}</select></label>
        <label class="full-field">亚种<select name="subspecies_id"><option value="">未知 / 无亚种</option>${subspeciesOptions}</select></label>
      </div>` : `<p class="field-hint">这是群体照片，只能修改备注。</p>`}
      <label>备注<textarea name="notes" rows="4">${Yuhen.escapeHtml(item.notes || "")}</textarea></label>
      <div class="observation-edit-actions">
        <span id="observation-edit-status" role="status"></span>
        <button type="button" class="secondary-button" data-cancel-observation-edit>取消</button>
        <button type="submit" class="primary-button">保存修改</button>
      </div>
    </form>`;

  const editForm = byId("observation-edit-form");
  editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = new FormData(editForm);
    const status = byId("observation-edit-status");
    const submit = editForm.querySelector("button[type=submit]");
    submit.disabled = true;
    status.textContent = "正在保存…";
    try {
      const payload = {
        sex: individual ? data.get("sex") : null,
        life_stage: individual ? data.get("life_stage") : null,
        subspecies_id: individual && data.get("subspecies_id")
          ? Number(data.get("subspecies_id"))
          : null,
        notes: data.get("notes") || null,
      };
      const updated = await Yuhen.api(`/api/observations/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const index = state.observations.findIndex((value) => value.id === item.id);
      state.observations[index] = updated;
      renderObservations();
      openObservationDetail(item.id);
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
    }
  });
}

function populateSpeciesSelect() {
  const select = byId("species-select");
  const current = select.value;
  select.innerHTML = `<option value="new">＋ 建立新物种</option>${state.species.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.catalog_number)} · ${Yuhen.escapeHtml(item.chinese_name)}</option>`
  ).join("")}`;
  if ([...select.options].some((option) => option.value === current)) select.value = current;
  toggleSpeciesMode();
}

function optionMarkup(items) {
  return items.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.chinese_name)} · ${Yuhen.escapeHtml(item.scientific_name)}</option>`
  ).join("");
}

function selectedOrder() {
  return state.taxonomy.find((item) => String(item.id) === byId("order-node-select").value) || null;
}

function selectedFamily() {
  return selectedOrder()?.families.find(
    (item) => String(item.id) === byId("family-node-select").value
  ) || null;
}

function selectedGenus() {
  return selectedFamily()?.genera.find(
    (item) => String(item.id) === byId("genus-node-select").value
  ) || null;
}

function populateTaxonomySelectors() {
  const select = byId("order-node-select");
  const previous = select.value;
  select.innerHTML = `<option value="new">＋ 新增目</option>${optionMarkup(state.taxonomy)}`;
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  updateFamilyOptions();
}

function updateFamilyOptions() {
  const select = byId("family-node-select");
  const previous = select.value;
  const families = selectedOrder()?.families || [];
  select.innerHTML = `<option value="new">＋ 在当前目下新增科</option>${optionMarkup(families)}`;
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  updateGenusOptions();
}

function updateGenusOptions() {
  const select = byId("genus-node-select");
  const previous = select.value;
  const genera = selectedFamily()?.genera || [];
  select.innerHTML = `<option value="new">＋ 在当前科下新增属</option>${optionMarkup(genera)}`;
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  syncTaxonomyFields();
}

function setRequired(containerId, required) {
  byId(containerId).querySelectorAll("input, select, textarea").forEach((field) => {
    field.required = required;
  });
}

function syncTaxonomyFields() {
  const isNewSpecies = byId("species-select").value === "new";
  for (const level of ["order", "family", "genus"]) {
    const show = isNewSpecies && byId(`${level}-node-select`).value === "new";
    byId(`${level}-new-fields`).hidden = !show;
    setRequired(`${level}-new-fields`, show);
  }
  for (const name of ["species_chinese", "species_scientific", "iucn_status"]) {
    form.elements[name].required = isNewSpecies;
  }
}

async function toggleSpeciesMode() {
  const isNew = byId("species-select").value === "new";
  byId("new-species-fields").hidden = !isNew;
  syncTaxonomyFields();
  toggleHasSubspecies();
  await populateSubspecies();
}

function parseSubspecies() {
  const text = form.elements.subspecies_list?.value || "";
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line) => {
    const [scientific_name, chinese_name] = line.split("|").map((part) => part.trim());
    return { scientific_name, chinese_name: chinese_name || null };
  });
}

async function populateSubspecies() {
  const select = byId("subspecies-select");
  select.innerHTML = `<option value="">未知 / 无亚种</option>`;
  const speciesId = byId("species-select").value;
  if (speciesId === "new") {
    parseSubspecies().forEach((item) => select.add(new Option(
      `${item.chinese_name ? `${item.chinese_name} · ` : ""}${item.scientific_name}`,
      item.scientific_name,
    )));
  } else if (speciesId) {
    const detail = await Yuhen.api(`/api/species/${speciesId}`);
    detail.subspecies.forEach((item) => select.add(new Option(
      `${item.chinese_name ? `${item.chinese_name} · ` : ""}${item.scientific_name}`,
      item.id,
    )));
  }
}

function toggleHasSubspecies() {
  const show = byId("species-select").value === "new" && byId("has-subspecies").checked;
  byId("subspecies-list-field").hidden = !show;
  form.elements.subspecies_list.required = show;
  populateSubspecies();
}

function togglePhotoType() {
  const individual = byId("photo-type").value === "individual";
  document.querySelectorAll(".individual-field").forEach((field) => field.hidden = !individual);
}

function taxonPayload(level, data) {
  const selected = level === "order" ? selectedOrder() : level === "family" ? selectedFamily() : selectedGenus();
  if (selected) return { chinese_name: selected.chinese_name, scientific_name: selected.scientific_name };
  return {
    chinese_name: data.get(`${level}_chinese`),
    scientific_name: data.get(`${level}_scientific`),
  };
}

function buildPayload() {
  const data = new FormData(form);
  const isNew = byId("species-select").value === "new";
  const individual = data.get("photo_type") === "individual";
  return {
    payload: {
      species_id: isNew ? null : Number(byId("species-select").value),
      location_id: data.get("location_id") ? Number(data.get("location_id")) : null,
      new_species: isNew ? {
        order: taxonPayload("order", data), family: taxonPayload("family", data), genus: taxonPayload("genus", data),
        chinese_name: data.get("species_chinese"), scientific_name: data.get("species_scientific"),
        iucn_status: data.get("iucn_status"), china_protection_status: data.get("china_status") || null,
        has_subspecies: byId("has-subspecies").checked,
        subspecies: byId("has-subspecies").checked ? parseSubspecies() : [], notes: null,
      } : null,
      subspecies_id: !isNew && individual && data.get("subspecies") ? Number(data.get("subspecies")) : null,
      subspecies_scientific_name: isNew && individual && data.get("subspecies") ? data.get("subspecies") : null,
      photo_type: data.get("photo_type"), observed_at: data.get("observed_at"),
      latitude: Number(data.get("latitude")), longitude: Number(data.get("longitude")),
      country_code: data.get("country_code"), country_name: data.get("country_name"),
      admin1_code: data.get("admin1_code"), admin1_name: data.get("admin1_name"),
      locality: data.get("locality"), season: data.get("season"), season_note: null,
      sex: individual ? data.get("sex") : null, life_stage: individual ? data.get("life_stage") : null,
      notes: data.get("notes") || null,
    },
    files: data,
  };
}

function openRecord() {
  form.reset();
  populateSpeciesSelect();
  populateTaxonomySelectors();
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  byId("observed-at").value = now.toISOString().slice(0, 16);
  byId("form-status").textContent = "";
  byId("photo-metadata-status").textContent = "选择照片后将自动读取 EXIF 拍摄时间。";
  toggleSpeciesMode();
  toggleHasSubspecies();
  togglePhotoType();
  recordDialog.showModal();
}

async function readPhotoTime(file) {
  const status = byId("photo-metadata-status");
  status.textContent = "正在读取 EXIF 拍摄时间…";
  const body = new FormData();
  body.append("photo", file);
  try {
    const result = await Yuhen.api("/api/media/exif-time", { method: "POST", body });
    if (byId("photo-input").files[0] !== file) return;
    if (result.observed_at) {
      byId("observed-at").value = result.observed_at;
      status.textContent = `已从照片读取拍摄时间：${result.observed_at.replace("T", " ")}`;
    } else {
      status.textContent = "照片中没有可用的 EXIF 拍摄时间，请手动填写。";
    }
  } catch (error) {
    status.textContent = error.message;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = byId("form-status");
  const submit = form.querySelector("button[type=submit]");
  submit.disabled = true;
  status.textContent = "正在校验并保存…";
  try {
    const { payload, files } = buildPayload();
    const body = new FormData();
    body.append("payload", JSON.stringify(payload));
    body.append("photo", files.get("photo"));
    for (const file of files.getAll("audio")) if (file.size) body.append("audio", file);
    const result = await Yuhen.api("/api/observations", { method: "POST", body });
    status.textContent = `${result.catalog_number} 已入藏`;
    await loadPage();
    setTimeout(() => recordDialog.close(), 650);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

byId("new-record-button").addEventListener("click", openRecord);
byId("observation-groups").addEventListener("click", (event) => {
  const card = event.target.closest("[data-observation-id]");
  if (card) openObservationDetail(card.dataset.observationId);
});
document.querySelectorAll("[data-close-observation-detail]").forEach((button) =>
  button.addEventListener("click", () => observationDetailDialog.close())
);
observationDetailDialog.addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-observation]");
  if (editButton) {
    editButton.disabled = true;
    try {
      await showObservationEditor(editButton.dataset.editObservation);
    } catch (error) {
      alert(error.message);
    } finally {
      if (editButton.isConnected) editButton.disabled = false;
    }
    return;
  }
  if (event.target.closest("[data-cancel-observation-edit]")) {
    byId("observation-edit-container").innerHTML = "";
  }
});
byId("observation-year-filter").addEventListener("change", () => {
  populateMonthFilter();
  renderObservations();
});
byId("observation-month-filter").addEventListener("change", renderObservations);
byId("observation-sort-order").addEventListener("change", renderObservations);
byId("observation-location-filter").addEventListener("change", renderObservations);
byId("observation-filter-reset").addEventListener("click", () => {
  byId("observation-year-filter").value = "";
  populateMonthFilter();
  byId("observation-month-filter").value = "";
  byId("observation-sort-order").value = "asc";
  byId("observation-location-filter").value = "";
  renderObservations();
});
document.querySelectorAll("[data-close-dialog]").forEach((button) =>
  button.addEventListener("click", () => recordDialog.close())
);
byId("species-select").addEventListener("change", toggleSpeciesMode);
byId("order-node-select").addEventListener("change", updateFamilyOptions);
byId("family-node-select").addEventListener("change", updateGenusOptions);
byId("genus-node-select").addEventListener("change", syncTaxonomyFields);
byId("has-subspecies").addEventListener("change", toggleHasSubspecies);
form.elements.subspecies_list.addEventListener("input", populateSubspecies);
byId("photo-type").addEventListener("change", togglePhotoType);
byId("location-select").addEventListener("change", (event) => {
  const location = state.locations.find((item) => String(item.id) === event.target.value);
  if (!location) return;
  form.elements.country_code.value = location.country_code;
  form.elements.country_name.value = location.country_name;
  form.elements.admin1_code.value = location.admin1_code;
  form.elements.admin1_name.value = location.admin1_name;
  form.elements.locality.value = location.name;
  if (!byId("latitude").value) byId("latitude").value = location.center_latitude;
  if (!byId("longitude").value) byId("longitude").value = location.center_longitude;
});
byId("photo-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (file) readPhotoTime(file);
});
byId("use-location").addEventListener("click", () => {
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => { byId("latitude").value = coords.latitude; byId("longitude").value = coords.longitude; },
    () => { byId("form-status").textContent = "无法读取设备位置，请手动填写经纬度"; },
  );
});

loadPage()
  .then(() => {
    const query = new URLSearchParams(window.location.search);
    if (query.get("new") === "1") openRecord();
    const observationId = Number(query.get("observation"));
    if (observationId) openObservationDetail(observationId);
  })
  .catch((error) => { byId("observation-empty").hidden = false; byId("observation-empty").textContent = error.message; });
