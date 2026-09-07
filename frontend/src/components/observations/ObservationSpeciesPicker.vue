<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import type { SpeciesSummary } from "@/api/types";

const props = defineProps<{
  modelValue: string;
  species: SpeciesSummary[];
  searchLabel: string;
  selectLabel: string;
  allowNew?: boolean;
}>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();
const query = ref("");
const choice = ref<HTMLSelectElement | null>(null);
const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase().trim();
const terms = computed(() => normalize(query.value).split(/\s+/u).filter(Boolean));
const matches = computed(() => props.species.filter((item) => {
  const text = normalize([
    item.catalog_number, item.chinese_name, item.scientific_name,
    item.family_name, item.family_scientific_name, item.genus_name, item.genus_scientific_name,
  ].join(" "));
  return terms.value.every((term) => text.includes(term));
}));
// Keep the current choice visible even when searching for a replacement.
const options = computed(() => props.species.filter((item) =>
  String(item.id) === props.modelValue || matches.value.includes(item),
));
function select(value: string): void {
  emit("update:modelValue", value);
  query.value = "";
  void nextTick(() => choice.value?.focus());
}
</script>

<template>
  <div class="species-picker full-field">
    <label>{{ searchLabel }}<input v-model="query" type="search" placeholder="图鉴编号、中文名、拉丁学名、科名或属名" /></label>
    <template v-if="terms.length">
      <p class="species-search-status" role="status">{{ matches.length ? `找到 ${matches.length} 个物种，点击选择` : '没有找到匹配的已有物种，请尝试其他名称或编号。' }}</p>
      <ul v-if="matches.length" class="observation-species-results" :aria-label="`${searchLabel}结果`">
        <li v-for="item in matches" :key="item.id">
          <button type="button" :aria-pressed="modelValue === String(item.id)" @click="select(String(item.id))">
            <strong>{{ item.chinese_name }}</strong><span>{{ item.scientific_name }}</span><small>{{ item.catalog_number }}</small>
          </button>
        </li>
      </ul>
    </template>
    <label>{{ selectLabel }}<select ref="choice" :value="modelValue" :required="allowNew" @change="select(($event.target as HTMLSelectElement).value)">
      <option value="" :disabled="allowNew">{{ allowNew ? '请选择物种' : '选择物种' }}</option>
      <option v-if="allowNew" value="new">＋ 登记新物种</option>
      <option v-for="item in options" :key="item.id" :value="String(item.id)">{{ item.catalog_number }} · {{ item.chinese_name }} · {{ item.scientific_name }}</option>
    </select></label>
  </div>
</template>

<style scoped>
.species-picker { display: grid; gap: 12px; min-width: 0; }
.species-search-status { margin: 0; color: var(--ink-soft); font: 12px/1.7 var(--sans); }
/* Keep results in the form flow, independent of legacy search popup styles. */
.observation-species-results { position: static; min-width: 0; max-height: 220px; overflow-y: auto; margin: 0; padding: 0; list-style: none; border: 1px solid var(--line); border-radius: 3px; background: var(--paper-light); }
.observation-species-results li + li { border-top: 1px solid var(--line); }
.observation-species-results button { display: flex; align-items: baseline; flex-wrap: wrap; gap: 4px 12px; width: 100%; padding: 10px 12px; border: 0; border-radius: 0; background: transparent; color: var(--ink); text-align: left; font: 13px/1.6 var(--sans); cursor: pointer; }
.observation-species-results button:hover, .observation-species-results button[aria-pressed="true"] { background: var(--paper); }
.observation-species-results span { font-style: italic; overflow-wrap: anywhere; }
.observation-species-results small { margin-left: auto; color: var(--ink-soft); }
</style>
