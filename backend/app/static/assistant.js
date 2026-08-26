(function () {
  "use strict";

  const page = document.body.dataset.page;
  if (!page || !window.Yuhen) return;
  const esc = (value) => Yuhen.escapeHtml(value == null ? "" : String(value));
  let available = false;
  let extraction = null;

  const pageNames = {
    home: "探索营地",
    observations: "田野记录",
    dex: "鸟类调查册",
    locations: "区域档案",
    trips: "远征日志",
  };
  const exampleQuestions = {
    home: ["首页可以做什么？", "如何选择首页封面？", "怎样备份全部资料？"],
    observations: ["如何记录一张照片中的多个物种？", "删除一笔观察会发生什么？", "怎样修改物种信息？"],
    dex: ["鸟类调查册收录哪些物种？", "怎样修改图鉴资料？", "如何设置物种封面？"],
    locations: ["如何通过地图新增地点？", "区域档案会展示哪些记录？", "地点如何关联远征？"],
    trips: ["如何建立包含多个地点的远征？", "怎样更换远征封面？", "删除远征会删除观察吗？"],
  };
  const greetings = [
    "探险家，你终于来了！今天想从哪一页飞羽见闻开始？",
    "飞羽精灵已醒来。探险家，要检索记录，还是一起翻阅调查手册？",
    "我听见档案页在轻轻振翅——探险家，今天有什么新发现？",
    "欢迎回到营地，探险家！把要整理的线索交给我吧。",
    `探险家，${pageNames[page]}的书页已经展开。需要我做些什么？`,
  ];
  let previousGreeting = -1;

  const launch = document.createElement("button");
  launch.className = "feather-launch is-offline";
  launch.type = "button";
  launch.innerHTML = '<img src="/static/assets/feather-spirit-avatar.png?v=20260825-1" alt="" /><span>飞羽精灵</span>';
  launch.setAttribute("aria-controls", "feather-panel");
  launch.setAttribute("aria-expanded", "false");

  const panel = document.createElement("aside");
  panel.id = "feather-panel";
  panel.className = "feather-panel";
  panel.hidden = true;
  panel.innerHTML = `
    <header class="feather-panel-header">
      <div class="feather-identity">
        <span class="feather-avatar"><img src="/static/assets/feather-spirit-avatar.png?v=20260825-1" alt="飞羽精灵头像" /></span>
        <div><p>ARCANE FIELD COMPANION</p><h2>飞羽精灵</h2><small>探险家的飞羽向导</small></div>
      </div>
      <button class="feather-panel-close" type="button" aria-label="关闭">×</button>
    </header>
    <div class="feather-status" id="feather-status">正在确认本地模型状态…</div>
    <nav class="feather-chat-modes" aria-label="飞羽精灵对话模式">
      <button class="is-active" type="button" data-feather-mode="chat">精灵对话</button>
      ${page === "observations" ? '<button type="button" data-feather-mode="search">检索田野记录</button>' : ""}
    </nav>
    <section class="feather-chat-stage">
      <div class="feather-chat-log" id="feather-chat-log" aria-live="polite"></div>
      <p class="feather-mode-note" id="feather-mode-note">可以自由聊天；涉及本项目功能时会参考${esc(pageNames[page])}的说明。</p>
      <div class="feather-quick-replies" id="feather-quick-replies"></div>
    </section>
    <form class="feather-composer" id="feather-composer">
      <textarea id="feather-chat-input" maxlength="500" rows="2" placeholder="给飞羽精灵发送消息…"></textarea>
      <button class="feather-action" id="feather-chat-send" type="submit" disabled aria-label="发送消息">发送</button>
    </form>`;

  document.body.append(launch, panel);

  function nextGreeting() {
    let index = Math.floor(Math.random() * greetings.length);
    if (greetings.length > 1 && index === previousGreeting) index = (index + 1) % greetings.length;
    previousGreeting = index;
    return greetings[index];
  }

  const chatLog = document.getElementById("feather-chat-log");
  const chatInput = document.getElementById("feather-chat-input");
  const chatSend = document.getElementById("feather-chat-send");
  const quickReplies = document.getElementById("feather-quick-replies");
  const modeNote = document.getElementById("feather-mode-note");
  let chatMode = "chat";
  let chatHistory = [];

  function scrollChat() {
    requestAnimationFrame(() => { chatLog.scrollTop = chatLog.scrollHeight; });
  }

  function appendMessage(role, text, pending = false) {
    const message = document.createElement("article");
    message.className = `feather-message is-${role}${pending ? " is-pending" : ""}`;
    if (role === "assistant") {
      const avatar = document.createElement("img");
      avatar.src = "/static/assets/feather-spirit-avatar.png?v=20260825-1";
      avatar.alt = "";
      message.append(avatar);
    }
    const bubble = document.createElement("div");
    const label = document.createElement("small");
    label.textContent = role === "assistant" ? "飞羽精灵" : "探险家";
    const copy = document.createElement("p");
    copy.textContent = text;
    bubble.append(label, copy);
    message.append(bubble);
    chatLog.append(message);
    scrollChat();
    return message;
  }

  function resolveMessage(message, text, failed = false) {
    message.classList.remove("is-pending");
    message.classList.toggle("is-error", failed);
    message.querySelector("p").textContent = text;
    scrollChat();
  }

  function renderQuickReplies(items = exampleQuestions[page]) {
    quickReplies.innerHTML = items.slice(0, 4).map((item) => `<button type="button">${esc(item)}</button>`).join("");
  }

  function setPanel(open) {
    panel.hidden = !open;
    launch.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("feather-panel-open", open);
    if (open) {
      appendMessage("assistant", nextGreeting());
      chatInput.focus();
    }
  }

  async function loadStatus() {
    const status = document.getElementById("feather-status");
    try {
      const result = await Yuhen.api("/api/assistant/status");
      available = Boolean(result.available);
      status.textContent = result.message;
      status.classList.toggle("is-online", available);
      launch.classList.toggle("is-offline", !available);
    } catch (error) {
      status.textContent = error.message;
    }
    document.querySelectorAll(
      "#feather-panel .feather-action, #feather-species-extract, #feather-species-research",
    ).forEach((button) => {
      button.disabled = !available;
    });
  }

  launch.addEventListener("click", () => setPanel(panel.hidden));
  panel.querySelector(".feather-panel-close").addEventListener("click", () => setPanel(false));
  panel.querySelectorAll("[data-feather-mode]").forEach((button) => button.addEventListener("click", () => {
    chatMode = button.dataset.featherMode;
    panel.querySelectorAll("[data-feather-mode]").forEach((item) => item.classList.toggle("is-active", item === button));
    const searching = chatMode === "search";
    modeNote.textContent = searching
      ? "描述日期、多个物种、目科属种、地点、远征或同框关系，我会查询并展示实际命中的记录。"
      : `可以自由聊天；涉及本项目功能时会参考${pageNames[page]}的说明。`;
    chatInput.placeholder = searching ? "例如：查询2024年4月5日拍到的白头鹎和灰喜鹊" : "给飞羽精灵发送消息…";
    renderQuickReplies(searching ? ["查询最近的多物种照片", "查看2024年4月5日的全部记录", "查询鸦科的所有记录"] : undefined);
    chatInput.focus();
  }));

  async function sendChatMessage(rawText) {
    const text = rawText.trim();
    if (!available || !text) return;
    appendMessage("user", text);
    chatInput.value = "";
    chatSend.disabled = true;
    const pendingText = chatMode === "search" ? "正在追踪这些田野线索…" : "正在翻阅随身手册…";
    const pending = appendMessage("assistant", pendingText, true);
    try {
      if (chatMode === "search") {
        const result = await Yuhen.api("/api/assistant/search-parse", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: text }),
        });
        document.dispatchEvent(new CustomEvent("feather:apply-observation-search", { detail: result }));
        const warnings = result.warnings.length ? `\n${result.warnings.join("\n")}` : "";
        resolveMessage(pending, `${result.answer}\n${result.interpretation}${warnings}`);
      } else {
        chatHistory.push({ role: "user", content: text });
        chatHistory = chatHistory.slice(-12);
        const result = await Yuhen.api("/api/assistant/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page, messages: chatHistory }),
        });
        chatHistory.push({ role: "assistant", content: result.answer });
        chatHistory = chatHistory.slice(-12);
        resolveMessage(pending, result.answer);
        renderQuickReplies(result.suggestions.length ? result.suggestions : undefined);
      }
    } catch (error) {
      resolveMessage(pending, `这条线索暂时没有回应：${error.message}`, true);
      if (chatMode === "chat" && chatHistory.at(-1)?.role === "user") chatHistory.pop();
    } finally {
      chatSend.disabled = !available;
      chatInput.focus();
    }
  }

  document.getElementById("feather-composer").addEventListener("submit", (event) => {
    event.preventDefault();
    sendChatMessage(chatInput.value);
  });
  chatInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendChatMessage(chatInput.value);
    }
  });
  quickReplies.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) sendChatMessage(button.textContent);
  });
  renderQuickReplies();
  document.addEventListener("feather:reload-status", loadStatus);

  function injectSpeciesExtractor() {
    const fields = document.getElementById("new-species-fields");
    if (!fields) return;
    const inline = document.createElement("section");
    inline.className = "feather-inline full-field";
    inline.innerHTML = `
      <span class="feather-inline-badge">FEATHER ASSISTED ENTRY</span>
      <h3>让飞羽精灵查阅本地资料</h3>
      <p>输入鸟名可检索本地论文与书籍；也可以粘贴一段资料直接识别。结果均先预览，不会直接保存。</p>
      <input id="feather-species-query" maxlength="300" placeholder="例如：蓝歌鸲" autocomplete="off" />
      <textarea id="feather-species-source" maxlength="6000" placeholder="或者粘贴包含目、科、属、种、拉丁学名或亚种信息的资料…"></textarea>
      <div class="feather-actions"><button class="feather-action" id="feather-species-research" type="button" disabled>查阅本地资料</button><button class="feather-action" id="feather-species-extract" type="button" disabled>识别粘贴内容</button></div>
      <div class="feather-result" id="feather-species-result" hidden></div>`;
    fields.prepend(inline);
    const source = document.getElementById("feather-species-source");
    const query = document.getElementById("feather-species-query");
    const researchButton = document.getElementById("feather-species-research");
    const button = document.getElementById("feather-species-extract");
    const result = document.getElementById("feather-species-result");
    button.disabled = !available;
    researchButton.disabled = !available;
    function renderExtraction(data, citations = []) {
      extraction = data;
      const rows = [
        ["目", data.order], ["科", data.family], ["属", data.genus], ["种", data.species],
        ["亚种", { chinese_name: data.subspecies.map((item) => item.chinese_name).filter(Boolean).join("、"), scientific_name: data.subspecies.map((item) => item.scientific_name).filter(Boolean).join("、") }],
      ];
      const sources = citations.length ? `<details class="feather-citations"><summary>查看 ${citations.length} 条本地资料证据</summary>${citations.map((item) => `<article><b>${esc(item.title)}</b><small>${esc(item.locator)} · ${esc(item.source_id)}</small><p>${esc(item.excerpt)}</p></article>`).join("")}</details>` : "";
      result.innerHTML = `<strong>填写建议</strong><div class="feather-extraction-grid">${rows.map(([label, item]) => `<span><small>${label}</small><b>${esc([item.chinese_name, item.scientific_name].filter(Boolean).join(" · ") || "资料不足")}</b></span>`).join("")}</div>${data.warnings.length ? `<ul>${data.warnings.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>` : ""}${sources}<div class="feather-actions"><button class="feather-action" type="button" data-feather-fill-species>填写到表单</button></div>`;
    }
    researchButton.addEventListener("click", async () => {
      if (!available || !query.value.trim()) return;
      researchButton.disabled = true;
      researchButton.textContent = "正在查阅…";
      result.hidden = false;
      result.innerHTML = "<p>我正在本地书架中寻找能够直接支持分类字段的证据…</p>";
      try {
        const response = await Yuhen.api("/api/assistant/taxonomy-research", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: query.value }),
        });
        renderExtraction(response.extraction, response.citations);
      } catch (error) {
        result.innerHTML = `<strong>查阅未完成</strong><p>${esc(error.message)}</p>`;
      } finally {
        researchButton.disabled = !available;
        researchButton.textContent = "查阅本地资料";
      }
    });
    button.addEventListener("click", async () => {
      if (!available || !source.value.trim()) return;
      button.disabled = true;
      button.textContent = "正在识别…";
      result.hidden = false;
      result.innerHTML = "<p>稍等一下，探险家。我正在核对原文里的分类铭文…</p>";
      try {
        const response = await Yuhen.api("/api/assistant/species-extract", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: source.value }),
        });
        renderExtraction(response);
      } catch (error) {
        result.innerHTML = `<strong>识别失败</strong><p>${esc(error.message)}</p>`;
      } finally {
        button.disabled = !available;
        button.textContent = "识别分类字段";
      }
    });
    result.addEventListener("click", (event) => {
      if (event.target.closest("[data-feather-fill-species]") && extraction) fillSpeciesForm(extraction, result);
    });
  }

  function normalized(value) {
    return String(value || "").normalize("NFKC").toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");
  }

  function fillTaxon(level, taxon) {
    if (!taxon || (!taxon.chinese_name && !taxon.scientific_name)) return;
    const select = document.getElementById(`${level}-node-select`);
    if (!select) return;
    const keys = [taxon.chinese_name, taxon.scientific_name].filter(Boolean).map(normalized);
    const match = [...select.options].find((option) => option.value !== "new" && keys.some((key) => normalized(option.textContent).includes(key)));
    select.value = match ? match.value : "new";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    if (!match) {
      const chinese = document.querySelector(`[name="${level}_chinese"]`);
      const scientific = document.querySelector(`[name="${level}_scientific"]`);
      if (chinese && taxon.chinese_name) chinese.value = taxon.chinese_name;
      if (scientific && taxon.scientific_name) scientific.value = taxon.scientific_name;
    }
  }

  function fillSpeciesForm(data, result) {
    fillTaxon("order", data.order);
    fillTaxon("family", data.family);
    fillTaxon("genus", data.genus);
    const chinese = document.querySelector('[name="species_chinese"]');
    const scientific = document.querySelector('[name="species_scientific"]');
    if (chinese && data.species.chinese_name) chinese.value = data.species.chinese_name;
    if (scientific && data.species.scientific_name) scientific.value = data.species.scientific_name;
    if (data.subspecies.length) {
      const checkbox = document.getElementById("has-subspecies");
      checkbox.checked = true;
      checkbox.dispatchEvent(new Event("change", { bubbles: true }));
      const list = document.querySelector('[name="subspecies_list"]');
      list.value = data.subspecies.map((item) => [item.scientific_name, item.chinese_name].filter(Boolean).join(" | ")).filter(Boolean).join("\n");
    }
    result.insertAdjacentHTML("beforeend", '<p><strong>已经抄写到表单了，探险家。请核对后再保存。</strong></p>');
  }

  injectSpeciesExtractor();
  loadStatus();
}());
