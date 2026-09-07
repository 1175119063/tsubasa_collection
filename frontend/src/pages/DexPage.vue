<script setup lang="ts">
import { computed, defineAsyncComponent, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { SpeciesSummary, TaxonomyOrder } from "@/api/types";
import DiscoveryCard from "@/components/DiscoveryCard.vue";
import SpeciesAudioForm from "@/components/dex/SpeciesAudioForm.vue";
import SpeciesDossier, { type SpeciesDetail } from "@/components/dex/SpeciesDossier.vue";
import SpeciesProfileForm from "@/components/dex/SpeciesProfileForm.vue";
import TaxonomyExplorer from "@/components/dex/TaxonomyExplorer.vue";
import {
  buildPersonalTaxonomyTree,
  taxonomyKeyFromRoute,
  taxonomyRankLabel,
  type TaxonomyNode,
  type TaxonomyNodeKey,
} from "@/components/dex/taxonomy-model";

const route = useRoute();
const router = useRouter();
const species = ref<SpeciesSummary[]>([]);
const taxonomy = ref<TaxonomyOrder[]>([]);
const query = ref("");
const order = ref("");
const family = ref("");
const genus = ref("");
const taxonomyQuery = ref("");
const loading = ref(true);
const error = ref("");
const dossier = ref<HTMLDialogElement>();
const detail = ref<SpeciesDetail | null>(null);
const detailLoading = ref(false);
const profileDialog = ref<HTMLDialogElement>();
const profileOpen = ref(false);
const audioDialog = ref<HTMLDialogElement>();
const audioOpen = ref(false);
const TaxonomyEditor = defineAsyncComponent(() => import('@/components/dex/TaxonomyEditor.vue'));
const editingTaxonomy = ref<TaxonomyNodeKey | null>(null);
async function taxonomySaved(): Promise<void> {
  editingTaxonomy.value = null;
  await loadSpecies();
  await refreshDetail();
}
let detailRequest = 0;

const orders = computed(() => [...new Set(species.value.map((item) => item.order_name))].sort());
const families = computed(() => [...new Set(species.value
  .filter((item) => !order.value || item.order_name === order.value)
  .map((item) => item.family_name))].sort());
const genera = computed(() => [...new Set(species.value
  .filter((item) => (!order.value || item.order_name === order.value)
    && (!family.value || item.family_name === family.value))
  .map((item) => item.genus_name))].sort());
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return species.value.filter((item) => `${item.catalog_number} ${item.chinese_name} ${item.scientific_name} ${item.family_name} ${item.genus_name}`
    .toLocaleLowerCase().includes(needle)
    && (!order.value || item.order_name === order.value)
    && (!family.value || item.family_name === family.value)
    && (!genus.value || item.genus_name === genus.value));
});

const taxonomyMode = computed(() => route.query.view === "taxonomy");
const personalTree = computed(() => buildPersonalTaxonomyTree(taxonomy.value, species.value));
const requestedTaxonomyKey = computed(() => taxonomyKeyFromRoute(route.query.rank, route.query.node));
const currentTaxonomyKey = computed<TaxonomyNodeKey>(() => {
  const requested = requestedTaxonomyKey.value;
  return requested && personalTree.value.nodes[requested] ? requested : personalTree.value.rootKey;
});
const taxonomySearchResults = computed<TaxonomyNode[]>(() => {
  const needle = taxonomyQuery.value.trim().toLocaleLowerCase();
  if (!needle) return [];
  return Object.values(personalTree.value.nodes)
    .filter((node) => node.key !== personalTree.value.rootKey
      && `${node.chineseName} ${node.scientificName} ${node.catalogNumber || ""}`
        .toLocaleLowerCase().includes(needle))
    .sort((a, b) => a.chineseName.localeCompare(b.chineseName, "zh-CN"))
    .slice(0, 8);
});
const taxonomyStats = computed(() => {
  const nodes = Object.values(personalTree.value.nodes);
  return {
    order: nodes.filter((node) => node.rank === "order").length,
    family: nodes.filter((node) => node.rank === "family").length,
    genus: nodes.filter((node) => node.rank === "genus").length,
  };
});

