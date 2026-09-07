<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { CollectionMembership, CollectionPlanDetail, CollectionSlot } from "@/api/types";

const props = defineProps<{
  detail: CollectionPlanDetail;
  previewMembership: CollectionMembership | null;
  previewSlot: CollectionSlot | null;
}>();
const emit = defineEmits<{
  close: [];
  edit: [];
  members: [];
  delete: [];
  evidence: [membership: CollectionMembership, slot: CollectionSlot];
  preview: [membership: CollectionMembership, slot: CollectionSlot];
  updated: [plan: CollectionPlanDetail];
}>();
const introductionDraft = ref("");
const introductionStatus = ref("");
const savingIntroduction = ref(false);
let selectedMembershipId: number | null = null;
const progress = computed(() => props.detail.slot_count
  ? Math.round(props.detail.completed_count / props.detail.slot_count * 100)
  : 0);
const pendingCount = computed(() => props.detail.slot_count - props.detail.completed_count);
const simplePlan = computed(() => props.detail.template_kind === "none");
const collectionState = computed(() => {
  if (!props.detail.memberships.length) return "等待加入鸟种";
  if (progress.value === 100) return "专题已经完成";
  return "专题装订中";
});
const templateName = computed(() => {
  if (props.detail.template_kind === "none") return "独立单项";
  if (props.detail.template_kind === "plumage") return "繁殖羽阶段";
  if (props.detail.template_kind === "sex_age") return "性别与年龄";
  return "自定义序列";
});
const templateLabels = computed(() => props.detail.subitems.filter(Boolean));
function collectionIndex(index: number): string {
  return String(index + 1).padStart(2, "0");
}
function avatarStyle(slot: CollectionSlot): Record<string, string> {
  return {
    transform: `scale(${slot.crop_zoom}) translate(${(0.5 - slot.crop_center_x) * 100}%, ${(0.5 - slot.crop_center_y) * 100}%)`,
  };
}
const logoStyle = computed(() => ({
  transform: `scale(${props.detail.logo.crop_zoom}) translate(${(0.5 - props.detail.logo.crop_center_x) * 100}%, ${(0.5 - props.detail.logo.crop_center_y) * 100}%)`,
}));
const chinaProtectionLabels: Record<string, string> = {
  three_protected: "国家三有保护动物",
  level_2: "国家二级重点保护",
  level_1: "国家一级重点保护",
};
const chinaProtectionLabel = computed(() => chinaProtectionLabels[
  props.previewMembership?.china_protection_status ?? ""
] ?? "暂无国家重点保护级别");
const iucnLabel = computed(() => ({
  NE: "未评估", LC: "无危", NT: "近危", VU: "易危", EN: "濒危", CR: "极危", EW: "野外灭绝", EX: "灭绝",
}[props.previewMembership?.iucn_status ?? "NE"]));
watch(() => props.previewMembership, (membership) => {
  const changedMembership = (membership?.id ?? null) !== selectedMembershipId;
  selectedMembershipId = membership?.id ?? null;
  introductionDraft.value = membership?.introduction ?? "";
  if (changedMembership) introductionStatus.value = "";
}, { immediate: true });
async function saveIntroduction(): Promise<void> {
  const membership = props.previewMembership;
  if (!membership) return;
  savingIntroduction.value = true;
  introductionStatus.value = "正在保存专题简介…";
  try {
    const plan = await api<CollectionPlanDetail>(
      `/api/collections/${props.detail.id}/species/${membership.species_id}/introduction`,
      jsonRequest("PUT", { introduction: introductionDraft.value || null }),
    );
    emit("updated", plan);
    await nextTick();
    introductionStatus.value = "专题简介已保存";
  } catch (caught) { introductionStatus.value = errorMessage(caught); }
  finally { savingIntroduction.value = false; }
}
function activate(membership: CollectionMembership, slot: CollectionSlot): void {
  if (slot.observation_species_id) emit("preview", membership, slot);
  else emit("evidence", membership, slot);
}
</script>

