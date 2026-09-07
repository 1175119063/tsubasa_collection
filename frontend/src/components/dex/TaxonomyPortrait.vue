<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  urls: string[];
  label: string;
}>();

const portraits = computed(() => props.urls.slice(0, 4));
</script>

<template>
  <span
    class="v2-taxonomy-portrait"
    :class="`has-${portraits.length}`"
    data-taxonomy-avatar
    :aria-label="portraits.length ? `${label}的分类头像` : `${label}暂无分类头像`"
  >
    <img v-for="(url, index) in portraits" :key="`${url}-${index}`" :src="url" alt="" />
    <b v-if="!portraits.length" aria-hidden="true">羽</b>
  </span>
</template>
