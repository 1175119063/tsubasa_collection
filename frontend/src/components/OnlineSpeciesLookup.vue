<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { OnlineSpeciesResult, OnlineTaxon, OnlineTaxonomyDraft } from "@/api/online-species";

const props = defineProps<{ allowApply?: boolean; applyMessage?: string }>();
const emit = defineEmits<{ apply: [draft: OnlineTaxonomyDraft] }>();
const query = ref("");
const enabled = ref(false);
const status = ref("正在检查联网查询设置…");
const busy = ref(false);
const result = ref<OnlineSpeciesResult | null>(null);
const selected = ref<OnlineTaxon | null>(null);
const message = ref("");
const applied = ref(false);
const nameSource = computed(() => result.value?.resolved ? result.value.wikidata
  : result.value?.candidates.find((item) => item.id === selected.value?.id)?.name_source);
const labels = { order: "目", family: "科", genus: "属", species: "种" } as const;
const rows = computed(() => selected.value
  ? (Object.keys(labels) as Array<keyof typeof labels>).map((key) => ({
    label: labels[key], ...selected.value!.draft[key],
  })) : []);

function sourceLink(value: string | null | undefined): string | undefined {
  try {
    const url = new URL(value || "");
    if (url.protocol === "https:" && ["www.inaturalist.org", "api.inaturalist.org", "www.wikidata.org"].includes(url.hostname)) return url.href;
  } catch { /* Missing provenance is rendered as text. */ }
  return undefined;
}
function timestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? "时间未知" : date.toLocaleString("zh-CN");
}
async function search(): Promise<void> {
  if (busy.value || !enabled.value || query.value.trim().length < 2) return;
  busy.value = true;
  result.value = null;
  selected.value = null;
  applied.value = false;
  message.value = "正在查阅在线物种资料…";
  try {
    result.value = await api<OnlineSpeciesResult>("/api/assistant/online-species/search", jsonRequest("POST", { query: query.value.trim() }));
    selected.value = result.value.taxon;
    message.value = selected.value ? "找到名称匹配，请核对学名与分类。"
      : result.value.candidates.length ? "名称尚未确定，请选择候选查看资料。" : "没有找到可用的鸟类物种。可以尝试完整学名。";
  } catch (error) { message.value = errorMessage(error); }
  finally { busy.value = false; }
}
async function choose(id: number): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  selected.value = null;
  applied.value = false;
  message.value = "正在读取候选详情…";
  try {
    selected.value = await api<OnlineTaxon>(`/api/assistant/online-species/${id}`);
    message.value = "已打开所选候选，请核对这是否是你要记录的物种。";
  } catch (error) { message.value = errorMessage(error); }
  finally { busy.value = false; }
}
function apply(): void {
  if (!selected.value || busy.value) return;
  emit("apply", selected.value.draft);
  applied.value = true;
}
onMounted(async () => {
  try {
    const value = await api<{ available: boolean; message: string }>("/api/assistant/online-species/status");
    enabled.value = value.available;
    status.value = value.message;
  } catch (error) { status.value = errorMessage(error); }
});
</script>

