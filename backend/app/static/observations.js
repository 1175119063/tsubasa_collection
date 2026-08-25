const state = { species: [], observations: [], taxonomy: [], locations: [], additionalSpecies: [] };
const byId = (id) => document.getElementById(id);
const form = byId("record-form");
const recordDialog = byId("record-dialog");
const observationDetailDialog = byId("observation-detail-dialog");
const isV2Editor = document.body.classList.contains("v2-page");

function observationSpeciesEntries(item) {
  if (Array.isArray(item.species_entries) && item.species_entries.length) return item.species_entries;
  return [{ species_name: item.species_name || "未命名物种" }];
}

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
  populateAdditionalSpeciesSelect();
  populateTaxonomySelectors();
  populateLocationSelectors();
  populateTimeFilters();
  renderObservations();
}

function populateAdditionalSpeciesSelect() {
  const select = byId("additional-species-select");
  const primaryId = byId("species-select").value;
  const selectedIds = new Set(state.additionalSpecies.map((item) => String(item.id)));
  select.innerHTML = `<option value="">选择物种</option>${state.species
    .filter((item) => String(item.id) !== primaryId && !selectedIds.has(String(item.id)))
    .map((item) => `<option value="${item.id}">${Yuhen.escapeHtml(item.chinese_name)} · ${Yuhen.escapeHtml(item.scientific_name)}</option>`)
    .join("")}`;
}

function renderAdditionalSpecies() {
  const container = byId("additional-species-list");
  container.innerHTML = state.additionalSpecies.length ? state.additionalSpecies.map((item) => `
    <article class="additional-species-entry" data-additional-species="${item.id}">
      <header><span><strong>${Yuhen.escapeHtml(item.chinese_name)}</strong><small>${Yuhen.escapeHtml(item.scientific_name)}</small></span><button type="button" data-remove-additional-species="${item.id}">移除</button></header>
      <div class="form-grid">
        <label>照片类型<select data-additional-photo-type><option value="individual">个体照片</option><option value="group">群体照片</option></select></label>
        <label data-additional-individual>性别<select data-additional-sex><option value="unknown">未知</option><option value="male">雄性</option><option value="female">雌性</option></select></label>
        <label data-additional-individual>生命阶段<select data-additional-life-stage><option value="unknown">未知</option><option value="egg">卵</option><option value="chick">雏鸟</option><option value="subadult">亚成</option><option value="adult">成鸟</option></select></label>
        <label data-additional-individual>亚种<select data-additional-subspecies><option value="">未知 / 无亚种</option>${(item.subspecies || []).map((subspecies) => `<option value="${subspecies.id}">${Yuhen.escapeHtml(subspecies.chinese_name || subspecies.scientific_name)}</option>`).join("")}</select></label>
        <label class="full-field">该物种备注<textarea data-additional-notes rows="2" placeholder="例如：位于画面右侧、约五只"></textarea></label>
      </div>
    </article>`).join("") : '<p class="field-hint">尚未添加其他物种。</p>';
  populateAdditionalSpeciesSelect();
}

async function addAdditionalSpecies() {
  const speciesId = Number(byId("additional-species-select").value);
  if (!speciesId || state.additionalSpecies.length >= 9) return;
  const summary = state.species.find((item) => item.id === speciesId);
  const detail = await Yuhen.api(`/api/species/${speciesId}`);
  state.additionalSpecies.push({ ...summary, subspecies: detail.subspecies });
  renderAdditionalSpecies();
}

function additionalSpeciesPayload() {
  return [...byId("additional-species-list").querySelectorAll("[data-additional-species]")].map((row) => {
    const individual = row.querySelector("[data-additional-photo-type]").value === "individual";
    return {
      species_id: Number(row.dataset.additionalSpecies),
      photo_type: individual ? "individual" : "group",
      sex: individual ? row.querySelector("[data-additional-sex]").value : null,
      life_stage: individual ? row.querySelector("[data-additional-life-stage]").value : null,
      subspecies_id: individual && row.querySelector("[data-additional-subspecies]").value ? Number(row.querySelector("[data-additional-subspecies]").value) : null,
      notes: row.querySelector("[data-additional-notes]").value || null,
    };
  });
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
  renderLocationSearchResults();
}

