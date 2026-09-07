<script setup lang="ts">
import { onMounted, watch } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppShell from "@/components/AppShell.vue";

const route = useRoute();

function syncDocumentTitle(): void {
  document.title = `${String(route.meta.title ?? "探索营地")} · 翼·时光记`;
  document.body.dataset.page = String(route.name ?? "home");
}

onMounted(syncDocumentTitle);
watch(() => route.fullPath, syncDocumentTitle);
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
</template>
