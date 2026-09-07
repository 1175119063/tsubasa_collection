<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { CollectionPlanDetail } from "@/api/types";

const props = defineProps<{ plan: CollectionPlanDetail }>();
const emit = defineEmits<{ close: []; saved: [plan: CollectionPlanDetail] }>();

const candidates = computed(() => {
  const seen = new Set<number>();
  return props.plan.memberships.flatMap((membership) => membership.slots
    .filter((slot) => slot.observation_species_id && slot.photo_url)
    .filter((slot) => {
      if (!slot.observation_species_id || seen.has(slot.observation_species_id)) return false;
      seen.add(slot.observation_species_id);
      return true;
    }));
});
const mode = ref<"collection" | "upload">(props.plan.logo.source === "collection" ? "collection" : "upload");
const selectedEntryId = ref<number | null>(props.plan.logo.observation_species_id);
const selectedFile = ref<File | null>(null);
const localUrl = ref<string | null>(null);
const centerX = ref(props.plan.logo.crop_center_x);
const centerY = ref(props.plan.logo.crop_center_y);
const zoom = ref(props.plan.logo.crop_zoom);
const saving = ref(false);
const status = ref("从已装订照片中挑选，或者上传一张本地 JPEG。");
let dragStart: { x: number; y: number; centerX: number; centerY: number } | null = null;

const previewUrl = computed(() => {
  if (mode.value === "upload") return localUrl.value || (props.plan.logo.source === "upload" ? props.plan.logo.url : null);
  return candidates.value.find((item) => item.observation_species_id === selectedEntryId.value)?.photo_url ?? null;
});
const imageStyle = computed(() => ({
  transform: `scale(${zoom.value}) translate(${(0.5 - centerX.value) * 100}%, ${(0.5 - centerY.value) * 100}%)`,
}));

watch(zoom, () => {
  const margin = 0.5 / zoom.value;
  centerX.value = Math.min(1 - margin, Math.max(margin, centerX.value));
  centerY.value = Math.min(1 - margin, Math.max(margin, centerY.value));
});
onBeforeUnmount(() => { if (localUrl.value) URL.revokeObjectURL(localUrl.value); });

function resetCrop(): void { centerX.value = 0.5; centerY.value = 0.5; zoom.value = 1; }
function chooseCollection(entryId: number | null): void {
  if (!entryId) return;
  mode.value = "collection";
  selectedEntryId.value = entryId;
  selectedFile.value = null;
  resetCrop();
}
function chooseFile(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0] ?? null;
  if (!file) return;
  if (localUrl.value) URL.revokeObjectURL(localUrl.value);
  selectedFile.value = file;
  localUrl.value = URL.createObjectURL(file);
  mode.value = "upload";
  resetCrop();
}
function startDrag(event: PointerEvent): void {
  if (!previewUrl.value) return;
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  dragStart = { x: event.clientX, y: event.clientY, centerX: centerX.value, centerY: centerY.value };
}
function drag(event: PointerEvent): void {
  if (!dragStart) return;
  const size = Math.max(1, (event.currentTarget as HTMLElement).clientWidth * zoom.value);
  const margin = 0.5 / zoom.value;
  centerX.value = Math.min(1 - margin, Math.max(margin, dragStart.centerX - (event.clientX - dragStart.x) / size));
  centerY.value = Math.min(1 - margin, Math.max(margin, dragStart.centerY - (event.clientY - dragStart.y) / size));
}
function endDrag(): void { dragStart = null; }
async function save(): Promise<void> {
  if (!previewUrl.value) { status.value = "请先选择一张照片。"; return; }
  saving.value = true; status.value = "正在保存计划 Logo…";
  try {
    let plan: CollectionPlanDetail;
    if (mode.value === "upload" && selectedFile.value) {
      const body = new FormData();
      body.append("photo", selectedFile.value);
      body.append("crop_center_x", String(centerX.value));
      body.append("crop_center_y", String(centerY.value));
      body.append("crop_zoom", String(zoom.value));
      plan = await api(`/api/collections/${props.plan.id}/logo`, { method: "POST", body });
    } else {
      plan = await api(`/api/collections/${props.plan.id}/logo`, jsonRequest("PUT", {
        observation_species_id: mode.value === "collection" ? selectedEntryId.value : null,
        crop_center_x: centerX.value,
        crop_center_y: centerY.value,
        crop_zoom: zoom.value,
      }));
    }
    emit("saved", plan);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { saving.value = false; }
}
async function clearLogo(): Promise<void> {
  saving.value = true; status.value = "正在移除计划 Logo…";
  try {
    emit("saved", await api(`/api/collections/${props.plan.id}/logo`, { method: "DELETE" }));
  } catch (caught) { status.value = errorMessage(caught); }
  finally { saving.value = false; }
}
</script>

<template>
  <section class="collection-logo-dialog">
    <header class="dialog-header"><div><p class="eyebrow">COLLECTION EMBLEM</p><h2>设置计划 Logo</h2></div><button type="button" class="icon-button" @click="emit('close')">×</button></header>
    <div class="collection-logo-body">
      <div class="collection-logo-crop">
        <div class="collection-logo-stage" :class="{ 'is-empty': !previewUrl }" @pointerdown="startDrag" @pointermove="drag" @pointerup="endDrag" @pointercancel="endDrag">
          <img v-if="previewUrl" :src="previewUrl" alt="计划 Logo 裁切预览" draggable="false" :style="imageStyle" />
          <span v-else>{{ plan.catalog_number }}</span>
          <i aria-hidden="true"></i>
        </div>
        <label>画面缩放<input v-model.number="zoom" type="range" min="1" max="4" step="0.05" :disabled="!previewUrl" /></label>
        <p>按住图片拖动取景。Logo 区会以正方形展示，原始照片不会被修改。</p>
      </div>
      <div class="collection-logo-sources">
        <section><p class="eyebrow">FROM COLLECTION</p><h3>从已收集照片中挑选</h3><div class="collection-logo-candidates"><button v-for="slot in candidates" :key="slot.id" type="button" :class="{ 'is-selected': mode === 'collection' && selectedEntryId === slot.observation_species_id }" @click="chooseCollection(slot.observation_species_id)"><img :src="slot.thumbnail_url || slot.photo_url || ''" alt="" /><span>{{ slot.label }}</span></button><p v-if="!candidates.length" class="compact-empty">先为收集项装订照片凭证，才可以从这里选择。</p></div></section>
        <section><p class="eyebrow">LOCAL JPEG</p><h3>上传本地图片</h3><label class="collection-logo-upload"><input type="file" accept="image/jpeg,.jpg,.jpeg" @change="chooseFile" /><span>{{ selectedFile?.name || (plan.logo.source === 'upload' ? '当前使用本地上传图片' : '选择 JPEG 图片') }}</span></label></section>
      </div>
    </div>
    <footer class="dialog-footer"><span>{{ status }}</span><button v-if="plan.logo.source" type="button" class="secondary-button" :disabled="saving" @click="clearLogo">移除 Logo</button><button type="button" class="primary-button" :disabled="saving || !previewUrl" @click="save">保存 Logo</button></footer>
  </section>
</template>
