<script setup lang="ts">
import { computed } from "vue";

export interface DossierObservation {
  id: number;
  observed_at: string;
  locality: string;
  admin1_name: string;
  thumbnail_url: string;
  sex?: string | null;
  life_stage?: string | null;
  subspecies?: { id: number } | null;
  audio?: Array<{ url: string }>;
}

export interface IntelItem {
  id?: string | number;
  name?: string;
  label?: string;
  value?: string;
  observation_id?: number | null;
  linked?: boolean;
}

export interface SpeciesDetail {
  id: number;
  catalog_number: string;
  chinese_name: string;
  scientific_name: string;
  iucn_status: string;
  observation_count: number;
  introduction?: string | null;
  has_subspecies: boolean;
  classification: Record<"order" | "family" | "genus", { chinese_name: string; scientific_name: string }>;
  cover: { observation_id: number; photo_url: string };
  first_encounter: { observation_id: number; observed_at: string; admin1_name: string; locality: string };
  ecology: { group: string; body_size: string; habitats: string[] };
  observations: DossierObservation[];
  species_audio: Array<{ id: number; title?: string | null; recorded_at?: string | null; locality?: string | null; notes?: string | null; url: string }>;
  collected: { admin1_regions: IntelItem[]; seasons: IntelItem[]; sexes: IntelItem[]; life_stages: IntelItem[] };
  individuals: IntelItem[];
  behaviors: IntelItem[];
  subspecies: Array<{ id: number; chinese_name?: string | null; scientific_name: string; captured: boolean; observation_id?: number | null }>;
}

const props = defineProps<{ detail: SpeciesDetail }>();
const emit = defineEmits<{
  close: [];
  setCover: [observationId: number];
  deleteObservation: [observationId: number];
  edit: [];
  addAudio: [];
  deleteAudio: [audioId: number];
}>();

const ecologyLabels: Record<string, string> = { unknown: "情报不足", raptor: "猛禽", songbird: "鸣禽", landfowl: "陆禽", scansorial: "攀禽", wader: "涉禽", waterfowl: "游禽" };
const sizeLabels: Record<string, string> = { unknown: "未知", small: "小型", small_medium: "中小型", medium: "中型", medium_large: "中大型", large: "大型" };
const habitatLabels: Record<string, string> = { city: "城市", farmland: "农田", grassland: "草原", shrub: "灌丛", forest: "森林", wetland: "湿地", river: "河流", lake: "湖泊", desert: "荒漠", coast: "海岸", ocean: "海洋", mudflat: "滩涂", alpine: "高山", other: "其他" };
const iucnLabels: Record<string, string> = { NE: "待定", LC: "无危", NT: "近危", VU: "易危", EN: "濒危", CR: "极危", EW: "野外灭绝", EX: "灭绝" };
const ecologyAssets: Record<string, string> = { raptor: "raptor-silhouette.png", songbird: "songbird-silhouette.png", landfowl: "landfowl-silhouette.png", scansorial: "scansorial-silhouette.png", wader: "wader-silhouette.png", waterfowl: "waterfowl-silhouette.png" };
const bodySizes = ["small", "small_medium", "medium", "medium_large", "large"];

const completeness = computed(() => {
  const detail = props.detail;
  return [
    { label: "分类信息", complete: ["order", "family", "genus"].every((rank) => {
      const node = detail.classification[rank as keyof typeof detail.classification];
      return Boolean(node?.chinese_name?.trim() && node?.scientific_name?.trim());
    }), hint: "目、科、属的中文名与学名" },
    { label: "物种介绍", complete: Boolean(detail.introduction?.trim()), hint: "已填写物种简介" },
    { label: "照片凭证", complete: Boolean(detail.cover.photo_url), hint: "已收录物种照片" },
    { label: "观察地点", complete: detail.observations.some((item) => Boolean(item.locality?.trim() && item.admin1_name?.trim())), hint: "观察中有行政区和具体地点" },
    { label: "声音记录", complete: detail.species_audio.some((item) => Boolean(item.url)) || detail.observations.some((item) => item.audio?.some((audio) => Boolean(audio.url))), hint: "独立物种录音或观察附带录音" },
    { label: "生态习性", complete: Boolean(detail.ecology.group && detail.ecology.group !== "unknown"), hint: "已填写生态类群" },
    { label: "体型大小", complete: Boolean(detail.ecology.body_size && detail.ecology.body_size !== "unknown"), hint: "已填写体型级别" },
    { label: "偏好生境", complete: detail.ecology.habitats.length > 0, hint: "已填写至少一种生境" },
  ];
});
const completedCount = computed(() => completeness.value.filter((item) => item.complete).length);
const recent = computed(() => [...props.detail.observations].sort((a, b) => b.observed_at.localeCompare(a.observed_at)).slice(0, 4));

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value.replace("T", " ") : new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric" }).format(date);
}

