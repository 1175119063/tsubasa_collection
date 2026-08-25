const state = { species: [], currentDetail: null, behaviorCounter: 0, individualCounter: 0 };
const byId = (id) => document.getElementById(id);
const detailDialog = byId("detail-dialog");
const profileDialog = byId("profile-dialog");
const profileForm = byId("profile-form");
const isV2Editor = document.body.classList.contains("v2-page");
const iucnLabels = {
  EX: "灭绝", EW: "野外灭绝", CR: "极危", EN: "濒危",
  VU: "易危", NT: "近危", LC: "无危", NE: "待定",
};
const ecologyGroups = [
  ["unknown", "未知"], ["raptor", "猛禽"], ["songbird", "鸣禽"],
  ["landfowl", "陆禽"], ["scansorial", "攀禽"], ["wader", "涉禽"],
  ["waterfowl", "游禽"],
];
const bodySizes = [
  ["small", "小型"], ["small_medium", "中小型"], ["medium", "中型"],
  ["medium_large", "中大型"], ["large", "大型"],
];
const habitatTypes = [
  ["city", "城市"], ["farmland", "农田"], ["grassland", "草原"],
  ["shrub", "灌丛"], ["forest", "森林"], ["wetland", "湿地"],
  ["river", "河流"], ["lake", "湖泊"], ["desert", "荒漠"],
  ["coast", "海岸"], ["ocean", "海洋"], ["mudflat", "滩涂"],
  ["alpine", "高山"], ["other", "其他"],
];

function birdIcon(type) {
  const paths = {
    landfowl: `<path d="M9 30a23 23 0 0 1 46 0L32 42z" opacity=".25"/><circle cx="15" cy="19" r="3"/><circle cx="31" cy="10" r="3"/><circle cx="49" cy="19" r="3"/><ellipse cx="32" cy="34" rx="8" ry="13"/><circle cx="32" cy="20" r="5"/><path d="m36 19 9 3-9 3"/>`,
    scansorial: `<path d="M49 5h6v54h-6z" opacity=".35"/><ellipse cx="38" cy="29" rx="9" ry="15" transform="rotate(22 38 29)"/><circle cx="32" cy="15" r="6"/><path d="m27 14-11 3 11 3m17 25 7 10M43 30l8 2"/>`,
    wader: `<ellipse cx="27" cy="28" rx="15" ry="8"/><path d="M38 27c8-5 1-14 8-17 5-2 9 1 10 5-7-2-7 9-12 17M18 34l-2 22m17-22 5 22M51 14l10 2-10 3"/>`,
    waterfowl: `<ellipse cx="30" cy="35" rx="22" ry="11"/><circle cx="43" cy="22" r="8"/><path d="m49 21 12 4-12 4M18 30l-9-9 3 14"/>`,
  };
  if (type === "unknown") {
    return `<svg viewBox="0 0 64 64" aria-hidden="true"><text x="32" y="45" text-anchor="middle">?</text></svg>`;
  }
  if (type === "songbird") {
    return `<img class="ecology-raster-icon ecology-raster-songbird" src="/static/assets/songbird-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
  }
  if (type === "raptor") {
    return `<img class="ecology-raster-icon ecology-raster-raptor" src="/static/assets/raptor-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
  }
  if (type === "waterfowl") {
    return `<img class="ecology-raster-icon ecology-raster-waterfowl" src="/static/assets/waterfowl-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
  }
  if (type === "wader") {
    return `<img class="ecology-raster-icon ecology-raster-wader" src="/static/assets/wader-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
  }
  if (type === "landfowl") {
    return `<img class="ecology-raster-icon ecology-raster-landfowl" src="/static/assets/landfowl-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
  }
  if (type === "scansorial") {
    return `<img class="ecology-raster-icon ecology-raster-scansorial" src="/static/assets/scansorial-silhouette.png?v=20260816-2" alt="" aria-hidden="true" />`;
  }
  return `<svg viewBox="0 0 64 64" aria-hidden="true">${paths[type] || paths.waterfowl}</svg>`;
}

function bodySizeIcon() {
  return `<img class="body-size-raster-icon" src="/static/assets/body-size-silhouette.png?v=20260816-1" alt="" aria-hidden="true" />`;
}

function ecologyPanel(ecology = {}) {
  const group = ecology.group || "unknown";
  const groupLabel = ecologyGroups.find(([value]) => value === group)?.[1] || "未知";
  const size = ecology.body_size || "unknown";
  const sizeLabel = bodySizes.find(([value]) => value === size)?.[1] || "未知";
  const habitats = ecology.habitats || [];
  return `<aside class="species-ecology-panel" aria-label="物种生态画像">
    <section class="ecology-summary-group"><p>生态习性</p><span class="ecology-icon">${birdIcon(group)}</span><strong>${groupLabel}</strong></section>
    <section class="body-size-summary"><p>体型大小 · ${sizeLabel}</p><div>${bodySizes.map(([value, label], index) =>
      `<span class="body-size-bird ${size === value ? "is-selected" : ""} ${size === "unknown" ? "is-unknown" : ""}" style="--bird-width:${28 + index * 5}px" title="${label}">${bodySizeIcon()}</span>`
    ).join("")}</div></section>
    <section class="habitat-summary"><p>偏好生境</p><div>${habitats.length
      ? habitats.map((value) => `<span>${habitatTypes.find(([key]) => key === value)?.[1] || Yuhen.escapeHtml(value)}</span>`).join("")
      : `<em>尚未填写</em>`}</div></section>
  </aside>`;
}

async function loadDex() {
  state.species = await Yuhen.api("/api/species");
  populateDexFilters();
  renderSpecies();
}

function uniqueTaxa(items, idKey, nameKey, scientificKey) {
  const taxa = new Map();
  for (const item of items) {
    taxa.set(String(item[idKey]), {
      id: String(item[idKey]), name: item[nameKey], scientificName: item[scientificKey],
    });
  }
  return [...taxa.values()].sort((left, right) => left.name.localeCompare(right.name, "zh-CN"));
}

function taxonOptions(items) {
  return items.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.name)} · ${Yuhen.escapeHtml(item.scientificName)}</option>`
  ).join("");
}

