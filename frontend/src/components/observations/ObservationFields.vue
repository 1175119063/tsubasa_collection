<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, toRef, toRefs, watch } from "vue";
import { api, errorMessage } from "@/api/client";
import type { SpeciesSummary, TaxonomyGenus, TaxonomyOrder } from "@/api/types";
import { applyObservationLocation, readAdditionalPhoto, readObservationPhoto, type AdditionalPhotoDraft, type ObservationDraft, type EntryLocation, type Subspecies } from "./observation-entry";
import ObservationSpeciesAssistant, { type AssistantTaxon, type SpeciesExtraction } from "./ObservationSpeciesAssistant.vue";
import OnlineSpeciesLookup from "../OnlineSpeciesLookup.vue";
import type { OnlineTaxonName, OnlineTaxonomyDraft } from "@/api/online-species";
import BehaviorPicker from "./BehaviorPicker.vue";
import ObservationSpeciesPicker from "./ObservationSpeciesPicker.vue";
import ObservationLocationPicker from "./ObservationLocationPicker.vue";
import SubspeciesAssistant from "./SubspeciesAssistant.vue";

const props = defineProps<{ draft: ObservationDraft; species: SpeciesSummary[]; locations: EntryLocation[]; taxonomy: TaxonomyOrder[]; fixedPhoto?: boolean }>();
const emit = defineEmits<{ locate: [] }>();
const { speciesId, orderId, familyId, genusId, photo, audio, photoStatus, additional } = toRefs(props.draft);
const form = props.draft.form;
const newSpecies = props.draft.newSpecies;
const taxonomy = toRef(props, "taxonomy");
const primarySubspecies = ref<Subspecies[]>([]);
const onlineReferenceOpen = ref(false);
const selectedSpecies = computed(() => props.species.find((item) => String(item.id) === speciesId.value));
const additionalId = ref("");
const status = ref("");
const onlineApplyStatus = ref("");
const photoPreview = ref("");
const additionalPreviews = new Map<string, string>();
watch(photo, (file) => {
  if (photoPreview.value) URL.revokeObjectURL(photoPreview.value);
  photoPreview.value = file && !props.fixedPhoto ? URL.createObjectURL(file) : "";
}, { immediate: true });
function additionalPreview(item: AdditionalPhotoDraft): string {
  let url = additionalPreviews.get(item.id);
  if (!url) { url = URL.createObjectURL(item.file); additionalPreviews.set(item.id, url); }
  return url;
}
function removeAdditionalPhoto(item: AdditionalPhotoDraft): void {
  const url = additionalPreviews.get(item.id); if (url) URL.revokeObjectURL(url);
  additionalPreviews.delete(item.id); props.draft.additionalPhotos = props.draft.additionalPhotos.filter((value) => value.id !== item.id);
  if (props.draft.coverPhotoId === item.id) props.draft.coverPhotoId = "primary";
}
onBeforeUnmount(() => { if (photoPreview.value) URL.revokeObjectURL(photoPreview.value); additionalPreviews.forEach((url) => URL.revokeObjectURL(url)); });
const availablePrimary = computed(() => props.species.filter((item) => !additional.value.some((entry) => entry.species.id === item.id)));
const selectedOrder = computed(() => taxonomy.value.find((item) => String(item.id) === orderId.value));
const families = computed(() => selectedOrder.value?.families || []);
const selectedFamily = computed(() => families.value.find((item) => String(item.id) === familyId.value));
const genera = computed(() => selectedFamily.value?.genera || []);
const availableAdditional = computed(() => {
  const used = new Set(additional.value.map((item) => item.species.id));
  return props.species.filter((item) => String(item.id) !== speciesId.value && !used.has(item.id));
});
watch(orderId, () => { familyId.value = "new"; genusId.value = "new"; });
watch(familyId, () => { genusId.value = "new"; });
watch(speciesId, () => { form.behavior_labels = []; form.subspecies_id = null; void loadSubspecies(); });
watch(() => additional.value.map((item) => item.species.id).join(","), () => {
  const valid = new Set(additional.value.map((item) => item.species.id));
  props.draft.primaryPhotoSpeciesIds = props.draft.primaryPhotoSpeciesIds.filter((id) => valid.has(id));
  props.draft.additionalPhotos.forEach((item) => { item.speciesIds = item.speciesIds.filter((id) => valid.has(id)); });
});
watch(availableAdditional, (items) => {
  if (!items.some((item) => String(item.id) === additionalId.value)) additionalId.value = "";
});
async function loadSubspecies(): Promise<void> {
  const id = speciesId.value;
  primarySubspecies.value = [];
  if (!id || id === "new") return;
  try {
    const detail = await api<{ subspecies: Subspecies[] }>(`/api/species/${id}`);
    if (id === speciesId.value) primarySubspecies.value = detail.subspecies;
  } catch (caught) { status.value = errorMessage(caught); }
}
function startNewSpecies(): void { speciesId.value = "new"; }
function cancelNewSpecies(): void { speciesId.value = ""; }
function locationChanged(value: string): void {
  form.location_id = value;
  selectLocation();
}
function selectLocation(): void {
  const location = props.locations.find((item) => String(item.id) === form.location_id);
  if (location) applyObservationLocation(props.draft, location);
}
async function photoChanged(event: Event): Promise<void> {
  const files = [...((event.target as HTMLInputElement).files || [])];
  await readObservationPhoto(props.draft, files[0] || null);
  props.draft.additionalPhotos = await Promise.all(files.slice(1).map(readAdditionalPhoto));
  props.draft.coverPhotoId = "primary";
}
function normalized(value: string | null | undefined): string { return String(value || "").normalize("NFKC").toLocaleLowerCase().replace(/[^\p{L}\p{N}]+/gu, ""); }
function taxonMatch<T extends TaxonomyGenus>(items: T[], suggestion: AssistantTaxon): T | undefined { const keys = [suggestion.chinese_name, suggestion.scientific_name].map(normalized).filter(Boolean); return items.find((item) => keys.some((key) => [item.chinese_name, item.scientific_name].map(normalized).some((value) => value.includes(key) || key.includes(value)))); }
async function applyAssistant(extraction: SpeciesExtraction): Promise<void> { const order = taxonMatch(taxonomy.value, extraction.order); orderId.value = order ? String(order.id) : "new"; if (!order) { newSpecies.order_chinese = extraction.order.chinese_name || ""; newSpecies.order_scientific = extraction.order.scientific_name || ""; } await nextTick(); const family = taxonMatch(families.value, extraction.family); familyId.value = family ? String(family.id) : "new"; if (!family) { newSpecies.family_chinese = extraction.family.chinese_name || ""; newSpecies.family_scientific = extraction.family.scientific_name || ""; } await nextTick(); const genus = taxonMatch(genera.value, extraction.genus); genusId.value = genus ? String(genus.id) : "new"; if (!genus) { newSpecies.genus_chinese = extraction.genus.chinese_name || ""; newSpecies.genus_scientific = extraction.genus.scientific_name || ""; } newSpecies.chinese_name = extraction.species.chinese_name || ""; newSpecies.scientific_name = extraction.species.scientific_name || ""; newSpecies.has_subspecies = extraction.subspecies.length > 0; newSpecies.subspecies_list = extraction.subspecies.map((item) => [item.scientific_name, item.chinese_name].filter(Boolean).join(" | ")).filter(Boolean).join("\n"); }
function sameTaxon(current: OnlineTaxonName, suggestion: OnlineTaxonName): boolean {
  if (current.scientific_name?.trim()) return normalized(current.scientific_name) === normalized(suggestion.scientific_name);
  if (current.chinese_name?.trim()) return normalized(current.chinese_name) === normalized(suggestion.chinese_name);
  return true;
}
async function applyOnline(draft: OnlineTaxonomyDraft): Promise<void> {
  const ranks = ["order", "family", "genus"] as const;
  const ids = { order: orderId, family: familyId, genus: genusId };
  const catalogs = { order: taxonomy, family: families, genus: genera };
  // Check the entire existing path before changing IDs (whose watchers reset descendants).
  for (const rank of ranks) {
    const selected = catalogs[rank].value.find((item) => String(item.id) === ids[rank].value);
    const current = selected || { chinese_name: newSpecies[`${rank}_chinese`], scientific_name: newSpecies[`${rank}_scientific`] };
    if (!draft[rank].scientific_name || !sameTaxon(current, draft[rank])) {
      onlineApplyStatus.value = "已有分类与在线资料不一致，或来源缺少完整分类；尚未填入，请手动核对。";
      return;
    }
  }
  if (!sameTaxon(newSpecies, draft.species)) {
    onlineApplyStatus.value = "已有物种名称与候选不一致，尚未填入，请先核对物种。";
    return;
  }
  for (const rank of ranks) {
    const suggestion = draft[rank];
    const matches = catalogs[rank].value.filter((item) => normalized(item.scientific_name) === normalized(suggestion.scientific_name));
    // Reuse a uniquely identified local taxon only when that rank has no typed values.
    if (!newSpecies[`${rank}_chinese`].trim() && !newSpecies[`${rank}_scientific`].trim() && matches.length === 1) {
      ids[rank].value = String(matches[0]!.id);
    } else if (ids[rank].value === "new") {
      if (!newSpecies[`${rank}_chinese`].trim()) newSpecies[`${rank}_chinese`] = suggestion.chinese_name || "";
      if (!newSpecies[`${rank}_scientific`].trim()) newSpecies[`${rank}_scientific`] = suggestion.scientific_name || "";
    }
    await nextTick();
  }
  if (!newSpecies.chinese_name.trim()) newSpecies.chinese_name = draft.species.chinese_name || "";
  if (!newSpecies.scientific_name.trim()) newSpecies.scientific_name = draft.species.scientific_name || "";
  const onlineSubspecies = draft.subspecies ?? [];
  if (onlineSubspecies.length && !newSpecies.subspecies_list.trim()) {
    newSpecies.has_subspecies = true;
    newSpecies.subspecies_list = onlineSubspecies
      .map((item) => [item.name, item.common_name].filter(Boolean).join(" | "))
      .filter(Boolean)
      .join("\n");
    onlineApplyStatus.value = `已补充空白分类字段，并填入 ${onlineSubspecies.length} 个亚种候选；请核对后再保存。`;
  } else if (onlineSubspecies.length) {
    onlineApplyStatus.value = "已补充空白分类字段；亚种名单已有内容，未覆盖。请对照在线列表核对。";
  } else {
    onlineApplyStatus.value = "已补充空白分类字段。中文名缺失时请手动补充；iNaturalist 未列出亚种。";
  }
}
function audioChanged(event: Event): void { audio.value = [...((event.target as HTMLInputElement).files || [])]; }
function onlineToggled(event: Event): void { onlineReferenceOpen.value = (event.target as HTMLDetailsElement).open; }
function useLocation(): void { navigator.geolocation.getCurrentPosition(({ coords }) => { form.latitude = coords.latitude; form.longitude = coords.longitude; }, () => { status.value = "无法读取设备位置，请手动填写经纬度"; }); }
async function addAdditional(): Promise<void> { const item = props.species.find((value) => String(value.id) === additionalId.value); if (!item || additional.value.length >= 9) return; try { const detail = await api<{ subspecies: Subspecies[] }>(`/api/species/${item.id}`); additional.value.push({ species: item, photo_type: "individual", sex: "unknown", life_stage: "unknown", subspecies_id: null, subspecies: detail.subspecies, notes: "", behavior_labels: [] }); additionalId.value = ""; } catch (caught) { status.value = errorMessage(caught); } }
onMounted(loadSubspecies);
</script>