function intelText(item: IntelItem): string {
  const labels: Record<string, string> = { spring: "春", summer: "夏", autumn: "秋", winter: "冬", other: "其他" };
  return item.name || item.label || labels[item.value || ""] || item.value || "未知";
}
</script>

<template>
  <button class="v2-dossier-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
  <section class="v2-dossier-hero">
    <div class="v2-dossier-image"><img :src="detail.cover.photo_url" :alt="detail.chinese_name" /></div>
    <div class="v2-dossier-title">
      <p class="v2-kicker">物种档案 · {{ detail.catalog_number }}</p>
      <h2>{{ detail.chinese_name }}</h2><em>{{ detail.scientific_name }}</em>
      <div class="v2-taxonomy-line">{{ detail.classification.order.chinese_name }} / {{ detail.classification.family.chinese_name }} / {{ detail.classification.genus.chinese_name }}</div>
      <div class="v2-status-row"><span class="v2-iucn" :class="`v2-iucn-${detail.iucn_status.toLowerCase()}`">{{ detail.iucn_status }} {{ iucnLabels[detail.iucn_status] }}</span><span>累计 {{ detail.observation_count }} 次记录</span></div>
      <div class="dossier-completeness" tabindex="0" role="group"
        :aria-label="`档案完整度：已完善 ${completedCount} / ${completeness.length} 项。${completeness.map(item => `${item.label}：${item.complete ? '已完善' : '待补充'}`).join('；')}`">
        <div class="dossier-completeness-heading"><strong>档案完整度</strong><span>{{ completedCount }} / {{ completeness.length }} 项 <small>查看构成 ⓘ</small></span></div>
        <div class="dossier-completeness-segments" aria-hidden="true"><span v-for="item in completeness" :key="item.label" :class="{ 'is-complete': item.complete }"></span></div>
        <div class="dossier-completeness-tooltip" aria-hidden="true">
          <strong>资料完善情况</strong><p>每段对应一项资料；亮色为已完善。</p>
          <ul><li v-for="item in completeness" :key="item.label"><span><b>{{ item.label }}</b><small>{{ item.hint }}</small></span><em :class="{ 'is-complete': item.complete }">{{ item.complete ? "✓ 已完善" : "待补充" }}</em></li></ul>
        </div>
      </div>
      <RouterLink class="dossier-first-encounter" :to="{ path: '/observations', query: { observation: detail.first_encounter.observation_id } }">
        <span class="dossier-encounter-label">首次遭遇 <i>查看记录 ↗</i></span>
        <strong>{{ formatDate(detail.first_encounter.observed_at) }}</strong>
        <span>{{ detail.first_encounter.admin1_name }} · {{ detail.first_encounter.locality }}</span>
      </RouterLink>
    </div>
    <div class="v2-ecology-panel">
      <section class="v2-ecology-group"><span class="v2-ecology-label">生态习性</span><div class="v2-ecology-group-row"><span class="v2-ecology-disc"><span v-if="detail.ecology.group === 'unknown'" class="v2-ecology-question">?</span><img v-else :src="`/static/assets/${ecologyAssets[detail.ecology.group]}?v=20260816-1`" alt="" /></span><strong>{{ ecologyLabels[detail.ecology.group] || detail.ecology.group }}</strong></div></section>
      <section class="v2-body-size"><span class="v2-ecology-label">体型大小 · {{ sizeLabels[detail.ecology.body_size] || detail.ecology.body_size }}</span><div class="v2-body-size-row"><span v-for="(size, index) in bodySizes" :key="size" class="v2-body-size-bird" :class="{ 'is-selected': detail.ecology.body_size === size, 'is-unknown': detail.ecology.body_size === 'unknown' }" :style="{ '--v2-bird-width': `${28 + index * 7}px` }"><img :src="'/static/assets/body-size-silhouette.png?v=20260816-1'" alt="" /></span></div></section>
      <section class="v2-habitat-block"><span class="v2-ecology-label">偏好生境</span><div class="v2-habitat-list"><span v-for="item in detail.ecology.habitats" :key="item">{{ habitatLabels[item] || item }}</span><small v-if="!detail.ecology.habitats.length">尚未填写</small></div></section>
    </div>
  </section>
  <section class="v2-dossier-paper">
    <div class="v2-dossier-main">
      <article><p class="v2-kicker">调查者手记</p><h3>物种简介</h3><p class="v2-note-copy">{{ detail.introduction || "尚未填写物种简介。" }}</p></article>
      <article><p class="v2-kicker">最近照片</p><h3>最近的照片凭证</h3><div class="v2-evidence-grid"><RouterLink v-for="item in recent" :key="item.id" :to="{ path: '/observations', query: { observation: item.id } }"><img :src="item.thumbnail_url" alt="" /><span>{{ formatDate(item.observed_at) }}</span></RouterLink></div></article>
      <article><p class="v2-kicker">记录管理</p><h3>观察记录与图鉴封面</h3><div class="v2-dex-observation-grid"><section v-for="item in detail.observations" :key="item.id" class="v2-dex-observation" :class="{ 'is-current': item.id === detail.cover.observation_id }"><RouterLink :to="{ path: '/observations', query: { observation: item.id } }"><img :src="item.thumbnail_url" alt="" /><span>{{ formatDate(item.observed_at) }} · {{ item.locality }}</span></RouterLink><div><button type="button" :disabled="item.id === detail.cover.observation_id" @click="emit('setCover', item.id)">{{ item.id === detail.cover.observation_id ? "当前封面" : "设为封面" }}</button><button type="button" class="is-danger" @click="emit('deleteObservation', item.id)">删除记录</button></div></section></div></article>
      <article><p class="v2-kicker">声音档案</p><h3>独立物种录音</h3><div class="v2-species-audio-list"><section v-for="audio in detail.species_audio" :key="audio.id"><strong>{{ audio.title || "未命名录音" }}</strong><small>{{ audio.recorded_at?.replace("T", " ") || "时间未记录" }}{{ audio.locality ? ` · ${audio.locality}` : "" }}</small><audio controls preload="metadata" :src="audio.url"></audio><p v-if="audio.notes">{{ audio.notes }}</p><button type="button" class="is-danger" @click="emit('deleteAudio', audio.id)">删除录音</button></section><p v-if="!detail.species_audio.length" class="v2-intel-missing">尚未添加独立物种录音。</p></div></article>
    </div>
    <aside class="v2-intel-column">
      <article v-for="section in [{ title: '地理情报', items: detail.collected.admin1_regions }, { title: '季节情报', items: detail.collected.seasons }, { title: '个体档案', items: detail.individuals.filter((item) => !String(item.id).startsWith('observed-')) }, { title: '行为档案', items: detail.behaviors }]" :key="section.title"><h3>{{ section.title }}</h3><div><template v-if="section.items.length"><RouterLink v-for="(item, index) in section.items" :key="index" class="v2-intel-chip" :class="{ 'is-static': !item.observation_id }" :to="item.observation_id ? { path: '/observations', query: { observation: item.observation_id } } : ''">{{ intelText(item) }}{{ item.linked === false ? " · 待关联" : "" }}</RouterLink></template><span v-else class="v2-intel-missing">{{ section.title.replace('情报', '') }}情报不足</span></div></article>
      <article><h3>亚种档案</h3><div><span v-if="!detail.has_subspecies" class="v2-intel-chip is-static">无亚种</span><template v-else><RouterLink v-for="item in detail.subspecies" :key="item.id" class="v2-intel-chip" :class="{ 'is-static is-pending': !item.captured }" :to="item.observation_id ? { path: '/observations', query: { observation: item.observation_id } } : ''">{{ item.chinese_name || item.scientific_name }} · {{ item.captured ? "已拍摄" : "未拍摄" }}</RouterLink></template></div></article>
      <div class="v2-dex-edit-actions"><button class="v2-button v2-button-primary v2-edit-jump" type="button" @click="emit('edit')">修改图鉴</button><button class="v2-button v2-button-ghost" type="button" @click="emit('addAudio')">添加录音</button></div>
    </aside>
  </section>
</template>
