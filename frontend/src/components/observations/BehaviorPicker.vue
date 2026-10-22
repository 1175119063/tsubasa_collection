<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { api, errorMessage } from "@/api/client";

const props = defineProps<{ modelValue: string[]; speciesId?: number | null }>();
const emit = defineEmits<{ "update:modelValue": [labels: string[]] }>();
const available = ref<string[]>([]);
const name = ref("");
const status = ref("");
const loading = ref(false);
const key = (value: string) => value.normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();
const choices = computed(() => {
  const labels = new Map<string, string>();
  [...available.value, ...props.modelValue].forEach((label) => labels.set(key(label), label));
  return [...labels.values()];
});
watch(() => props.speciesId, async (id, _, onCleanup) => {
  let active = true;
  onCleanup(() => { active = false; });
  available.value = []; name.value = ""; status.value = "";
  loading.value = Boolean(id);
  if (!id) return;
  try {
    const tags = await api<Array<{ label: string }>>(`/api/species/${id}/behaviors`);
    if (active) available.value = tags.map((tag) => tag.label);
  } catch (caught) { if (active) status.value = `行为标签读取失败：${errorMessage(caught)}`; }
  finally { if (active) loading.value = false; }
}, { immediate: true });
function selected(label: string): boolean { return props.modelValue.some((value) => key(value) === key(label)); }
function toggle(label: string): void {
  if (selected(label)) emit("update:modelValue", props.modelValue.filter((v) => key(v) !== key(label)));
  else if (props.modelValue.length < 50) emit("update:modelValue", [...props.modelValue, label]);
  else status.value = "每个物种在一笔观察中最多选择 50 个行为标签。";
}
function add(): void {
  const label = name.value.trim();
  if (!label) return;
  const existing = choices.value.find((v) => key(v) === key(label));
  if (!selected(existing || label)) toggle(existing || label);
  name.value = "";
}
</script>

<template>
  <section class="behavior-picker" aria-label="行为标签">
    <strong>行为标签（可多选）</strong>
    <p class="field-hint">记录这次观察中该物种的行为。新标签随观察一起保存，并加入该物种的行为档案。</p>
    <p v-if="loading" role="status">正在读取已有标签…</p>
    <div class="behavior-choices"><label v-for="label in choices" :key="key(label)"><input type="checkbox" :checked="selected(label)" @change="toggle(label)" />{{ label }}</label></div>
    <p v-if="!loading && !choices.length" class="field-hint">暂无行为标签，可以在下方新建。</p>
    <div class="behavior-create"><label>新行为标签<input v-model="name" maxlength="80" placeholder="例如：飞行、捕食、理羽" @keydown.enter.prevent="add" /></label><button type="button" class="secondary-button" :disabled="!name.trim()" @click="add">添加并选中</button></div>
    <p v-if="status" role="alert">{{ status }}</p>
  </section>
</template>

<style scoped>
.behavior-picker { grid-column: 1 / -1; padding: 14px; border: 1px solid var(--line); border-radius: 6px; }
.behavior-choices { display: flex; flex-wrap: wrap; gap: 8px 16px; }
.behavior-choices label { display: flex; align-items: center; gap: 7px; }
.behavior-choices input { width: 16px; height: 16px; margin: 0; }
.behavior-create { display: flex; gap: 12px; align-items: end; margin-top: 12px; }
.behavior-create label { flex: 1; min-width: 0; }
@media(max-width:600px) { .behavior-create { flex-wrap: wrap; } }
</style>
