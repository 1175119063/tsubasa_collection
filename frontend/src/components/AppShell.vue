<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import FeatherAssistant from "@/components/FeatherAssistant.vue";

const route = useRoute();
const currentName = computed(() => String(route.name ?? "home"));
const assistantPage = computed(() => {
  const value = currentName.value;
  return (["home", "observations", "dex", "locations", "map", "trips"].includes(value) ? value : "home") as
    "home" | "observations" | "dex" | "locations" | "map" | "trips";
});

const navItems = [
  { name: "home", label: "探索营地", to: "/" },
  { name: "dex", label: "鸟类调查册", to: "/dex" },
  { name: "observations", label: "田野记录", to: "/observations" },
  { name: "locations", label: "区域档案", to: "/locations" },
  { name: "trips", label: "远征日志", to: "/trips" },
];
</script>

<template>
  <div class="v2-grain" aria-hidden="true"></div>
  <header class="v2-topbar">
    <RouterLink class="v2-brand" to="/">
      <span class="v2-brand-seal">
        <img :src="'/static/assets/wing-chronicle-logo.png?v=20260816-1'" alt="" aria-hidden="true" />
      </span>
      <span><strong>翼·时光记</strong><small>EXPLORER'S FIELD JOURNAL</small></span>
    </RouterLink>
    <nav class="v2-topnav" aria-label="主要导航">
      <RouterLink
        v-for="item in navItems"
        :key="item.name"
        :class="{ 'is-active': currentName === item.name || (currentName === 'map' && item.name === 'locations') }"
        :to="item.to"
      >{{ item.label }}</RouterLink>
    </nav>
    <a class="v2-stable-link" href="/">当前稳定版</a>
  </header>
  <slot />
  <footer class="v2-footer">
    <span>翼·时光记 · 探索者田野日志</span><span>所有资料仍保存在本地</span>
  </footer>
  <FeatherAssistant :page="assistantPage" />
</template>
