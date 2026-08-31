<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { SpeciesSummary } from "@/api/types";
import DiscoveryCard from "@/components/DiscoveryCard.vue";
import SpeciesDossier, { type SpeciesDetail } from "@/components/dex/SpeciesDossier.vue";
import SpeciesProfileForm from "@/components/dex/SpeciesProfileForm.vue";
import SpeciesAudioForm from "@/components/dex/SpeciesAudioForm.vue";

const route = useRoute();
const router = useRouter();
const species = ref<SpeciesSummary[]>([]);
const query = ref("");
const order = ref("");
const family = ref("");
const genus = ref("");
const loading = ref(true);
const error = ref("");
const dossier = ref<HTMLDialogElement>();
const detail = ref<SpeciesDetail | null>(null);
const detailLoading = ref(false);
const profileDialog = ref<HTMLDialogElement>(); const profileOpen = ref(false);
const audioDialog = ref<HTMLDialogElement>(); const audioOpen = ref(false);

const orders = computed(() => [...new Set(species.value.map((item) => item.order_name))].sort());
const families = computed(() => [...new Set(species.value.filter((item) => !order.value || item.order_name === order.value).map((item) => item.family_name))].sort());
const genera = computed(() => [...new Set(species.value.filter((item) => (!order.value || item.order_name === order.value) && (!family.value || item.family_name === family.value)).map((item) => item.genus_name))].sort());
const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return species.value.filter((item) => `${item.catalog_number} ${item.chinese_name} ${item.scientific_name} ${item.family_name} ${item.genus_name}`.toLocaleLowerCase().includes(needle) && (!order.value || item.order_name === order.value) && (!family.value || item.family_name === family.value) && (!genus.value || item.genus_name === genus.value));
});

watch(order, () => { if (!families.value.includes(family.value)) family.value = ""; });
watch(family, () => { if (!genera.value.includes(genus.value)) genus.value = ""; });

async function loadSpecies(): Promise<void> {
  loading.value = true;
  try { species.value = await api<SpeciesSummary[]>("/api/species"); }
  catch (caught) { error.value = errorMessage(caught); }
  finally { loading.value = false; }
}

async function openDossier(speciesId: number): Promise<void> {
  detailLoading.value = true;
  detail.value = null;
  dossier.value?.showModal();
  try {
    detail.value = await api<SpeciesDetail>(`/api/species/${speciesId}`);
    await router.replace({ query: { ...route.query, species: speciesId } });
  } catch (caught) { error.value = errorMessage(caught); }
  finally { detailLoading.value = false; }
}

function closeDossier(): void {
  dossier.value?.close();
  detail.value = null;
  const nextQuery = { ...route.query }; delete nextQuery.species;
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
  if (result.removed_species) closeDossier(); else await refreshDetail();
}

async function deleteAudio(audioId: number): Promise<void> {
  if (!detail.value || !window.confirm("永久删除这段独立物种录音吗？")) return;
  await api(`/api/species/${detail.value.id}/audio/${audioId}`, { method: "DELETE" });
  await refreshDetail();
}

function reset(): void { query.value = ""; order.value = ""; family.value = ""; genus.value = ""; }

async function openProfileEditor(): Promise<void> { if (!detail.value) return; profileOpen.value = true; await nextTick(); profileDialog.value?.showModal(); }
function closeProfileEditor(): void { profileDialog.value?.close(); profileOpen.value = false; }
async function profileSaved(saved: SpeciesDetail): Promise<void> { closeProfileEditor(); detail.value = saved; await loadSpecies(); }
async function openAudioForm(): Promise<void> { if (!detail.value) return; audioOpen.value = true; await nextTick(); audioDialog.value?.showModal(); }
function closeAudioForm(): void { audioDialog.value?.close(); audioOpen.value = false; }
async function audioSaved(): Promise<void> { closeAudioForm(); await refreshDetail(); }

onMounted(async () => {
  await loadSpecies();
  await nextTick();
  const requested = Number(route.query.species);
  if (requested && species.value.some((item) => item.id === requested)) await openDossier(requested);
});
</script>

<template>
  <main class="v2-dex-layout">
    <aside class="v2-filter-book">
      <div class="v2-book-tab">BIRD INDEX</div><p class="v2-kicker">INVESTIGATION MANUAL</p><h1>鸟类调查册</h1>
      <p class="v2-filter-intro">只收录由你亲自拍摄并确认的鸟类。每一页都由真实的相遇解锁。</p>
      <label class="v2-search-label" for="vue-dex-search">检索馆藏</label><input id="vue-dex-search" v-model="query" class="v2-search" type="search" placeholder="中文名、拉丁学名或编号" />
      <label>目</label><select v-model="order"><option value="">全部目</option><option v-for="item in orders" :key="item">{{ item }}</option></select>
      <label>科</label><select v-model="family"><option value="">全部科</option><option v-for="item in families" :key="item">{{ item }}</option></select>
      <label>属</label><select v-model="genus"><option value="">全部属</option><option v-for="item in genera" :key="item">{{ item }}</option></select>
      <button class="v2-filter-reset" type="button" @click="reset">清除检索条件</button>
      <div class="v2-book-count"><strong>{{ query || order || family || genus ? `${filtered.length} / ${species.length}` : species.length }}</strong><span>已装订图鉴页</span></div>
    </aside>
    <section class="v2-dex-content">
      <header class="v2-dex-header"><div><p class="v2-kicker">COLLECTED SPECIES</p><h2>已确认的飞羽</h2></div><div class="v2-view-mark">PERSONAL<br />ARCHIVE</div></header>
      <div class="v2-species-grid"><DiscoveryCard v-for="item in filtered" :key="item.id" :species="item" @click="openDossier(item.id)" /><p v-if="loading" class="v2-loading">正在翻阅馆藏目录…</p><p v-if="error" class="v2-loading">{{ error }}</p></div>
      <div v-if="!loading && !filtered.length" class="v2-empty"><strong>没有找到对应图鉴页</strong><span>换一个名称或清除分类筛选试试。</span></div>
    </section>
  </main>
  <dialog ref="dossier" class="v2-dossier" @click.self="closeDossier">
    <p v-if="detailLoading" class="v2-loading v2-dossier-loading">正在调取调查档案…</p>
    <SpeciesDossier v-if="detail" :detail="detail" @close="closeDossier" @set-cover="setCover" @delete-observation="deleteObservation" @delete-audio="deleteAudio" @edit="openProfileEditor" @add-audio="openAudioForm" />
  </dialog>
  <dialog ref="profileDialog" class="record-dialog profile-dialog" @click.self="closeProfileEditor"><SpeciesProfileForm v-if="profileOpen && detail" :detail="detail" @close="closeProfileEditor" @saved="profileSaved" /></dialog>
  <dialog ref="audioDialog" class="record-dialog" @click.self="closeAudioForm"><SpeciesAudioForm v-if="audioOpen && detail" :detail="detail" @close="closeAudioForm" @saved="audioSaved" /></dialog>
</template>
