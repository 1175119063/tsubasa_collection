<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, errorMessage } from "@/api/client";
import type {
  CollectionMembership,
  CollectionPlanDetail,
  CollectionPlanSummary,
  CollectionSlot,
  SpeciesSummary,
} from "@/api/types";
import CollectionEvidenceDialog from "@/components/collections/CollectionEvidenceDialog.vue";
import CollectionLogoDialog from "@/components/collections/CollectionLogoDialog.vue";
import CollectionPlanDetailView from "@/components/collections/CollectionPlanDetail.vue";
import CollectionPlanForm from "@/components/collections/CollectionPlanForm.vue";
import CollectionSpeciesManager from "@/components/collections/CollectionSpeciesManager.vue";

const route = useRoute();
const router = useRouter();
const plans = ref<CollectionPlanSummary[]>([]);
const species = ref<SpeciesSummary[]>([]);
const query = ref("");
const loading = ref(true);
const error = ref("");
const detail = ref<CollectionPlanDetail | null>(null);
const editing = ref<CollectionPlanDetail | null>(null);
const evidenceTarget = ref<{ membership: CollectionMembership; slot: CollectionSlot } | null>(null);
const previewMembership = ref<CollectionMembership | null>(null);
const previewSlot = ref<CollectionSlot | null>(null);
const detailDialog = ref<HTMLDialogElement>();
const formDialog = ref<HTMLDialogElement>();
const memberDialog = ref<HTMLDialogElement>();
const evidenceDialog = ref<HTMLDialogElement>();
const logoDialog = ref<HTMLDialogElement>();

const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return plans.value.filter((item) => !needle
    || item.name.toLocaleLowerCase().includes(needle)
    || (item.introduction ?? "").toLocaleLowerCase().includes(needle));
});
function templateLabel(plan: CollectionPlanSummary): string {
  if (plan.template_kind === "none") return "无子项";
  if (plan.template_kind === "plumage") return "br. / non br.";
  if (plan.template_kind === "sex_age") return "♂ / ♀ / juv.";
  return plan.subitems.join(" / ");
}
function planLogoStyle(plan: CollectionPlanSummary): Record<string, string> | undefined {
  if (!plan.logo.url) return undefined;
  return {
    transform: `scale(${plan.logo.crop_zoom}) translate(${(0.5 - plan.logo.crop_center_x) * 100}%, ${(0.5 - plan.logo.crop_center_y) * 100}%)`,
  };
}
function replaceDetail(
  plan: CollectionPlanDetail,
  speciesId = previewMembership.value?.species_id,
  slotId = previewSlot.value?.id,
): void {
  detail.value = plan;
  const membership = plan.memberships.find((item) => item.species_id === speciesId) ?? null;
  const slot = membership?.slots.find((item) => item.id === slotId) ?? null;
  previewMembership.value = slot ? membership : null;
  previewSlot.value = slot;
}
async function load(): Promise<void> {
  loading.value = true; error.value = "";
  try {
    [plans.value, species.value] = await Promise.all([
      api<CollectionPlanSummary[]>("/api/collections"),
      api<SpeciesSummary[]>("/api/species"),
    ]);
  }
  catch (caught) { error.value = errorMessage(caught); }
  finally { loading.value = false; }
}
async function open(id: number): Promise<void> {
  try {
    detail.value = await api<CollectionPlanDetail>(`/api/collections/${id}`);
    previewMembership.value = null;
    previewSlot.value = null;
    await nextTick();
    if (!detailDialog.value?.open) detailDialog.value?.showModal();
    const query = { ...route.query };
    delete query.new;
    await router.replace({ query: { ...query, collection: String(id) } });
  } catch (caught) { error.value = errorMessage(caught); }
}
function closeDetail(): void {
  detailDialog.value?.close(); detail.value = null; previewMembership.value = null; previewSlot.value = null;
  const next = { ...route.query }; delete next.collection; void router.replace({ query: next });
}
async function openForm(plan: CollectionPlanDetail | null = null): Promise<void> {
  editing.value = plan; await nextTick(); formDialog.value?.showModal();
}
function hideForm(): void { formDialog.value?.close(); editing.value = null; }
function closeForm(): void {
  hideForm();
  if (route.query.new) {
    const query = { ...route.query }; delete query.new; void router.replace({ query });
  }
}
async function saved(plan: CollectionPlanDetail): Promise<void> {
  hideForm(); await load(); await open(plan.id);
}
async function remove(): Promise<void> {
  if (!detail.value || !confirm("删除计划只会移除收集关系，不会删除任何物种、观察或照片。确定删除吗？")) return;
  try { await api(`/api/collections/${detail.value.id}`, { method: "DELETE" }); closeDetail(); await load(); }
  catch (caught) { error.value = errorMessage(caught); }
}
function openMembers(): void { memberDialog.value?.showModal(); }
function closeMembers(): void { memberDialog.value?.close(); }
async function membersSaved(plan: CollectionPlanDetail): Promise<void> {
  closeMembers(); replaceDetail(plan); await load();
}
async function openEvidence(membership: CollectionMembership, slot: CollectionSlot): Promise<void> {
  evidenceTarget.value = { membership, slot }; await nextTick(); evidenceDialog.value?.showModal();
}
function closeEvidence(): void { evidenceDialog.value?.close(); evidenceTarget.value = null; }
async function evidenceSaved(plan: CollectionPlanDetail): Promise<void> {
  const speciesId = evidenceTarget.value?.membership.species_id;
  const slotId = evidenceTarget.value?.slot.id;
  closeEvidence(); replaceDetail(plan, speciesId, slotId); await load();
}
function openLogo(): void { logoDialog.value?.showModal(); }
function closeLogo(): void { logoDialog.value?.close(); }
async function logoSaved(plan: CollectionPlanDetail): Promise<void> {
  closeLogo();
  replaceDetail(plan);
  if (editing.value?.id === plan.id) editing.value = plan;
  await load();
}
function openPreview(membership: CollectionMembership, slot: CollectionSlot): void {
  previewMembership.value = membership;
  previewSlot.value = slot;
}
function detailUpdated(plan: CollectionPlanDetail): void { replaceDetail(plan); }
onMounted(async () => {
  await load(); const requested = Number(route.query.collection);
  if (requested && plans.value.some((item) => item.id === requested)) await open(requested);
  else if (route.query.new === "1") await openForm();
});
</script>