<template>
  <section class="online-species" aria-label="联网物种查询" :aria-busy="busy">
    <div class="online-intro"><span>ONLINE FIELD GUIDE</span><h3>让鸟名成为一条线索</h3><p>{{ status }}</p></div>
    <div class="online-search">
      <label>鸟名或完整学名<input v-model="query" data-online-query maxlength="300" placeholder="例如：喜鹊 / Pica serica" :disabled="busy" @keydown.enter.prevent="search" /></label>
      <button type="button" data-online-search :disabled="!enabled || busy || query.trim().length < 2" @click="search">{{ busy ? "查询中…" : "查物种" }}</button>
    </div>
    <p v-if="message" class="online-message" role="status">{{ message }}</p>
    <ul v-if="result?.warnings.length" class="online-warnings"><li v-for="warning in result.warnings" :key="warning">{{ warning }}</li></ul>
    <div v-if="result?.candidates.length" class="online-candidates" aria-label="物种候选">
      <button v-for="candidate in result.candidates" :key="candidate.id" type="button" :disabled="busy" :class="{ selected: selected?.id === candidate.id }" @click="choose(candidate.id)"><strong>{{ candidate.common_name || candidate.name }}</strong><em>{{ candidate.name }}</em><span>查看资料 ↗</span></button>
    </div>
    <article v-if="selected" class="online-detail" data-online-detail>
      <header><small>iNaturalist · #{{ selected.id }}</small><h4>{{ selected.common_name || selected.name }}</h4><em>{{ selected.name }}</em></header>
      <dl><div v-for="row in rows" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.chinese_name || "中文名待补充" }}<em>{{ row.scientific_name || "学名待补充" }}</em></dd></div></dl>
      <p class="online-source"><a :href="sourceLink(selected.url)" target="_blank" rel="noopener noreferrer">查看 iNaturalist 原始条目 ↗</a><a :href="sourceLink(selected.source_url)" target="_blank" rel="noopener noreferrer">数据来源 ↗</a><span>{{ selected.cached ? "缓存资料 · 获取于" : "资料获取于" }} {{ timestamp(selected.fetched_at) }}</span></p>
      <p v-if="nameSource" class="online-source"><a :href="sourceLink(nameSource.source_url)" target="_blank" rel="noopener noreferrer">Wikidata 名称依据 ↗</a><span>{{ timestamp(nameSource.fetched_at) }}{{ nameSource.cached ? " · 缓存" : "" }}</span></p>
      <details v-if="selected.summary || selected.conservation.length || selected.photo"><summary>简介与补充资料</summary><p v-if="selected.summary">{{ selected.summary }}</p><ul v-if="selected.conservation.length"><li v-for="(item, index) in selected.conservation" :key="index">{{ [item.authority, item.status, item.place].filter(Boolean).join(" · ") }}</li></ul><p v-if="selected.photo" class="online-muted">来源图片署名：{{ selected.photo.attribution || "未提供" }}；许可：{{ selected.photo.license || "未提供" }}。</p></details>
      <template v-if="props.allowApply"><p class="online-muted">只补充空白分类字段；已有内容、亚种、保护等级和备注由你核对填写。分类冲突或资料不完整时停止填入。</p><button class="online-apply" type="button" data-online-apply :disabled="busy" @click="apply">{{ applied ? "重新检查并填入空白字段" : "核对后填入空白分类字段" }}</button><p v-if="applied && props.applyMessage" class="online-message" role="status">{{ props.applyMessage }}</p></template>
      <p v-else class="online-muted">可在「登记新发现 → 新物种」中查阅并填入分类资料。</p>
    </article>
  </section>
</template>

<style scoped>
.online-species{padding:20px;min-width:0;background:#f7f5ed;color:#263e39;font:13px/1.6 "Microsoft YaHei",sans-serif;overflow-wrap:anywhere}
.online-intro>span{font-size:9px;letter-spacing:.15em;color:#8d7450}.online-intro h3{font-size:20px;font-weight:500;margin:5px 0 8px}.online-intro p,.online-muted{font-size:12px;color:#70776e;margin:8px 0 12px}
.online-search{display:flex;align-items:flex-end;gap:8px}.online-search label{display:grid;gap:5px;flex:1;min-width:0;font-size:12px}.online-search input{box-sizing:border-box;width:100%;min-height:40px;padding:9px 10px;border:1px solid #bcc9bd;background:#fffef9;color:#263e39;border-radius:4px}.online-species button{cursor:pointer;font:inherit}.online-search button,.online-apply{border:1px solid #365d51;border-radius:4px;background:#365d51;color:#fffdf4;padding:9px 12px;white-space:normal}.online-search button{flex:0 0 auto;min-height:40px}.online-species button:disabled{opacity:.5;cursor:default}.online-message{padding:10px 0;margin:0;color:#526657}.online-warnings{padding-left:20px;color:#7e694a;font-size:12px}.online-candidates{display:grid;gap:8px;margin:10px 0}.online-candidates button{text-align:left;padding:12px;background:#fffef8;color:#304c40;border:1px solid #d7ddcf;border-radius:5px}.online-candidates button.selected{border-color:#45786a;box-shadow:inset 3px 0 #45786a}.online-candidates strong,.online-candidates em{display:block}.online-candidates span{font-size:11px;color:#697965}.online-detail{margin-top:14px;padding:16px;background:#fffef9;border:1px solid #d7ddcf;border-radius:6px}.online-detail header small{color:#8d7450;font-size:10px}.online-detail h4{margin:4px 0 0;font-size:24px;font-weight:500}.online-detail em{color:#657767;font-family:Georgia,serif;font-weight:normal}.online-detail dl{margin:16px 0}.online-detail dl>div{display:grid;grid-template-columns:26px 1fr;gap:8px;border-top:1px solid #e4e6db;padding:8px 0}.online-detail dt{color:#8a856f}.online-detail dd{margin:0}.online-detail dd em{display:block}.online-source{display:flex;flex-wrap:wrap;gap:5px 12px;font-size:11px}.online-source a{color:#3d7166;text-decoration:underline}.online-source span{flex-basis:100%;color:#7f8275}.online-detail details{margin:14px 0;font-size:12px}.online-detail summary{cursor:pointer;color:#526958}.online-detail details p{max-height:240px;overflow:auto;white-space:pre-line}.online-apply{width:100%;margin-top:4px}
@media(max-width:480px){.online-species{padding:14px}.online-detail{padding:12px}.online-search{flex-wrap:wrap}.online-search label{flex-basis:100%}.online-search button{width:100%}}
</style>
