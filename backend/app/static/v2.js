(function () {
  "use strict";

  const page = document.body.dataset.page;
  const byId = (id) => document.getElementById(id);
  const esc = (value) => Tsubasa.escapeHtml(value == null ? "" : String(value));
  const ecologyLabels = {
    unknown: "情报不足", raptor: "猛禽", songbird: "鸣禽", landfowl: "陆禽",
    scansorial: "攀禽", wader: "涉禽", waterfowl: "游禽",
  };
  const sizeLabels = {
    unknown: "未知", small: "小型", small_medium: "中小型", medium: "中型",
    medium_large: "中大型", large: "大型",
  };
  const habitatLabels = {
    city: "城市", farmland: "农田", grassland: "草原", shrub: "灌丛", forest: "森林",
    wetland: "湿地", river: "河流", lake: "湖泊", desert: "荒漠", coast: "海岸",
    ocean: "海洋", mudflat: "滩涂", alpine: "高山", other: "其他",
  };
  const iucnLabels = { NE: "待定", LC: "无危", NT: "近危", VU: "易危", EN: "濒危", CR: "极危", EW: "野外灭绝", EX: "灭绝" };
  const ecologyAssets = {
    raptor: "raptor-silhouette.png?v=20260816-1", songbird: "songbird-silhouette.png?v=20260816-1",
    landfowl: "landfowl-silhouette.png?v=20260816-1", scansorial: "scansorial-silhouette.png?v=20260816-2",
    wader: "wader-silhouette.png?v=20260816-1", waterfowl: "waterfowl-silhouette.png?v=20260816-1",
  };
  const bodySizes = [["small", "小型"], ["small_medium", "中小型"], ["medium", "中型"], ["medium_large", "中大型"], ["large", "大型"]];

  function formatDate(value) {
    if (!value) return "时间未记录";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value).replace("T", " ");
    return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(date);
  }

  function discoveryCard(item, compact = false) {
    return `<button class="v2-discovery-card${compact ? " is-compact" : ""}" data-v2-species="${item.id}">
      <span class="v2-discovery-photo"><img src="${esc(item.cover_url)}" alt="${esc(item.chinese_name)}" loading="lazy" /></span>
      <span class="v2-discovery-copy">
        <span class="v2-card-code">${esc(item.catalog_number)}</span>
        <strong>${esc(item.chinese_name)}</strong>
        <em>${esc(item.scientific_name)}</em>
        <span class="v2-card-facts"><i>${esc(item.order_name)} · ${esc(item.family_name)}</i><i>${item.observation_count} 次记录</i></span>
      </span>
    </button>`;
  }

  const homeState = { observations: [], featuredId: null };

  function applyHomepageFeature(feature) {
    const observation = feature.observation;
    homeState.featuredId = feature.selection_mode === "manual" && observation
      ? observation.id
      : null;
    if (!observation) {
      byId("featured-tag").innerHTML = "<span>调查册尚未启用</span><strong>登记第一笔观察</strong><i>从一张照片开始你的探索</i>";
      byId("featured-photo").style.backgroundImage = "";
      return;
    }
    byId("featured-photo").style.backgroundImage = `url("${observation.photo_url}")`;
    const label = feature.selection_mode === "manual" ? "指定馆藏" : "最新记录";
    byId("featured-tag").innerHTML = `<span>${label} · ${esc(observation.catalog_number)} · OBSERVATION ${observation.id}</span><strong>${esc(observation.species_name)}</strong><i>${esc(observation.species_scientific_name)}</i>`;
  }

  function renderHomeCoverChoices() {
    const query = byId("home-cover-search").value.trim().toLocaleLowerCase();
    const filtered = homeState.observations.filter((item) => [
      item.catalog_number,
      item.species_name,
      item.species_scientific_name,
      item.locality,
      item.admin1_name,
      item.observed_at,
    ].some((value) => String(value || "").toLocaleLowerCase().includes(query)));
    byId("home-cover-status").textContent = `共 ${homeState.observations.length} 笔记录，当前显示 ${filtered.length} 笔`;
    byId("home-cover-grid").innerHTML = filtered.length
      ? filtered.map((item) => `<button class="v2-home-cover-card${item.id === homeState.featuredId ? " is-selected" : ""}" type="button" data-home-cover-observation="${item.id}">
          <img src="${esc(item.thumbnail_url)}" alt="${esc(item.species_name)}" loading="lazy" />
          <span><b>${esc(item.species_name)}</b><i>${esc(item.catalog_number)} · OBSERVATION ${item.id}</i><small>${esc(item.observed_at.replace("T", " "))}<br />${esc(item.admin1_name)} · ${esc(item.locality)}</small></span>
          <em>${item.id === homeState.featuredId ? "当前首页封面" : "设为首页封面"}</em>
        </button>`).join("")
      : "<p class=\"v2-loading\">没有符合搜索条件的观察记录。</p>";
  }

  async function openHomeCoverPicker() {
    const dialog = byId("home-cover-dialog");
    dialog.showModal();
    byId("home-cover-status").textContent = "正在整理照片档案……";
    byId("home-cover-grid").innerHTML = "";
    try {
      homeState.observations = await Tsubasa.api("/api/observations");
      renderHomeCoverChoices();
    } catch (error) {
      byId("home-cover-status").textContent = error.message;
    }
  }

  async function selectHomepageFeature(observationId) {
    try {
      byId("home-cover-status").textContent = "正在保存首页封面……";
      const feature = await Tsubasa.api("/api/home/cover", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ observation_id: observationId }),
      });
      applyHomepageFeature(feature);
      byId("home-cover-dialog").close();
    } catch (error) {
      byId("home-cover-status").textContent = error.message;
    }
  }

  function setupHomeCoverPicker() {
    byId("change-home-cover").addEventListener("click", openHomeCoverPicker);
    byId("close-home-cover").addEventListener("click", () => byId("home-cover-dialog").close());
    byId("home-cover-search").addEventListener("input", renderHomeCoverChoices);
    byId("home-cover-grid").addEventListener("click", async (event) => {
      const choice = event.target.closest("[data-home-cover-observation]");
      if (choice) await selectHomepageFeature(Number(choice.dataset.homeCoverObservation));
    });
    byId("reset-home-cover").addEventListener("click", () => selectHomepageFeature(null));
    byId("home-cover-dialog").addEventListener("click", (event) => {
      if (event.target === byId("home-cover-dialog")) byId("home-cover-dialog").close();
    });
  }

  function setupBackup() {
    const dialog = byId("backup-dialog");
    const status = byId("backup-status");
    const confirmButton = byId("confirm-backup");
    const restoreButton = byId("confirm-restore");
    const restoreFile = byId("restore-backup-file");
    const restoreStatus = byId("restore-status");
    const download = byId("download-backup");
    byId("create-backup").addEventListener("click", () => {
      status.textContent = "准备创建备份。备份期间请不要关闭软件。";
      download.hidden = true;
      dialog.showModal();
    });
    byId("close-backup").addEventListener("click", () => dialog.close());
    restoreFile.addEventListener("change", () => {
      restoreStatus.textContent = restoreFile.files[0]
        ? `已选择：${restoreFile.files[0].name}`
        : "尚未选择备份。";
    });
    restoreButton.addEventListener("click", async () => {
      const file = restoreFile.files[0];
      if (!file) { restoreStatus.textContent = "请先选择 ZIP 备份。"; return; }
      if (!confirm("恢复会用备份中的数据库和媒体替换当前资料。程序会先自动备份当前状态，确定继续吗？")) return;
      restoreButton.disabled = true;
      confirmButton.disabled = true;
      restoreStatus.textContent = "正在校验数据库、文件哈希和媒体引用，请不要关闭软件……";
      try {
        const body = new FormData(); body.append("backup", file);
        const result = await Tsubasa.api("/api/backups/restore", { method: "POST", body });
        restoreStatus.textContent = `${result.message} 当前状态的安全备份：${result.safety_backup.filename}`;
        setTimeout(() => window.location.reload(), 1200);
      } catch (error) {
        restoreStatus.textContent = error.message;
      } finally {
        restoreButton.disabled = false;
        confirmButton.disabled = false;
      }
    });
    confirmButton.addEventListener("click", async () => {
      confirmButton.disabled = true;
      status.textContent = "正在生成一致性数据库快照并归档媒体文件……";
      try {
        const result = await Tsubasa.api("/api/backups", { method: "POST" });
        const sizeMb = (result.size_bytes / 1024 / 1024).toFixed(1);
        status.textContent = `备份完成：${result.filename}（${sizeMb} MB）`;
        download.href = result.download_url;
        download.download = result.filename;
        download.hidden = false;
      } catch (error) {
        status.textContent = error.message;
      } finally {
        confirmButton.disabled = false;
      }
    });
  }

  function setupUpdates() {
    byId("check-update").addEventListener("click", async () => {
      const button = byId("check-update"); button.disabled = true;
      try {
        const status = await Tsubasa.api("/api/updates/status");
        if (!status.update_available) { alert(status.message); return; }
        if (!confirm(`${status.message}\n${status.notes || ""}\n\n现在下载经过 SHA-256 校验的安装包吗？`)) return;
        const result = await Tsubasa.api("/api/updates/download", { method: "POST" });
        const link = document.createElement("a"); link.href = result.download_url; link.download = result.filename; link.click();
        alert(`${result.message}\n安装包：${result.filename}`);
      } catch (error) { alert(error.message); }
      finally { button.disabled = false; }
    });
  }

  let integrationState = null;

  function renderIntegrationSummary(config) {
    integrationState = config;
    const amap = config.amap;
    const llm = config.llm;
    byId("api-amap-summary").textContent = amap.configured
      ? `已配置 · ${amap.key_hint || "密钥已隐藏"}`
      : "尚未配置";
    byId("api-llm-provider").textContent = llm.provider === "openai_compatible"
      ? "外部大模型"
      : "本地 Ollama";
    byId("api-llm-summary").textContent = llm.provider === "openai_compatible"
      ? `${llm.model || "模型未填写"}${llm.api_key_hint ? ` · ${llm.api_key_hint}` : " · Key 未配置"}`
      : `${config.local_model.model} · 对话留在本机`;
  }

  function updateLlmFieldState() {
    const external = byId("api-llm-provider-select").value === "openai_compatible";
    ["api-llm-model", "api-llm-base-url", "api-llm-key", "api-llm-clear"].forEach((id) => {
      byId(id).disabled = !external;
    });
    byId("test-llm-api").disabled = !external;
  }

  function fillIntegrationDialog(config) {
    const amap = config.amap;
    const llm = config.llm;
    byId("api-amap-key").value = "";
    byId("api-amap-clear").checked = false;
    byId("api-amap-hint").textContent = amap.configured
      ? `当前密钥：${amap.key_hint}（${amap.source === "environment" ? "环境配置" : "配置册"}）`
      : "当前未配置 Key";
    byId("api-llm-provider-select").value = llm.provider;
    byId("api-llm-base-url").value = llm.base_url || "";
    byId("api-llm-model").value = llm.model || "";
    byId("api-llm-key").value = "";
    byId("api-llm-clear").checked = false;
    byId("api-llm-hint").textContent = llm.provider === "openai_compatible"
      ? `当前模型：${llm.model || "未填写"} · Key：${llm.api_key_hint || "未配置"}`
      : `当前使用 ${config.local_model.model}（${config.local_model.base_url}）`;
    updateLlmFieldState();
  }

  async function loadIntegrations(fillDialog = false) {
    const config = await Tsubasa.api("/api/integrations");
    renderIntegrationSummary(config);
    if (fillDialog) fillIntegrationDialog(config);
    return config;
  }

  function setApiActionStatus(button, status, busyText, task) {
    const label = button.textContent;
    button.disabled = true;
    button.textContent = busyText;
    status.textContent = busyText;
    return task().then((message) => {
      status.textContent = message;
    }).catch((error) => {
      status.textContent = error.message;
    }).finally(() => {
      button.textContent = label;
      updateLlmFieldState();
      if (!button.id.includes("llm")) button.disabled = false;
    });
  }

  function setupApiManager() {
    const dialog = byId("api-manager-dialog");
    byId("open-api-manager").addEventListener("click", async () => {
      byId("api-amap-status").textContent = "正在读取配置…";
      byId("api-llm-status").textContent = "";
      dialog.showModal();
      try {
        await loadIntegrations(true);
        byId("api-amap-status").textContent = "密钥不会在页面中回显。";
      } catch (error) {
        byId("api-amap-status").textContent = error.message;
      }
    });
    byId("close-api-manager").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    byId("api-llm-provider-select").addEventListener("change", updateLlmFieldState);

    byId("save-amap-api").addEventListener("click", () => {
      const button = byId("save-amap-api");
      const status = byId("api-amap-status");
      setApiActionStatus(button, status, "正在保存…", async () => {
        const config = await Tsubasa.api("/api/integrations/amap", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            api_key: byId("api-amap-key").value || null,
            clear_api_key: byId("api-amap-clear").checked,
          }),
        });
        byId("api-amap-key").value = "";
        const merged = { ...integrationState, ...config };
        renderIntegrationSummary(merged);
        fillIntegrationDialog(merged);
        return "地图配置已加密保存。";
      });
    });

    byId("test-amap-api").addEventListener("click", () => {
      setApiActionStatus(byId("test-amap-api"), byId("api-amap-status"), "正在测试…", async () => {
        const result = await Tsubasa.api("/api/integrations/amap/test", { method: "POST" });
        return result.message;
      });
    });

    byId("save-llm-api").addEventListener("click", () => {
      setApiActionStatus(byId("save-llm-api"), byId("api-llm-status"), "正在保存…", async () => {
        const config = await Tsubasa.api("/api/integrations/llm", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            provider: byId("api-llm-provider-select").value,
            base_url: byId("api-llm-base-url").value || null,
            model: byId("api-llm-model").value || null,
            api_key: byId("api-llm-key").value || null,
            clear_api_key: byId("api-llm-clear").checked,
          }),
        });
        byId("api-llm-key").value = "";
        const merged = { ...integrationState, ...config };
        renderIntegrationSummary(merged);
        fillIntegrationDialog(merged);
        await loadStatusAfterProviderChange();
        return "飞羽精灵的对话模型配置已保存。";
      });
    });

    byId("test-llm-api").addEventListener("click", () => {
      setApiActionStatus(byId("test-llm-api"), byId("api-llm-status"), "正在测试…", async () => {
        const result = await Tsubasa.api("/api/integrations/llm/test", { method: "POST" });
        return result.message;
      });
    });
  }

  async function loadStatusAfterProviderChange() {
    document.dispatchEvent(new CustomEvent("feather:reload-status"));
  }

  async function loadHome() {
    try {
      const [stats, species, feature] = await Promise.all([
        Tsubasa.api("/api/stats"),
        Tsubasa.api("/api/species"),
        Tsubasa.api("/api/home/cover"),
      ]);
      byId("v2-species-count").textContent = stats.species_count;
      byId("v2-observation-count").textContent = stats.observation_count;
      byId("v2-photo-count").textContent = stats.photo_count;
      byId("v2-audio-count").textContent = stats.audio_count;
      applyHomepageFeature(feature);

      const latest = [...species].sort((a, b) => b.id - a.id);
      if (latest.length) {
        byId("latest-species").innerHTML = latest.slice(0, 4).map((item) => discoveryCard(item, true)).join("");
        document.querySelectorAll("[data-v2-species]").forEach((card) => card.addEventListener("click", () => {
          window.location.href = `/dex?species=${card.dataset.v2Species}`;
        }));
      } else {
        byId("latest-species").innerHTML = "<p class=\"v2-loading\">尚无已确认物种。</p>";
      }
    } catch (error) {
      byId("latest-species").innerHTML = `<p class="v2-loading">${esc(error.message)}</p>`;
    }
  }

  const dexState = { species: [], currentSpeciesId: null };

  function fillSelect(select, values, placeholder) {
    const current = select.value;
    select.innerHTML = `<option value="">${placeholder}</option>${values.map((value) => `<option value="${esc(value)}">${esc(value)}</option>`).join("")}`;
    if (values.includes(current)) select.value = current;
  }

  function updateDexFilters() {
    const order = byId("v2-order-filter").value;
    const family = byId("v2-family-filter").value;
    fillSelect(byId("v2-family-filter"), [...new Set(dexState.species.filter((item) => !order || item.order_name === order).map((item) => item.family_name))].sort(), "全部科");
    const activeFamily = byId("v2-family-filter").value || family;
    if (activeFamily && [...byId("v2-family-filter").options].some((option) => option.value === activeFamily)) byId("v2-family-filter").value = activeFamily;
    fillSelect(byId("v2-genus-filter"), [...new Set(dexState.species.filter((item) => (!order || item.order_name === order) && (!activeFamily || item.family_name === activeFamily)).map((item) => item.genus_name))].sort(), "全部属");
  }

  function renderDex() {
    const query = byId("v2-dex-search").value.trim().toLocaleLowerCase();
    const order = byId("v2-order-filter").value;
    const family = byId("v2-family-filter").value;
    const genus = byId("v2-genus-filter").value;
    const filtered = dexState.species.filter((item) => {
      const haystack = `${item.catalog_number} ${item.chinese_name} ${item.scientific_name} ${item.family_name} ${item.genus_name}`.toLocaleLowerCase();
      return (!query || haystack.includes(query)) && (!order || item.order_name === order) && (!family || item.family_name === family) && (!genus || item.genus_name === genus);
    });
    byId("v2-dex-count").textContent = query || order || family || genus ? `${filtered.length} / ${dexState.species.length}` : dexState.species.length;
    byId("v2-species-grid").innerHTML = filtered.map((item) => discoveryCard(item)).join("");
    byId("v2-dex-empty").hidden = filtered.length !== 0;
    document.querySelectorAll("[data-v2-species]").forEach((card) => card.addEventListener("click", () => openDossier(Number(card.dataset.v2Species))));
  }

  function archiveList(items, label) {
    if (!items || !items.length) return `<span class="v2-intel-missing">${label}情报不足</span>`;
    return items.map((item) => {
      const text = item.name || Tsubasa.labels[item.value] || item.value || item.label;
      return item.observation_id
        ? `<a href="/observations?observation=${item.observation_id}" class="v2-intel-chip">${esc(text)}</a>`
        : `<span class="v2-intel-chip is-static">${esc(text)}${item.linked === false ? " · 待关联" : ""}</span>`;
    }).join("");
  }

  function subspeciesArchive(detail) {
    if (!detail.has_subspecies) return "<span class=\"v2-intel-chip is-static\">无亚种</span>";
    return detail.subspecies.map((item) => {
      const name = item.chinese_name || item.scientific_name;
      return item.captured && item.observation_id
        ? `<a href="/observations?observation=${item.observation_id}" class="v2-intel-chip">${esc(name)} · 已拍摄</a>`
        : `<span class="v2-intel-chip is-static is-pending">${esc(name)} · 未拍摄</span>`;
    }).join("");
  }

  function dossierProgress(detail) {
    const checks = [
      Boolean(detail.introduction), detail.ecology.group !== "unknown", detail.ecology.body_size !== "unknown",
      detail.ecology.habitats.length > 0, detail.behaviors.length > 0, detail.individuals.length > 0,
    ];
    return Math.round(checks.filter(Boolean).length / checks.length * 100);
  }

  function ecologyPanel(ecology) {
    const group = ecology.group || "unknown";
    const groupVisual = group === "unknown"
      ? "<span class=\"v2-ecology-question\">?</span>"
      : `<img src="/static/assets/${ecologyAssets[group]}" alt="" aria-hidden="true" />`;
    const size = ecology.body_size || "unknown";
    const habitats = ecology.habitats || [];
    return `<div class="v2-ecology-panel">
      <section class="v2-ecology-group"><span class="v2-ecology-label">生态习性</span><div class="v2-ecology-group-row"><span class="v2-ecology-disc">${groupVisual}</span><strong>${ecologyLabels[group] || group}</strong></div></section>
      <section class="v2-body-size"><span class="v2-ecology-label">体型大小 · ${sizeLabels[size] || size}</span><div class="v2-body-size-row">${bodySizes.map(([value, label], index) => `<span class="v2-body-size-bird ${size === value ? "is-selected" : ""} ${size === "unknown" ? "is-unknown" : ""}" style="--v2-bird-width:${28 + index * 7}px" title="${label}"><img src="/static/assets/body-size-silhouette.png?v=20260816-1" alt="" aria-hidden="true" /></span>`).join("")}</div></section>
      <section class="v2-habitat-block"><span class="v2-ecology-label">偏好生境</span><div class="v2-habitat-list">${habitats.length ? habitats.map((item) => `<span>${esc(habitatLabels[item] || item)}</span>`).join("") : "<small>尚未填写</small>"}</div></section>
    </div>`;
  }

  async function openDossier(speciesId) {
    dexState.currentSpeciesId = Number(speciesId);
    const dialog = byId("v2-dossier");
    byId("v2-dossier-content").innerHTML = "<p class=\"v2-loading v2-dossier-loading\">正在调取调查档案…</p>";
    if (!dialog.open) dialog.showModal();
    try {
      const detail = await Tsubasa.api(`/api/species/${speciesId}`);
      const progress = dossierProgress(detail);
      const recent = [...detail.observations].sort((a, b) => b.observed_at.localeCompare(a.observed_at)).slice(0, 4);
      byId("v2-dossier-content").innerHTML = `
        <section class="v2-dossier-hero">
          <div class="v2-dossier-image"><img src="${esc(detail.cover.photo_url)}" alt="${esc(detail.chinese_name)}" /></div>
          <div class="v2-dossier-title">
            <p class="v2-kicker">物种档案 · ${esc(detail.catalog_number)}</p>
            <h2>${esc(detail.chinese_name)}</h2><em>${esc(detail.scientific_name)}</em>
            <div class="v2-taxonomy-line">${esc(detail.classification.order.chinese_name)} / ${esc(detail.classification.family.chinese_name)} / ${esc(detail.classification.genus.chinese_name)}</div>
            <div class="v2-status-row"><span class="v2-iucn v2-iucn-${detail.iucn_status.toLowerCase()}">${detail.iucn_status} ${iucnLabels[detail.iucn_status] || ""}</span><span>累计 ${detail.observation_count} 次记录</span></div>
            <div class="v2-progress"><span><i style="width:${progress}%"></i></span><b>调查情报 ${progress}%</b></div>
          </div>
          ${ecologyPanel(detail.ecology)}
        </section>
        <section class="v2-dossier-paper">
          <div class="v2-dossier-main">
            <article><p class="v2-kicker">调查者手记</p><h3>物种简介</h3><p class="v2-note-copy">${esc(detail.introduction || "尚未填写物种简介。")}</p></article>
            <article><p class="v2-kicker">首次相遇</p><h3>首次遭遇</h3><a class="v2-first-encounter" href="/observations?observation=${detail.first_encounter.observation_id}"><strong>${formatDate(detail.first_encounter.observed_at)}</strong><span>${esc(detail.first_encounter.admin1_name)} · ${esc(detail.first_encounter.locality)}</span></a></article>
            <article><p class="v2-kicker">最近照片</p><h3>最近的照片凭证</h3><div class="v2-evidence-grid">${recent.map((item) => `<a href="/observations?observation=${item.id}"><img src="${esc(item.thumbnail_url)}" alt="" /><span>${formatDate(item.observed_at)}</span></a>`).join("")}</div></article>
            <article><p class="v2-kicker">馆藏管理</p><h3>观察记录与图鉴封面</h3><div class="v2-dex-observation-grid">${detail.observations.map((item) => { const current = item.id === detail.cover.observation_id; return `<section class="v2-dex-observation ${current ? "is-current" : ""}"><a href="/observations?observation=${item.id}"><img src="${esc(item.thumbnail_url)}" alt="" /><span>${formatDate(item.observed_at)} · ${esc(item.locality)}</span></a><div><button type="button" data-v2-species-cover="${item.id}" ${current ? "disabled" : ""}>${current ? "当前封面" : "设为封面"}</button><button type="button" class="is-danger" data-v2-delete-species-observation="${item.id}">删除记录</button></div></section>`; }).join("")}</div></article>
            <article><p class="v2-kicker">声音档案</p><h3>独立物种录音</h3><div class="v2-species-audio-list">${detail.species_audio.length ? detail.species_audio.map((audio) => `<section><strong>${esc(audio.title || "未命名录音")}</strong><small>${esc(audio.recorded_at ? String(audio.recorded_at).replace("T", " ") : "时间未记录")}${audio.locality ? ` · ${esc(audio.locality)}` : ""}</small><audio controls preload="metadata" src="${esc(audio.url)}"></audio>${audio.notes ? `<p>${esc(audio.notes)}</p>` : ""}<button type="button" class="is-danger" data-v2-delete-species-audio="${audio.id}">删除录音</button></section>`).join("") : "<p class=\"v2-intel-missing\">尚未添加独立物种录音。</p>"}</div></article>
          </div>
          <aside class="v2-intel-column">
            <article><h3>地理情报</h3><div>${archiveList(detail.collected.admin1_regions, "地理")}</div></article>
            <article><h3>季节情报</h3><div>${archiveList(detail.collected.seasons, "季节")}</div></article>
            <article><h3>个体档案</h3><div>${archiveList(detail.individuals.filter((item) => !String(item.id).startsWith("observed-")), "个体")}</div></article>
            <article><h3>行为档案</h3><div>${archiveList(detail.behaviors, "行为")}</div></article>
            <article><h3>亚种档案</h3><div>${subspeciesArchive(detail)}</div></article>
            <div class="v2-dex-edit-actions"><button class="v2-button v2-button-primary v2-edit-jump" type="button" data-v2-edit-species="${detail.id}">修改图鉴</button><button class="v2-button v2-button-ghost" type="button" data-v2-add-species-audio="${detail.id}">添加录音</button></div>
          </aside>
        </section>`;
    } catch (error) {
      byId("v2-dossier-content").innerHTML = `<p class="v2-loading v2-dossier-loading">${esc(error.message)}</p>`;
    }
  }

  async function loadDex() {
    try {
      dexState.species = await Tsubasa.api("/api/species");
      fillSelect(byId("v2-order-filter"), [...new Set(dexState.species.map((item) => item.order_name))].sort(), "全部目");
      updateDexFilters();
      renderDex();
      const requested = new URLSearchParams(window.location.search).get("species");
      if (requested && dexState.species.some((item) => String(item.id) === requested)) openDossier(Number(requested));
    } catch (error) {
      byId("v2-species-grid").innerHTML = `<p class="v2-loading">${esc(error.message)}</p>`;
    }

    byId("v2-dex-search").addEventListener("input", renderDex);
    byId("v2-order-filter").addEventListener("change", () => { updateDexFilters(); renderDex(); });
    byId("v2-family-filter").addEventListener("change", () => { updateDexFilters(); renderDex(); });
    byId("v2-genus-filter").addEventListener("change", renderDex);
    byId("v2-filter-reset").addEventListener("click", () => {
      byId("v2-dex-search").value = ""; byId("v2-order-filter").value = "";
      updateDexFilters(); byId("v2-family-filter").value = ""; updateDexFilters(); byId("v2-genus-filter").value = ""; renderDex();
    });
    byId("v2-dossier").querySelector(".v2-dossier-close").addEventListener("click", () => byId("v2-dossier").close());
    byId("v2-dossier").addEventListener("click", async (event) => {
      if (event.target === byId("v2-dossier")) { byId("v2-dossier").close(); return; }
      const edit = event.target.closest("[data-v2-edit-species]");
      if (edit && window.TsubasaDexEditor) { await window.TsubasaDexEditor.openProfile(Number(edit.dataset.v2EditSpecies)); return; }
      const cover = event.target.closest("[data-v2-species-cover]");
      if (cover) { await Tsubasa.api(`/api/species/${dexState.currentSpeciesId}/cover`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ observation_id: Number(cover.dataset.v2SpeciesCover) }) }); await openDossier(dexState.currentSpeciesId); return; }
      const remove = event.target.closest("[data-v2-delete-species-observation]");
      if (remove && confirm("删除将立即永久生效；若这是最后一笔观察，整个物种档案也会被删除。确定继续吗？")) { const result = await Tsubasa.api(`/api/observations/${remove.dataset.v2DeleteSpeciesObservation}`, { method: "DELETE" }); if (result.removed_species) { window.location.href = "/dex"; } else { await openDossier(dexState.currentSpeciesId); } return; }
      const audio = event.target.closest("[data-v2-add-species-audio]");
      if (audio) { dexState.currentSpeciesId = Number(audio.dataset.v2AddSpeciesAudio); byId("species-audio-form").reset(); byId("species-audio-status").textContent = ""; byId("species-audio-dialog").showModal(); }
      const removeAudio = event.target.closest("[data-v2-delete-species-audio]");
      if (removeAudio && confirm("永久删除这段独立物种录音吗？")) { await Tsubasa.api(`/api/species/${dexState.currentSpeciesId}/audio/${removeAudio.dataset.v2DeleteSpeciesAudio}`, { method: "DELETE" }); await openDossier(dexState.currentSpeciesId); }
    });
    document.querySelectorAll("[data-close-species-audio]").forEach((button) => button.addEventListener("click", () => byId("species-audio-dialog").close()));
    byId("species-audio-form").addEventListener("submit", async (event) => {
      event.preventDefault(); const form = event.currentTarget; const status = byId("species-audio-status"); const submit = form.querySelector("button[type=submit]"); submit.disabled = true; status.textContent = "正在保存录音…";
      try { const data = new FormData(form); const body = new FormData(); body.append("audio", data.get("audio")); body.append("payload", JSON.stringify({ title: data.get("title") || null, notes: data.get("notes") || null, recorded_at: data.get("recorded_at") || null, locality: data.get("locality") || null })); await Tsubasa.api(`/api/species/${dexState.currentSpeciesId}/audio`, { method: "POST", body }); byId("species-audio-dialog").close(); await openDossier(dexState.currentSpeciesId); }
      catch (error) { status.textContent = error.message; } finally { submit.disabled = false; }
    });
  }

  if (page === "home") {
    setupHomeCoverPicker();
    setupBackup();
    setupUpdates();
    setupApiManager();
    loadHome();
    loadIntegrations().catch((error) => {
      byId("api-amap-summary").textContent = error.message;
      byId("api-llm-summary").textContent = "配置读取失败";
    });
  }
  if (page === "dex") loadDex();
}());
