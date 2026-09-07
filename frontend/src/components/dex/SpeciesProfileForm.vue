<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { DossierObservation, SpeciesDetail } from "@/components/dex/SpeciesDossier.vue";

interface TagDraft { label: string; observation_id: number | null }
interface EvidenceDraft { dimension: "sex" | "life_stage" | "subspecies"; value_key: string; label: string; observation_id: number; options: DossierObservation[] }

const props = defineProps<{ detail: SpeciesDetail }>();
const emit = defineEmits<{ close: []; saved: [detail: SpeciesDetail] }>();

const ecologyGroups = [
  ["unknown", "未知"], ["raptor", "猛禽"], ["songbird", "鸣禽"], ["landfowl", "陆禽"],
  ["scansorial", "攀禽"], ["wader", "涉禽"], ["waterfowl", "游禽"],
] as const;
const bodySizes = [["unknown", "未知"], ["small", "小型"], ["small_medium", "中小型"], ["medium", "中型"], ["medium_large", "中大型"], ["large", "大型"]] as const;
const habitats = [["city", "城市"], ["farmland", "农田"], ["grassland", "草原"], ["shrub", "灌丛"], ["forest", "森林"], ["wetland", "湿地"], ["river", "河流"], ["lake", "湖泊"], ["desert", "荒漠"], ["coast", "海岸"], ["ocean", "海洋"], ["mudflat", "滩涂"], ["alpine", "高山"], ["other", "其他"]] as const;
const ecologyAssets: Record<string, string> = { raptor: "raptor-silhouette.png", songbird: "songbird-silhouette.png", landfowl: "landfowl-silhouette.png", scansorial: "scansorial-silhouette.png", wader: "wader-silhouette.png", waterfowl: "waterfowl-silhouette.png" };
const valueLabels: Record<string, string> = { male: "雄性", female: "雌性", unknown: "未知", egg: "卵", chick: "雏鸟", subadult: "亚成", adult: "成鸟" };

const form = reactive({
  introduction: props.detail.introduction || "",
  ecological_group: props.detail.ecology.group || "unknown", body_size: props.detail.ecology.body_size || "unknown",
  preferred_habitats: [...(props.detail.ecology.habitats || [])],
});
const behaviors = reactive<TagDraft[]>(props.detail.behaviors.map((item) => ({ label: item.label || "", observation_id: item.observation_id || null })));
const individuals = reactive<TagDraft[]>(props.detail.individuals.filter((item) => !String(item.id).startsWith("observed-")).map((item) => ({ label: item.label || "", observation_id: item.observation_id || null })));
const status = ref(""); const busy = ref(false);

function evidenceFor(dimension: EvidenceDraft["dimension"], valueKey: string, label: string, selected: number | null | undefined): EvidenceDraft | null {
  const options = props.detail.observations.filter((item) => dimension === "sex" ? item.sex === valueKey : dimension === "life_stage" ? item.life_stage === valueKey : String(item.subspecies?.id || "") === valueKey);
  if (!options.length) return null;
  return { dimension, value_key: valueKey, label, observation_id: selected && options.some((item) => item.id === selected) ? selected : options[0].id, options };
}
const evidence = reactive<EvidenceDraft[]>([
  ...(props.detail.collected.sexes || []).map((item) => evidenceFor("sex", item.value || "", `性别 · ${valueLabels[item.value || ""] || item.value}`, item.observation_id)),
  ...(props.detail.collected.life_stages || []).map((item) => evidenceFor("life_stage", item.value || "", `生命阶段 · ${valueLabels[item.value || ""] || item.value}`, item.observation_id)),
  ...props.detail.subspecies.filter((item) => item.captured).map((item) => evidenceFor("subspecies", String(item.id), `亚种 · ${item.chinese_name || item.scientific_name}`, item.observation_id)),
].filter((item): item is EvidenceDraft => Boolean(item)));
const habitatStatus = computed(() => `${form.preferred_habitats.length} / 3`);

