<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { onBeforeRouteLeave } from "vue-router";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { SpeciesSummary, TaxonomyOrder, TripDetail, TripSummary } from "@/api/types";
import ObservationFields from "./ObservationFields.vue";
import { copyBatchFields, newSpeciesIdentity, type BatchItem } from "./batch-entry";
import {
  createObservationDraft, readObservationPhoto, observationIssues, saveObservationDraft,
  isUncertainSave, type EntryLocation,
} from "./observation-entry";

const props = defineProps<{ species: SpeciesSummary[]; locations: EntryLocation[] }>();
const emit = defineEmits<{ close: []; changed: [] }>();
const species = ref([...props.species]);
const taxonomy = ref<TaxonomyOrder[]>([]);
const loaded = ref(false);
const items = ref<BatchItem[]>([]);
const activeId = ref("");
const adding = ref(false);
const saving = ref(false);
const pauseRequested = ref(false);
const message = ref("");
const applyFields = reactive({ species: true, location: false, season: false });
const registeredSpecies = new Map<string, { id: number; signature: string }>();
const active = computed(() => items.value.find((item) => item.draft.id === activeId.value));
const editable = (item: BatchItem) => item.state === "draft" || item.state === "error";
const issues = (item: BatchItem) => observationIssues(item.draft, taxonomy.value);
const ready = computed(() => items.value.filter((item) => editable(item) && !issues(item).length));
const saved = computed(() => items.value.filter((item) => item.state === "saved"));
const hasUncertain = computed(() => items.value.some((item) => item.state === "uncertain"));
const selectedTargets = computed(() => items.value.filter((item) => item.selected && editable(item) && item !== active.value));
const busy = computed(() => saving.value || adding.value || linking.value);
let disposed = false;

const trips = ref<TripSummary[]>([]);
const tripId = ref("");
const linking = ref(false);
const tripMessage = ref("");

onMounted(async () => {
  window.addEventListener("beforeunload", beforeUnload);
  try { taxonomy.value = await api<TaxonomyOrder[]>("/api/taxonomy/tree"); loaded.value = true; }
  catch (caught) { message.value = `无法读取分类资料：${errorMessage(caught)}。请关闭后重新打开。`; }
  try { trips.value = await api<TripSummary[]>("/api/trips"); }
  catch (caught) { tripMessage.value = `暂时无法读取远征：${errorMessage(caught)}`; }
});

function statusLabel(item: BatchItem): string {
  if (item.state === "saved") return `已保存 · #${item.observationId}`;
  if (item.state === "saving") return "正在保存";
  if (item.state === "uncertain") return "保存结果待核实";
  if (item.draft.readingPhoto) return "正在读取照片";
  if (item.state === "error") return "保存失败，可修改后重试";
  return issues(item).length ? "待填写 / 检查" : "可保存";
}

async function addFiles(files: File[]): Promise<void> {
  if (busy.value || !files.length) return;
  adding.value = true;
  message.value = "正在逐张读取照片；可先查看并填写已读入的照片。";
  try {
    for (const file of files) {
      if (disposed) break;
      const draft = createObservationDraft("", true);
      draft.photo = file;
      const item = reactive<BatchItem>({
        draft, previewUrl: URL.createObjectURL(file), selected: true, state: "draft", message: "", observationId: null,
      });
      items.value.push(item);
      if (!activeId.value) activeId.value = draft.id;
      await readObservationPhoto(item.draft, file);
    }
    message.value = "照片已加入。请填写当前照片，或把物种、地点、季节应用到勾选的其他照片。";
  } finally { adding.value = false; }
}
function filesChanged(event: Event): void {
  const input = event.target as HTMLInputElement;
  void addFiles(Array.from(input.files || []));
  input.value = "";
}
function dropFiles(event: DragEvent): void { void addFiles(Array.from(event.dataTransfer?.files || [])); }

function selectAll(value: boolean): void {
  items.value.forEach((item) => { if (editable(item)) item.selected = value; });
}
function removeItem(item: BatchItem): void {
  if (busy.value || !editable(item)) return;
  URL.revokeObjectURL(item.previewUrl);
  items.value = items.value.filter((entry) => entry !== item);
  if (activeId.value === item.draft.id) activeId.value = items.value[0]?.draft.id || "";
}

