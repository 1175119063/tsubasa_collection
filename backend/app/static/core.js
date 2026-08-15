window.Yuhen = {
  labels: {
    spring: "春", summer: "夏", autumn: "秋", winter: "冬", other: "其他",
    male: "雄性", female: "雌性", egg: "卵", chick: "雏鸟", subadult: "亚成", adult: "成鸟",
    unknown: "未知",
    three_protected: "三有", level_2: "国家二级", level_1: "国家一级",
  },

  escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  },

  async api(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item) => item.msg).join("；")
        : data.detail || `请求失败（${response.status}）`;
      throw new Error(detail);
    }
    return response.json();
  },

  updateStats(stats) {
    const values = {
      "species-count": stats.species_count,
      "observation-count": stats.observation_count,
      "audio-count": stats.audio_count,
    };
    for (const [id, value] of Object.entries(values)) {
      const element = document.getElementById(id);
      if (element) element.textContent = value;
    }
  },
};
