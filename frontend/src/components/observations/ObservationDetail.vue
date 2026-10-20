<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ObservationRecord } from "@/api/types";

const props = defineProps<{ observation: ObservationRecord; speciesIndex: number }>();
defineEmits<{ close: []; previous: []; next: []; edit: []; delete: [] }>();

const entries = computed(() => props.observation.species_entries?.length
  ? props.observation.species_entries
  : [{
      id: null,
      species_id: props.observation.species_id,
      species_name: props.observation.species_name,
      species_scientific_name: props.observation.species_scientific_name,
      photo_type: props.observation.photo_type,
      sex: props.observation.sex,
      life_stage: props.observation.life_stage,
      subspecies: props.observation.subspecies,
      notes: null,
      is_primary: true,
    }]);
const entry = computed(() => entries.value[Math.min(props.speciesIndex, entries.value.length - 1)]);
const activePhotoIndex = ref(0);
const photos = computed(() => {
  const all = props.observation.photos?.length ? props.observation.photos : [{
    id: 0, asset_id: props.observation.photo_asset_id, observed_at: props.observation.observed_at,
    position: 0, is_cover: true, species_entry_ids: entries.value.map((item) => item.id).filter((id): id is number => id !== null),
    photo_url: props.observation.photo_url, thumbnail_url: props.observation.thumbnail_url,
  }];
  const entryId = entry.value?.id;
  const matched = entryId ? all.filter((photo) => photo.species_entry_ids.includes(entryId)) : all;
  return matched.length ? matched : all;
});
const activePhoto = computed(() => photos.value[Math.min(activePhotoIndex.value, photos.value.length - 1)]);
watch(photos, (items) => {
  const coverIndex = items.findIndex((photo) => photo.is_cover);
  activePhotoIndex.value = coverIndex >= 0 ? coverIndex : 0;
}, { immediate: true });
function navigatePhoto(direction: -1 | 1): void { activePhotoIndex.value = (activePhotoIndex.value + direction + photos.value.length) % photos.value.length; }
const labels: Record<string, string> = {
  male: "雄性", female: "雌性", unknown: "未知", egg: "卵", chick: "雏鸟", subadult: "亚成", adult: "成鸟",
};
const individualInfo = computed(() => {
  if (entry.value.photo_type === "group") return "群体照片";
  const sex = !entry.value.sex || entry.value.sex === "unknown" ? "性别未知" : labels[entry.value.sex] || entry.value.sex;
  const stage = !entry.value.life_stage || entry.value.life_stage === "unknown" ? "生命阶段未知" : labels[entry.value.life_stage] || entry.value.life_stage;
  return `${sex} · ${stage}`;
});
const subspecies = computed(() => entry.value.subspecies
  ? [entry.value.subspecies.chinese_name, entry.value.subspecies.scientific_name].filter(Boolean).join(" · ")
  : "未记录");
const seasonLabels: Record<string, string> = { spring: "春", summer: "夏", autumn: "秋", winter: "冬", other: "其他" };
</script>

<template>
  <button class="v2-dossier-close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
  <section class="v2-observation-hero">
    <div class="v2-observation-hero-photo"><img :src="activePhoto.photo_url" :alt="`${entry.species_name}的观察照片`" /><div v-if="photos.length > 1" class="observation-photo-navigation"><button type="button" aria-label="上一张照片" @click="navigatePhoto(-1)">‹</button><span>{{ activePhotoIndex + 1 }} / {{ photos.length }}</span><button type="button" aria-label="下一张照片" @click="navigatePhoto(1)">›</button></div><div v-if="photos.length > 1" class="observation-photo-thumbnails"><button v-for="(photo, index) in photos" :key="photo.id" type="button" :class="{ 'is-active': index === activePhotoIndex }" :aria-label="`查看第 ${index + 1} 张照片`" @click="activePhotoIndex = index"><img :src="photo.thumbnail_url" alt="" /></button></div></div>
    <div class="v2-observation-hero-copy">
      <p class="v2-kicker">田野记录 · OBSERVATION {{ observation.id }}<template v-if="entries.length > 1"> · {{ speciesIndex + 1 }}/{{ entries.length }}</template></p>
      <h2>{{ entry.species_name }}</h2><em>{{ entry.species_scientific_name }}</em>
      <div class="observation-detail-tags"><span>{{ seasonLabels[observation.season] || observation.season || '未记录季节' }}</span><span>{{ entry.photo_type === 'group' ? '群体观察' : '个体观察' }}</span><span>{{ photos.length }} 张照片</span></div>
      <dl>
        <div><dt>个体信息</dt><dd>{{ individualInfo }}</dd></div>
        <div><dt>亚种</dt><dd>{{ subspecies }}</dd></div>
        <div><dt>拍摄时间</dt><dd>{{ observation.observed_at.replace("T", " ") }}</dd></div>
        <div v-if="photos.length > 1"><dt>当前照片</dt><dd>{{ activePhoto.observed_at.replace("T", " ") }} · 共 {{ photos.length }} 张</dd></div>
        <div><dt>拍摄地点</dt><dd>{{ observation.country_name }} · {{ observation.admin1_name }} · {{ observation.locality }}</dd></div>
        <div><dt>坐标</dt><dd>{{ observation.latitude }}, {{ observation.longitude }}</dd></div>
        <div><dt>所属远征</dt><dd>{{ observation.trip ? `${observation.trip.catalog_number} · ${observation.trip.name}` : "未关联" }}</dd></div>
        <div v-if="entry.notes"><dt>物种备注</dt><dd>{{ entry.notes }}</dd></div>
      </dl>
      <div class="v2-detail-actions v2-species-navigation">
        <button class="v2-button v2-button-primary" type="button" @click="$emit('edit')">修改记录</button>
        <a class="v2-button v2-button-ghost observation-original-link" :href="activePhoto.photo_url" target="_blank" rel="noopener">查看原图 ↗</a>
        <button v-if="entries.length > 1" class="v2-button v2-button-ghost" type="button" @click="$emit('previous')">上一个物种</button>
        <button v-if="entries.length > 1" class="v2-button v2-button-ghost" type="button" @click="$emit('next')">下一个物种</button>
      </div>
    </div>
  </section>
  <section class="v2-observation-notes">
    <h3>现场笔记</h3>
    <p :class="{ 'observation-note-empty': !observation.notes }">{{ observation.notes || "本次观察尚未填写笔记。" }}</p>
    <div v-if="observation.audio.length" class="v2-audio-list"><h4>现场录音 · {{ observation.audio.length }} 段</h4><audio v-for="(audio, index) in observation.audio" :key="audio.id" controls preload="none" :aria-label="`现场录音 ${index + 1}`" :src="audio.url"></audio></div>
  </section>
  <section class="v2-archive-danger-zone v2-observation-danger-zone">
    <div><p class="v2-kicker">记录管理</p><span>永久删除会同时移除这笔观察的照片、录音与全部物种记录。</span></div>
    <button class="v2-button v2-button-danger" type="button" @click="$emit('delete')">永久删除</button>
  </section>
</template>