function populateDexFilters() {
  const familySelect = byId("family-filter");
  const previousFamily = familySelect.value;
  const families = uniqueTaxa(state.species, "family_id", "family_name", "family_scientific_name");
  familySelect.innerHTML = `<option value="">全部科</option>${taxonOptions(families)}`;
  if (families.some((item) => item.id === previousFamily)) familySelect.value = previousFamily;
  updateGenusFilter();
}

function updateGenusFilter() {
  const familyId = byId("family-filter").value;
  const genusSelect = byId("genus-filter");
  const previousGenus = genusSelect.value;
  const candidates = state.species.filter((item) => !familyId || String(item.family_id) === familyId);
  const genera = uniqueTaxa(candidates, "genus_id", "genus_name", "genus_scientific_name");
  genusSelect.innerHTML = `<option value="">全部属</option>${taxonOptions(genera)}`;
  if (genera.some((item) => item.id === previousGenus)) genusSelect.value = previousGenus;
  updateSpeciesFilter();
}

function updateSpeciesFilter() {
  const familyId = byId("family-filter").value;
  const genusId = byId("genus-filter").value;
  const speciesSelect = byId("species-filter");
  const previousSpecies = speciesSelect.value;
  const candidates = state.species.filter((item) =>
    (!familyId || String(item.family_id) === familyId)
    && (!genusId || String(item.genus_id) === genusId)
  );
  speciesSelect.innerHTML = `<option value="">全部种</option>${candidates.map((item) =>
    `<option value="${item.id}">${Yuhen.escapeHtml(item.chinese_name)} · ${Yuhen.escapeHtml(item.scientific_name)}</option>`
  ).join("")}`;
  if (candidates.some((item) => String(item.id) === previousSpecies)) speciesSelect.value = previousSpecies;
}

