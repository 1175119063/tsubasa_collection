<script setup lang="ts">
import { computed } from "vue";
import type { ObservationRecord, ObservationSpeciesEntry } from "@/api/types";

const props = defineProps<{ observation: ObservationRecord }>();

const labels: Record<string, string> = {
  spring: "春", summer: "夏", autumn: "秋", winter: "冬", other: "其他",
};

function entries(item: ObservationRecord): ObservationSpeciesEntry[] {
  if (item.species_entries?.length) return item.species_entries;
  return [{
    id: null,
    species_id: item.species_id,
    species_name: item.species_name || "未命名物种",
    species_scientific_name: item.species_scientific_name || "",
    photo_type: item.photo_type,
    sex: item.sex,
    life_stage: item.life_stage,
    subspecies: item.subspecies,
    notes: null,
    is_primary: true,
  }];
}

const speciesEntries = computed(() => entries(props.observation));
const title = computed(() => {
  const names = speciesEntries.value.map((entry) => entry.species_name);
  return names.length > 2 ? `${names.slice(0, 2).join("、")}等 ${names.length} 种` : names.join("、");
});
const count = computed(() => props.observation.species_count || speciesEntries.value.length);
const dateTime = computed(() => props.observation.observed_at.replace("T", " ").slice(0, 16));
</script>

<template>
  <button class="v2-field-card" type="button">
    <span class="v2-field-photo">
      <img :src="observation.thumbnail_url" :alt="title" loading="lazy" />
      <i>#{{ String(observation.id).padStart(4, '0') }}</i>
      <span v-if="count > 1" class="observation-photo-count">{{ count }} 种同框</span>
      <span v-else-if="observation.photo_count > 1" class="observation-photo-count">{{ observation.photo_count }} 张</span>
    </span>
    <span class="v2-field-copy">
      <strong :title="title">{{ title }}</strong>
      <em>{{ count > 1 ? `${count} 种鸟类 · 同一次相遇` : speciesEntries[0]?.species_scientific_name }}</em>
      <span class="observation-card-meta"><span>时间</span><time :datetime="observation.observed_at">{{ dateTime }}</time></span>
      <small class="observation-card-meta"><span>地点</span><span :title="observation.location?.name || observation.locality">{{ observation.location?.name || observation.locality }}</span></small>
      <b><span>{{ labels[observation.season] || observation.season }} · {{ count > 1 ? "多物种照片" : observation.photo_type === "group" ? "群体照片" : "个体照片" }}</span><span v-if="observation.audio.length">{{ observation.audio.length }} 段录音</span></b>
    </span>
  </button>
</template>