<template>

    <ObservationSpeciesAssistant v-if="speciesId === 'new'" :online-apply-message="onlineApplyStatus" :latitude="form.latitude" :longitude="form.longitude" :locality="form.locality" :observed-at="form.observed_at" @apply="applyAssistant" @apply-online="applyOnline" />
    <fieldset tabindex="-1">
<legend>
<span>01</span> 目标物种</legend>
<div class="form-grid">
<ObservationSpeciesPicker v-model="speciesId" :species="availablePrimary" search-label="搜索已有图鉴物种" select-label="选择图鉴物种" allow-new />
<button v-if="speciesId !== 'new'" class="secondary-button full-field" type="button" data-new-species @click="startNewSpecies">＋ 登记新物种</button>
<button v-else class="secondary-button full-field" type="button" @click="cancelNewSpecies">取消登记新物种，改选已有物种</button>
<template v-if="speciesId === 'new'">
<label>目<select v-model="orderId">
<option value="new">新增目</option>
<option v-for="item in taxonomy" :key="item.id" :value="String(item.id)">{{ item.chinese_name }} · {{ item.scientific_name }}</option>
</select>
</label>
<label v-if="orderId === 'new'">目中文名<input v-model="newSpecies.order_chinese" required />
</label>
<label v-if="orderId === 'new'">目拉丁学名<input v-model="newSpecies.order_scientific" required />
</label>
<label>科<select v-model="familyId">
<option value="new">新增科</option>
<option v-for="item in families" :key="item.id" :value="String(item.id)">{{ item.chinese_name }} · {{ item.scientific_name }}</option>
</select>
</label>
<label v-if="familyId === 'new'">科中文名<input v-model="newSpecies.family_chinese" required />
</label>
<label v-if="familyId === 'new'">科拉丁学名<input v-model="newSpecies.family_scientific" required />
</label>
<label>属<select v-model="genusId">
<option value="new">新增属</option>
<option v-for="item in genera" :key="item.id" :value="String(item.id)">{{ item.chinese_name }} · {{ item.scientific_name }}</option>
</select>
</label>
<label v-if="genusId === 'new'">属中文名<input v-model="newSpecies.genus_chinese" required />
</label>
<label v-if="genusId === 'new'">属拉丁学名<input v-model="newSpecies.genus_scientific" required />
</label>
<label>种中文名<input v-model="newSpecies.chinese_name" required />
</label>
<label>种拉丁学名<input v-model="newSpecies.scientific_name" required />
</label>
<label>IUCN 等级<select v-model="newSpecies.iucn_status">
<option v-for="item in ['NE','LC','NT','VU','EN','CR','EW','EX']" :key="item">{{ item }}</option>
</select>
</label>
<label>中国保护等级<select v-model="newSpecies.china_status">
<option value="">无</option>
<option value="three_protected">三有</option>
<option value="level_2">二级</option>
<option value="level_1">一级</option>
</select>
</label>
<label class="check-field full-field">
<input v-model="newSpecies.has_subspecies" type="checkbox" />
<span>该物种存在亚种</span>
</label>
<label v-if="newSpecies.has_subspecies" class="full-field">完整亚种名单<textarea v-model="newSpecies.subspecies_list" rows="3" required placeholder="每行一个：拉丁学名 | 可选中文名">
</textarea>
</label>
</template>
</div>
</fieldset>
    <fieldset tabindex="-1">