<template>
  <main class="v2-archive-layout collection-page">
    <div class="v2-sidebar-column"><aside class="v2-archive-sidebar"><div class="v2-book-tab">COLLECTION PLANS</div><p class="v2-kicker">私人专题收集</p><h1>收集计划</h1><p class="v2-filter-intro">把形态相近、渊源相连或令你着迷的鸟种，编成属于自己的专题收集。</p><label for="collection-search">检索计划</label><input id="collection-search" v-model="query" type="search" placeholder="计划名称或简介" /><button class="v2-filter-reset" type="button" @click="query = ''">清除检索条件</button><div class="v2-book-count"><strong>{{ filtered.length }}</strong><span>份收集计划</span></div></aside></div>
    <section class="v2-archive-content"><header class="v2-dex-header"><div><p class="v2-kicker">PERSONAL COLLECTIONS</p><h2>把相遇编成自己的主题</h2></div><button class="v2-new-entry" type="button" @click="openForm()">＋ 创建计划</button></header><p v-if="loading" class="v2-loading">正在整理收集计划…</p><p v-else-if="error" class="v2-loading">{{ error }}</p><div v-else-if="filtered.length" class="collection-plan-grid"><button v-for="plan in filtered" :key="plan.id" class="collection-plan-card" type="button" @click="open(plan.id)"><span class="collection-plan-cover"><img v-if="plan.logo.url || plan.cover_url" :src="plan.logo.url || plan.cover_url || ''" alt="" :style="planLogoStyle(plan)" /><b v-else>?</b><small>{{ plan.catalog_number }}</small></span><span class="collection-plan-copy"><em>{{ templateLabel(plan) }}</em><strong>{{ plan.name }}</strong><p>{{ plan.introduction || "尚未填写观察记录简介。" }}</p><span><b>{{ plan.species_count }}</b> 种鸟类 · <b>{{ plan.completed_count }}</b> / {{ plan.slot_count }} 项完成</span></span></button></div><div v-else class="v2-empty"><strong>还没有收集计划</strong><span>从已经观察到的鸟种中挑选一个主题开始吧。</span></div></section>
  </main>

  <dialog ref="detailDialog" class="v2-archive-dialog collection-detail-dialog" @click.self="closeDetail"><CollectionPlanDetailView v-if="detail" :detail="detail" :preview-membership="previewMembership" :preview-slot="previewSlot" @close="closeDetail" @members="openMembers" @edit="openForm(detail)" @delete="remove" @evidence="openEvidence" @preview="openPreview" @updated="detailUpdated" /></dialog>
  <dialog ref="formDialog" class="record-dialog collection-form-dialog" @click.self="closeForm"><CollectionPlanForm :plan="editing" @close="closeForm" @logo="openLogo" @saved="saved" /></dialog>
  <dialog ref="memberDialog" class="record-dialog collection-member-dialog" @click.self="closeMembers"><CollectionSpeciesManager v-if="detail" :plan="detail" :species="species" @close="closeMembers" @saved="membersSaved" /></dialog>
  <dialog ref="evidenceDialog" class="record-dialog collection-evidence-modal" @click.self="closeEvidence"><CollectionEvidenceDialog v-if="detail && evidenceTarget" :plan-id="detail.id" :membership="evidenceTarget.membership" :slot="evidenceTarget.slot" @close="closeEvidence" @saved="evidenceSaved" /></dialog>
  <dialog ref="logoDialog" class="record-dialog collection-logo-modal" @click.self="closeLogo"><CollectionLogoDialog v-if="detail" :plan="detail" @close="closeLogo" @saved="logoSaved" /></dialog>
</template>