watch(order, () => { if (!families.value.includes(family.value)) family.value = ""; });
watch(family, () => { if (!genera.value.includes(genus.value)) genus.value = ""; });

watch(
  [taxonomyMode, loading, () => route.query.rank, () => route.query.node, personalTree],
  ([enabled, isLoading]) => {
    if (!enabled || isLoading) return;
    const requested = requestedTaxonomyKey.value;
    if (requested && personalTree.value.nodes[requested]) return;
    void router.replace({
      query: { ...route.query, view: "taxonomy", rank: "class", node: "aves" },
    });
  },
  { immediate: true },
);

watch(
  [() => route.query.species, loading],
  ([value, isLoading]) => {
    if (isLoading) return;
    const requested = Number(value);
    if (requested && species.value.some((item) => item.id === requested)) {
      void displayDossier(requested);
    } else if (!requested) {
      hideDossier();
    }
  },
  { immediate: true },
);

async function loadSpecies(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    [species.value, taxonomy.value] = await Promise.all([
      api<SpeciesSummary[]>("/api/species"),
      api<TaxonomyOrder[]>("/api/taxonomy/tree"),
    ]);
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    loading.value = false;
  }
}

async function displayDossier(speciesId: number): Promise<void> {
  if (detail.value?.id === speciesId && dossier.value?.open) return;
  const request = ++detailRequest;
  detailLoading.value = true;
  detail.value = null;
  if (!dossier.value?.open) dossier.value?.showModal();
  try {
    const loaded = await api<SpeciesDetail>(`/api/species/${speciesId}`);
    if (request === detailRequest) detail.value = loaded;
  } catch (caught) {
    if (request === detailRequest) error.value = errorMessage(caught);
  } finally {
    if (request === detailRequest) detailLoading.value = false;
  }
}

async function openDossier(speciesId: number): Promise<void> {
  await router.replace({ query: { ...route.query, species: String(speciesId) } });
}

function hideDossier(): void {
  detailRequest += 1;
  dossier.value?.close();
  detail.value = null;
  detailLoading.value = false;
}

function closeDossier(): void {
  hideDossier();
  const nextQuery = { ...route.query };
  delete nextQuery.species;
  void router.replace({ query: nextQuery });
}

async function refreshDetail(): Promise<void> {
  if (detail.value) detail.value = await api<SpeciesDetail>(`/api/species/${detail.value.id}`);
}

async function setCover(observationId: number): Promise<void> {
  if (!detail.value) return;
  await api(`/api/species/${detail.value.id}/cover`, jsonRequest("PUT", { observation_id: observationId }));
  await Promise.all([refreshDetail(), loadSpecies()]);
}

async function deleteObservation(observationId: number): Promise<void> {
  if (!window.confirm("删除将立即永久生效；若这是最后一笔观察，整个物种档案也会被删除。确定继续吗？")) return;
  const result = await api<{ removed_species: boolean }>(`/api/observations/${observationId}`, { method: "DELETE" });
  await loadSpecies();
  if (result.removed_species) closeDossier();
  else await refreshDetail();
}

async function deleteAudio(audioId: number): Promise<void> {
  if (!detail.value || !window.confirm("永久删除这段独立物种录音吗？")) return;
  await api(`/api/species/${detail.value.id}/audio/${audioId}`, { method: "DELETE" });
  await refreshDetail();
}

function reset(): void {
  query.value = "";
  order.value = "";
  family.value = "";
  genus.value = "";
}

async function enterTaxonomy(): Promise<void> {
  hideDossier();
  const nextQuery = { ...route.query };
  delete nextQuery.species;
  await router.push({ query: { ...nextQuery, view: "taxonomy", rank: "class", node: "aves" } });
}