function renderSpecies() {
  const query = byId("search-input").value.trim().toLocaleLowerCase();
  const familyId = byId("family-filter").value;
  const genusId = byId("genus-filter").value;
  const speciesId = byId("species-filter").value;
  const filtered = state.species.filter((item) =>
    `${item.chinese_name} ${item.scientific_name}`.toLocaleLowerCase().includes(query)
    && (!familyId || String(item.family_id) === familyId)
    && (!genusId || String(item.genus_id) === genusId)
    && (!speciesId || String(item.id) === speciesId)
  );
  byId("dex-total").textContent = filtered.length === state.species.length
    ? `${state.species.length} 个物种`
    : `显示 ${filtered.length} / ${state.species.length} 个物种`;
  byId("empty-state").hidden = state.species.length !== 0;
  byId("dex-filter-empty").hidden = state.species.length === 0 || filtered.length !== 0;
  byId("species-grid").innerHTML = filtered.map((item) => `
    <button class="species-card" data-species-id="${item.id}">
      <img src="${item.cover_url}" alt="${Yuhen.escapeHtml(item.chinese_name)}" loading="lazy" />
      <span class="card-body"><span class="card-number">${Yuhen.escapeHtml(item.catalog_number)}</span>
        <h3>${Yuhen.escapeHtml(item.chinese_name)}</h3>
        <span class="latin">${Yuhen.escapeHtml(item.scientific_name)}</span>
        <span class="card-meta"><span>${Yuhen.escapeHtml(item.family_name)}</span><span>${item.observation_count} 笔记录</span></span>
      </span>
    </button>`).join("");
  document.querySelectorAll(".species-card[data-species-id]").forEach((button) =>
    button.addEventListener("click", () => openDetail(button.dataset.speciesId))
  );
}

function archiveBadge(item, text, pending = false) {
  const label = Yuhen.escapeHtml(text);
  if (item.observation_id) {
    return `<a class="archive-badge done archive-proof-link" href="/observations?observation=${item.observation_id}" title="预览照片凭证">${label}</a>`;
  }
  return `<span class="archive-badge ${pending ? "pending" : ""}">${label}</span>`;
}

function individualDisplayLabel(item) {
  if (!String(item.id).startsWith("observed-")) return item.label;
  const [prefix, value] = item.label.split(" · ");
  return `${prefix} · ${Yuhen.labels[value] || value}`;
}

function uniqueIndividuals(items) {
  const values = new Map();
  for (const item of items) {
    values.set(individualDisplayLabel(item).normalize("NFKC").trim().toLocaleLowerCase(), item);
  }
  return [...values.values()];
}

function badgeList(items, format = (item) => item.name || Yuhen.labels[item.value] || item.value) {
  if (!items.length) return `<span class="archive-badge pending">尚无记录</span>`;
  return items.map((item) => archiveBadge(item, format(item))).join("");
}

async function setCover(speciesId, observationId) {
  await Yuhen.api(`/api/species/${speciesId}/cover`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ observation_id: Number(observationId) }),
  });
  await loadDex();
  await openDetail(speciesId);
}