function toggleHabitat(value: string, checked: boolean): void {
  if (checked) { if (form.preferred_habitats.length >= 3) { status.value = "偏好生境最多选择 3 项。"; return; } form.preferred_habitats.push(value); }
  else form.preferred_habitats = form.preferred_habitats.filter((item) => item !== value);
  status.value = "";
}
function observationLabel(item: DossierObservation): string { return `${item.observed_at.replace("T", " ")} · ${item.locality}`; }
function addTag(target: TagDraft[]): void { target.push({ label: "", observation_id: null }); }
async function submit(): Promise<void> {
  busy.value = true; status.value = "正在保存图鉴资料…";
  try {
    const saved = await api<SpeciesDetail>(`/api/species/${props.detail.id}/profile`, jsonRequest("PUT", {
      introduction: form.introduction || null,
      ecological_group: form.ecological_group, body_size: form.body_size, preferred_habitats: form.preferred_habitats,
      evidence_selections: evidence.map((item) => ({ dimension: item.dimension, value_key: item.value_key, observation_id: item.observation_id })),
      behaviors: behaviors.map((item) => ({ label: item.label, observation_id: item.observation_id })),
      individuals: individuals.map((item) => ({ label: item.label, observation_id: item.observation_id })),
    }));
    emit("saved", saved);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
</script>

<template>
  <form @submit.prevent="submit"><header class="dialog-header"><div><p class="eyebrow">SPECIES PROFILE</p><h2>修改图鉴资料</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">×</button></header><div class="form-scroll">
    <fieldset><legend><span>01</span> 调查者手记</legend><label>物种简介<textarea v-model="form.introduction" rows="7" maxlength="10000" placeholder="记录识别经验、习性、鸣声或个人观察印象。"></textarea></label></fieldset>
    <fieldset><legend><span>02</span> 生态画像</legend><div class="profile-ecology-editor"><section><h3>生态类群</h3><div class="ecology-choice-grid"><label v-for="([value,label]) in ecologyGroups" :key="value" class="ecology-choice"><input v-model="form.ecological_group" type="radio" :value="value" /><span class="ecology-icon"><b v-if="value === 'unknown'">?</b><img v-else :src="`/static/assets/${ecologyAssets[value]}`" alt="" /></span><strong>{{ label }}</strong></label></div></section><section><h3>体型大小</h3><div class="body-size-choice-grid"><label v-for="([value,label],index) in bodySizes" :key="value" class="body-size-choice" :style="{ '--bird-width': `${32 + Math.max(0,index - 1) * 8}px` }"><input v-model="form.body_size" type="radio" :value="value" /><span v-if="value !== 'unknown'"><img class="body-size-raster-icon" :src="'/static/assets/body-size-silhouette.png'" alt="" /></span><span v-else>?</span><strong>{{ label }}</strong></label></div></section><section><div class="profile-choice-heading"><h3>偏好生境</h3><span>{{ habitatStatus }}</span></div><div class="habitat-choice-grid"><label v-for="([value,label]) in habitats" :key="value" class="habitat-choice"><input type="checkbox" :checked="form.preferred_habitats.includes(value)" @change="toggleHabitat(value, ($event.target as HTMLInputElement).checked)" /><span>{{ label }}</span></label></div></section></div></fieldset>
    <fieldset><legend><span>03</span> 个体档案</legend><p class="field-hint">建立“成年雄性繁殖羽”等自定义个体标签，并可选择一笔观察作为照片凭证。</p><div class="profile-behavior-list"><div v-for="(item,index) in individuals" :key="index" class="profile-behavior-row"><label>个体标签<input v-model="item.label" maxlength="120" required /></label><label>照片凭证<select v-model="item.observation_id"><option :value="null">暂不关联</option><option v-for="observation in detail.observations" :key="observation.id" :value="observation.id">{{ observationLabel(observation) }}</option></select></label><button type="button" class="danger-button" @click="individuals.splice(index,1)">删除标签</button></div></div><button type="button" class="secondary-button" @click="addTag(individuals)">＋ 添加个体标签</button></fieldset>
    <fieldset><legend><span>04</span> 档案照片凭证</legend><div class="profile-evidence-list"><label v-for="item in evidence" :key="`${item.dimension}-${item.value_key}`" class="profile-evidence-row"><span>{{ item.label }}</span><select v-model="item.observation_id"><option v-for="observation in item.options" :key="observation.id" :value="observation.id">{{ observationLabel(observation) }}</option></select></label><p v-if="!evidence.length" class="field-hint">目前没有可设置照片凭证的个体或亚种档案。</p></div></fieldset>
    <fieldset><legend><span>05</span> 行为档案</legend><div class="profile-behavior-list"><div v-for="(item,index) in behaviors" :key="index" class="profile-behavior-row"><label>行为标签<input v-model="item.label" maxlength="80" required /></label><label>照片凭证<select v-model="item.observation_id"><option :value="null">暂不关联</option><option v-for="observation in detail.observations" :key="observation.id" :value="observation.id">{{ observationLabel(observation) }}</option></select></label><button type="button" class="danger-button" @click="behaviors.splice(index,1)">删除标签</button></div></div><button type="button" class="secondary-button" @click="addTag(behaviors)">＋ 添加行为标签</button></fieldset>
  </div><footer class="dialog-footer"><span role="status">{{ status }}</span><button type="submit" class="primary-button" :disabled="busy">{{ busy ? "正在保存…" : "保存图鉴资料" }}</button></footer></form>
</template>

<style scoped>
.ecology-icon{display:grid;place-items:center}.ecology-icon img{display:block;width:88%;height:88%;object-fit:contain}.ecology-icon b{font:24px Georgia,serif}.body-size-choice>span{min-height:24px}.profile-behavior-row .danger-button{min-width:82px}
</style>
