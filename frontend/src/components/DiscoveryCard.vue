<script setup lang="ts">
import type { SpeciesSummary } from "@/api/types";

defineProps<{
  species: SpeciesSummary;
  compact?: boolean;
}>();
</script>

<template>
  <button class="v2-discovery-card" :class="{ 'is-compact': compact }" type="button">
    <span class="v2-discovery-photo">
      <img :src="species.cover_url" :alt="species.chinese_name" loading="lazy" />
    </span>
    <span class="v2-discovery-copy">
      <span class="v2-card-code">{{ species.catalog_number }}</span>
      <strong>{{ species.chinese_name }}</strong>
      <em>{{ species.scientific_name }}</em>
      <span class="v2-card-facts">
        <i>{{ species.order_name }} · {{ species.family_name }}</i>
        <i>{{ species.observation_count }} 次记录</i>
      </span>
    </span>
  </button>
</template>