async function openDetail(speciesId) {
  const detail = await Yuhen.api(`/api/species/${speciesId}`);
  state.currentDetail = detail;
  const individuals = uniqueIndividuals(detail.individuals || []);
  const china = detail.china_protection_status ? Yuhen.labels[detail.china_protection_status] : "无";
  const behaviors = detail.behaviors.length
    ? detail.behaviors.map((item) => archiveBadge(item, `${item.label}${item.linked ? "" : " · 待关联"}`, !item.linked)).join("")
    : `<span class="archive-badge pending">尚无行为标签</span>`;
  const subspecies = detail.has_subspecies
    ? detail.subspecies.map((item) => archiveBadge(
      item,
      `${item.chinese_name || item.scientific_name} · ${item.captured ? "已拍摄" : "未拍摄"}`,
      !item.captured
    )).join("")
    : `<span class="archive-badge">无亚种</span>`;
  byId("detail-content").innerHTML = `
    <section class="detail-hero species-detail-hero">
      <img src="${detail.cover.photo_url}" alt="${Yuhen.escapeHtml(detail.chinese_name)}" />
      <div class="species-hero-panel">
        <div class="detail-title"><p class="eyebrow">${Yuhen.escapeHtml(detail.catalog_number)}</p>
          <h2>${Yuhen.escapeHtml(detail.chinese_name)}</h2><p class="latin">${Yuhen.escapeHtml(detail.scientific_name)}</p>
          <div class="detail-classification">${Yuhen.escapeHtml(detail.classification.order.chinese_name)} · ${Yuhen.escapeHtml(detail.classification.family.chinese_name)} · ${Yuhen.escapeHtml(detail.classification.genus.chinese_name)}</div>
          <div class="species-status-stack">
            <span>中国保护等级：${china}</span>
            <span class="iucn-badge iucn-${detail.iucn_status.toLowerCase()}">${detail.iucn_status} ${iucnLabels[detail.iucn_status] || ""}</span>
          </div>
          <p class="species-observation-total">总共记录 <strong>${detail.observation_count}</strong> 次</p>
        </div>
        ${ecologyPanel(detail.ecology)}
      </div>
    </section>
    <div class="detail-body">
      <section class="detail-section species-introduction"><h3>自定义简介</h3><p>${Yuhen.escapeHtml(detail.introduction || "尚未填写物种简介。")} </p></section>
      <section class="detail-section"><h3>初次遇见</h3><p>${Yuhen.escapeHtml(detail.first_encounter.observed_at.replace("T", " "))} · ${Yuhen.escapeHtml(detail.first_encounter.admin1_name)} ${Yuhen.escapeHtml(detail.first_encounter.locality)}</p></section>
      <section class="detail-section"><h3>地理档案</h3><div class="badge-list">${badgeList(detail.collected.countries)} ${badgeList(detail.collected.admin1_regions)}</div></section>
      <section class="detail-section"><h3>季节档案</h3><div class="badge-list">${badgeList(detail.collected.seasons)}</div></section>
      <section class="detail-section"><h3>个体档案</h3><div class="badge-list">${badgeList(detail.collected.sexes)} ${badgeList(detail.collected.life_stages)}</div></section>
      <section class="detail-section"><h3>行为档案</h3><div class="badge-list">${behaviors}</div></section>
      <section class="detail-section"><h3>亚种档案</h3><div class="badge-list">${subspecies}</div></section>
      <section class="detail-section"><h3>观察记录与封面</h3><p class="section-note">选择任意一笔观察作为该物种的图鉴封面。</p><div class="observation-list">${detail.observations.map((item) => {
        const currentCover = item.id === detail.cover.observation_id;
        return `<article class="observation-card ${currentCover ? "is-current-cover" : ""}">
          <img src="${item.thumbnail_url}" alt="观察照片" />
          <div class="observation-info">${Yuhen.escapeHtml(item.observed_at.replace("T", " "))}<br />${Yuhen.escapeHtml(item.admin1_name)} · ${Yuhen.escapeHtml(item.locality)}<br />${Yuhen.labels[item.season] || item.season}<br />
            <span class="observation-card-actions">
              <button class="cover-button" data-cover-observation="${item.id}" ${currentCover ? "disabled" : ""}>${currentCover ? "当前图鉴封面" : "设为图鉴封面"}</button>
              <a class="observation-preview-link" href="/observations?observation=${item.id}">预览这笔观察</a>
            </span>
            <button class="danger-button" data-delete-observation="${item.id}">永久删除这笔观察</button>
          </div>
        </article>`;
      }).join("")}</div></section>
      <div class="species-detail-footer"><button type="button" class="secondary-button" data-edit-profile>修改图鉴</button></div>
    </div>`;
  if (!detailDialog.open) detailDialog.showModal();
  const archiveSections = byId("detail-content").querySelectorAll(".detail-section");
  if (archiveSections[4]) {
    archiveSections[4].querySelector(".badge-list").innerHTML = badgeList(individuals, individualDisplayLabel);
  }

  document.querySelector("[data-edit-profile]").addEventListener("click", openProfileEditor);
  document.querySelectorAll("[data-cover-observation]").forEach((button) =>
    button.addEventListener("click", () => setCover(speciesId, button.dataset.coverObservation))
  );
  document.querySelectorAll("[data-delete-observation]").forEach((button) =>
    button.addEventListener("click", async () => {
      if (!confirm("删除将立即永久生效；若这是最后一笔观察，整个物种档案也会被删除。确定继续吗？")) return;
      const result = await Yuhen.api(`/api/observations/${button.dataset.deleteObservation}`, { method: "DELETE" });
      detailDialog.close();
      await loadDex();
      if (!result.removed_species) await openDetail(speciesId);
    })
  );
}

