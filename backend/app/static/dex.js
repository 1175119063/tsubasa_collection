const state = { species: [] };
const byId = (id) => document.getElementById(id);
const detailDialog = byId("detail-dialog");

async function loadDex() {
  state.species = await Yuhen.api("/api/species");
  populateDexFilters();
  renderSpecies();
}

function uniqueTaxa(items, idKey, nameKey, scientificKey) {
  const taxa = new Map();
  for (const item of items) {
    taxa.set(String(item[idKey]), {
      id: String(item[idKey]),
      name: item[nameKey],
      scientificName: item[scientificKey],
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
  const families = uniqueTaxa(
    state.species, "family_id", "family_name", "family_scientific_name"
  );
  familySelect.innerHTML = `<option value="">全部科</option>${taxonOptions(families)}`;
  if (families.some((item) => item.id === previousFamily)) familySelect.value = previousFamily;
  updateGenusFilter();
}

function updateGenusFilter() {
  const familyId = byId("family-filter").value;
  const genusSelect = byId("genus-filter");
  const previousGenus = genusSelect.value;
  const candidates = state.species.filter((item) =>
    !familyId || String(item.family_id) === familyId
  );
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
  if (candidates.some((item) => String(item.id) === previousSpecies)) {
    speciesSelect.value = previousSpecies;
  }
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
      <span class="card-body">
        <span class="card-number">${Yuhen.escapeHtml(item.catalog_number)}</span>
        <h3>${Yuhen.escapeHtml(item.chinese_name)}</h3>
        <span class="latin">${Yuhen.escapeHtml(item.scientific_name)}</span>
        <span class="card-meta"><span>${Yuhen.escapeHtml(item.family_name)}</span><span>${item.observation_count} 笔记录</span></span>
      </span>
    </button>`).join("");
  document.querySelectorAll(".species-card[data-species-id]").forEach((button) =>
    button.addEventListener("click", () => openDetail(button.dataset.speciesId))
  );
}

function badgeList(items, format = (item) => item.name || Yuhen.labels[item.value] || item.value) {
  if (!items.length) return `<span class="archive-badge pending">尚无记录</span>`;
  return items.map((item) =>
    `<span class="archive-badge done">${Yuhen.escapeHtml(format(item))}</span>`
  ).join("");
}

async function setCover(speciesId, observationId) {
  await Yuhen.api(`/api/species/${speciesId}/cover`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ observation_id: Number(observationId) }),
  });
  await loadDex();
  await openDetail(speciesId);
}

async function openDetail(speciesId) {
  const detail = await Yuhen.api(`/api/species/${speciesId}`);
  const china = detail.china_protection_status
    ? Yuhen.labels[detail.china_protection_status]
    : "无";
  byId("detail-content").innerHTML = `
    <section class="detail-hero">
      <img src="/api/media/${detail.cover.asset_id}" alt="${Yuhen.escapeHtml(detail.chinese_name)}" />
      <div class="detail-title"><p class="eyebrow">${Yuhen.escapeHtml(detail.catalog_number)}</p>
        <h2>${Yuhen.escapeHtml(detail.chinese_name)}</h2><p class="latin">${Yuhen.escapeHtml(detail.scientific_name)}</p>
        <div class="detail-classification">${Yuhen.escapeHtml(detail.classification.order.chinese_name)} · ${Yuhen.escapeHtml(detail.classification.family.chinese_name)} · ${Yuhen.escapeHtml(detail.classification.genus.chinese_name)}<br />IUCN ${detail.iucn_status} · 中国保护等级：${china}</div>
      </div>
    </section>
    <div class="detail-body">
      <section class="detail-section"><h3>初次遇见</h3><p>${Yuhen.escapeHtml(detail.first_encounter.observed_at.replace("T", " "))} · ${Yuhen.escapeHtml(detail.first_encounter.admin1_name)} ${Yuhen.escapeHtml(detail.first_encounter.locality)}</p></section>
      <section class="detail-section"><h3>地理档案</h3><div class="badge-list">${badgeList(detail.collected.countries)} ${badgeList(detail.collected.admin1_regions)}</div></section>
      <section class="detail-section"><h3>季节档案</h3><div class="badge-list">${badgeList(detail.collected.seasons)}</div></section>
      <section class="detail-section"><h3>个体档案</h3><div class="badge-list">${badgeList(detail.collected.sexes)} ${badgeList(detail.collected.life_stages)}</div></section>
      <section class="detail-section"><h3>亚种档案</h3><div class="badge-list">${detail.has_subspecies ? detail.subspecies.map((item) => `<span class="archive-badge ${item.captured ? "done" : "pending"}">${Yuhen.escapeHtml(item.chinese_name || item.scientific_name)} · ${item.captured ? "已拍摄" : "未拍摄"}</span>`).join("") : `<span class="archive-badge">无亚种</span>`}</div></section>
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
    </div>`;
  if (!detailDialog.open) detailDialog.showModal();

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

document.querySelectorAll("[data-close-detail]").forEach((button) =>
  button.addEventListener("click", () => detailDialog.close())
);
byId("search-input").addEventListener("input", renderSpecies);
byId("family-filter").addEventListener("change", () => {
  updateGenusFilter();
  renderSpecies();
});
byId("genus-filter").addEventListener("change", () => {
  updateSpeciesFilter();
  renderSpecies();
});
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

loadDex()
  .then(() => {
    const speciesId = Number(new URLSearchParams(window.location.search).get("species"));
    if (speciesId && state.species.some((item) => item.id === speciesId)) openDetail(speciesId);
  })
  .catch((error) => {
    byId("empty-state").hidden = false;
    byId("empty-state").querySelector("p").textContent = error.message;
  });
