<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { ObservationRecord, SpeciesSummary } from "@/api/types";
import BehaviorPicker from "./BehaviorPicker.vue";
import ObservationPhotoManager from "./ObservationPhotoManager.vue";

interface Subspecies { id: number; chinese_name: string | null; scientific_name: string }
const props = defineProps<{ observation: ObservationRecord; species: SpeciesSummary[]; initialIndex: number }>();
const emit = defineEmits<{ close: []; updated: [observation: ObservationRecord] }>();
const current = ref(props.observation);
const index = ref(props.initialIndex);
const subspecies = ref<Subspecies[]>([]);
const status = ref("");
const entry = computed(() => current.value.species_entries[index.value]);
const availableSpecies = computed(() => {
  const ids = new Set(current.value.species_entries.map((item) => item.species_id));
  return props.species.filter((item) => !ids.has(item.id));
});
const newSpeciesId = ref("");
const newPhotoType = ref<"individual" | "group">("individual");
const sex = ref<string | null>(null);
const lifeStage = ref<string | null>(null);
const subspeciesId = ref<number | null>(null);
const entryNotes = ref("");
const behaviorLabels = ref<string[]>([]);
const behaviorDrafts = new Map<number, string[]>();
const observationNotes = ref(current.value.notes || "");

async function syncEntry(): Promise<void> {
  const value = entry.value;
  if (!value) return;
  sex.value = value.sex;
  lifeStage.value = value.life_stage;
  subspeciesId.value = value.subspecies?.id || null;
  entryNotes.value = value.notes || "";
  behaviorLabels.value = [...(behaviorDrafts.get(value.species_id) || value.behavior_labels || [])];
  if (value.photo_type === "individual") {
    try {
      subspecies.value = [];
      const detail = await api<{ subspecies: Subspecies[] }>(`/api/species/${value.species_id}`);
      if (entry.value?.species_id === value.species_id) subspecies.value = detail.subspecies;
    } catch (caught) { status.value = errorMessage(caught); }
  } else subspecies.value = [];
}
watch(() => entry.value?.species_id, (_value, previous) => {
  if (previous) behaviorDrafts.set(previous, [...behaviorLabels.value]);
  void syncEntry();
}, { immediate: true });

async function addSpecies(): Promise<void> {
  const speciesId = Number(newSpeciesId.value);
  if (!speciesId) return;
  status.value = "正在加入物种…";
  try {
    current.value = await api<ObservationRecord>(`/api/observations/${current.value.id}/species`, jsonRequest("POST", {
      species_id: speciesId,
      photo_type: newPhotoType.value,
      sex: newPhotoType.value === "individual" ? "unknown" : null,
      life_stage: newPhotoType.value === "individual" ? "unknown" : null,
      subspecies_id: null,
      notes: null,
    }));
    index.value = current.value.species_entries.findIndex((item) => item.species_id === speciesId);
    newSpeciesId.value = "";
    status.value = "";
    emit("updated", current.value);
  } catch (caught) { status.value = errorMessage(caught); }
}
async function removeSpecies(): Promise<void> {
  const value = entry.value;
  if (!value?.id || current.value.species_entries.length === 1 || !confirm(`从这笔观察中删除“${value.species_name}”的观察信息吗？照片和其他物种信息会保留。`)) return;
  status.value = "正在移除物种…";
  try {
    await api(`/api/observations/${current.value.id}/species/${value.id}`, { method: "DELETE" });
    current.value = await api<ObservationRecord[]>("/api/observations").then((items) => items.find((item) => item.id === current.value.id) as ObservationRecord);
    index.value = 0;
    emit("updated", current.value);
  } catch (caught) { status.value = errorMessage(caught); }
}
async function save(): Promise<void> {
  const value = entry.value;
  if (!value?.id) return;
  status.value = "正在保存…";
  try {
    const speciesUpdated = await api<ObservationRecord>(`/api/observations/${current.value.id}/species/${value.id}`, jsonRequest("PATCH", {
      sex: value.photo_type === "individual" ? sex.value : null,
      life_stage: value.photo_type === "individual" ? lifeStage.value : null,
      subspecies_id: value.photo_type === "individual" ? subspeciesId.value : null,
      notes: entryNotes.value || null,
      behavior_labels: behaviorLabels.value,
    }));
    behaviorDrafts.set(value.species_id, [...behaviorLabels.value]);
    for (const other of speciesUpdated.species_entries) {
      if (other.id === value.id || !behaviorDrafts.has(other.species_id)) continue;
      await api(`/api/observations/${current.value.id}/species/${other.id}`, jsonRequest("PATCH", {
        sex: other.sex, life_stage: other.life_stage, subspecies_id: other.subspecies?.id || null,
        notes: other.notes, behavior_labels: behaviorDrafts.get(other.species_id),
      }));
    }
    const primary = speciesUpdated.species_entries.find((item) => item.is_primary) || speciesUpdated.species_entries[0];
    current.value = await api<ObservationRecord>(`/api/observations/${current.value.id}`, jsonRequest("PATCH", {
      sex: primary.photo_type === "individual" ? primary.sex : null,
      life_stage: primary.photo_type === "individual" ? primary.life_stage : null,
      subspecies_id: primary.photo_type === "individual" ? primary.subspecies?.id || null : null,
      notes: observationNotes.value || null,
    }));
    emit("updated", current.value);
    emit("close");
  } catch (caught) { status.value = errorMessage(caught); }
}
function photosUpdated(updated: ObservationRecord): void {
  current.value = updated;
  emit("updated", updated);
}
</script>

