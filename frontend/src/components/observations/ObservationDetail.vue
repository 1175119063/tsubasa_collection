<script setup lang="ts">
import { computed } from "vue";
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
</script>

<template>
  <button class="v2-dossier-close" type="button" aria-label="关闭" @click="$emit('close')">×</button>
  <section class="v2-observation-hero">
    <div class="v2-observation-hero-photo"><img :src="observation.photo_url" alt="观察照片" /></div>
    <div class="v2-observation-hero-copy">
      <p class="v2-kicker">田野记录 · OBSERVATION {{ observation.id }}<template v-if="entries.length > 1"> · {{ speciesIndex + 1 }}/{{ entries.length }}</template></p>
      <h2>{{ entry.species_name }}</h2><em>{{ entry.species_scientific_name }}</em>
      <dl>
        <div><dt>个体信息</dt><dd>{{ individualInfo }}</dd></div>
        <div><dt>亚种</dt><dd>{{ subspecies }}</dd></div>
        <div><dt>拍摄时间</dt><dd>{{ observation.observed_at.replace("T", " ") }}</dd></div>
        <div><dt>拍摄地点</dt><dd>{{ observation.country_name }} · {{ observation.admin1_name }} · {{ observation.locality }}</dd></div>
        <div><dt>坐标</dt><dd>{{ observation.latitude }}, {{ observation.longitude }}</dd></div>
        <div><dt>所属远征</dt><dd>{{ observation.trip ? `${observation.trip.catalog_number} · ${observation.trip.name}` : "未关联" }}</dd></div>
        <div v-if="entry.notes"><dt>物种备注</dt><dd>{{ entry.notes }}</dd></div>
      </dl>
      <div class="v2-detail-actions v2-species-navigation">
        <button class="v2-button v2-button-primary" type="button" @click="$emit('edit')">修改记录</button>
        <button class="v2-button v2-button-ghost" type="button" :disabled="entries.length === 1" @click="$emit('previous')">上一个物种</button>
        <button class="v2-button v2-button-ghost" type="button" :disabled="entries.length === 1" @click="$emit('next')">下一个物种</button>
      </div>
    </div>
  </section>
  <section class="v2-observation-notes">
    <p class="v2-kicker">现场备注</p><h3>调查者记录</h3>
    <p>{{ observation.notes || "本次观察没有附加备注。" }}</p>
    <div v-if="observation.audio.length" class="v2-audio-list"><audio v-for="audio in observation.audio" :key="audio.id" controls :src="audio.url"></audio></div>
  </section>
  <section class="v2-archive-danger-zone v2-observation-danger-zone">
    <div><p class="v2-kicker">记录管理</p><span>永久删除会同时移除这笔观察的照片、录音与全部物种记录。</span></div>
    <button class="v2-button v2-button-danger" type="button" @click="$emit('delete')">永久删除</button>
  </section>
</template>
