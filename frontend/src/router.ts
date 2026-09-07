import { createRouter, createWebHistory } from "vue-router";
import HomePage from "@/pages/HomePage.vue";
import DexPage from "@/pages/DexPage.vue";
import MapPage from "@/pages/MapPage.vue";
import ObservationsPage from "@/pages/ObservationsPage.vue";
import LocationsPage from "@/pages/LocationsPage.vue";
import TripsPage from "@/pages/TripsPage.vue";
import CollectionsPage from "@/pages/CollectionsPage.vue";

const router = createRouter({
  history: createWebHistory("/"),
  routes: [
    { path: "/", name: "home", component: HomePage, meta: { title: "探索营地" } },
    { path: "/dex", name: "dex", component: DexPage, meta: { title: "鸟类调查册" } },
    { path: "/observations", name: "observations", component: ObservationsPage, meta: { title: "田野记录" } },
    { path: "/locations", name: "locations", component: LocationsPage, meta: { title: "区域档案" } },
    { path: "/map", name: "map", component: MapPage, meta: { title: "探索地图" } },
    { path: "/trips", name: "trips", component: TripsPage, meta: { title: "远征日志" } },
    { path: "/collections", name: "collections", component: CollectionsPage, meta: { title: "收集计划" } },
  ],
  scrollBehavior: (to, from, savedPosition) => {
    if (savedPosition) return savedPosition;
    const staysInsideTaxonomy = to.path === "/dex"
      && from.path === "/dex"
      && to.query.view === "taxonomy"
      && from.query.view === "taxonomy";
    return staysInsideTaxonomy ? false : { top: 0 };
  },
});

export default router;