<legend>
<span>02</span> 时间与地点</legend>
<div class="form-grid">
<ObservationLocationPicker class="full-field" :model-value="form.location_id" :locations="locations" allow-create @update:model-value="locationChanged" @create="emit('locate')" />
<label>拍摄时间<input v-model="form.observed_at" type="datetime-local" step="60" required />
</label>
<label>季节<select v-model="form.season" aria-label="季节" required>
<option value="" disabled>请选择季节</option>
<option value="spring">春</option>
<option value="summer">夏</option>
<option value="autumn">秋</option>
<option value="winter">冬</option>
<option value="other">其他</option>
</select>
</label>
<label>纬度<input v-model.number="form.latitude" type="number" min="-90" max="90" step="any" required />
</label>
<label>经度<input v-model.number="form.longitude" type="number" min="-180" max="180" step="any" required />
</label>
<button type="button" class="secondary-button full-field" @click="useLocation">使用当前设备位置</button>
<label>国家代码<input v-model="form.country_code" required />
</label>
<label>国家名称<input v-model="form.country_name" required />
</label>
<label>一级行政区代码<input v-model="form.admin1_code" required />
</label>
<label>一级行政区名称<input v-model="form.admin1_name" required />
</label>
<label class="full-field">具体地点<input v-model="form.locality" required />
</label>
<label class="full-field">备注<textarea v-model="form.notes" rows="3">
</textarea>
</label>
</div>
</fieldset>

    <fieldset tabindex="-1">