function matchingLocations(query) {
  return state.locations.filter((item) => [
    item.catalog_number, item.name, item.country_name, item.admin1_name, item.city, item.district,
  ].filter(Boolean).join(" ").toLocaleLowerCase().includes(query));
}

function renderLocationSearchResults() {
  const input = byId("location-search");
  const results = byId("location-search-results");
  const status = byId("location-search-status");
  const query = input.value.normalize("NFKC").trim().toLocaleLowerCase();
  if (!query) {
    results.hidden = true;
    results.innerHTML = "";
    status.textContent = `当前地点资料库共有 ${state.locations.length} 个地点`;
    return;
  }
  const matches = matchingLocations(query);
  results.innerHTML = matches.length ? matches.slice(0, 10).map((item) => `
    <button type="button" class="species-search-result location-search-result" role="option" data-location-result="${item.id}">
      <span><strong>${Yuhen.escapeHtml(item.name)}</strong><em>${Yuhen.escapeHtml(item.admin1_name)}</em><small>${Yuhen.escapeHtml(item.catalog_number)} · ${Yuhen.escapeHtml(item.country_name)}</small></span><b>选择</b>
    </button>
  `).join("") : '<p class="species-search-empty">没有匹配地点。</p>';
  results.hidden = false;
  status.textContent = matches.length ? `找到 ${matches.length} 个已有地点，请点击候选项进行选择` : "没有匹配地点";
}

function chooseLocation(locationId) {
  const location = state.locations.find((item) => String(item.id) === String(locationId));
  if (!location) return;
  byId("location-select").value = String(location.id);
  byId("location-search").value = `${location.name} ${location.admin1_name}`;
  byId("location-search-results").hidden = true;
  byId("location-search-status").textContent = `已选择 ${location.catalog_number} · ${location.name}`;
  byId("location-select").dispatchEvent(new Event("change", { bubbles: true }));
}

const taxonomySearchConfig = {
  order: { input: "order-node-search", results: "order-node-results", status: "order-node-status", select: "order-node-select" },
  family: { input: "family-node-search", results: "family-node-results", status: "family-node-status", select: "family-node-select" },
  genus: { input: "genus-node-search", results: "genus-node-results", status: "genus-node-status", select: "genus-node-select" },
};

function taxonomySearchItems(level) {
  if (level === "order") return state.taxonomy;
  if (level === "family") return selectedOrder()?.families || [];
  return selectedFamily()?.genera || [];
}

function renderTaxonomySearch(level) {
  const config = taxonomySearchConfig[level];
  const input = byId(config.input);
  const results = byId(config.results);
  const status = byId(config.status);
  const query = input.value.normalize("NFKC").trim().toLocaleLowerCase();
  const items = taxonomySearchItems(level);
  const matches = items.filter((item) => `${item.chinese_name} ${item.scientific_name}`.toLocaleLowerCase().includes(query));
  if (!query) {
    results.hidden = true;
    results.innerHTML = "";
    status.textContent = `${items.length ? `当前已有 ${items.length} 个${level === "order" ? "目" : level === "family" ? "科" : "属"}` : "请先选择上级分类"}`;
    return;
  }
  results.innerHTML = matches.length ? matches.slice(0, 10).map((item) => `
    <button type="button" class="species-search-result taxonomy-search-result" role="option" data-taxonomy-level="${level}" data-taxonomy-result="${item.id}">
      <span><strong>${Yuhen.escapeHtml(item.chinese_name)}</strong><em>${Yuhen.escapeHtml(item.scientific_name)}</em></span><b>选择</b>
    </button>
  `).join("") : '<p class="species-search-empty">没有匹配结果，可以选择新增。</p>';
  results.hidden = false;
  status.textContent = matches.length ? `找到 ${matches.length} 个已有项目，请点击候选项进行选择` : "没有匹配结果，可以选择新增";
}

function syncTaxonomySearchSelection(level) {
  const config = taxonomySearchConfig[level];
  const selected = level === "order" ? selectedOrder() : level === "family" ? selectedFamily() : selectedGenus();
  byId(config.input).value = selected ? `${selected.chinese_name} ${selected.scientific_name}` : "";
  byId(config.results).hidden = true;
  byId(config.status).textContent = selected ? `已选择 ${selected.chinese_name}` : "可选择已有项目，或使用下拉框新增";
}