function applyToSelected(): void {
  if (!active.value || !editable(active.value) || busy.value) return;
  const source = active.value.draft;
  if (applyFields.species && !source.speciesId) { message.value = "请先为当前照片选择目标物种。"; return; }
  if (applyFields.season && !source.form.season) { message.value = "请先为当前照片选择季节。"; return; }
  if (!applyFields.species && !applyFields.location && !applyFields.season) return;
  const count = selectedTargets.value.length;
  for (const item of selectedTargets.value) {
    copyBatchFields(source, item.draft, applyFields);
    item.state = "draft";
    item.message = "";
  }
  message.value = `已应用到 ${count} 张照片。每张照片的拍摄时间、个体信息和备注保持各自填写的内容。`;
}

async function saveReady(): Promise<void> {
  if (busy.value || !loaded.value || hasUncertain.value) return;
  const queue = [...ready.value];
  if (!queue.length) return;
  saving.value = true;
  pauseRequested.value = false;
  message.value = `准备保存 ${queue.length} 张照片…`;
  try {
    for (const item of queue) {
      if (pauseRequested.value || disposed) break;
      const identity = newSpeciesIdentity(item.draft, taxonomy.value);
      const registered = identity ? registeredSpecies.get(identity.key) : undefined;
      if (identity && registered && registered.signature !== identity.signature) {
        item.state = "error";
        item.message = "同名新物种已在本批登记，但分类资料不同。请改选已有图鉴物种并核对。";
        continue;
      }
      item.state = "saving";
      item.message = "";
      try {
        const result = await saveObservationDraft(item.draft, taxonomy.value, registered?.id);
        // Record success before doing any optional refresh; a refresh failure must never resubmit a photo.
        item.observationId = result.observation_id;
        item.state = "saved";
        item.selected = false;
        if (identity) registeredSpecies.set(identity.key, { id: result.species_id, signature: identity.signature });
      } catch (caught) {
        item.state = isUncertainSave(caught) ? "uncertain" : "error";
        item.message = item.state === "uncertain"
          ? "连接中断或服务异常，无法确认这张照片是否已保存。请在田野记录中核实；本批已暂停，不会重复提交。"
          : errorMessage(caught);
        if (item.state === "uncertain") break;
      }
    }
    message.value = `本批已保存 ${saved.value.length} / ${items.value.length} 张。${hasUncertain.value ? "有保存结果待核实的照片，请先检查田野记录。" : pauseRequested.value ? "已暂停，其余照片保留在队列中。" : "未保存照片保留在队列中，可继续填写或重试明确失败的项目。"}`;
    try { species.value = await api<SpeciesSummary[]>("/api/species"); }
    catch { message.value += " 图鉴列表暂未刷新，可关闭后重新打开。"; }
    emit("changed");
  } finally { saving.value = false; }
}

async function linkTrip(): Promise<void> {
  if (busy.value || !tripId.value || !saved.value.length) return;
  linking.value = true;
  tripMessage.value = "正在核对时间、地点并关联远征…";
  try {
    const detail = await api<TripDetail>(`/api/trips/${tripId.value}`);
    const ids = [...new Set([...detail.observations.map((item) => item.id), ...saved.value.map((item) => item.observationId!)])];
    await api(`/api/trips/${tripId.value}/observations`, jsonRequest("PUT", { observation_ids: ids }));
    tripMessage.value = "本批已保存照片已关联到远征，原有观察已保留。";
    emit("changed");
  } catch (caught) { tripMessage.value = `远征关联未确认：${errorMessage(caught)}。已保存照片保留，可单独重试关联。`; }
  finally { linking.value = false; }
}

function canClose(): boolean {
  if (busy.value) { message.value = "请等待当前操作完成；保存过程中可以先点击暂停。"; return false; }
  if (items.value.some((item) => item.state !== "saved")) {
    return window.confirm("未保存照片的填写内容仅保留在本次窗口中，关闭后需要重新整理。已经保存的记录会保留。确定关闭吗？");
  }
  return true;
}
function requestClose(): void { if (canClose()) emit("close"); }
function beforeUnload(event: BeforeUnloadEvent): void {
  if (busy.value || items.value.some((item) => item.state !== "saved")) { event.preventDefault(); event.returnValue = ""; }
}
onBeforeRouteLeave(() => canClose());
onBeforeUnmount(() => {
  disposed = true;
  items.value.forEach((item) => URL.revokeObjectURL(item.previewUrl));
  window.removeEventListener("beforeunload", beforeUnload);
});
defineExpose({ requestClose });
</script>