function observationOption(item, selectedId) {
  const selected = item.id === selectedId ? "selected" : "";
  return `<option value="${item.id}" ${selected}>${Yuhen.escapeHtml(item.observed_at.replace("T", " "))} · ${Yuhen.escapeHtml(item.locality)}</option>`;
}

function matchingObservations(detail, dimension, valueKey) {
  return detail.observations.filter((item) => {
    if (dimension === "sex") return item.sex === valueKey;
    if (dimension === "life_stage") return item.life_stage === valueKey;
    if (dimension === "subspecies") return String(item.subspecies?.id || "") === valueKey;
    return false;
  });
}

function evidenceEditorRow(detail, dimension, valueKey, label, selectedId) {
  const options = matchingObservations(detail, dimension, valueKey)
    .map((item) => observationOption(item, selectedId)).join("");
  return `<label class="profile-evidence-row"><span>${Yuhen.escapeHtml(label)}</span>
    <select data-evidence-dimension="${dimension}" data-evidence-value="${Yuhen.escapeHtml(valueKey)}">${options}</select>
  </label>`;
}

function behaviorRow(detail, behavior = {}) {
  const rowId = ++state.behaviorCounter;
  const options = detail.observations.map((item) => observationOption(item, behavior.observation_id)).join("");
  return `<div class="profile-behavior-row" data-behavior-row="${rowId}">
    <label>行为标签<input data-behavior-label maxlength="80" required value="${Yuhen.escapeHtml(behavior.label || "")}" placeholder="例如：飞行" /></label>
    <label>照片凭证<select data-behavior-observation><option value="">暂不关联</option>${options}</select></label>
    <button type="button" class="danger-button behavior-remove-button" data-remove-behavior="${rowId}">删除标签</button>
  </div>`;
}

function individualRow(detail, individual = {}) {
  const rowId = ++state.individualCounter;
  const options = detail.observations.map((item) => observationOption(item, individual.observation_id)).join("");
  return `<div class="profile-behavior-row" data-individual-row="${rowId}">
    <label>个体标签<input data-individual-label maxlength="120" required value="${Yuhen.escapeHtml(individualDisplayLabel(individual) || "")}" placeholder="例如：雄性 · 成鸟 · 繁殖羽" /></label>
    <label>照片凭证<select data-individual-observation><option value="">暂不关联</option>${options}</select></label>
    <button type="button" class="danger-button behavior-remove-button" data-remove-individual="${rowId}">删除标签</button>
  </div>`;
}

function updateHabitatStatus(message = "") {
  const selected = byId("profile-habitat-options").querySelectorAll("input:checked").length;
  const status = byId("profile-habitat-status");
  status.textContent = message || `${selected} / 3`;
  status.classList.toggle("is-error", Boolean(message));
}

