<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { DossierObservation, SpeciesDetail } from "@/components/dex/SpeciesDossier.vue";

interface TagDraft { label: string; observation_id: number | null }
interface BehaviorDraft { id?: number; label: string; observation_ids: number[] }
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
const behaviors = reactive<BehaviorDraft[]>(props.detail.behaviors.map((item) => ({ id: typeof item.id === "number" ? item.id : undefined, label: item.label || "", observation_ids: [...(item.observation_ids || [])] })));
const individuals = reactive<TagDraft[]>(props.detail.individuals.filter((item) => !String(item.id).startsWith("observed-")).map((item) => ({ label: item.label || "", observation_id: item.observation_id || null })));
const status = ref(""); const busy = ref(false);
const profileBusy = ref(false); const profileStatus = ref("");

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
async function completeIntroduction(): Promise<void> {
  if (profileBusy.value || busy.value) return;
  profileBusy.value = true;
  profileStatus.value = "飞羽精灵正在查资料并整理简介…";
  try {
    const result = await api<{ introduction: string; warnings?: string[] }>(
      "/api/assistant/species-profile",
      jsonRequest("POST", {
        scientific_name: props.detail.scientific_name,
        chinese_name: props.detail.chinese_name,
        introduction: form.introduction || "",
      }),
    );
    form.introduction = result.introduction;
    const warnings = (result.warnings || []).filter(Boolean).slice(0, 2);
    profileStatus.value = warnings.length
      ? `已生成草稿；${warnings.join("；")}`
      : "已生成草稿，保存后才会写入资料库。";
  } catch (caught) {
    profileStatus.value = errorMessage(caught);
  } finally {
    profileBusy.value = false;
  }
}
async function submit(): Promise<void> {
  busy.value = true; status.value = "正在保存图鉴资料…";
  try {
    const saved = await api<SpeciesDetail>(`/api/species/${props.detail.id}/profile`, jsonRequest("PUT", {
      introduction: form.introduction || null,
      ecological_group: form.ecological_group, body_size: form.body_size, preferred_habitats: form.preferred_habitats,
      evidence_selections: evidence.map((item) => ({ dimension: item.dimension, value_key: item.value_key, observation_id: item.observation_id })),
      behaviors: behaviors.map((item) => ({ id: item.id, label: item.label, observation_ids: item.observation_ids })),
      individuals: individuals.map((item) => ({ label: item.label, observation_id: item.observation_id })),
    }));
    emit("saved", saved);
  } catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
</script>

<template>
  <form @submit.prevent="submit"><header class="dialog-header"><div><p class="eyebrow">SPECIES PROFILE</p><h2>修改图鉴资料</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">×</button></header><div class="form-scroll">
    <fieldset><legend><span>01</span> 调查者手记</legend><div class="profile-intro-field"><label for="species-profile-introduction">物种简介</label><div class="profile-intro-wrap"><textarea id="species-profile-introduction" v-model="form.introduction" rows="7" maxlength="10000" :disabled="profileBusy" placeholder="记录识别经验、习性、鸣声或个人观察印象。"></textarea><button type="button" class="assistant-complete" data-profile-complete :disabled="profileBusy || busy" @click="completeIntroduction">{{ profileBusy ? "整理中…" : "✦ 飞羽精灵补全" }}</button></div><p v-if="profileStatus" class="field-hint profile-intro-status" role="status">{{ profileStatus }}</p></div></fieldset>
    <fieldset><legend><span>02</span> 生态画像</legend><div class="profile-ecology-editor"><section><h3>生态类群</h3><div class="ecology-choice-grid"><label v-for="([value,label]) in ecologyGroups" :key="value" class="ecology-choice"><input v-model="form.ecological_group" type="radio" :value="value" /><span class="ecology-icon"><b v-if="value === 'unknown'">?</b><img v-else :src="`/static/assets/${ecologyAssets[value]}`" alt="" /></span><strong>{{ label }}</strong></label></div></section><section><h3>体型大小</h3><div class="body-size-choice-grid"><label v-for="([value,label],index) in bodySizes" :key="value" class="body-size-choice" :style="{ '--bird-width': `${32 + Math.max(0,index - 1) * 8}px` }"><input v-model="form.body_size" type="radio" :value="value" /><span v-if="value !== 'unknown'"><img class="body-size-raster-icon" :src="'/static/assets/body-size-silhouette.png'" alt="" /></span><span v-else>?</span><strong>{{ label }}</strong></label></div></section><section><div class="profile-choice-heading"><h3>偏好生境</h3><span>{{ habitatStatus }}</span></div><div class="habitat-choice-grid"><label v-for="([value,label]) in habitats" :key="value" class="habitat-choice"><input type="checkbox" :checked="form.preferred_habitats.includes(value)" @change="toggleHabitat(value, ($event.target as HTMLInputElement).checked)" /><span>{{ label }}</span></label></div></section></div></fieldset>
    <fieldset><legend><span>03</span> 自定义个体标签</legend><p class="field-hint">建立“成年雄性繁殖羽”等自定义个体标签，并可选择一笔观察作为照片凭证。</p><div class="profile-behavior-list"><div v-for="(item,index) in individuals" :key="index" class="profile-behavior-row"><label>个体标签<input v-model="item.label" maxlength="120" required /></label><label>照片凭证<select v-model="item.observation_id"><option :value="null">暂不关联</option><option v-for="observation in detail.observations" :key="observation.id" :value="observation.id">{{ observationLabel(observation) }}</option></select></label><button type="button" class="danger-button" @click="individuals.splice(index,1)">删除标签</button></div></div><button type="button" class="secondary-button" @click="addTag(individuals)">＋ 添加个体标签</button></fieldset>
    <fieldset><legend><span>04</span> 自动档案照片凭证</legend><p class="field-hint">对应外部“观察自动汇总”与亚种档案的凭证；自定义个体标签在上方单独关联。</p><div class="profile-evidence-list"><label v-for="item in evidence" :key="`${item.dimension}-${item.value_key}`" class="profile-evidence-row"><span>{{ item.label }}</span><select v-model="item.observation_id"><option v-for="observation in item.options" :key="observation.id" :value="observation.id">{{ observationLabel(observation) }}</option></select></label><p v-if="!evidence.length" class="field-hint">目前没有可设置照片凭证的个体或亚种档案。</p></div></fieldset>
    <fieldset><legend><span>05</span> 行为档案</legend>
      <p class="field-hint">一个行为可关联多笔观察；这里的关联与田野记录的行为字段同步。删除标签会从该物种的所有观察中移除该行为，不删除观察。</p>
      <div class="profile-behavior-list"><section v-for="(item,index) in behaviors" :key="item.id || `new-${index}`" class="profile-behavior-entry">
        <label>行为标签<input v-model="item.label" maxlength="80" required /></label>
        <fieldset class="behavior-observations"><legend>关联观察（可多选）</legend>
          <label v-for="observation in detail.observations" :key="observation.id"><input v-model="item.observation_ids" type="checkbox" :value="observation.id" />{{ observationLabel(observation) }}</label>
        </fieldset>
        <button type="button" class="danger-button" @click="behaviors.splice(index,1)">删除行为标签</button>
      </section></div>
      <button type="button" class="secondary-button" @click="behaviors.push({ label: '', observation_ids: [] })">＋ 添加行为标签</button>
    </fieldset>
  </div><footer class="dialog-footer"><span role="status">{{ status }}</span><button type="submit" class="primary-button" :disabled="busy || profileBusy">{{ busy ? "正在保存…" : "保存图鉴资料" }}</button></footer></form>
</template>

<style scoped>
.ecology-icon{display:grid;place-items:center}.ecology-icon img{display:block;width:88%;height:88%;object-fit:contain}.ecology-icon b{font:24px Georgia,serif}.body-size-choice>span{min-height:24px}.profile-behavior-row .danger-button{min-width:82px}
.profile-behavior-entry { padding: 14px; border: 1px solid var(--line); margin-bottom: 12px; }
.behavior-observations { max-height: 240px; overflow: auto; margin: 12px 0; }
.behavior-observations label { display: flex; align-items: center; gap: 8px; }
.behavior-observations input { width: 16px; height: 16px; flex-shrink: 0; }
.profile-intro-field { display: block; }
.profile-intro-wrap { position: relative; display: block; }
.profile-intro-wrap textarea { padding-bottom: 2.75rem; }
.assistant-complete { position: absolute; right: 10px; bottom: 10px; border: 1px solid var(--line); border-radius: 999px; background: color-mix(in srgb, var(--paper) 88%, white); color: inherit; padding: 6px 12px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer; }
.assistant-complete:hover:not(:disabled) { border-color: var(--ink); }
.assistant-complete:disabled { opacity: .65; cursor: progress; }
.profile-intro-status { margin-top: 8px; }
</style>
