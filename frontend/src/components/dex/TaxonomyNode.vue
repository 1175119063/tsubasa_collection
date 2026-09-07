<script setup lang="ts">
import type { TaxonomyNode } from "@/components/dex/taxonomy-model";
import { taxonomyRankLabel } from "@/components/dex/taxonomy-model";
import TaxonomyPortrait from "@/components/dex/TaxonomyPortrait.vue";

defineProps<{
  node: TaxonomyNode;
  role: "child" | "current" | "parent";
}>();

defineEmits<{ select: [key: TaxonomyNode["key"]] }>();
</script>

<template>
  <button
    type="button"
    class="v2-taxonomy-node"
    :class="`is-${role}`"
    :aria-current="role === 'current' ? 'true' : undefined"
    :aria-label="role === 'current' ? `当前${taxonomyRankLabel(node.rank)}：${node.chineseName}` : `查看${taxonomyRankLabel(node.rank)}：${node.chineseName}`"
    :data-taxonomy-current="role === 'current' ? '' : undefined"
    :data-taxonomy-parent="role === 'parent' ? '' : undefined"
    :data-taxonomy-child="role === 'child' ? '' : undefined"
    :data-rank="node.rank"
    :data-node-id="node.sourceId"
    @click="$emit('select', node.key)"
  >
    <TaxonomyPortrait :urls="node.portraitUrls" :label="node.chineseName" />
    <span class="v2-taxonomy-node-copy">
      <small v-if="node.rank === 'species' && node.catalogNumber">{{ node.catalogNumber }}</small>
      <strong>{{ node.chineseName }}</strong>
      <em>{{ node.scientificName }}</em>
    </span>
  </button>
</template>
