<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type {
  CollectionMembership,
  CollectionPlanDetail,
  CollectionSlot,
  ObservationRecord,
} from "@/api/types";

const props = defineProps<{
  planId: number;
  membership: CollectionMembership;
  slot: CollectionSlot;
}>();
const emit = defineEmits<{
  close: [];
  saved: [plan: CollectionPlanDetail];
}>();

const candidates = ref<ObservationRecord[]>([]);
const selectedId = ref<number | null>(null);
const centerX = ref(0.5);
const centerY = ref(0.5);
const zoom = ref(1);
const status = ref("正在读取该物种的照片凭证…");
const saving = ref(false);
let dragStart: { x: number; y: number; centerX: number; centerY: number } | null = null;

const selected = computed(() => candidates.value.find((item) => item.id === selectedId.value) ?? null);
const imageStyle = computed(() => ({
  transform: `scale(${zoom.value}) translate(${(0.5 - centerX.value) * 100}%, ${(0.5 - centerY.value) * 100}%)`,
}));

watch(() => [props.planId, props.slot.id] as const, async () => {
  selectedId.value = props.slot.observation_id;
  centerX.value = props.slot.crop_center_x;
  centerY.value = props.slot.crop_center_y;
  zoom.value = props.slot.crop_zoom;
  status.value = "正在读取该物种的照片凭证…";
  try {
    candidates.value = await api<ObservationRecord[]>(`/api/collections/${props.planId}/species/${props.membership.species_id}/observations`);
    status.value = candidates.value.length ? "请选择照片，再拖动画面并调整缩放。" : "该物种暂无可用观察。";
  } catch (caught) {
    status.value = errorMessage(caught);
  }
}, { immediate: true });
watch(zoom, () => {
  const margin = 0.5 / zoom.value;
  centerX.value = Math.min(1 - margin, Math.max(margin, centerX.value));
  centerY.value = Math.min(1 - margin, Math.max(margin, centerY.value));
});

function choose(observation: ObservationRecord): void {
  selectedId.value = observation.id;
  centerX.value = 0.5;
  centerY.value = 0.5;
  zoom.value = 1;
}
function startDrag(event: PointerEvent): void {
  if (!selected.value) return;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  dragStart = { x: event.clientX, y: event.clientY, centerX: centerX.value, centerY: centerY.value };
}
function drag(event: PointerEvent): void {
  if (!dragStart) return;
  const target = event.currentTarget as HTMLElement;
  const size = Math.max(1, target.clientWidth * zoom.value);
  const margin = 0.5 / zoom.value;
  centerX.value = Math.min(1 - margin, Math.max(margin, dragStart.centerX - (event.clientX - dragStart.x) / size));
  centerY.value = Math.min(1 - margin, Math.max(margin, dragStart.centerY - (event.clientY - dragStart.y) / size));
}
function endDrag(): void { dragStart = null; }
async function save(clear = false): Promise<void> {
  if (!clear && !selected.value) { status.value = "请先选择一笔照片凭证。"; return; }
  const entry = selected.value?.species_entries.find((item) => item.species_id === props.membership.species_id);
  if (!clear && !entry?.id) { status.value = "这笔观察缺少对应物种条目。"; return; }
  saving.value = true;
  status.value = clear ? "正在解除照片凭证…" : "正在保存头像…";
  try {
    const plan = await api<CollectionPlanDetail>(
      `/api/collections/${props.planId}/slots/${props.slot.id}`,
      jsonRequest("PUT", {
        observation_species_id: clear ? null : entry?.id,
        crop_center_x: centerX.value,
        crop_center_y: centerY.value,
        crop_zoom: zoom.value,
      }),
    );
    emit("saved", plan);
  } catch (caught) {
    status.value = errorMessage(caught);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <section class="collection-evidence-dialog">
    <header class="dialog-header"><div><p class="eyebrow">PHOTO EVIDENCE</p><h2>{{ slot.label }}</h2></div><button type="button" class="icon-button" @click="emit('close')">×</button></header>
    <div class="collection-evidence-body">
      <div class="collection-crop-column">
        <div class="collection-crop-stage" :class="{ 'is-empty': !selected }" @pointerdown="startDrag" @pointermove="drag" @pointerup="endDrag" @pointercancel="endDrag">
          <img v-if="selected" :src="selected.photo_url" alt="裁切预览" draggable="false" :style="imageStyle" />
          <span v-else>?</span>
          <i aria-hidden="true"></i>
        </div>
        <label>缩放 <input v-model.number="zoom" type="range" min="1" max="4" step="0.05" :disabled="!selected" /></label>
        <p>圆框内就是计划中显示的头像。按住图片拖动取景，原照片不会被修改。</p>
      </div>
      <div class="collection-evidence-list">
        <button v-for="item in candidates" :key="item.id" type="button" :class="{ 'is-selected': selectedId === item.id }" @click="choose(item)">
          <img :src="item.thumbnail_url" alt="" /><span><b>{{ item.observed_at.replace('T', ' ') }}</b><small>{{ item.location?.name || item.locality }}</small></span>
        </button>
        <p v-if="!candidates.length" class="compact-empty">没有可选择的照片凭证。</p>
      </div>
    </div>
    <footer class="dialog-footer"><span>{{ status }}</span><button v-if="slot.observation_species_id" type="button" class="secondary-button" :disabled="saving" @click="save(true)">解除凭证</button><button type="button" class="primary-button" :disabled="saving || !selected" @click="save(false)">保存头像</button></footer>
  </section>
</template>