function renderEcologyEditor(ecology = {}) {
  const group = ecology.group || "unknown";
  const size = ecology.body_size || "unknown";
  const habitats = new Set(ecology.habitats || []);
  byId("profile-ecology-options").innerHTML = ecologyGroups.map(([value, label]) => `
    <label class="ecology-choice"><input type="radio" name="ecological_group" value="${value}" ${group === value ? "checked" : ""} />
      <span class="ecology-icon">${birdIcon(value)}</span><strong>${label}</strong>
    </label>`).join("");
  byId("profile-body-size-options").innerHTML = `
    <label class="body-size-choice body-size-unknown"><input type="radio" name="body_size" value="unknown" ${size === "unknown" ? "checked" : ""} /><span>未知</span></label>
    ${bodySizes.map(([value, label], index) => `
      <label class="body-size-choice" style="--bird-width:${32 + index * 8}px"><input type="radio" name="body_size" value="${value}" ${size === value ? "checked" : ""} />
        <span>${bodySizeIcon()}</span><strong>${label}</strong>
      </label>`).join("")}`;
  byId("profile-habitat-options").innerHTML = habitatTypes.map(([value, label]) => `
    <label class="habitat-choice"><input type="checkbox" value="${value}" ${habitats.has(value) ? "checked" : ""} /><span>${label}</span></label>
  `).join("");
  updateHabitatStatus();
}

function openProfileEditor() {
  const detail = state.currentDetail;
  if (!detail) return;
  profileForm.elements.introduction.value = detail.introduction || "";
  for (const rank of ["order", "family", "genus"]) {
    profileForm.elements[`${rank}_chinese_name`].value = detail.classification[rank].chinese_name;
    profileForm.elements[`${rank}_scientific_name`].value = detail.classification[rank].scientific_name;
  }
  renderEcologyEditor(detail.ecology);
  const rows = [];
  detail.collected.sexes.forEach((item) => rows.push(evidenceEditorRow(
    detail, "sex", item.value, `性别 · ${Yuhen.labels[item.value] || item.value}`, item.observation_id
  )));
  detail.collected.life_stages.forEach((item) => rows.push(evidenceEditorRow(
    detail, "life_stage", item.value, `生命阶段 · ${Yuhen.labels[item.value] || item.value}`, item.observation_id
  )));
  rows.length = 0;
  detail.subspecies.filter((item) => item.captured).forEach((item) => rows.push(evidenceEditorRow(
    detail, "subspecies", String(item.id), `亚种 · ${item.chinese_name || item.scientific_name}`, item.observation_id
  )));
  byId("profile-evidence-list").innerHTML = rows.length
    ? rows.join("") : `<p class="preview-empty">目前没有可设置照片凭证的个体或亚种档案。</p>`;
  byId("profile-individual-list").innerHTML = uniqueIndividuals(detail.individuals || []).map((item) => individualRow(detail, item)).join("");
  byId("profile-behavior-list").innerHTML = detail.behaviors.map((item) => behaviorRow(detail, item)).join("");
  byId("profile-form-status").textContent = "";
  if (!profileDialog.open) profileDialog.showModal();
}

byId("add-behavior-button").addEventListener("click", () => {
  if (!state.currentDetail) return;
  byId("profile-behavior-list").insertAdjacentHTML("beforeend", behaviorRow(state.currentDetail));
});

byId("add-individual-button").addEventListener("click", () => {
  if (!state.currentDetail) return;
  byId("profile-individual-list").insertAdjacentHTML("beforeend", individualRow(state.currentDetail));
});

