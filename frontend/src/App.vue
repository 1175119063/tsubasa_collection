<script setup lang="ts">
import { onMounted, watch } from "vue";
import { RouterView, useRoute } from "vue-router";
import AppShell from "@/components/AppShell.vue";

const route = useRoute();

function syncDocumentTitle(): void {
  document.title = `${String(route.meta.title ?? "探索营地")} · 翼·时光记`;
  document.body.dataset.page = String(route.name ?? "home");
  const needsLegacyStyles = !["home", "map"].includes(String(route.name ?? "home"));
  const existing = document.querySelector<HTMLLinkElement>("link[data-vue-legacy-styles]");
  if (needsLegacyStyles && !existing) {
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = "/static/styles.css?v=20260816-4";
    stylesheet.dataset.vueLegacyStyles = "true";
    document.head.append(stylesheet);
  } else if (!needsLegacyStyles) {
    existing?.remove();
  }
}

onMounted(syncDocumentTitle);
watch(() => route.fullPath, syncDocumentTitle);
</script>

<template>
  <AppShell>
    <RouterView />
  </AppShell>
</template>
