<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { ObservationPhoto, ObservationRecord } from "@/api/types";

const props = defineProps<{ observation: ObservationRecord }>();
const emit = defineEmits<{ updated: [observation: ObservationRecord] }>();
const file = ref<File | null>(null);
const preview = ref("");
const observedAt = ref("");
const selectedEntryIds = ref<number[]>([]);
const status = ref("");
const busy = ref(false);
const edits = ref<Record<number, { observed_at: string; species_entry_ids: number[] }>>({});
const photos = computed(() => props.observation.photos || []);

function edit(photo: ObservationPhoto) {
  return edits.value[photo.id] ||= {
    observed_at: photo.observed_at,
    species_entry_ids: [...photo.species_entry_ids],
  };
}
async function chooseFile(event: Event): Promise<void> {
  const selected = (event.target as HTMLInputElement).files?.[0] || null;
  if (preview.value) URL.revokeObjectURL(preview.value);
  file.value = selected; preview.value = selected ? URL.createObjectURL(selected) : "";
  const primary = props.observation.species_entries[0]?.id;
  selectedEntryIds.value = primary ? [primary] : [];
  observedAt.value = ""; status.value = "";
  if (!selected) return;
  const body = new FormData(); body.append("photo", selected);
  try {
    const result = await api<{ observed_at: string | null }>("/api/media/exif-time", { method: "POST", body });
    observedAt.value = result.observed_at || "";
    status.value = result.observed_at ? "已读取照片拍摄时间" : "没有 EXIF 时间，请手动填写";
  } catch (caught) { status.value = errorMessage(caught); }
}
async function addPhoto(): Promise<void> {
  if (!file.value || !observedAt.value || !selectedEntryIds.value.length || busy.value) return;
  busy.value = true; status.value = "正在保存照片…";
  const body = new FormData(); body.append("photo", file.value);
  body.append("payload", JSON.stringify({ observed_at: observedAt.value, species_entry_ids: selectedEntryIds.value, is_cover: false }));
  try {
    const updated = await api<ObservationRecord>(`/api/observations/${props.observation.id}/photos`, { method: "POST", body });
    file.value = null; observedAt.value = ""; selectedEntryIds.value = [];
    if (preview.value) URL.revokeObjectURL(preview.value); preview.value = "";
    status.value = "照片已加入这笔观察"; emit("updated", updated);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
async function savePhoto(photo: ObservationPhoto, cover = photo.is_cover): Promise<void> {
  const value = edit(photo);
  if (!value.species_entry_ids.length || busy.value) return;
  busy.value = true; status.value = cover && !photo.is_cover ? "正在更换封面…" : "正在保存照片信息…";
  try {
    const updated = await api<ObservationRecord>(`/api/observations/${props.observation.id}/photos/${photo.id}`, jsonRequest("PATCH", { ...value, is_cover: cover }));
    edits.value = {}; status.value = cover && !photo.is_cover ? "封面已更新" : "照片信息已更新"; emit("updated", updated);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
async function removePhoto(photo: ObservationPhoto): Promise<void> {
  if (photos.value.length <= 1 || busy.value || !confirm(`从这笔观察中移除这张照片吗？${photo.is_cover ? "系统会将下一张照片设为封面。" : ""}`)) return;
  busy.value = true; status.value = "正在移除照片…";
  try {
    const updated = await api<ObservationRecord>(`/api/observations/${props.observation.id}/photos/${photo.id}`, { method: "DELETE" });
    edits.value = {}; status.value = "照片已移除"; emit("updated", updated);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
onBeforeUnmount(() => { if (preview.value) URL.revokeObjectURL(preview.value); });
</script>

<template>
  <section class="observation-photo-manager">
    <header><div><p class="eyebrow">OBSERVATION PHOTOS</p><h3>这次相遇的照片</h3></div><span>{{ photos.length }} / 20 张</span></header>
    <div class="observation-photo-manager-list">
      <article v-for="photo in photos" :key="photo.id">
        <img :src="photo.thumbnail_url" alt="观察照片缩略图" />
        <div>
          <div class="observation-photo-manager-title"><strong>{{ photo.is_cover ? '封面照片' : `照片 ${photo.position + 1}` }}</strong><span>{{ photo.is_cover ? '当前封面' : '' }}</span></div>
          <label>拍摄时间<input v-model="edit(photo).observed_at" type="datetime-local" step="60" required /></label>
          <fieldset><legend>照片中的物种</legend><label v-for="entry in observation.species_entries" :key="entry.id || entry.species_id"><input v-model="edit(photo).species_entry_ids" type="checkbox" :value="entry.id" />{{ entry.species_name }}</label></fieldset>
          <div class="observation-photo-manager-actions"><button type="button" class="secondary-button" :disabled="busy || !edit(photo).species_entry_ids.length" @click="savePhoto(photo)">保存照片信息</button><button v-if="!photo.is_cover" type="button" class="secondary-button" :disabled="busy" @click="savePhoto(photo, true)">设为封面</button><button type="button" class="danger-button" :disabled="busy || photos.length === 1" @click="removePhoto(photo)">移除</button></div>
        </div>
      </article>
    </div>
    <div class="observation-photo-add">
      <h4>补充照片</h4>
      <label>选择 JPEG/JPG<input type="file" accept="image/jpeg,.jpg,.jpeg" :disabled="busy || photos.length >= 20" @change="chooseFile" /></label>
      <img v-if="preview" :src="preview" alt="待加入照片预览" />
      <label v-if="file">拍摄时间<input v-model="observedAt" type="datetime-local" step="60" required /></label>
      <fieldset v-if="file"><legend>照片中的物种</legend><label v-for="entry in observation.species_entries" :key="entry.id || entry.species_id"><input v-model="selectedEntryIds" type="checkbox" :value="entry.id" />{{ entry.species_name }}</label></fieldset>
      <button v-if="file" type="button" class="primary-button" :disabled="busy || !observedAt || !selectedEntryIds.length" @click="addPhoto">保存这张补充照片</button>
    </div>
    <p class="field-hint" role="status">{{ status }}</p>
  </section>
</template>