<template>
  <section class="batch-import" aria-label="登记新发现">
    <header class="dialog-header">
      <div><p class="eyebrow">NEW OBSERVATIONS</p><h2>登记新发现</h2><p class="batch-intro">选择一张或多张照片，每张建立一笔观察，逐张校对后统一保存。</p></div>
      <button class="icon-button" type="button" aria-label="关闭登记新发现" @click="requestClose">×</button>
    </header>
    <div class="batch-workspace">
      <aside class="batch-queue" aria-label="待保存照片队列">
        <label class="batch-drop" @dragover.prevent @drop.prevent="dropFiles">
          <strong>＋ 选择或拖入照片</strong><span>单张或多张 JPEG/JPG · 每张不超过 10 MB</span>
          <input type="file" multiple accept="image/jpeg,.jpg,.jpeg" :disabled="busy" aria-label="批量选择照片" @change="filesChanged" />
        </label>
        <div class="batch-queue-tools"><span>{{ items.length }} 张 · 已保存 {{ saved.length }}</span><button type="button" :disabled="busy" @click="selectAll(true)">全选</button><button type="button" :disabled="busy" @click="selectAll(false)">全不选</button></div>
        <ol class="batch-items">
          <li v-for="(item, index) in items" :key="item.draft.id" class="batch-item" :class="{ 'is-active': item === active, 'is-saved': item.state === 'saved' }" :data-state="item.state">
            <input v-model="item.selected" type="checkbox" :disabled="busy || !editable(item)" :aria-label="`勾选 ${item.draft.photo?.name}`" />
            <button class="batch-photo-button" type="button" :aria-pressed="item === active" @click="activeId = item.draft.id">
              <img v-if="!item.draft.photoError" :src="item.previewUrl" alt="" loading="lazy" /><span v-else class="batch-invalid-photo">!</span>
              <span><strong :title="item.draft.photo?.name">{{ index + 1 }}. {{ item.draft.photo?.name }}</strong><small>{{ statusLabel(item) }}</small></span>
            </button>
            <button v-if="editable(item)" class="batch-remove" type="button" :disabled="busy" :aria-label="`移除 ${item.draft.photo?.name}`" @click="removeItem(item)">×</button>
          </li>
        </ol>
        <p class="batch-session-note">填写内容保留在本次窗口中。请完成保存后再关闭页面。</p>
      </aside>
      <section class="batch-editor">
        <template v-if="active">
          <div class="batch-photo-heading"><img v-if="!active.draft.photoError" :src="active.previewUrl" alt="当前待校对照片" /><div><p class="eyebrow">PHOTO REVIEW</p><h3 :title="active.draft.photo?.name">{{ active.draft.photo?.name }}</h3><p>{{ statusLabel(active) }}</p><p v-if="active.message" role="alert">{{ active.message }}</p><a v-if="active.observationId" :href="`/observations?observation=${active.observationId}`" target="_blank" rel="noopener">查看已保存记录 ↗</a><a v-if="active.state === 'uncertain'" href="/observations" target="_blank" rel="noopener">打开田野记录核实 ↗</a></div></div>
          <template v-if="editable(active)">
            <div class="batch-apply" :inert="busy">
              <strong>将当前照片的信息应用到勾选的其他照片</strong>
              <div><label><input v-model="applyFields.species" type="checkbox" />目标物种</label><label><input v-model="applyFields.location" type="checkbox" />地点与坐标</label><label><input v-model="applyFields.season" type="checkbox" />季节</label></div>
              <p>所选字段会覆盖目标照片中的对应内容，照片时间、个体信息和备注分别保留。</p>
              <button type="button" class="secondary-button" :disabled="!selectedTargets.length || busy" @click="applyToSelected">应用到 {{ selectedTargets.length }} 张照片</button>
            </div>
            <div v-if="issues(active).length" class="batch-issues" role="status">{{ issues(active).join('；') }}</div>
            <form :key="active.draft.id" class="batch-entry-form" :inert="saving || linking" @submit.prevent>
              <ObservationFields :draft="active.draft" :species="species" :locations="locations" :taxonomy="taxonomy" fixed-photo />
            </form>
          </template>
        </template>
        <div v-else class="batch-empty"><p class="eyebrow">YOUR FIELD ARCHIVE</p><h3>把这次出行的照片放进手册</h3><p>先选择照片，再按物种或地点成组填写。每张照片仍可单独校对。</p></div>
      </section>
    </div>
    <div v-if="saved.length" class="batch-trip">
      <label>保存后关联远征（可选）<select v-model="tripId" :disabled="busy"><option value="">选择远征</option><option v-for="trip in trips" :key="trip.id" :value="String(trip.id)">{{ trip.name }}</option></select></label>
      <button type="button" class="secondary-button" :disabled="busy || !tripId" @click="linkTrip">关联本批已保存照片</button><span role="status">{{ tripMessage }}</span>
    </div>
    <footer class="dialog-footer batch-footer">
      <span role="status">{{ message || '季节和物种初始留空；请确认每张照片的拍摄信息。' }}</span>
      <button v-if="saving" type="button" class="secondary-button" :disabled="pauseRequested" @click="pauseRequested = true">{{ pauseRequested ? '当前照片完成后暂停' : '暂停保存' }}</button>
      <button v-else type="button" class="primary-button" :disabled="busy || !loaded || !ready.length || hasUncertain" @click="saveReady">保存就绪照片（{{ ready.length }}）</button>
    </footer>
  </section>