<legend>
<span>03</span> 个体与行为</legend>
<div class="form-grid">
<label class="full-field file-field observation-photo-input"><span v-if="!fixedPhoto">JPEG/JPG 照片（每张不超过 10 MB）</span><img v-if="photoPreview && !draft.photoError" class="observation-photo-preview" :src="photoPreview" alt="当前选择的观察照片" /><input v-if="!fixedPhoto" type="file" accept="image/jpeg,.jpg,.jpeg" multiple :required="!photo" @change="photoChanged" />
<span class="field-hint" role="status">{{ photoStatus }}</span>
<button v-if="fixedPhoto && photo" type="button" :disabled="draft.readingPhoto" @click="readObservationPhoto(draft, photo)">重新读取照片时间</button>
</label>
<section v-if="photo" class="observation-photo-associations full-field">
<header><strong>封面照片</strong><label v-if="!fixedPhoto"><input v-model="draft.coverPhotoId" type="radio" value="primary" />设为封面</label></header>
<div class="observation-photo-species"><label><input v-model="draft.primaryPhotoIncludesPrimary" type="checkbox" />{{ speciesId === 'new' ? (newSpecies.chinese_name || '目标物种') : (species.find(item => String(item.id) === speciesId)?.chinese_name || '目标物种') }}</label><label v-for="item in additional" :key="item.species.id"><input v-model="draft.primaryPhotoSpeciesIds" type="checkbox" :value="item.species.id" />{{ item.species.chinese_name }}</label></div>
</section>
<article v-for="item in draft.additionalPhotos" :key="item.id" class="observation-additional-photo full-field">
<img :src="additionalPreview(item)" alt="附加观察照片" /><div><header><strong :title="item.file.name">{{ item.file.name }}</strong><button type="button" @click="removeAdditionalPhoto(item)">移除</button></header><label>照片拍摄时间<input v-model="item.observed_at" type="datetime-local" step="60" required /></label><span class="field-hint" :class="{ 'is-error': item.error }">{{ item.status }}</span><label><input v-model="draft.coverPhotoId" type="radio" :value="item.id" />设为封面</label><div class="observation-photo-species"><label><input v-model="item.includesPrimary" type="checkbox" />{{ speciesId === 'new' ? (newSpecies.chinese_name || '目标物种') : (species.find(value => String(value.id) === speciesId)?.chinese_name || '目标物种') }}</label><label v-for="entry in additional" :key="entry.species.id"><input v-model="item.speciesIds" type="checkbox" :value="entry.species.id" />{{ entry.species.chinese_name }}</label></div></div>
</article>
<label>照片类型<select v-model="form.photo_type">
<option value="individual">个体照片</option>
<option value="group">群体照片</option>
</select>
</label>
<template v-if="form.photo_type === 'individual'">
<label>性别<select v-model="form.sex">
<option value="unknown">未知</option>
<option value="male">雄性</option>
<option value="female">雌性</option>
</select>
</label>
<label>生命阶段<select v-model="form.life_stage">
<option value="unknown">未知</option>
<option value="egg">卵</option>
<option value="chick">雏鸟</option>
<option value="subadult">亚成</option>
<option value="adult">成鸟</option>
</select>
</label>
<label v-if="speciesId !== 'new'">亚种<select v-model="form.subspecies_id">
<option :value="null">未知 / 无亚种</option>
<option v-for="item in primarySubspecies" :key="item.id" :value="item.id">{{ item.chinese_name || item.scientific_name }}</option>
</select>
</label>
<SubspeciesAssistant
  v-if="speciesId !== 'new'"
  :scientific-name="selectedSpecies?.scientific_name || ''"
  :latitude="form.latitude"
  :longitude="form.longitude"
  :locality="form.locality"
  :observed-at="form.observed_at"
  :subspecies="primarySubspecies"
  :model-value="form.subspecies_id"
  @update:model-value="form.subspecies_id = $event"
