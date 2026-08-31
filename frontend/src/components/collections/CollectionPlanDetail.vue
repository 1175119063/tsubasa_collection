<script setup lang="ts">
import { computed } from "vue";
import type { CollectionMembership, CollectionPlanDetail, CollectionSlot } from "@/api/types";

const props = defineProps<{ detail: CollectionPlanDetail }>();
const emit = defineEmits<{
  close: [];
  edit: [];
  members: [];
  delete: [];
  evidence: [membership: CollectionMembership, slot: CollectionSlot];
  preview: [membership: CollectionMembership, slot: CollectionSlot];
}>();
const progress = computed(() => props.detail.slot_count
  ? Math.round(props.detail.completed_count / props.detail.slot_count * 100)
  : 0);
function avatarStyle(slot: CollectionSlot): Record<string, string> {
  return {
    transform: `scale(${slot.crop_zoom}) translate(${(0.5 - slot.crop_center_x) * 100}%, ${(0.5 - slot.crop_center_y) * 100}%)`,
  };
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
      <p class="v2-kicker">{{ detail.catalog_number }} · PERSONAL COLLECTION</p>
      <h2>{{ detail.name }}</h2>
      <p>{{ detail.introduction || "这份收集计划还没有填写简介。" }}</p>
      <div class="collection-progress"><span><i :style="{ width: `${progress}%` }"></i></span><b>{{ detail.completed_count }} / {{ detail.slot_count }} · {{ progress }}%</b></div>
      <div class="collection-dossier-actions"><button type="button" class="v2-primary-action" @click="emit('members')">{{ detail.memberships.length ? "管理鸟种" : "＋ 添加鸟种" }}</button><button type="button" @click="emit('edit')">修改计划资料</button><button type="button" @click="emit('delete')">删除计划</button></div>
    </header>
    <section class="collection-dossier-body">
      <div v-if="detail.memberships.length" class="collection-species-grid">
        <article v-for="membership in detail.memberships" :key="membership.id" class="collection-species-column">
          <div v-for="slot in membership.slots" :key="slot.id" class="collection-slot-row">
            <button class="collection-slot" type="button" :aria-label="slot.observation_species_id ? `预览 ${slot.label} 的观察记录` : `为 ${slot.label} 选择照片凭证`" @click="activate(membership, slot)">
              <span class="collection-avatar" :class="{ 'is-empty': !slot.photo_url }"><img v-if="slot.photo_url" :src="slot.photo_url" alt="" :style="avatarStyle(slot)" /><b v-else>?</b></span>
              <span class="collection-label">{{ slot.label }}</span>
            </button>
            <button v-if="slot.observation_species_id" class="collection-slot-change" type="button" title="更换照片或重新裁切" @click="emit('evidence', membership, slot)">✎</button>
          </div>
        </article>
      </div>
      <div v-else class="v2-empty"><strong>计划中还没有鸟种</strong><span>点击“添加鸟种”，从个人图鉴中选择已经观察到的物种。</span></div>
    </section>
  </article>
</template>
