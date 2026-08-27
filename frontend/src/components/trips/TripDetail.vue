<script setup lang="ts">
import { computed } from "vue";
import type { TripDetail } from "@/api/types";

const props = defineProps<{ detail: TripDetail }>();
defineEmits<{ close: []; edit: []; link: []; editObservations: []; cover: []; delete: [] }>();

const recentObservations = computed(() => [...props.detail.observations].reverse().slice(0, 8));
function dateTime(value: string): string { return value.replace("T", " "); }
function durationLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60); const rest = minutes % 60;
  return [hours ? `${hours}小时` : "", rest ? `${rest}分钟` : ""].filter(Boolean).join(" ") || "0分钟";
}
</script>

<template>
  <button class="v2-dossier-close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
  <section class="v2-archive-detail-hero">
    <div class="v2-archive-cover"><img v-if="detail.cover_url" :src="detail.cover_url.replace('thumbnail=true', 'thumbnail=false')" alt="" /><i v-else>⌁</i></div>
    <div class="v2-archive-hero-copy"><p class="v2-kicker">远征日志 · {{ detail.catalog_number }}</p><h2>{{ detail.name }}</h2><em>{{ detail.location.name }} · {{ dateTime(detail.started_at) }} — {{ dateTime(detail.ended_at) }}</em>
      <div class="v2-hero-stat-grid"><article><strong>{{ detail.species_count }}</strong><span>种</span></article><article><strong>{{ detail.location_count }}</strong><span>地点</span></article><article><strong>{{ detail.observation_count }}</strong><span>记录</span></article><article><strong>{{ durationLabel(detail.duration_minutes) }}</strong><span>持续</span></article></div>
      <div class="v2-detail-actions"><button class="v2-button v2-button-primary" type="button" @click="$emit('edit')">修改远征</button><button class="v2-button v2-button-ghost" type="button" @click="$emit('link')">关联观察</button><button class="v2-button v2-button-ghost" type="button" @click="$emit('editObservations')">编辑观察</button></div>
    </div>
  </section>
  <section class="v2-archive-detail-paper">
    <div class="v2-trip-detail-column v2-trip-detail-left">
      <article><p class="v2-kicker">远征手记</p><h3>行程备注</h3><p class="v2-long-copy">{{ detail.notes || "本次远征没有附加备注。" }}</p></article>
      <article><p class="v2-kicker">物种成果</p><h3>本次确认的飞羽</h3><div class="v2-mini-species-grid"><RouterLink v-for="item in detail.species" :key="item.id" class="v2-mini-species" :to="{ path: '/dex', query: { species: item.id } }"><img :src="item.thumbnail_url" alt="" /><span><strong>{{ item.chinese_name }}</strong><em>{{ item.scientific_name }}</em><small>{{ item.observation_count }} 次记录</small></span></RouterLink><p v-if="!detail.species.length" class="v2-detail-empty">尚未获得物种情报。</p></div></article>
    </div>
    <div class="v2-trip-detail-column v2-trip-detail-right">
      <section class="v2-trip-route"><p class="v2-kicker">行程路线</p><h3>本次远征到访地点</h3><div><RouterLink v-for="location in detail.locations" :key="location.id" class="v2-trip-route-stop" :to="{ path: '/locations', query: { location: location.id } }"><b>{{ String(location.visit_order || 1).padStart(2, "0") }}</b><span>{{ location.name }}</span><small v-if="location.is_primary">主要地点</small></RouterLink></div></section>
      <article><p class="v2-kicker">田野凭证</p><h3>本次远征记录</h3><div class="v2-detail-evidence-grid"><RouterLink v-for="item in recentObservations" :key="item.id" class="v2-detail-evidence" :to="{ path: '/observations', query: { observation: item.id } }"><img :src="item.thumbnail_url" alt="" /><span><strong>{{ item.species_name }}</strong><small>{{ dateTime(item.observed_at) }}</small></span></RouterLink><RouterLink v-if="detail.observations.length" class="v2-detail-evidence v2-evidence-more" :to="{ path: '/observations', query: { trip: detail.id } }"><span><strong>查看更多</strong><small>检视本次远征全部 {{ detail.observations.length }} 笔记录 →</small></span></RouterLink><p v-else class="v2-detail-empty">尚未关联观察记录。</p></div></article>
    </div>
  </section>
  <section class="v2-archive-danger-zone"><div><p class="v2-kicker">档案管理</p><span>删除远征只会解除其中观察记录的关联，不会删除观察记录本身。</span></div><div class="v2-archive-danger-actions"><button class="v2-button v2-button-ghost" type="button" :disabled="!detail.observations.length" @click="$emit('cover')">更换封面</button><button class="v2-button v2-button-danger" type="button" @click="$emit('delete')">删除远征</button></div></section>
</template>