async function leaveTaxonomy(): Promise<void> {
  hideDossier();
  const nextQuery = { ...route.query };
  delete nextQuery.view;
  delete nextQuery.rank;
  delete nextQuery.node;
  delete nextQuery.species;
  await router.push({ query: nextQuery });
}

async function selectTaxonomyNode(key: TaxonomyNodeKey): Promise<void> {
  const node = personalTree.value.nodes[key];
  if (!node) return;
  await router.push({
    query: {
      ...route.query,
      view: "taxonomy",
      rank: node.rank,
      node: node.sourceId,
    },
  });
}

async function viewSpeciesObservations(speciesId: number): Promise<void> {
  await router.push({ path: "/observations", query: { species: String(speciesId) } });
}

async function openProfileEditor(): Promise<void> {
  if (!detail.value) return;
  profileOpen.value = true;
  await nextTick();
  profileDialog.value?.showModal();
}
function closeProfileEditor(): void { profileDialog.value?.close(); profileOpen.value = false; }
async function profileSaved(saved: SpeciesDetail): Promise<void> { closeProfileEditor(); detail.value = saved; await loadSpecies(); }
async function openAudioForm(): Promise<void> {
  if (!detail.value) return;
  audioOpen.value = true;
  await nextTick();
  audioDialog.value?.showModal();
}
function closeAudioForm(): void { audioDialog.value?.close(); audioOpen.value = false; }
async function audioSaved(): Promise<void> { closeAudioForm(); await refreshDetail(); }

onMounted(loadSpecies);
</script>