</template>

<style scoped>
.batch-import{display:flex;flex-direction:column;height:min(920px,92vh);color:var(--ink-deep);background:var(--paper,#f4eddf)}
.batch-import .dialog-header{flex-shrink:0;background:var(--ink-deep);color:#f5eedf;gap:16px;padding:18px 24px}
.batch-import .dialog-header h2{color:inherit;margin:4px 0}.batch-intro{margin:0;font-size:13px;opacity:.8}.batch-import .icon-button{color:inherit}
.batch-workspace{display:grid;grid-template-columns:minmax(250px,28%) minmax(0,1fr);flex:1;min-height:0}
.batch-queue{display:flex;flex-direction:column;padding:16px;border-right:1px solid var(--line);min-height:0;background:rgba(115,95,54,.05)}
.batch-drop{display:grid;gap:8px;padding:18px 12px;border:1px dashed #8e7955;text-align:center;cursor:pointer}.batch-drop span{font-size:12px}.batch-drop input{max-width:100%;font-size:12px}
.batch-queue-tools{display:flex;align-items:center;gap:8px;padding:12px 0;font-size:12px}.batch-queue-tools span{flex:1}.batch-queue-tools button,.batch-remove{background:none;border:0;color:inherit;padding:4px}
.batch-items{list-style:none;padding:0;margin:0;overflow:auto;flex:1;min-height:80px}.batch-item{display:flex;align-items:center;gap:8px;padding:8px 4px;border:1px solid transparent;border-bottom-color:var(--line)}.batch-item.is-active{border-color:#8e7955;background:#e9e0cc}.batch-item.is-saved{opacity:.7}.batch-item>input{flex:0 0 auto;width:16px}
.batch-photo-button{display:flex;align-items:center;gap:10px;min-width:0;flex:1;text-align:left;border:0;background:none;padding:0;color:inherit}.batch-photo-button img,.batch-invalid-photo{width:56px;height:56px;object-fit:cover;flex-shrink:0}.batch-photo-button>span{min-width:0}.batch-photo-button strong{display:block;overflow-wrap:anywhere;font-size:13px}.batch-photo-button small{display:block;margin-top:5px;font-size:11px}.batch-invalid-photo{display:grid;place-content:center;background:#e4d1c8;color:#963d30}.batch-session-note{font-size:11px;line-height:1.6;margin:12px 0 0}
.batch-editor{overflow:auto;padding:20px 26px;min-width:0}.batch-photo-heading{display:flex;gap:20px;align-items:center;margin-bottom:20px}.batch-photo-heading>img{width:38%;height:180px;object-fit:contain;background:#20352c}.batch-photo-heading>div{min-width:0}.batch-photo-heading h3{overflow-wrap:anywhere;margin:6px 0}.batch-photo-heading p{font-size:13px}.batch-photo-heading a{font-size:13px;color:#365b42}
.batch-apply{padding:16px;border:1px solid var(--line);background:#ede4cf;margin-bottom:14px}.batch-apply>div{display:flex;flex-wrap:wrap;gap:20px;margin:12px 0}.batch-apply label{display:flex;align-items:center;gap:7px}.batch-apply input{width:auto}.batch-apply p{font-size:12px;line-height:1.7}.batch-issues{padding:10px 12px;border-left:3px solid #9c7740;background:#f4e9d2;font-size:12px;line-height:1.8;margin-bottom:12px}
.batch-entry-form{display:block!important;max-height:none!important}.batch-entry-form :deep(fieldset){min-width:0}.batch-empty{display:grid;align-content:center;min-height:350px;text-align:center;padding:25px}.batch-empty p{line-height:1.8}.batch-trip{display:flex;align-items:end;gap:14px;padding:12px 24px;border-top:1px solid var(--line);flex-wrap:wrap}.batch-trip label{display:grid;gap:6px;font-size:12px}.batch-trip select{min-width:160px}.batch-trip span{font-size:12px;flex:1;min-width:180px}.batch-footer{gap:18px;padding:15px 24px!important;flex-shrink:0}.batch-footer>span{font-size:12px;line-height:1.7;flex:1}.batch-footer>button{flex-shrink:0}
@media(max-width:760px){.batch-workspace{grid-template-columns:1fr;overflow:auto;display:block}.batch-queue{border-right:0;border-bottom:1px solid var(--line);max-height:320px}.batch-editor{overflow:visible;padding:18px}.batch-photo-heading>img{height:140px}.batch-import{height:94vh}.batch-footer{flex-wrap:wrap}.batch-import .dialog-header{padding:14px 18px}.batch-footer>span{flex-basis:100%}}

.batch-import { background: var(--paper-light); }
.batch-import .dialog-header h2 { font-size: 25px; }
.batch-import .eyebrow { margin: 0 0 7px; font: 10px var(--sans); letter-spacing: .16em; }
.batch-import .dialog-header .eyebrow { color: var(--gold-light); }
.batch-import .icon-button { flex-shrink: 0; }
.batch-queue { padding: 16px; }
.batch-drop { position: relative; padding: 20px 10px; gap: 6px; background: rgba(255,255,255,.3); }
.batch-drop strong { font: 14px var(--sans); }
.batch-drop input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.batch-drop:focus-within { outline: 2px solid var(--gold); outline-offset: 3px; }
.batch-photo-button strong { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font: 12px var(--sans); }
.batch-photo-button small { font: 11px/1.5 var(--sans); color: var(--ink-soft); }
.batch-item { padding: 10px 7px; border-radius: 3px; }
.batch-item.is-active { border-color: var(--moss); background: #e0e5d8; box-shadow: inset 3px 0 var(--moss); }
.batch-item[data-state="error"], .batch-item[data-state="uncertain"] { border-left: 3px solid var(--rust); }
.batch-photo-heading { gap: 18px; margin-bottom: 16px; }
.batch-photo-heading > img { width: 40%; height: 155px; }
.batch-photo-heading > div { flex: 1; }
.batch-photo-heading h3 { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font: 16px var(--sans); }
.batch-photo-heading p { font: 12px/1.7 var(--sans); }
.batch-apply { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 16px; padding: 14px 16px; background: var(--paper); }
.batch-apply > strong { grid-column: 1 / -1; font: 13px var(--sans); }
.batch-apply > div { margin: 0; gap: 12px; align-items: center; }
.batch-apply label { font: 12px var(--sans); }
.batch-apply > button { grid-column: 2; grid-row: 2; padding: 9px 12px; font: 12px var(--sans); }
.batch-apply p { grid-column: 1 / -1; margin: 0; font: 11px/1.7 var(--sans); color: var(--ink-soft); }
.batch-editor { scrollbar-gutter: stable; }
.batch-trip { background: var(--paper); }
.batch-trip span:empty { display: none; }
@media (max-width: 1000px) {
  .batch-apply { grid-template-columns: 1fr; }
  .batch-apply > button { grid-column: 1; grid-row: auto; justify-self: start; }
}
@media (max-width: 760px) {
  .batch-import { height: 94dvh; }
  .batch-import .dialog-header h2 { font-size: 22px; }
  .batch-intro { font-size: 11px; }
  .batch-queue { padding: 12px 14px; max-height: none; }
  .batch-drop { padding: 12px 8px; }
  .batch-drop span { font-size: 10px; }
  .batch-queue-tools { padding: 8px 0; }
  .batch-items { display: flex; gap: 8px; min-height: 0; flex: none; overflow-x: auto; padding-bottom: 4px; }
  .batch-item { flex: 0 0 210px; min-width: 0; padding: 7px; border: 1px solid var(--line); }
  .batch-photo-button img, .batch-invalid-photo { width: 40px; height: 44px; }
  .batch-photo-button { gap: 7px; }
  .batch-photo-button strong { font-size: 11px; }
  .batch-session-note { margin-top: 6px; font-size: 10px; }
  .batch-editor { padding: 16px 14px; }
  .batch-photo-heading > img { height: 100px; width: 36%; }
  .batch-photo-heading h3 { font-size: 13px; }
  .batch-apply { padding: 12px; }
  .batch-trip { max-height: 24dvh; overflow: auto; flex-shrink: 0; padding: 10px 16px; gap: 8px; }
  .batch-trip select { min-width: 0; width: 100%; }
  .batch-trip button { padding: 9px 12px; font-size: 11px; }
  .batch-footer { padding: 11px 16px !important; gap: 8px; }
  .batch-footer > span { font-size: 11px; line-height: 1.5; }
  .batch-footer > button { width: 100%; padding: 11px; }
}
</style>
