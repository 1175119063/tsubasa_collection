<script setup lang="ts">
import { computed, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { OnlineSpeciesResult } from "@/api/online-species";
import type { Subspecies } from "./observation-entry";

const props = defineProps<{
  scientificName: string;
  latitude?: number | null;
  longitude?: number | null;
  locality?: string | null;
  observedAt?: string | null;
  subspecies: Subspecies[];
  modelValue: number | null;
}>();
const emit = defineEmits<{ "update:modelValue": [value: number | null] }>();
const open = ref(false);
const busy = ref(false);
const result = ref<OnlineSpeciesResult | null>(null);
const message = ref("");
const ready = computed(() => Boolean(props.scientificName.trim())
  && typeof props.latitude === "number" && typeof props.longitude === "number"
  && Number.isFinite(props.latitude) && Number.isFinite(props.longitude)
  && Boolean(props.observedAt));
const normalize = (value: string | null | undefined) => (value || "").normalize("NFKC").toLocaleLowerCase().replace(/[^a-z0-9]/g, "");
const localMatches = computed(() => {
  const byName = new Map(props.subspecies.map((item) => [normalize(item.scientific_name), item]));
  return (result.value?.ai?.subspecies ?? []).map((item) => ({ ...item, local: byName.get(normalize(item.name)) || null }));
});
async function suggest(): Promise<void> {
  if (!ready.value || busy.value) return;
  open.value = true;
  busy.value = true;
  message.value = "正在请飞羽精灵按地点与亚种资料排序…";
  try {
    const body: Record<string, unknown> = {
      query: props.scientificName.trim(),
      latitude: props.latitude,
      longitude: props.longitude,
      observed_at: props.observedAt,
    };
    if (props.locality?.trim()) body.locality = props.locality.trim();
    result.value = await api<OnlineSpeciesResult>("/api/assistant/online-species/search", jsonRequest("POST", body));
    message.value = result.value.ai?.available
      ? (result.value.ai.message || "AI 建议已生成；请核对后手动选择。")
      : (result.value.ai?.message || "AI 暂不可用，可参考 iNaturalist 亚种列表。");
  } catch (caught) {
    message.value = errorMessage(caught);
  } finally {
    busy.value = false;
  }
}
function choose(id: number | null): void {
  if (id === null) return;
  emit("update:modelValue", id);
  message.value = "已填入所选亚种；保存前仍可修改。";
}
</script>

<template>
  <div class="subspecies-assistant full-field">
    <button class="secondary-button" type="button" data-subspecies-ai :disabled="!ready || busy" @click="suggest">
      ✦ {{ busy ? "正在判断亚种…" : "AI 辅助判断亚种" }}
    </button>
    <p v-if="!ready" class="subspecies-assistant-hint">填写拍摄时间与经纬度后可用；AI 只给建议，不自动选中。</p>
    <section v-else-if="open" class="subspecies-assistant-panel" data-subspecies-ai-panel aria-live="polite">
      <p class="subspecies-assistant-hint">{{ message }}</p>
      <ul v-if="localMatches.length" class="subspecies-assistant-list">
        <li v-for="item in localMatches" :key="item.id">
          <div><strong>{{ item.common_name || item.name }}</strong><span>{{ item.name }} · {{ item.confidence === "high" ? "高置信" : item.confidence === "low" ? "低置信" : "中置信" }}</span><p>{{ item.reason }}</p></div>
          <button v-if="item.local" type="button" :aria-pressed="modelValue === item.local.id" @click="choose(item.local.id)">{{ modelValue === item.local.id ? "已选" : "选为亚种" }}</button>
          <small v-else>本地亚种名单暂无此项，请先在图鉴中补充。</small>
        </li>
      </ul>
      <p v-else-if="result?.taxon?.children?.length" class="subspecies-assistant-hint">AI 没有给出可用的亚种排序；可直接参考 iNaturalist 列表核对。</p>
    </section>
  </div>
</template>

<style scoped>
.subspecies-assistant { display: grid; gap: 8px; }
.subspecies-assistant > button { justify-self: start; }
.subspecies-assistant-hint { margin: 0; color: var(--ink-soft); font: 12px/1.7 var(--sans); }
.subspecies-assistant-panel { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--line); border-radius: 4px; background: var(--paper-light); }
.subspecies-assistant-list { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
.subspecies-assistant-list li { display: flex; align-items: start; justify-content: space-between; gap: 14px; padding: 10px 0; border-top: 1px solid var(--line); }
.subspecies-assistant-list li:first-child { border-top: 0; }
.subspecies-assistant-list strong, .subspecies-assistant-list span { display: block; }
.subspecies-assistant-list span { margin-top: 3px; color: var(--ink-soft); font: 11px/1.5 var(--sans); }
.subspecies-assistant-list p { margin: 6px 0 0; font: 12px/1.7 var(--sans); }
.subspecies-assistant-list button { flex: 0 0 auto; }
.subspecies-assistant-list small { flex: 0 1 180px; color: var(--rust); font: 11px/1.6 var(--sans); }
</style>