<template>
  <form class="observation-edit-form" @submit.prevent="save">
    <header class="dialog-header"><div><p class="eyebrow">EDIT OBSERVATION</p><h2>修改观察记录</h2><span>可以管理照片；观察的主要时间与地点保持不变</span></div><button type="button" class="icon-button" @click="$emit('close')">×</button></header>
    <div class="form-scroll">
      <ObservationPhotoManager :observation="current" @updated="photosUpdated" />
      <section class="observation-species-manager">
        <label>正在编辑的物种<select v-model.number="index"><option v-for="(item, itemIndex) in current.species_entries" :key="item.id || item.species_id" :value="itemIndex">{{ item.species_name }}{{ item.is_primary ? " · 主记录" : "" }}</option></select></label>
        <div class="observation-add-species"><label>加入其他物种<select v-model="newSpeciesId"><option value="">选择尚未记录的物种</option><option v-for="item in availableSpecies" :key="item.id" :value="String(item.id)">{{ item.chinese_name }} · {{ item.scientific_name }}</option></select></label><label>照片类型<select v-model="newPhotoType"><option value="individual">个体照片</option><option value="group">群体照片</option></select></label><button type="button" class="secondary-button" :disabled="!newSpeciesId" @click="addSpecies">加入这笔观察</button></div>
      </section>
      <div v-if="entry?.photo_type === 'individual'" class="observation-edit-grid"><label>性别<select v-model="sex"><option value="unknown">未知</option><option value="male">雄性</option><option value="female">雌性</option></select></label><label>生命阶段<select v-model="lifeStage"><option value="unknown">未知</option><option value="egg">卵</option><option value="chick">雏鸟</option><option value="subadult">亚成</option><option value="adult">成鸟</option></select></label><label class="full-field">亚种<select v-model="subspeciesId"><option :value="null">未知 / 无亚种</option><option v-for="item in subspecies" :key="item.id" :value="item.id">{{ item.chinese_name ? `${item.chinese_name} · ` : "" }}{{ item.scientific_name }}</option></select></label></div>
      <p v-else class="field-hint">这是群体照片，可以修改行为标签和备注。</p>
      <BehaviorPicker v-if="entry" :key="entry.species_id" v-model="behaviorLabels" :species-id="entry.species_id" />
      <label>物种备注<textarea v-model="entryNotes" rows="3"></textarea></label>
      <label>整笔观察备注<textarea v-model="observationNotes" rows="4"></textarea></label>
    </div>
    <footer class="dialog-footer">
      <span role="status">{{ status }}</span>
      <div class="observation-editor-actions">
        <button type="button" class="danger-button" :disabled="current.species_entries.length === 1" @click="removeSpecies">删除当前物种信息</button>
        <button type="button" class="secondary-button" @click="$emit('close')">取消</button>
        <button type="submit" class="primary-button">保存修改</button>
      </div>
    </footer>
  </form>
</template>