byId("profile-behavior-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-behavior]");
  if (button) button.closest("[data-behavior-row]").remove();
});
byId("profile-individual-list").addEventListener("click", (event) => {
  const button = event.target.closest("[data-remove-individual]");
  if (button) button.closest("[data-individual-row]").remove();
});
byId("profile-habitat-options").addEventListener("change", (event) => {
  if (!event.target.matches("input[type=checkbox]")) return;
  const selected = byId("profile-habitat-options").querySelectorAll("input:checked");
  if (selected.length > 3) {
    event.target.checked = false;
    updateHabitatStatus("最多选择 3 项");
    return;
  }
  updateHabitatStatus();
});

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const detail = state.currentDetail;
  if (!detail) return;
  const status = byId("profile-form-status");
  const submit = profileForm.querySelector("button[type=submit]");
  submit.disabled = true;
  status.textContent = "正在保存…";
  try {
    const evidenceSelections = [...byId("profile-evidence-list").querySelectorAll("[data-evidence-dimension]")]
      .map((select) => ({
        dimension: select.dataset.evidenceDimension,
        value_key: select.dataset.evidenceValue,
        observation_id: Number(select.value),
      }));
    const behaviors = [...byId("profile-behavior-list").querySelectorAll("[data-behavior-row]")]
      .map((row) => ({
        label: row.querySelector("[data-behavior-label]").value,
        observation_id: row.querySelector("[data-behavior-observation]").value
          ? Number(row.querySelector("[data-behavior-observation]").value) : null,
      }));
    const individuals = [...byId("profile-individual-list").querySelectorAll("[data-individual-row]")]
      .map((row) => ({
        label: row.querySelector("[data-individual-label]").value,
        observation_id: row.querySelector("[data-individual-observation]").value
          ? Number(row.querySelector("[data-individual-observation]").value) : null,
      }));
    const payload = {
      introduction: profileForm.elements.introduction.value || null,
      order: { chinese_name: profileForm.elements.order_chinese_name.value, scientific_name: profileForm.elements.order_scientific_name.value },
      family: { chinese_name: profileForm.elements.family_chinese_name.value, scientific_name: profileForm.elements.family_scientific_name.value },
      genus: { chinese_name: profileForm.elements.genus_chinese_name.value, scientific_name: profileForm.elements.genus_scientific_name.value },
      ecological_group: profileForm.elements.ecological_group.value,
      body_size: profileForm.elements.body_size.value,
      preferred_habitats: [...byId("profile-habitat-options").querySelectorAll("input:checked")].map((input) => input.value),
      evidence_selections: evidenceSelections,
      behaviors,
      individuals,
    };
    await Yuhen.api(`/api/species/${detail.id}/profile`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
    });
    profileDialog.close();
    if (isV2Editor) { window.location.href = `/dex?species=${detail.id}`; return; }
    await loadDex();
    await openDetail(detail.id);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

document.querySelectorAll("[data-close-detail]").forEach((button) =>
  button.addEventListener("click", () => detailDialog.close())
);
document.querySelectorAll("[data-close-profile]").forEach((button) =>
  button.addEventListener("click", () => profileDialog.close())
);
byId("search-input").addEventListener("input", renderSpecies);
byId("family-filter").addEventListener("change", () => { updateGenusFilter(); renderSpecies(); });
byId("genus-filter").addEventListener("change", () => { updateSpeciesFilter(); renderSpecies(); });
byId("species-filter").addEventListener("change", renderSpecies);
byId("dex-filter-reset").addEventListener("click", () => {
  byId("search-input").value = "";
  byId("family-filter").value = "";
  updateGenusFilter();
  byId("genus-filter").value = "";
  updateSpeciesFilter();
  byId("species-filter").value = "";
  renderSpecies();
});

window.YuhenDexEditor = {
  async openProfile(speciesId) {
    state.currentDetail = await Yuhen.api(`/api/species/${speciesId}`);
    openProfileEditor();
  },
  async setCover(speciesId, observationId) {
    await Yuhen.api(`/api/species/${speciesId}/cover`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ observation_id: Number(observationId) }),
    });
    if (isV2Editor) window.location.reload();
  },
};

loadDex().then(() => {
  const speciesId = Number(new URLSearchParams(window.location.search).get("species"));
  if (!isV2Editor && speciesId && state.species.some((item) => item.id === speciesId)) openDetail(speciesId);
}).catch((error) => {
  byId("empty-state").hidden = false;
  byId("empty-state").querySelector("p").textContent = error.message;
});
