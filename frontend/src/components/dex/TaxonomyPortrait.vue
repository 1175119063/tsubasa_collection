<script setup lang="ts">
import { computed } from "vue";
import TaxonomyPlaceholder from "./TaxonomyPlaceholder.vue";

const props = defineProps<{
  urls: string[];
  label: string;
}>();

const portrait = computed(() => props.urls[0]);
</script>

<template>
  <span
    class="v2-taxonomy-portrait"
    :class="{ 'has-photo': portrait }"
    data-taxonomy-avatar
    :aria-label="portrait ? `${label}的分类头像` : `${label}暂无分类头像`"
  >
    <img v-if="portrait" :src="portrait" alt="" />
    <TaxonomyPlaceholder v-else />
  </span>
</template>
