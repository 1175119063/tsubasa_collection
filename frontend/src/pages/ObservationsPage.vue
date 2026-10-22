<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, errorMessage } from "@/api/client";
import type { LocationSummary, ObservationRecord, SpeciesSummary } from "@/api/types";
import ObservationCard from "@/components/observations/ObservationCard.vue";
import ObservationDetail from "@/components/observations/ObservationDetail.vue";
const ObservationBatchImport = defineAsyncComponent(() => import("@/components/observations/ObservationBatchImport.vue"));
const ObservationEditor = defineAsyncComponent(() => import("@/components/observations/ObservationEditor.vue"));

interface AssistantSearchDetail { observation_ids?: Array<number | string>; sort?: "asc" | "desc" }

const route = useRoute();
const router = useRouter();
const observations = ref<ObservationRecord[]>([]);
const year = ref("");
const month = ref("");
const locationId = ref("");
const sort = ref<"asc" | "desc">("asc");
const tripId = ref<number | null>(null);
const speciesId = ref<number | null>(null);
const multiSpeciesOnly = ref(false);
const queryIds = ref<Set<number> | null>(null);
const loading = ref(true);
const error = ref("");
const dialog = ref<HTMLDialogElement>();
const selected = ref<ObservationRecord | null>(null);
const speciesIndex = ref(0);
const species = ref<SpeciesSummary[]>([]); const editorDialog = ref<HTMLDialogElement>(); const editorOpen = ref(false);
const locationsArchive = ref<LocationSummary[]>([]);
const batchDialog = ref<HTMLDialogElement>();
const batchImport = ref<InstanceType<typeof ObservationBatchImport>>();
const batchOpen = ref(false);
const expandedMonths = ref(new Set<string>());
const monthPreviewLimit = 5;

// Determine first encounters from the full journal, before filtering or folding months.
const firstEncounterIds = computed(() => {
  const firstBySpecies = new Map<number, ObservationRecord>();
  for (const item of observations.value) {
    const entries = item.species_entries?.length ? item.species_entries : [{ species_id: item.species_id }];
    for (const entry of entries) {
      const previous = firstBySpecies.get(entry.species_id);
      if (!previous || item.observed_at < previous.observed_at
        || (item.observed_at === previous.observed_at && item.id < previous.id)) {
        firstBySpecies.set(entry.species_id, item);
      }
    }
  }
  return new Set([...firstBySpecies.values()].map((item) => item.id));
});

function toggleMonth(key: string): void {
  if (expandedMonths.value.has(key)) expandedMonths.value.delete(key);
  else expandedMonths.value.add(key);
}

const years = computed(() => [...new Set(observations.value.map((item) => item.observed_at.slice(0, 4)))].sort());
const months = computed(() => [...new Set(observations.value.filter((item) => !year.value || item.observed_at.startsWith(`${year.value}-`)).map((item) => item.observed_at.slice(5, 7)))].sort());
const locations = computed(() => {
  const values = new Map<number, string>();
  observations.value.forEach((item) => { if (item.location) values.set(item.location.id, item.location.name); });
  return [...values].map(([id, name]) => ({ id, name }));
});
const filtered = computed(() => observations.value.filter((item) => {
  const entries = item.species_entries?.length ? item.species_entries : [{ species_id: item.species_id }];
  return (!year.value || item.observed_at.slice(0, 4) === year.value)
    && (!month.value || item.observed_at.slice(5, 7) === month.value)
    && (!locationId.value || String(item.location?.id) === locationId.value)
    && (!tripId.value || item.trip?.id === tripId.value)
    && (!speciesId.value || entries.some((entry) => entry.species_id === speciesId.value))
    && (!multiSpeciesOnly.value || entries.length > 1)
    && (queryIds.value === null || queryIds.value.has(item.id));
}).sort((a, b) => a.observed_at.localeCompare(b.observed_at) * (sort.value === "desc" ? -1 : 1)));
const groups = computed(() => {
  const result = new Map<string, ObservationRecord[]>();
  filtered.value.forEach((item) => {
    const key = item.observed_at.slice(0, 7);
    if (!result.has(key)) result.set(key, []);
    result.get(key)?.push(item);
  });
  return [...result].map(([key, items]) => ({ key, items }));
});
const countLabel = computed(() => filtered.value.length === observations.value.length ? observations.value.length : `${filtered.value.length}/${observations.value.length}`);

watch(year, () => { if (!months.value.includes(month.value)) month.value = ""; });
watch([year, month, locationId, sort, tripId, speciesId, multiSpeciesOnly, queryIds], () => {
  expandedMonths.value.clear();
});

