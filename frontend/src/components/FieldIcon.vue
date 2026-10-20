<script setup lang="ts">
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  home: "M3 20 12 4l9 16H3Zm5 0 4-8 4 8M12 4V2m-8 8 2-1m12 0 2 1",
  dex: "M4 4c3-1 5 0 8 2 3-2 5-3 8-2v15c-3-1-5 0-8 2-3-2-5-3-8-2V4Zm8 2v15M7 8l2 1m-2 3 2 1m6-4 2-1m-2 5 2-1",
  observations: "M6 3h14v18H6V3ZM3 7h5m-5 5h5m-5 5h5m3-8h5m-5 4h5m-5 4h3",
  locations: "M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0ZM15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  trips: "m3 18 5-9 4 6 3-4 6 7H3ZM15 4v7m0-7h5l-2 2 2 2h-5",
  collections: "M4 6h16v15H4V6Zm3-3h10M4 10h16m-10 5h4m-2-2v4",
};
</script>

<template>
  <svg class="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path :d="paths[name] || paths.dex" /></svg>
</template>
