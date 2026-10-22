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
}

export interface IntelItem {
  id?: string | number;
  name?: string;
  label?: string;
  value?: string;
  observation_id?: number | null;
  linked?: boolean;
  observation_ids?: number[];
  observations?: Array<{ observation_id: number; observed_at: string; locality: string }>;
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

const individualLabels: Record<string, string> = { male: "雄性", female: "雌性", egg: "卵", chick: "雏鸟", subadult: "亚成", adult: "成鸟" };
const automaticIndividuals = computed(() => [
  ...props.detail.collected.sexes.map((item) => ({ ...item, label: `性别 · ${individualLabels[item.value || ''] || item.value}` })),
  ...props.detail.collected.life_stages.map((item) => ({ ...item, label: `生命阶段 · ${individualLabels[item.value || ''] || item.value}` })),
]);
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
      <div class="dossier-identity-row">
        <div class="dossier-species-name"><h2>{{ detail.chinese_name }}</h2><em>{{ detail.scientific_name }}</em></div>
      <RouterLink class="dossier-first-encounter" :to="{ path: '/observations', query: { observation: detail.first_encounter.observation_id } }">
        <span class="dossier-encounter-label">首次遭遇 <i>查看记录 ↗</i></span>
        <strong>{{ formatDate(detail.first_encounter.observed_at) }}</strong>
        <span>{{ detail.first_encounter.admin1_name }} · {{ detail.first_encounter.locality }}</span>
      </RouterLink>
      </div>
      <div class="dossier-classification-row">
        <div class="dossier-classification-summary">
      <div class="v2-taxonomy-line">{{ detail.classification.order.chinese_name }} / {{ detail.classification.family.chinese_name }} / {{ detail.classification.genus.chinese_name }}</div>
      <div class="v2-status-row"><span class="v2-iucn" :class="`v2-iucn-${detail.iucn_status.toLowerCase()}`">{{ detail.iucn_status }} {{ iucnLabels[detail.iucn_status] }}</span><span>累计 {{ detail.observation_count }} 次记录</span></div>
        </div>
      <section class="v2-ecology-group"><span class="v2-ecology-label">生态习性</span><div class="v2-ecology-group-row"><span class="v2-ecology-disc"><span v-if="detail.ecology.group === 'unknown'" class="v2-ecology-question">?</span><img v-else :src="`/static/assets/${ecologyAssets[detail.ecology.group]}?v=20260816-1`" alt="" /></span><strong>{{ ecologyLabels[detail.ecology.group] || detail.ecology.group }}</strong></div></section>
      </div>
      <div class="v2-ecology-panel">
      <section class="v2-habitat-block"><span class="v2-ecology-label">偏好生境</span><div class="v2-habitat-list"><span v-for="item in detail.ecology.habitats" :key="item">{{ habitatLabels[item] || item }}</span><small v-if="!detail.ecology.habitats.length">尚未填写</small></div></section>
      <section class="v2-body-size"><span class="v2-ecology-label">体型大小 · {{ sizeLabels[detail.ecology.body_size] || detail.ecology.body_size }}</span><div class="v2-body-size-row"><span v-for="(size, index) in bodySizes" :key="size" class="v2-body-size-bird" :class="{ 'is-selected': detail.ecology.body_size === size, 'is-unknown': detail.ecology.body_size === 'unknown' }" :style="{ '--v2-bird-width': `${28 + index * 7}px` }"><img :src="'/static/assets/body-size-silhouette.png?v=20260816-1'" alt="" /></span></div></section>
      </div>
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
      <article v-for="section in [{ title: '地理情报', items: detail.collected.admin1_regions }, { title: '季节情报', items: detail.collected.seasons }]" :key="section.title"><h3>{{ section.title }}</h3><div><template v-if="section.items.length"><RouterLink v-for="(item, index) in section.items" :key="index" class="v2-intel-chip" :class="{ 'is-static': !item.observation_id }" :to="item.observation_id ? { path: '/observations', query: { observation: item.observation_id } } : ''">{{ intelText(item) }}{{ item.linked === false ? " · 待关联" : "" }}</RouterLink></template><span v-else class="v2-intel-missing">{{ section.title.replace('情报', '') }}情报不足</span></div></article>
      <article><h3>个体档案</h3>
        <section data-profile-evidence="automatic"><h4>观察自动汇总</h4><RouterLink v-for="item in automaticIndividuals" :key="item.label" class="v2-intel-chip" :to="{ path: '/observations', query: { observation: item.observation_id, species: detail.id } }">{{ item.label }}</RouterLink><span v-if="!automaticIndividuals.length" class="v2-intel-missing">尚无已确认的性别或生命阶段。</span></section>
        <section data-profile-evidence="custom"><h4>自定义个体标签</h4><template v-for="item in detail.individuals.filter(v => !String(v.id).startsWith('observed-'))" :key="item.id"><RouterLink v-if="item.linked && item.observation_id" class="v2-intel-chip" :to="{ path: '/observations', query: { observation: item.observation_id, species: detail.id } }">{{ item.label }}</RouterLink><span v-else class="v2-intel-chip is-static">{{ item.label }} · 待关联</span></template></section>
      </article>
      <article class="dossier-behaviors"><h3>行为档案</h3>
        <section v-for="tag in detail.behaviors" :key="tag.id" class="dossier-behavior">
          <strong>{{ tag.label }} <small>· {{ tag.observation_ids?.length || 0 }} 笔观察</small></strong>
          <div v-if="tag.observations?.length"><RouterLink v-for="observation in tag.observations" :key="observation.observation_id" class="v2-intel-chip" :to="{ path: '/observations', query: { observation: observation.observation_id, species: detail.id } }">{{ formatDate(observation.observed_at) }} · {{ observation.locality }}</RouterLink></div>
          <span v-else class="v2-intel-missing">待关联观察</span>
        </section>
        <span v-if="!detail.behaviors.length" class="v2-intel-missing">尚未记录行为，可在田野记录或修改图鉴时添加。</span>
      </article>
      <article><h3>亚种档案</h3><div><span v-if="!detail.has_subspecies" class="v2-intel-chip is-static">无亚种</span><template v-else><RouterLink v-for="item in detail.subspecies" :key="item.id" class="v2-intel-chip" :class="{ 'is-static is-pending': !item.captured }" :to="item.observation_id ? { path: '/observations', query: { observation: item.observation_id } } : ''">{{ item.chinese_name || item.scientific_name }} · {{ item.captured ? "已拍摄" : "未拍摄" }}</RouterLink></template></div></article>
      <div class="v2-dex-edit-actions"><button class="v2-button v2-button-primary v2-edit-jump" type="button" @click="emit('edit')">修改图鉴</button><button class="v2-button v2-button-ghost" type="button" @click="emit('addAudio')">添加录音</button></div>
    </aside>
  </section>
</template>

<style scoped>
[data-profile-evidence] h4 { font-size: 12px; margin: 12px 0 8px; }
.dossier-behavior + .dossier-behavior { margin-top: 16px; }
.dossier-behavior > strong { display: block; margin-bottom: 8px; }
.dossier-behavior small { font-weight: normal; }
</style>
