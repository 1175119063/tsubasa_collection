<script setup lang="ts">
import { computed, ref } from "vue";
import type { ObservationSummary } from "@/api/types";

const props = defineProps<{
  observations: ObservationSummary[];
  featuredId: number | null;
  loading: boolean;
  status: string;
}>();

const emit = defineEmits<{
  select: [observationId: number | null];
  open: [];
}>();

const dialog = ref<HTMLDialogElement>();
const query = ref("");

const filtered = computed(() => {
  const needle = query.value.trim().toLocaleLowerCase();
  if (!needle) return props.observations;
  return props.observations.filter((item) => [
    item.catalog_number,
    item.species_name,
    item.species_scientific_name,
    item.locality,
    item.admin1_name,
    item.observed_at,
  ].some((value) => String(value || "").toLocaleLowerCase().includes(needle)));
});

function open(): void {
  query.value = "";
  dialog.value?.showModal();
  emit("open");
}

function close(): void {
  dialog.value?.close();
}

defineExpose({ open, close });
</script>

<template>
  <dialog ref="dialog" class="v2-home-cover-dialog" @click.self="close">
    <header>
      <div><p class="v2-kicker">CAMP COVER ARCHIVE</p><h2>选择首页封面</h2></div>
      <button type="button" aria-label="关闭" @click="close">×</button>
    </header>
    <div class="v2-home-cover-toolbar">
      <label for="vue-home-cover-search">搜索已有观察记录</label>
      <input
        id="vue-home-cover-search"
        v-model="query"
        type="search"
        placeholder="输入物种名、图鉴编号、地点或日期"
        autocomplete="off"
      />
      <p v-if="loading">正在整理照片档案……</p>
      <p v-else-if="status">{{ status }}</p>
      <p v-else>共 {{ observations.length }} 笔记录，当前显示 {{ filtered.length }} 笔</p>
    </div>
    <div class="v2-home-cover-grid">
      <button
        v-for="item in filtered"
        :key="item.id"
        class="v2-home-cover-card"
        :class="{ 'is-selected': item.id === featuredId }"
        type="button"
        @click="emit('select', item.id)"
      >
        <img :src="item.thumbnail_url" :alt="item.species_name" loading="lazy" />
        <span>
          <b>{{ item.species_name }}</b>
          <i>{{ item.catalog_number }} · OBSERVATION {{ item.id }}</i>
          <small>{{ item.observed_at.replace("T", " ") }}<br />{{ item.admin1_name }} · {{ item.locality }}</small>
        </span>
        <em>{{ item.id === featuredId ? "当前首页封面" : "设为首页封面" }}</em>
      </button>
      <p v-if="!loading && !filtered.length" class="v2-loading">没有符合搜索条件的观察记录。</p>
    </div>
    <footer>
      <button class="v2-button v2-button-ghost" type="button" @click="emit('select', null)">
        恢复自动选择最新记录
      </button>
    </footer>
  </dialog>
</template>
