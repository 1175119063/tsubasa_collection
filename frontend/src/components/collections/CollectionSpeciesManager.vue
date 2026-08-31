<script setup lang="ts">
import { computed, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { CollectionPlanDetail, SpeciesSummary } from "@/api/types";

const props = defineProps<{
  plan: CollectionPlanDetail;
  species: SpeciesSummary[];
}>();
const emit = defineEmits<{
  close: [];
  saved: [plan: CollectionPlanDetail];
}>();

const query = ref("");
const speciesIds = ref(props.plan.memberships.map((item) => item.species_id));
const status = ref("勾选鸟种后，可以在下方调整它们的展示顺序。");
const saving = ref(false);
const filteredSpecies = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  return props.species.filter((item) => !needle
    || item.chinese_name.toLocaleLowerCase().includes(needle)
    || item.scientific_name.toLocaleLowerCase().includes(needle));
});
const selectedSpecies = computed(() => speciesIds.value
  .map((id) => props.species.find((item) => item.id === id))
  .filter((item): item is SpeciesSummary => Boolean(item)));

function toggleSpecies(id: number): void {
  const index = speciesIds.value.indexOf(id);
  if (index >= 0) speciesIds.value.splice(index, 1);
  else speciesIds.value.push(id);
}
function moveSpecies(index: number, offset: number): void {
  const target = index + offset;
  if (target < 0 || target >= speciesIds.value.length) return;
  [speciesIds.value[index], speciesIds.value[target]] = [speciesIds.value[target], speciesIds.value[index]];
}
async function save(): Promise<void> {
  saving.value = true;
  status.value = "正在整理计划中的鸟种…";
  try {
    const plan = await api<CollectionPlanDetail>(
      `/api/collections/${props.plan.id}/species`,
      jsonRequest("PUT", { species_ids: speciesIds.value }),
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
  <form class="collection-member-form" @submit.prevent="save">
    <header class="dialog-header"><div><p class="eyebrow">MEMBER SPECIES</p><h2>管理计划中的鸟种</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">×</button></header>
    <div class="form-scroll collection-member-scroll">
      <p class="section-note">这里只列出已经进入鸟类调查册的物种。取消勾选会将鸟种及其计划头像移出本计划，但不会删除任何田野记录或照片。</p>
      <label class="collection-member-search">查找鸟种<input v-model="query" type="search" placeholder="按中文名或拉丁名查找" /></label>
      <div class="collection-species-options">
        <label v-for="item in filteredSpecies" :key="item.id">
          <input type="checkbox" :checked="speciesIds.includes(item.id)" @change="toggleSpecies(item.id)" />
          <img :src="item.cover_url" alt="" /><span><b>{{ item.chinese_name }}</b><small>{{ item.scientific_name }}</small></span>
        </label>
      </div>
      <p v-if="!filteredSpecies.length" class="compact-empty">没有符合检索条件的已观察鸟种。</p>
      <div v-if="selectedSpecies.length" class="collection-order-list">
        <p>展示顺序 · {{ selectedSpecies.length }} 种</p>
        <div v-for="(item, index) in selectedSpecies" :key="item.id">
          <span>{{ index + 1 }}. {{ item.chinese_name }}</span>
          <button type="button" :disabled="index === 0" :aria-label="`${item.chinese_name}上移`" @click="moveSpecies(index, -1)">↑</button>
          <button type="button" :disabled="index === selectedSpecies.length - 1" :aria-label="`${item.chinese_name}下移`" @click="moveSpecies(index, 1)">↓</button>
        </div>
      </div>
    </div>
    <footer class="dialog-footer"><span>{{ status }}</span><button class="primary-button" type="submit" :disabled="saving">{{ saving ? "保存中…" : "保存鸟种" }}</button></footer>
  </form>
</template>