<template>
  <article class="collection-dossier">
    <button class="v2-dossier-close" type="button" aria-label="关闭" @click="emit('close')">×</button>
    <header class="collection-dossier-hero">
      <div class="collection-hero-primary">
        <section class="collection-logo-panel">
          <img v-if="detail.logo.url" :src="detail.logo.url" alt="计划 Logo" :style="logoStyle" />
          <div v-else class="collection-logo-placeholder"><span>PERSONAL<br />COLLECTION</span><strong>{{ detail.catalog_number }}</strong><i>✦</i></div>
        </section>
        <section class="collection-hero-story">
        <p class="v2-kicker">{{ detail.catalog_number }} · PERSONAL COLLECTION</p>
        <h2>{{ detail.name }}</h2>
        <p class="collection-introduction">{{ detail.introduction || "这份收集计划还没有填写简介。" }}</p>
        <div class="collection-dossier-actions"><button type="button" class="v2-primary-action" @click="emit('members')">{{ detail.memberships.length ? "管理鸟种" : "＋ 添加鸟种" }}</button><button type="button" @click="emit('edit')">修改计划资料</button><button type="button" @click="emit('delete')">删除计划</button></div>
        </section>
      </div>
      <aside class="collection-index-panel">
        <div class="collection-index-heading"><p>COLLECTION INDEX</p><span>{{ collectionState }}</span></div>
        <template v-if="!simplePlan">
          <div class="collection-index-progress">
          <div class="collection-progress-ring" :style="{ '--collection-progress': `${progress * 3.6}deg` }"><strong>{{ detail.completed_count }}</strong><small>/ {{ detail.slot_count }}</small></div>
          <p><span>装订进度</span><b>{{ progress }}%</b><strong>{{ detail.completed_count }} / {{ detail.slot_count }} 项凭证</strong><small>{{ pendingCount ? `尚待补充 ${pendingCount} 项` : "所有槽位均已装订" }}</small></p>
          </div>
          <dl class="collection-index-facts"><div><dt>收录鸟种</dt><dd>{{ detail.species_count }} 种</dd></div><div><dt>统一模板</dt><dd>{{ templateName }}</dd></div></dl>
          <div class="collection-template-note"><span>UNIFORM SET</span><p><i v-for="label in templateLabels" :key="label">{{ label }}</i></p></div>
        </template>
        <template v-else>
          <div class="collection-simple-index"><article><span>收录物种</span><strong>{{ detail.species_count }}</strong><small>SPECIES</small></article><article><span>已设照片</span><strong>{{ detail.completed_count }}</strong><small>PORTRAITS</small></article></div>
          <div class="collection-simple-note"><span>SINGLE PORTRAIT SERIES</span><strong>{{ detail.completed_count === detail.species_count && detail.species_count ? "每种鸟都已有代表照片" : `还有 ${detail.species_count - detail.completed_count} 种等待照片` }}</strong><small>最近整理 · {{ detail.updated_at.replace('T', ' ') }}</small></div>
        </template>
      </aside>
    </header>
    <div class="collection-dossier-content">
      <section class="collection-dossier-body">
      <header class="collection-display-heading"><div><p class="v2-kicker">COLLECTION OVERVIEW</p><h3>收集一览</h3><span>点击头像查看计划内物种档案；问号表示尚待装订的形态。</span></div><div class="collection-status-legend"><span><i class="is-complete"></i>已装订</span><span><i></i>待凭证</span></div></header>
      <div v-if="detail.memberships.length" class="collection-species-grid">
        <article v-for="(membership, membershipIndex) in detail.memberships" :key="membership.id" class="collection-species-column" :data-index="collectionIndex(membershipIndex)">
          <div v-for="slot in membership.slots" :key="slot.id" class="collection-slot-row">
            <button class="collection-slot" type="button" :aria-label="slot.observation_species_id ? `查看 ${slot.label} 的计划档案` : `为 ${slot.label} 选择照片凭证`" @click="activate(membership, slot)">
              <span class="collection-avatar" :class="{ 'is-empty': !slot.photo_url, 'is-complete': slot.photo_url }"><img v-if="slot.photo_url" :src="slot.photo_url" alt="" :style="avatarStyle(slot)" /><b v-else>?</b></span>
              <span class="collection-label" :class="{ 'has-subitem': slot.subitem_label }">
                <b>{{ membership.species_name }}</b>
                <i v-if="slot.subitem_label">{{ slot.subitem_label }}</i>
              </span>
            </button>
            <button v-if="slot.observation_species_id" class="collection-slot-change" type="button" title="更换照片或重新裁切" @click="emit('evidence', membership, slot)">✎</button>
            <span v-else class="collection-slot-change-space" aria-hidden="true"></span>
          </div>
        </article>
      </div>
      <div v-else class="v2-empty"><strong>计划中还没有鸟种</strong><span>点击“添加鸟种”，从个人图鉴中选择已经观察到的物种。</span></div>
      </section>
      <aside class="collection-preview-panel">
        <template v-if="previewMembership && previewSlot">
          <section class="collection-profile-summary">
            <div class="collection-profile-heading">
              <span class="collection-profile-avatar"><img v-if="previewSlot.photo_url" :src="previewSlot.photo_url" :alt="previewMembership.species_name" :style="avatarStyle(previewSlot)" /></span>
              <div><p class="v2-kicker">{{ previewMembership.catalog_number }} · SPECIES FILE</p><h3>{{ previewMembership.species_name }}</h3><i>{{ previewMembership.scientific_name }}</i><em v-if="previewSlot.subitem_label">收集子项 · {{ previewSlot.subitem_label }}</em></div>
            </div>
            <div class="collection-protection-row"><span :class="`is-${previewMembership.iucn_status.toLowerCase()}`">IUCN {{ previewMembership.iucn_status }} · {{ iucnLabel }}</span><span>{{ chinaProtectionLabel }}</span></div>
            <dl class="collection-taxonomy-list">
              <div><dt>目</dt><dd><strong>{{ previewMembership.order_name }}</strong><i>{{ previewMembership.order_scientific_name }}</i></dd></div>
              <div><dt>科</dt><dd><strong>{{ previewMembership.family_name }}</strong><i>{{ previewMembership.family_scientific_name }}</i></dd></div>
              <div><dt>属</dt><dd><strong>{{ previewMembership.genus_name }}</strong><i>{{ previewMembership.genus_scientific_name }}</i></dd></div>
              <div><dt>种</dt><dd><strong>{{ previewMembership.species_name }}</strong><i>{{ previewMembership.scientific_name }}</i></dd></div>
            </dl>
            <RouterLink v-if="previewSlot.observation_id" :to="{ path: '/observations', query: { observation: previewSlot.observation_id } }">查看这笔照片凭证 →</RouterLink>
          </section>
          <section class="collection-profile-note"><p class="v2-kicker">EXPLORER'S NOTE</p><h4>本计划中的物种简介</h4><p>这段文字只属于“{{ detail.name }}”，不会修改鸟类调查册中的物种资料。</p><textarea v-model="introductionDraft" rows="8" maxlength="10000" :placeholder="`写下${previewMembership.species_name}为什么被收入这个专题，以及你对它的观察与理解……`"></textarea><footer><span>{{ introductionStatus || `${introductionDraft.length} / 10000` }}</span><button type="button" :disabled="savingIntroduction" @click="saveIntroduction">{{ savingIntroduction ? "保存中…" : "保存简介" }}</button></footer></section>
        </template>
        <div v-else class="collection-preview-empty"><span>SPECIES FILE</span><i>◎</i><strong>选择一项照片凭证</strong><p>点击左侧已经装订的圆形头像，这里会展开该物种在本收集计划中的专属档案。</p><small>{{ detail.introduction || detail.name }}</small></div>
      </aside>
    </div>
  </article>
</template>