function chooseTaxonomy(level, id) {
  const config = taxonomySearchConfig[level];
  const item = taxonomySearchItems(level).find((value) => String(value.id) === String(id));
  if (!item) return;
  byId(config.select).value = String(item.id);
  syncTaxonomySearchSelection(level);
  if (level === "order") updateFamilyOptions();
  if (level === "family") updateGenusOptions();
  if (level === "genus") syncTaxonomyFields();
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
      <img src="${item.thumbnail_url}" alt="观察照片" loading="lazy" />
      <span class="record-tile-body">
        <strong>${Yuhen.escapeHtml(observationSpeciesEntries(item).map((entry) => entry.species_name).join("、"))}</strong>
        <span>${Yuhen.escapeHtml(item.observed_at.replace("T", " "))}</span>
        <span>${Yuhen.escapeHtml(item.admin1_name)} · ${Yuhen.escapeHtml(item.locality)}</span>
        ${item.location ? `<span>地点档案 · ${Yuhen.escapeHtml(item.location.name)}</span>` : ""}
        <span>${Yuhen.labels[item.season] || Yuhen.escapeHtml(item.season)} · ${item.species_count} 个物种</span>
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
        <div class="observation-preview-scroll">
          <p class="eyebrow">${Yuhen.escapeHtml(item.catalog_number)} · OBSERVATION ${item.id}</p>
          <h2>${Yuhen.escapeHtml(item.species_name)}</h2>
          <p class="latin">${Yuhen.escapeHtml(item.species_scientific_name)}</p>
          <dl class="observation-facts">
            <div><dt>拍摄时间</dt><dd>${Yuhen.escapeHtml(item.observed_at.replace("T", " "))}</dd></div>
            <div><dt>拍摄地点</dt><dd>${Yuhen.escapeHtml(item.country_name)} · ${Yuhen.escapeHtml(item.admin1_name)} · ${Yuhen.escapeHtml(item.locality)}</dd></div>
            <div><dt>地点档案</dt><dd>${item.location ? `<a href="/locations?location=${item.location.id}">${Yuhen.escapeHtml(item.location.name)}</a>` : "未关联"}</dd></div>
            <div><dt>所属行程</dt><dd>${item.trip ? `<a href="/trips?trip=${item.trip.id}">${Yuhen.escapeHtml(item.trip.catalog_number)} · ${Yuhen.escapeHtml(item.trip.name)}</a>` : "未关联"}</dd></div>
            <div><dt>经纬度</dt><dd>${item.latitude}, ${item.longitude}</dd></div>
            <div><dt>季节</dt><dd>${Yuhen.escapeHtml(valueLabel(item.season))}</dd></div>
            <div><dt>照片类型</dt><dd>${individual ? "个体照片" : "群体照片"}</dd></div>
            ${individual ? `<div><dt>性别</dt><dd>${Yuhen.escapeHtml(valueLabel(item.sex))}</dd></div>
            <div><dt>生命阶段</dt><dd>${Yuhen.escapeHtml(valueLabel(item.life_stage))}</dd></div>
            <div><dt>亚种</dt><dd>${Yuhen.escapeHtml(subspecies)}</dd></div>` : ""}
          </dl>
          <section class="preview-notes"><h3>备注</h3><p>${Yuhen.escapeHtml(item.notes || "无备注")}</p></section>
          <section class="preview-audio-list"><h3>录音</h3>${audio}</section>
          <div id="observation-edit-container"></div>
        </div>
        <div class="preview-primary-actions">
          <button type="button" class="primary-button" data-edit-observation="${item.id}">修改记录</button>
          <a class="secondary-button button-link" href="/dex?species=${item.species_id}">查看该物种图鉴</a>
        </div>
      </div>
    </article>`;
  if (!observationDetailDialog.open) observationDetailDialog.showModal();
}

function enumOptions(values, selected) {
  return values.map((value) =>
    `<option value="${value}" ${value === selected ? "selected" : ""}>${Yuhen.escapeHtml(valueLabel(value))}</option>`
  ).join("");
}

async function showObservationEditor(observationId, requestedEntryId = null) {
  const item = state.observations.find((value) => value.id === Number(observationId));
  if (!item) return;
  const entries = observationSpeciesEntries(item);
  const entry = entries.find((value) => value.id === Number(requestedEntryId)) || entries[0];
  const individual = entry.photo_type === "individual";
  const speciesDetail = individual ? await Yuhen.api(`/api/species/${entry.species_id}`) : null;
  const subspeciesOptions = speciesDetail
    ? speciesDetail.subspecies.map((subspecies) => {
      const selected = entry.subspecies?.id === subspecies.id ? "selected" : "";
      const label = `${subspecies.chinese_name ? `${subspecies.chinese_name} · ` : ""}${subspecies.scientific_name}`;
      return `<option value="${subspecies.id}" ${selected}>${Yuhen.escapeHtml(label)}</option>`;
    }).join("")
    : "";
  const existingSpeciesIds = new Set(entries.map((value) => value.species_id));
  const addSpeciesOptions = state.species.filter((value) => !existingSpeciesIds.has(value.id)).map((value) =>
    `<option value="${value.id}">${Yuhen.escapeHtml(value.chinese_name)} · ${Yuhen.escapeHtml(value.scientific_name)}</option>`
  ).join("");
  const container = byId("observation-edit-container");
  container.innerHTML = `
    <form id="observation-edit-form" class="observation-edit-form">
      <header><h3>修改观察记录</h3><span>照片、时间与地点不可修改</span></header>
      <section class="observation-species-manager">
        <label>正在编辑的物种<select data-edit-species-entry>${entries.map((value) => `<option value="${value.id}" ${value.id === entry.id ? "selected" : ""}>${Yuhen.escapeHtml(value.species_name)}${value.is_primary ? " · 主记录" : ""}</option>`).join("")}</select></label>
        <div class="observation-add-species">
          <label>加入其他物种<select data-new-observation-species><option value="">选择尚未记录的物种</option>${addSpeciesOptions}</select></label>
          <label>照片类型<select data-new-species-photo-type><option value="individual">个体照片</option><option value="group">群体照片</option></select></label>
          <button type="button" class="secondary-button" data-add-observation-species ${addSpeciesOptions ? "" : "disabled"}>加入这笔观察</button>
        </div>
      </section>
      ${individual ? `<div class="observation-edit-grid">
        <label>性别<select name="sex">${enumOptions(["unknown", "male", "female"], entry.sex)}</select></label>
        <label>生命阶段<select name="life_stage">${enumOptions(["unknown", "egg", "chick", "subadult", "adult"], entry.life_stage)}</select></label>
        <label class="full-field">亚种<select name="subspecies_id"><option value="">未知 / 无亚种</option>${subspeciesOptions}</select></label>
      </div>` : `<p class="field-hint">这是群体照片，只能修改备注。</p>`}
      <label>物种备注<textarea name="entry_notes" rows="3">${Yuhen.escapeHtml(entry.notes || "")}</textarea></label>
      <label>整笔观察备注<textarea name="notes" rows="4">${Yuhen.escapeHtml(item.notes || "")}</textarea></label>
      <div class="observation-edit-actions">
        <span id="observation-edit-status" role="status"></span>
        <button type="button" class="danger-button" data-delete-observation-species ${entries.length === 1 ? "disabled title=\"一笔观察必须至少保留一个物种\"" : ""}>删除当前物种信息</button>
        <button type="button" class="secondary-button" data-cancel-observation-edit>取消</button>
        <button type="submit" class="primary-button">保存修改</button>
      </div>
    </form>`;

  const editForm = byId("observation-edit-form");
  editForm.scrollIntoView({ behavior: "smooth", block: "start" });
  editForm.querySelector("[data-cancel-observation-edit]").addEventListener("click", () => {
    container.innerHTML = "";
  });
  editForm.querySelector("[data-edit-species-entry]").addEventListener("change", (event) => {
    showObservationEditor(item.id, Number(event.target.value));
  });
  editForm.querySelector("[data-add-observation-species]").addEventListener("click", async (event) => {
    const speciesId = Number(editForm.querySelector("[data-new-observation-species]").value);
    if (!speciesId) return;
    const photoType = editForm.querySelector("[data-new-species-photo-type]").value;
    event.currentTarget.disabled = true;
    try {
      const updated = await Yuhen.api(`/api/observations/${item.id}/species`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ species_id: speciesId, photo_type: photoType, sex: photoType === "individual" ? "unknown" : null, life_stage: photoType === "individual" ? "unknown" : null, subspecies_id: null, notes: null }),
      });
      state.observations[state.observations.findIndex((value) => value.id === item.id)] = updated;
      const added = updated.species_entries.find((value) => value.species_id === speciesId);
      await showObservationEditor(item.id, added.id);
    } catch (error) {
      byId("observation-edit-status").textContent = error.message;
      event.currentTarget.disabled = false;
    }
  });
  editForm.querySelector("[data-delete-observation-species]").addEventListener("click", async (event) => {
    if (event.currentTarget.disabled || !confirm(`从这笔观察中删除“${entry.species_name}”的观察信息吗？照片和其他物种信息会保留。`)) return;
    event.currentTarget.disabled = true;
    try {
      await Yuhen.api(`/api/observations/${item.id}/species/${entry.id}`, { method: "DELETE" });
      const observations = await Yuhen.api("/api/observations");
      state.observations = observations;
      const updated = observations.find((value) => value.id === item.id);
      await showObservationEditor(item.id, updated.species_entries[0].id);
    } catch (error) {
      byId("observation-edit-status").textContent = error.message;
      event.currentTarget.disabled = false;
    }
  });
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
        notes: data.get("entry_notes") || null,
      };
      const speciesUpdated = await Yuhen.api(`/api/observations/${item.id}/species/${entry.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const primary = speciesUpdated.species_entries.find((value) => value.is_primary) || speciesUpdated.species_entries[0];
      const updated = await Yuhen.api(`/api/observations/${item.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sex: primary.photo_type === "individual" ? primary.sex : null, life_stage: primary.photo_type === "individual" ? primary.life_stage : null, subspecies_id: primary.photo_type === "individual" ? (primary.subspecies?.id || null) : null, notes: data.get("notes") || null }),
      });
      const index = state.observations.findIndex((value) => value.id === item.id);
      state.observations[index] = updated;
      if (isV2Editor) {
        window.location.href = `/observations?observation=${item.id}`;
      } else {
        renderObservations();
        openObservationDetail(item.id);
      }
    } catch (error) {
      status.textContent = error.message;
      submit.disabled = false;
    }
  });
}

function matchingSpecies(query) {
  return state.species.filter((item) => [
    item.catalog_number,
    item.chinese_name,
    item.scientific_name,
    item.order_name,
    item.family_name,
    item.family_scientific_name,
    item.genus_name,
    item.genus_scientific_name,
  ].join(" ").toLocaleLowerCase().includes(query));
}

function renderSpeciesSearchResults(matches, query) {
  const results = byId("species-search-results");
  if (!query) {
    results.hidden = true;
    results.innerHTML = "";
    return;
  }
  results.innerHTML = matches.length ? matches.slice(0, 10).map((item) => `
    <button type="button" class="species-search-result" role="option" data-species-result="${item.id}">
      <span>
        <strong>${Yuhen.escapeHtml(item.chinese_name)}</strong>
        <em>${Yuhen.escapeHtml(item.scientific_name)}</em>
        <small>${Yuhen.escapeHtml(item.catalog_number)} · ${Yuhen.escapeHtml(item.family_name)} · ${Yuhen.escapeHtml(item.genus_name)}</small>
      </span>
      <b>选择</b>
    </button>
  `).join("") : '<p class="species-search-empty">没有匹配结果，可在下方建立新物种。</p>';
  results.hidden = false;
}

function updateSpeciesSelectionSummary() {
  const value = byId("species-select").value;
  const item = state.species.find((species) => String(species.id) === value);
  const summary = byId("species-selection-summary");
  summary.hidden = !item;
  if (item) {
    byId("species-selection-text").textContent = `${item.catalog_number} · ${item.chinese_name} · ${item.scientific_name}`;
  }
}

function chooseSpecies(speciesId) {
  const select = byId("species-select");
  const item = state.species.find((species) => String(species.id) === String(speciesId));
  if (!item) return;
  select.value = String(item.id);
  byId("species-search").value = `${item.chinese_name} ${item.scientific_name}`;
  byId("species-search-results").hidden = true;
  byId("species-search-status").textContent = `已选择 ${item.catalog_number} · ${item.chinese_name}`;
  updateSpeciesSelectionSummary();
  toggleSpeciesMode();
  state.additionalSpecies = state.additionalSpecies.filter((entry) => entry.id !== item.id);
  renderAdditionalSpecies();
}

function populateSpeciesSelect() {
  const select = byId("species-select");
  const current = select.value;
  const query = byId("species-search").value.normalize("NFKC").trim().toLocaleLowerCase();
  const matches = matchingSpecies(query);
  select.innerHTML = `<option value="new">＋ 建立新物种</option>${matches.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.catalog_number)} · ${Yuhen.escapeHtml(item.chinese_name)}</option>`
  ).join("")}`;
  if ([...select.options].some((option) => option.value === current)) select.value = current;
  renderSpeciesSearchResults(matches, query);
  const status = byId("species-search-status");
  status.textContent = query
    ? (matches.length ? `找到 ${matches.length} 个已有物种，请点击候选项进行选择` : "没有匹配的已有物种，可以选择“建立新物种”")
    : `当前图鉴共有 ${state.species.length} 个物种`;
  updateSpeciesSelectionSummary();
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
  syncTaxonomySearchSelection("order");
  updateFamilyOptions();
}

function updateFamilyOptions() {
  const select = byId("family-node-select");
  const previous = select.value;
  const families = selectedOrder()?.families || [];
  select.innerHTML = `<option value="new">＋ 在当前目下新增科</option>${optionMarkup(families)}`;
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  syncTaxonomySearchSelection("family");
  updateGenusOptions();
}

function updateGenusOptions() {
  const select = byId("genus-node-select");
  const previous = select.value;
  const genera = selectedFamily()?.genera || [];
  select.innerHTML = `<option value="new">＋ 在当前科下新增属</option>${optionMarkup(genera)}`;
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  syncTaxonomySearchSelection("genus");
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
      additional_species: additionalSpeciesPayload(),
    },
    files: data,
  };
}