/>
</template>
<BehaviorPicker v-if="speciesId" v-model="form.behavior_labels" :species-id="Number(speciesId) || null" />
<details v-if="speciesId !== 'new'" class="full-field online-species-reference" @toggle="onlineToggled">
<summary>联网核对亚种与保护状态（只读参考）</summary>
<OnlineSpeciesLookup
  v-if="onlineReferenceOpen"
  :key="speciesId"
  :initial-query="selectedSpecies?.scientific_name || selectedSpecies?.chinese_name || ''"
  :latitude="form.latitude"
  :longitude="form.longitude"
  :locality="form.locality"
  apply-hint="只读参考；请在下方亚种下拉框中选择，确认后保存。AI 建议不会自动选中。"
/>
</details>
<label class="full-field file-field">MP3 录音（可多选）<input type="file" accept="audio/mpeg,.mp3" multiple @change="audioChanged" />
<span v-if="audio.length" class="field-hint">已选择：{{ audio.map(file => file.name).join('、') }}</span>
</label>
</div>
</fieldset>
    <fieldset tabindex="-1">
<legend>
<span>04</span> 其他物种</legend>
<div class="form-grid">
<ObservationSpeciesPicker v-model="additionalId" :species="availableAdditional" search-label="搜索照片中的其他物种" select-label="选择已有图鉴物种" />
<button class="secondary-button full-field" type="button" @click="addAdditional">＋ 添加到这笔观察</button>
<article v-for="(item, index) in additional" :key="item.species.id" class="additional-species-entry full-field">
<header>
<span>
<strong>{{ item.species.chinese_name }}</strong>
<small>{{ item.species.scientific_name }}</small>
</span>
<button type="button" @click="additional.splice(index, 1)">移除</button>
</header>
<div class="form-grid">
<label>照片类型<select v-model="item.photo_type">
<option value="individual">个体照片</option>
<option value="group">群体照片</option>
</select>
</label>
<template v-if="item.photo_type === 'individual'">
<label>性别<select v-model="item.sex">
<option value="unknown">未知</option>
<option value="male">雄性</option>
<option value="female">雌性</option>
</select>
</label>
<label>生命阶段<select v-model="item.life_stage">
<option value="unknown">未知</option>
<option value="egg">卵</option>
<option value="chick">雏鸟</option>
<option value="subadult">亚成</option>
<option value="adult">成鸟</option>
</select>
</label>
<label>亚种<select v-model="item.subspecies_id">
<option :value="null">未知 / 无亚种</option>
<option v-for="sub in item.subspecies" :key="sub.id" :value="sub.id">{{ sub.chinese_name || sub.scientific_name }}</option>
</select>
</label>
</template>
<BehaviorPicker v-model="item.behavior_labels" :species-id="item.species.id" />
<label class="full-field">该物种备注<textarea v-model="item.notes" rows="2">
</textarea>
</label>
</div>
</article>
</div>
</fieldset>

<p v-if="status" role="status">{{ status }}</p>
</template>
