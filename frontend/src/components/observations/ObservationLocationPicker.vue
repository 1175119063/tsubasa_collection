<script setup lang="ts">
import { computed, ref } from "vue";
import type { EntryLocation } from "./observation-entry";

const props = defineProps<{ modelValue: string; locations: EntryLocation[]; allowCreate?: boolean }>();
const emit = defineEmits<{ "update:modelValue": [value: string]; create: [] }>();
const query = ref("");
const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase().trim();
const terms = computed(() => normalize(query.value).split(/\s+/u).filter(Boolean));
const selected = computed(() => props.locations.find((item) => String(item.id) === props.modelValue));
const matches = computed(() => {
  if (!terms.value.length) return [];
  return props.locations.filter((item) => {
    const text = normalize([item.name, item.admin1_name, item.city, item.district].filter(Boolean).join(" "));
    return terms.value.every((term) => text.includes(term));
  });
});
function select(value: string): void {
  emit("update:modelValue", value);
  query.value = "";
}
</script>

<template>
  <div class="location-picker full-field">
    <label>地点资料库<input v-model="query" type="search" data-observation-location-search placeholder="搜索地点、城市或行政区" autocomplete="off" /></label>
    <p v-if="terms.length" class="location-picker-status" role="status">{{ matches.length ? `找到 ${matches.length} 个地点，点击选择` : "没有找到匹配地点；可去区域档案新增。" }}</p>
    <ul v-if="terms.length && matches.length" class="location-picker-results" aria-label="地点检索结果">
      <li v-for="item in matches" :key="item.id">
        <button type="button" :aria-pressed="modelValue === String(item.id)" @click="select(String(item.id))">
          <strong>{{ item.name }}</strong><span>{{ [item.admin1_name, item.city, item.district].filter(Boolean).join(" · ") }}</span>
        </button>
      </li>
    </ul>
    <div v-if="selected" class="location-picker-selected">
      <span>已关联：<strong>{{ selected.name }}</strong> · {{ selected.admin1_name }}</span>
      <button type="button" class="link-button" @click="select('')">清除关联</button>
    </div>
    <button v-if="allowCreate" class="secondary-button location-picker-create" type="button" data-location-create @click="emit('create')">＋ 区域档案中新增地点</button>
  </div>
</template>

<style scoped>
.location-picker { display: grid; gap: 10px; }
.location-picker-status { margin: 0; color: var(--ink-soft); font: 12px/1.7 var(--sans); }
.location-picker-results { position: static; max-height: 220px; overflow-y: auto; margin: 0; padding: 0; list-style: none; border: 1px solid var(--line); border-radius: 3px; background: var(--paper-light); }
.location-picker-results li + li { border-top: 1px solid var(--line); }
.location-picker-results button { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; width: 100%; padding: 10px 12px; border: 0; background: transparent; color: var(--ink); text-align: left; font: 13px/1.6 var(--sans); cursor: pointer; }
.location-picker-results button:hover, .location-picker-results button[aria-pressed="true"] { background: var(--paper); }
.location-picker-results span { color: var(--ink-soft); font-size: 12px; }
.location-picker-selected { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 9px 12px; border: 1px solid var(--line); border-radius: 3px; background: var(--paper); font: 12px/1.6 var(--sans); }
.location-picker-create { justify-self: start; }
</style>