async function loadObservations(): Promise<void> {
  loading.value = true; error.value = "";
  try { [observations.value, species.value, locationsArchive.value] = await Promise.all([api<ObservationRecord[]>("/api/observations"), api<SpeciesSummary[]>("/api/species"), api<LocationSummary[]>("/api/locations")]); }
  catch (caught) { error.value = errorMessage(caught); }
  finally { loading.value = false; }
}

async function openObservation(item: ObservationRecord, index = item.species_entries?.findIndex((entry) => entry.species_id === speciesId.value) ?? 0): Promise<void> {
  selected.value = item;
  const count = item.species_entries?.length || 1;
  speciesIndex.value = Math.max(0, Math.min(index, count - 1));
  await nextTick();
  dialog.value?.showModal();
  const query = { ...route.query };
  delete query.new;
  await router.replace({ query: { ...query, observation: String(item.id) } });
}

function closeObservation(): void {
  dialog.value?.close(); selected.value = null; speciesIndex.value = 0;
  const query = { ...route.query }; delete query.observation;
  void router.replace({ query });
}

function navigateSpecies(direction: -1 | 1): void {
  if (!selected.value) return;
  const count = selected.value.species_entries?.length || 1;
  speciesIndex.value = (speciesIndex.value + direction + count) % count;
}

function reset(): void {
  year.value = ""; month.value = ""; locationId.value = ""; sort.value = "asc";
  tripId.value = null; speciesId.value = null; multiSpeciesOnly.value = false; queryIds.value = null;
  void router.replace({ path: "/observations" });
}

async function openNew(): Promise<void> { batchOpen.value = true; await nextTick(); batchDialog.value?.showModal(); }
function closeBatch(): void {
  batchDialog.value?.close(); batchOpen.value = false;
  if (route.query.new) { const query = { ...route.query }; delete query.new; void router.replace({ query }); }
  void loadObservations();
}
async function openEditor(): Promise<void> { if (!selected.value) return; editorOpen.value = true; await nextTick(); editorDialog.value?.showModal(); }
function closeEditor(): void { editorDialog.value?.close(); editorOpen.value = false; }
function editorUpdated(updated: ObservationRecord): void { const index = observations.value.findIndex((item) => item.id === updated.id); if (index >= 0) observations.value[index] = updated; selected.value = updated; speciesIndex.value = Math.min(speciesIndex.value, updated.species_entries.length - 1); }

async function deleteObservation(): Promise<void> {
  if (!selected.value || !window.confirm("这会永久删除该观察及其照片、录音；若它是物种的最后一笔记录，物种档案也会一并删除。确定继续吗？")) return;
  const id = selected.value.id;
  try {
    await api(`/api/observations/${id}`, { method: "DELETE" });
    closeObservation();
    await loadObservations();
  } catch (caught) { error.value = errorMessage(caught); }
}

function handleAssistantSearch(event: Event): void {
  const filters = (event as CustomEvent<AssistantSearchDetail>).detail || {};
  queryIds.value = new Set((filters.observation_ids || []).map(Number));
  tripId.value = null; speciesId.value = null; multiSpeciesOnly.value = false;
  year.value = ""; month.value = ""; locationId.value = "";
  if (filters.sort) sort.value = filters.sort;
}

onMounted(async () => {
  const requestedLocation = Number(route.query.location);
  tripId.value = Number(route.query.trip) || null;
  speciesId.value = Number(route.query.species) || null;
  multiSpeciesOnly.value = route.query.multi_species === "1";
  await loadObservations();
  if (requestedLocation && locations.value.some((item) => item.id === requestedLocation)) locationId.value = String(requestedLocation);
  const requestedObservation = Number(route.query.observation);
  const target = observations.value.find((item) => item.id === requestedObservation);
  if (target) await openObservation(target);
  else if (route.query.new === "1") await openNew();
  document.addEventListener("feather:apply-observation-search", handleAssistantSearch);
});

onBeforeUnmount(() => document.removeEventListener("feather:apply-observation-search", handleAssistantSearch));
</script>

