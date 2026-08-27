<script setup lang="ts">
import { computed } from "vue";
import type { LocationDetail } from "@/api/types";

const props = defineProps<{ detail: LocationDetail }>();
defineEmits<{ close: []; edit: []; cover: []; link: []; delete: [] }>();

const locationTypes: Record<string, string> = {
  wetland_park: "湿地公园", forest_park: "森林公园", urban_park: "城市公园",
  nature_reserve: "自然保护区", reservoir: "水库", farmland: "农田", coast: "海岸", other: "其他",
};
const maxVisits = computed(() => Math.max(1, ...props.detail.monthly_activity.map((item) => item.visit_day_count)));
const recentObservations = computed(() => [...props.detail.observations].reverse().slice(0, 8));
function dateTime(value: string): string { return value.replace("T", " "); }
function monthLabel(value: string): string { return `${value.slice(0, 4)}年${Number(value.slice(5, 7))}月`; }
</script>

<template>
  <button class="v2-dossier-close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
  <section class="v2-archive-detail-hero">
    <div class="v2-archive-cover"><img v-if="detail.cover_url" :src="detail.cover_url.replace('thumbnail=true', 'thumbnail=false')" :alt="detail.name" /><i v-else>⌖</i></div>
    <div class="v2-archive-hero-copy">
      <p class="v2-kicker">区域档案 · {{ detail.catalog_number }}</p><h2>{{ detail.name }}</h2>
      <em>{{ locationTypes[detail.location_type] || detail.location_type }} · {{ detail.admin1_name }} {{ detail.city || "" }} {{ detail.district || "" }}</em>
      <div class="v2-hero-stat-grid"><article><strong>{{ detail.species_count }}</strong><span>记录物种</span></article><article><strong>{{ detail.observation_count }}</strong><span>观察记录</span></article><article><strong>{{ detail.visit_day_count }}</strong><span>到访日</span></article><article><strong>{{ detail.trip_count }}</strong><span>远征</span></article></div>
      <p>中心坐标 {{ detail.center_latitude }}, {{ detail.center_longitude }} · {{ detail.coordinate_system === "gcj02" ? "GCJ-02" : "WGS-84" }}</p>
      <div class="v2-detail-actions"><button class="v2-button v2-button-primary" type="button" @click="$emit('edit')">修改区域</button><button class="v2-button v2-button-ghost" type="button" @click="$emit('cover')">{{ detail.cover_source === "custom" ? "更换封面" : "上传封面" }}</button><button class="v2-button v2-button-ghost" type="button" @click="$emit('link')">关联观察</button></div>
    </div>
  </section>
  <section class="v2-archive-detail-paper">
    <article><p class="v2-kicker">区域手记</p><h3>地点简介</h3><p class="v2-long-copy">{{ detail.notes || "尚未填写地点简介。" }}</p></article>
    <article><p class="v2-kicker">到访频率</p><h3>时间轨迹</h3><div class="v2-month-bars"><div v-for="item in detail.monthly_activity" :key="item.month"><span>{{ monthLabel(item.month) }}</span><i><b :style="{ width: `${item.visit_day_count / maxVisits * 100}%` }"></b></i><small>{{ item.visit_day_count }} 到访日 · {{ item.observation_count }} 条记录</small></div><p v-if="!detail.monthly_activity.length">暂无记录</p></div></article>
    <article><p class="v2-kicker">区域物种</p><h3>已经确认的飞羽</h3><div class="v2-mini-species-grid"><RouterLink v-for="item in detail.species" :key="item.id" class="v2-mini-species" :to="{ path: '/dex', query: { species: item.id } }"><img :src="item.thumbnail_url" alt="" /><span><strong>{{ item.chinese_name }}</strong><em>{{ item.scientific_name }}</em><small>{{ item.observation_count }} 次记录</small></span></RouterLink><p v-if="!detail.species.length" class="v2-detail-empty">尚未获得物种情报。</p></div></article>
    <div class="v2-location-record-column">
      <article><p class="v2-kicker">远征记录</p><h3>与本区域关联的远征</h3><div class="v2-location-trip-list"><RouterLink v-for="trip in detail.trips" :key="trip.id" class="v2-location-trip" :to="{ path: '/trips', query: { trip: trip.id } }"><small>{{ trip.catalog_number }}{{ trip.is_primary_location ? " · 主要地点" : " · 途经地点" }}</small><strong>{{ trip.name }}</strong><span>{{ dateTime(trip.started_at) }} — {{ dateTime(trip.ended_at) }}</span><em>{{ trip.observation_count }} 笔观察</em></RouterLink><p v-if="!detail.trips.length" class="v2-detail-empty">尚未关联远征记录。</p></div></article>
      <article class="v2-location-observations"><p class="v2-kicker">照片凭证</p><h3>区域观察记录</h3><div class="v2-detail-evidence-grid"><RouterLink v-for="item in recentObservations" :key="item.id" class="v2-detail-evidence" :to="{ path: '/observations', query: { observation: item.id } }"><img :src="item.thumbnail_url" alt="" /><span><strong>{{ item.species_name }}</strong><small>{{ dateTime(item.observed_at) }}</small></span></RouterLink><RouterLink v-if="detail.observations.length" class="v2-detail-evidence v2-evidence-more" :to="{ path: '/observations', query: { location: detail.id } }"><span><strong>查看更多</strong><small>检视该区域全部 {{ detail.observation_count }} 笔记录 →</small></span></RouterLink><p v-else class="v2-detail-empty">尚未关联观察记录。</p></div></article>
    </div>
  </section>
  <section class="v2-archive-danger-zone"><div><p class="v2-kicker">档案管理</p><span>删除区域只会解除其中观察记录的关联，不会删除观察记录本身。</span></div><button class="v2-button v2-button-danger" type="button" @click="$emit('delete')">删除区域</button></section>
</template>