function openRecord() {
  form.reset();
  state.additionalSpecies = [];
  populateSpeciesSelect();
  populateTaxonomySelectors();
  const now = new Date(Date.now() - new Date().getTimezoneOffset() * 60000);
  byId("observed-at").value = now.toISOString().slice(0, 16);
  byId("form-status").textContent = "";
  byId("photo-metadata-status").textContent = "选择照片后将自动读取 EXIF 拍摄时间。";
  toggleSpeciesMode();
  toggleHasSubspecies();
  togglePhotoType();
  renderAdditionalSpecies();
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
    if (isV2Editor) {
      setTimeout(() => { window.location.href = `/observations?observation=${result.observation_id}`; }, 450);
    } else {
      await loadPage();
      setTimeout(() => recordDialog.close(), 650);
    }
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
byId("species-select").addEventListener("change", () => {
  byId("species-search-results").hidden = true;
  updateSpeciesSelectionSummary();
  toggleSpeciesMode();
  const primaryId = Number(byId("species-select").value);
  state.additionalSpecies = state.additionalSpecies.filter((entry) => entry.id !== primaryId);
  renderAdditionalSpecies();
});
byId("species-search").addEventListener("input", populateSpeciesSelect);
byId("species-search").addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    byId("species-search-results").hidden = true;
    return;
  }
  if (event.key !== "Enter") return;
  event.preventDefault();
  const query = event.currentTarget.value.normalize("NFKC").trim().toLocaleLowerCase();
  const first = matchingSpecies(query)[0];
  if (first) chooseSpecies(first.id);
});
byId("species-search-results").addEventListener("click", (event) => {
  const result = event.target.closest("[data-species-result]");
  if (result) chooseSpecies(result.dataset.speciesResult);
});
byId("change-species-selection").addEventListener("click", () => {
  byId("species-search").value = "";
  byId("species-select").value = "new";
  populateSpeciesSelect();
  byId("species-search").focus();
});
document.addEventListener("click", (event) => {
  if (!event.target.closest(".species-search-field, .taxonomy-node, .location-search-field")) {
    byId("species-search-results").hidden = true;
    for (const config of Object.values(taxonomySearchConfig)) byId(config.results).hidden = true;
    byId("location-search-results").hidden = true;
  }
});
byId("order-node-select").addEventListener("change", () => { syncTaxonomySearchSelection("order"); updateFamilyOptions(); });
byId("family-node-select").addEventListener("change", () => { syncTaxonomySearchSelection("family"); updateGenusOptions(); });
byId("genus-node-select").addEventListener("change", () => { syncTaxonomySearchSelection("genus"); syncTaxonomyFields(); });
for (const level of Object.keys(taxonomySearchConfig)) {
  const config = taxonomySearchConfig[level];
  byId(config.input).addEventListener("input", () => renderTaxonomySearch(level));
  byId(config.input).addEventListener("keydown", (event) => {
    if (event.key === "Escape") { byId(config.results).hidden = true; return; }
    if (event.key !== "Enter") return;
    event.preventDefault();
    const query = event.currentTarget.value.normalize("NFKC").trim().toLocaleLowerCase();
    const item = taxonomySearchItems(level).find((value) => `${value.chinese_name} ${value.scientific_name}`.toLocaleLowerCase().includes(query));
    if (item) chooseTaxonomy(level, item.id);
  });
  byId(config.results).addEventListener("click", (event) => {
    const result = event.target.closest("[data-taxonomy-result]");
    if (result) chooseTaxonomy(level, result.dataset.taxonomyResult);
  });
}
byId("has-subspecies").addEventListener("change", toggleHasSubspecies);
form.elements.subspecies_list.addEventListener("input", populateSubspecies);
byId("photo-type").addEventListener("change", togglePhotoType);
byId("add-additional-species").addEventListener("click", async () => {
  try { await addAdditionalSpecies(); } catch (error) { byId("form-status").textContent = error.message; }
});
byId("additional-species-list").addEventListener("click", (event) => {
  const remove = event.target.closest("[data-remove-additional-species]");
  if (remove) {
    state.additionalSpecies = state.additionalSpecies.filter((item) => String(item.id) !== remove.dataset.removeAdditionalSpecies);
    renderAdditionalSpecies();
  }
});
byId("additional-species-list").addEventListener("change", (event) => {
  if (!event.target.matches("[data-additional-photo-type]")) return;
  const row = event.target.closest("[data-additional-species]");
  row.querySelectorAll("[data-additional-individual]").forEach((field) => { field.hidden = event.target.value === "group"; });
});
byId("location-select").addEventListener("change", (event) => {
  const location = state.locations.find((item) => String(item.id) === event.target.value);
  if (!location) {
    byId("location-search").value = "";
    byId("location-search-results").hidden = true;
    byId("location-search-status").textContent = `当前地点资料库共有 ${state.locations.length} 个地点`;
    return;
  }
  byId("location-search").value = `${location.name} ${location.admin1_name}`;
  byId("location-search-results").hidden = true;
  byId("location-search-status").textContent = `已选择 ${location.catalog_number} · ${location.name}`;
  form.elements.country_code.value = location.country_code;
  form.elements.country_name.value = location.country_name;
  form.elements.admin1_code.value = location.admin1_code;
  form.elements.admin1_name.value = location.admin1_name;
  form.elements.locality.value = location.name;
  if (!byId("latitude").value) byId("latitude").value = location.center_latitude;
  if (!byId("longitude").value) byId("longitude").value = location.center_longitude;
});
byId("location-search").addEventListener("input", renderLocationSearchResults);
byId("location-search").addEventListener("keydown", (event) => {
  if (event.key === "Escape") { byId("location-search-results").hidden = true; return; }
  if (event.key !== "Enter") return;
  event.preventDefault();
  const query = event.currentTarget.value.normalize("NFKC").trim().toLocaleLowerCase();
  const first = matchingLocations(query)[0];
  if (first) chooseLocation(first.id);
});
byId("location-search-results").addEventListener("click", (event) => {
  const result = event.target.closest("[data-location-result]");
  if (result) chooseLocation(result.dataset.locationResult);
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
    if (observationId && !isV2Editor) openObservationDetail(observationId);
  })
  .catch((error) => { byId("observation-empty").hidden = false; byId("observation-empty").textContent = error.message; });

window.YuhenObservationEditor = { openRecord, showObservationEditor };