<template>
  <main class="v2-archive-layout observations-page">
    <div class="v2-sidebar-column"><aside class="v2-archive-sidebar">
      <div class="v2-book-tab">FIELD NOTES</div><p class="v2-kicker">野外调查手记</p><h1>田野记录</h1>
      <p class="v2-filter-intro">按拍摄月份翻阅每一次真实相遇。照片、时间与地点共同构成调查凭证。</p>
      <div class="observation-filters">
      <div class="observation-filter-field"><label for="vue-observation-year">年份</label><select id="vue-observation-year" v-model="year"><option value="">全部年份</option><option v-for="item in years" :key="item" :value="item">{{ item }}年</option></select></div>
      <div class="observation-filter-field"><label for="vue-observation-month">月份</label><select id="vue-observation-month" v-model="month"><option value="">全部月份</option><option v-for="item in months" :key="item" :value="item">{{ Number(item) }}月</option></select></div>
      <div class="observation-filter-field"><label for="vue-observation-location">调查区域</label><select id="vue-observation-location" v-model="locationId"><option value="">全部区域</option><option v-for="item in locations" :key="item.id" :value="String(item.id)">{{ item.name }}</option></select></div>
      <div class="observation-filter-field"><label for="vue-observation-sort">装订顺序</label><select id="vue-observation-sort" v-model="sort"><option value="asc">从早到晚</option><option value="desc">从晚到早</option></select></div>
      <button class="v2-filter-reset" type="button" @click="reset">清除检索条件</button>
      <a class="v2-filter-reset" href="/api/exports/observations.csv" download>导出田野记录 CSV</a>
      </div>
      <div class="v2-book-count"><strong>{{ countLabel }}</strong><span>页田野记录</span></div>
    </aside></div>
    <section class="v2-archive-content">
      <header class="v2-dex-header"><div><p class="v2-kicker">按时间装订 · {{ filtered.length }} 笔观察</p><h2>沿着日期重返现场</h2></div><button class="v2-new-entry" type="button" @click="openNew">＋ 登记新发现</button></header>
      <p v-if="loading" class="v2-loading">正在整理田野手记…</p><p v-else-if="error" class="v2-loading">{{ error }}</p>
      <div v-else class="v2-record-groups">
        <section v-for="group in groups" :key="group.key" class="v2-month-section">
          <header>
            <div><span>{{ group.key.slice(0, 4) }}</span><h3>{{ Number(group.key.slice(5, 7)) }}月调查记录</h3></div>
            <button v-if="group.items.length > monthPreviewLimit" class="observation-month-toggle" type="button" :aria-expanded="expandedMonths.has(group.key)" :aria-controls="`month-records-${group.key}`" @click="toggleMonth(group.key)">共 {{ group.items.length }} 页，点击{{ expandedMonths.has(group.key) ? '收起' : '展开' }}</button>
            <b v-else>共 {{ group.items.length }} 页</b>
          </header>
          <div :id="`month-records-${group.key}`" class="v2-field-grid"><ObservationCard v-for="item in (expandedMonths.has(group.key) ? group.items : group.items.slice(0, monthPreviewLimit))" :key="item.id" :observation="item" :is-first-encounter="firstEncounterIds.has(item.id)" @click="openObservation(item)" /></div>
        </section>
      </div>
      <div v-if="!loading && !error && !filtered.length" class="v2-empty"><strong>{{ observations.length ? '没有符合条件的记录' : '从一次相遇开始' }}</strong><span>{{ observations.length ? '换一个月份或区域，重新翻阅田野记录。' : '添加一张照片，记下你遇见的第一只鸟。' }}</span><button class="v2-button v2-button-primary" type="button" @click="observations.length ? reset() : openNew()">{{ observations.length ? '查看全部记录' : '登记第一笔观察' }}</button></div>
    </section>
  </main>
  <dialog ref="dialog" class="v2-archive-dialog observation-detail-dialog" @cancel.prevent="closeObservation" @click.self="closeObservation">
    <ObservationDetail v-if="selected" :observation="selected" :species-index="speciesIndex" @close="closeObservation" @previous="navigateSpecies(-1)" @next="navigateSpecies(1)" @edit="openEditor" @delete="deleteObservation" />
  </dialog>
  <dialog ref="editorDialog" class="record-dialog observation-entry-dialog observation-editor-dialog" @click.self="closeEditor"><ObservationEditor v-if="editorOpen && selected" :observation="selected" :species="species" :initial-index="speciesIndex" @close="closeEditor" @updated="editorUpdated" /></dialog>
  <dialog ref="batchDialog" class="batch-dialog" @cancel.prevent="batchImport?.requestClose()" @click.self="batchImport?.requestClose()">
    <ObservationBatchImport v-if="batchOpen" ref="batchImport" :species="species" :locations="locationsArchive" @close="closeBatch" @changed="loadObservations" />
  </dialog>
</template>

<style scoped>
.batch-dialog{width:min(1380px,96vw);max-width:96vw;max-height:94vh;padding:0;border:1px solid #8e7955}
@media(max-width:760px){.batch-dialog{width:98vw;max-width:98vw}}
</style>