<template>
  <main class="v2-dex-layout" :class="{ 'is-taxonomy-view': taxonomyMode }">
    <div class="v2-sidebar-column"><aside class="v2-filter-book">
      <template v-if="taxonomyMode">
        <div class="v2-book-tab">TAXONOMY</div>
        <p class="v2-kicker">LIVING CLASSIFICATION</p>
        <h1>个人分类树</h1>
        <p class="v2-filter-intro">它不从完整名录抄写而来，而是随你的每一次观察逐级生长。</p>
        <label class="v2-search-label" for="vue-taxonomy-search">寻找分类节点</label>
        <input id="vue-taxonomy-search" v-model="taxonomyQuery" type="search" placeholder="中文名、拉丁名或图鉴编号" />
        <div v-if="taxonomyQuery" class="v2-taxonomy-search-results">
          <button v-for="node in taxonomySearchResults" :key="node.key" type="button" @click="selectTaxonomyNode(node.key)">
            <span>{{ taxonomyRankLabel(node.rank) }}</span>
            <strong>{{ node.chineseName }}</strong>
            <em>{{ node.scientificName }}</em>
          </button>
          <p v-if="!taxonomySearchResults.length">没有找到已解锁的分类节点。</p>
        </div>
        <button class="v2-filter-reset" type="button" @click="selectTaxonomyNode(personalTree.rootKey)">回到鸟纲根节点</button>
        <dl class="v2-taxonomy-sidebar-stats">
          <div><dt>目</dt><dd>{{ taxonomyStats.order }}</dd></div>
          <div><dt>科</dt><dd>{{ taxonomyStats.family }}</dd></div>
          <div><dt>属</dt><dd>{{ taxonomyStats.genus }}</dd></div>
        </dl>
        <div class="v2-book-count"><strong>{{ species.length }}</strong><span>个末端物种</span></div>
      </template>
      <template v-else>
        <div class="v2-book-tab">BIRD INDEX</div>
        <p class="v2-kicker">INVESTIGATION MANUAL</p>
        <h1>鸟类调查册</h1>
        <p class="v2-filter-intro">只收录由你亲自拍摄并确认的鸟类。每一页都由真实的相遇解锁。</p>
        <label class="v2-search-label" for="vue-dex-search">检索图鉴</label>
        <input id="vue-dex-search" v-model="query" class="v2-search" type="search" placeholder="中文名、拉丁学名或编号" />
        <label>目</label>
        <select v-model="order"><option value="">全部目</option><option v-for="item in orders" :key="item">{{ item }}</option></select>
        <label>科</label>
        <select v-model="family"><option value="">全部科</option><option v-for="item in families" :key="item">{{ item }}</option></select>
        <label>属</label>
        <select v-model="genus"><option value="">全部属</option><option v-for="item in genera" :key="item">{{ item }}</option></select>
        <button class="v2-filter-reset" type="button" @click="reset">清除检索条件</button>
        <div class="v2-book-count"><strong>{{ query || order || family || genus ? `${filtered.length} / ${species.length}` : species.length }}</strong><span>已装订图鉴页</span></div>
      </template>
    </aside></div>

    <section class="v2-dex-content">
      <header class="v2-dex-header">
        <div v-if="taxonomyMode"><p class="v2-kicker">PERSONAL TAXONOMY</p><h2>沿分类脉络重返相遇</h2></div>
        <div v-else><p class="v2-kicker">COLLECTED SPECIES</p><h2>已确认的飞羽</h2></div>
        <button
          class="v2-view-mark"
          :class="{ 'is-taxonomy': taxonomyMode }"
          type="button"
          data-taxonomy-switch
          :aria-label="taxonomyMode ? '返回鸟类图鉴浏览' : '打开个人分类树'"
          @click="taxonomyMode ? leaveTaxonomy() : enterTaxonomy()"
        >
          <span>{{ taxonomyMode ? "FIELD GUIDE" : "PERSONAL TREE" }}</span>
          <strong>{{ taxonomyMode ? "返回图鉴" : "分类树" }}</strong>
        </button>
      </header>

      <p v-if="loading" class="v2-loading">{{ taxonomyMode ? "正在展开个人分类树…" : "正在翻阅图鉴目录…" }}</p>
      <p v-else-if="error" class="v2-loading">{{ error }}</p>
      <TaxonomyExplorer
        v-else-if="taxonomyMode"
        :tree="personalTree"
        :current-key="currentTaxonomyKey"
        @select="selectTaxonomyNode"
        @open-species="openDossier"
        @view-observations="viewSpeciesObservations"
        @edit-taxonomy="editingTaxonomy = $event"
      />
      <template v-else>
        <div class="v2-species-grid"><DiscoveryCard v-for="item in filtered" :key="item.id" :species="item" @click="openDossier(item.id)" /></div>
        <div v-if="!filtered.length" class="v2-empty"><strong>没有找到对应图鉴页</strong><span>换一个名称或清除分类筛选试试。</span></div>
      </template>
    </section>
  </main>

  <dialog ref="dossier" class="v2-dossier" @click.self="closeDossier">
    <p v-if="detailLoading" class="v2-loading v2-dossier-loading">正在调取调查档案…</p>
    <SpeciesDossier v-if="detail" :detail="detail" @close="closeDossier" @set-cover="setCover" @delete-observation="deleteObservation" @delete-audio="deleteAudio" @edit="openProfileEditor" @add-audio="openAudioForm" />
  </dialog>
  <dialog ref="profileDialog" class="record-dialog profile-dialog" @click.self="closeProfileEditor"><SpeciesProfileForm v-if="profileOpen && detail" :detail="detail" @close="closeProfileEditor" @saved="profileSaved" /></dialog>
  <TaxonomyEditor v-if="editingTaxonomy" :node-key="editingTaxonomy" :tree="personalTree" @close="editingTaxonomy = null" @saved="taxonomySaved" />
  <dialog ref="audioDialog" class="record-dialog" @click.self="closeAudioForm"><SpeciesAudioForm v-if="audioOpen && detail" :detail="detail" @close="closeAudioForm" @saved="audioSaved" /></dialog>
</template>
