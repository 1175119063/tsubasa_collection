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
const editorScroll = ref<HTMLElement | null>(null);
const sections = ["目标物种", "个体与行为", "其他物种", "时间与地点"];
const activeNumber = computed(() => items.value.findIndex((item) => item === active.value) + 1);
const pendingCount = computed(() => items.value.length - saved.value.length - ready.value.length);
function goToSection(index: number): void {
  const field = editorScroll.value?.querySelectorAll<HTMLElement>(".batch-entry-form > fieldset")[index];
  if (!field) return;
  field.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  field.focus({ preventScroll: true });
}
function itemTone(item: BatchItem): string {
  if (item.state === "saved") return "saved";
  if (item.state === "error" || item.state === "uncertain" || item.draft.photoError) return "error";
  return issues(item).length ? "pending" : "ready";
}
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
      <div><p class="eyebrow">NEW OBSERVATIONS</p><h2>登记新发现</h2><p class="batch-intro">一张照片，一次相遇。逐张整理后，一起存入手册。</p></div>
      <div v-if="items.length" class="batch-overview" aria-label="本批整理进度">
        <span><b>{{ pendingCount }}</b>待检查</span><span class="ready"><b>{{ ready.length }}</b>可保存</span><span><b>{{ saved.length }}</b>已保存</span>
      </div>
      <button class="icon-button" type="button" aria-label="关闭登记新发现" @click="requestClose">×</button>
    </header>
    <div class="batch-workspace">
      <aside class="batch-queue" aria-label="待保存照片队列">
        <label class="batch-drop" @dragover.prevent @drop.prevent="dropFiles">
          <strong>＋ {{ items.length ? '继续添加照片' : '选择或拖入照片' }}</strong><span>JPEG / JPG · 每张不超过 10 MB</span>
          <input type="file" multiple accept="image/jpeg,.jpg,.jpeg" :disabled="busy" aria-label="批量选择照片" @change="filesChanged" />
        </label>
        <figure v-if="active" class="batch-preview">
          <div class="batch-preview-image"><img v-if="!active.draft.photoError" :src="active.previewUrl" alt="当前待校对照片" /><span v-else>无法预览此照片</span><span class="batch-preview-number">{{ String(activeNumber).padStart(2, '0') }} / {{ String(items.length).padStart(2, '0') }}</span></div>
          <figcaption><strong :title="active.draft.photo?.name">{{ active.draft.photo?.name }}</strong><span>{{ active.draft.form.observed_at?.replace('T', ' ') || '拍摄时间待填写' }}</span></figcaption>
        </figure>
        <div class="batch-queue-tools"><span>照片队列 · {{ items.length }}</span><button type="button" :disabled="busy || !items.length" @click="selectAll(true)">全选</button><button type="button" :disabled="busy || !items.length" @click="selectAll(false)">全不选</button></div>
        <ol class="batch-items">
          <li v-for="(item, index) in items" :key="item.draft.id" class="batch-item" :class="{ 'is-active': item === active, 'is-saved': item.state === 'saved' }" :data-state="item.state" :data-tone="itemTone(item)">
            <input v-model="item.selected" type="checkbox" :disabled="busy || !editable(item)" :aria-label="`勾选 ${item.draft.photo?.name}`" />
            <button class="batch-photo-button" type="button" :aria-pressed="item === active" @click="activeId = item.draft.id">
              <img v-if="!item.draft.photoError" :src="item.previewUrl" alt="" loading="lazy" /><span v-else class="batch-invalid-photo">!</span>
              <span><strong :title="item.draft.photo?.name">{{ index + 1 }}. {{ item.draft.photo?.name }}</strong><small><i aria-hidden="true"></i>{{ statusLabel(item) }}</small></span>
            </button>
            <button v-if="editable(item)" class="batch-remove" type="button" :disabled="busy" :aria-label="`移除 ${item.draft.photo?.name}`" @click="removeItem(item)">×</button>
          </li>
        </ol>
        <p class="batch-session-note">勾选照片可批量填写共用信息。<br />草稿仅保留在本次窗口，请保存后再关闭。</p>
      </aside>
      <section class="batch-editor">
        <template v-if="active">
          <div class="batch-editor-top">
            <div class="batch-photo-heading"><div><p class="eyebrow">PHOTO {{ String(activeNumber).padStart(2, '0') }}</p><h3>校对这次相遇</h3></div><span class="batch-status" :data-tone="itemTone(active)">{{ statusLabel(active) }}</span></div>
            <nav v-if="editable(active)" class="batch-section-nav" aria-label="观察表单分组"><button v-for="(section, index) in sections" :key="section" type="button" @click="goToSection(index)"><span>{{ String(index + 1).padStart(2, '0') }}</span>{{ section }}</button></nav>
          </div>
          <div ref="editorScroll" class="batch-editor-scroll">
            <p v-if="active.message" class="batch-error" role="alert">{{ active.message }}</p>
            <template v-if="editable(active)">
              <div v-if="items.length > 1" class="batch-apply" :inert="busy">
                <strong>共用信息，一次填写</strong>
                <div><label><input v-model="applyFields.species" type="checkbox" />目标物种</label><label><input v-model="applyFields.location" type="checkbox" />地点与坐标</label><label><input v-model="applyFields.season" type="checkbox" />季节</label></div>
                <p>覆盖勾选照片的对应字段。行为逐张填写；更换物种会清空原行为选择。</p>
                <button type="button" class="secondary-button" :disabled="!selectedTargets.length || busy" @click="applyToSelected">应用到 {{ selectedTargets.length }} 张照片</button>
              </div>
              <div v-if="issues(active).length" class="batch-issues" role="status"><strong>还需完善 {{ issues(active).length }} 项</strong><ul><li v-for="issue in issues(active)" :key="issue">{{ issue }}</li></ul></div>
              <form :key="active.draft.id" class="batch-entry-form" :inert="saving || linking" @submit.prevent>
                <ObservationFields :draft="active.draft" :species="species" :locations="locations" :taxonomy="taxonomy" fixed-photo />
              </form>
            </template>
            <div v-else class="batch-result"><span class="batch-result-mark" aria-hidden="true">{{ active.state === 'saved' ? '✓' : '…' }}</span><h3>{{ active.state === 'saved' ? '这次相遇已存入手册' : statusLabel(active) }}</h3><p>{{ active.state === 'saved' ? '可以继续整理其他照片，或在下方关联本次远征。' : '请等待保存完成；结果待核实时，请先到田野记录确认。' }}</p><a v-if="active.observationId" :href="`/observations?observation=${active.observationId}`" target="_blank" rel="noopener">查看已保存记录 ↗</a><a v-if="active.state === 'uncertain'" href="/observations" target="_blank" rel="noopener">打开田野记录核实 ↗</a></div>
          </div>
        </template>
        <div v-else class="batch-empty">
          <svg class="batch-empty-art" viewBox="0 0 180 140" fill="none" aria-hidden="true"><rect x="25" y="22" width="108" height="90" rx="5" transform="rotate(-10 25 22)" /><rect x="45" y="25" width="112" height="94" rx="5" /><path d="M57 94 83 67 102 84 118 64 145 94" /><circle cx="127" cy="47" r="7" /><path d="M65 107h44" /></svg>
          <p class="eyebrow">YOUR FIELD ARCHIVE</p><h3>从一张照片，记下这次相遇</h3><p>添加照片，开始整理你的观鸟发现。</p>
          <ol class="batch-empty-steps"><li><b>01</b><span>选择照片<small>每张建立一笔观察</small></span></li><li><b>02</b><span>补全记录<small>物种、行为、时间与地点</small></span></li><li><b>03</b><span>存入手册<small>同时积累个人图鉴</small></span></li></ol>
        </div>
      </section>
    </div>
    <div v-if="saved.length" class="batch-trip">
      <label>保存后关联远征（可选）<select v-model="tripId" :disabled="busy"><option value="">选择远征</option><option v-for="trip in trips" :key="trip.id" :value="String(trip.id)">{{ trip.name }}</option></select></label>
      <button type="button" class="secondary-button" :disabled="busy || !tripId" @click="linkTrip">关联本批已保存照片</button><span role="status">{{ tripMessage }}</span>
    </div>
    <footer class="dialog-footer batch-footer">
      <span role="status">{{ message || '先添加照片，再填写物种、季节和拍摄信息。' }}</span>
      <button v-if="saving" type="button" class="secondary-button" :disabled="pauseRequested" @click="pauseRequested = true">{{ pauseRequested ? '当前照片完成后暂停' : '暂停保存' }}</button>
      <button v-else type="button" class="primary-button" :disabled="busy || !loaded || !ready.length || hasUncertain" @click="saveReady">保存就绪照片（{{ ready.length }}）</button>
    </footer>
  </section>
</template>

<style scoped>
.batch-import { display: flex; flex-direction: column; height: min(960px, 94dvh); color: var(--ink-deep); background: var(--paper-light); }
.batch-import .dialog-header { flex-shrink: 0; background: var(--ink-deep); color: #f5eedf; gap: 24px; padding: 20px 26px; }
.batch-import .dialog-header h2 { color: inherit; font-size: 25px; margin: 4px 0 8px; }
.batch-import .eyebrow { margin: 0 0 6px; font: 10px var(--sans); letter-spacing: .18em; color: var(--ink-soft); }
.batch-import .dialog-header .eyebrow { color: var(--gold-light); }
.batch-intro { margin: 0; font: 12px/1.6 var(--sans); opacity: .8; }
.batch-import .icon-button { flex-shrink: 0; color: inherit; }
.batch-overview { display: flex; gap: 22px; margin-left: auto; }
.batch-overview span { display: grid; gap: 5px; text-align: center; font: 10px var(--sans); color: #d1d9ca; }
.batch-overview b { font: 24px/1 Georgia, serif; color: #f7f1df; }
.batch-overview .ready b { color: #dbcc98; }
.batch-workspace { display: grid; grid-template-columns: minmax(245px, 28%) minmax(0, 1fr); flex: 1; min-height: 0; }
.batch-queue { display: flex; flex-direction: column; padding: 18px; border-right: 1px solid var(--line); min-height: 0; background: #eef0e6; }
.batch-drop { position: relative; display: grid; gap: 7px; padding: 16px 10px; border: 1px dashed #899983; border-radius: 6px; background: #fafbf4; text-align: center; cursor: pointer; flex-shrink: 0; }
.batch-drop strong { font: 13px var(--sans); }.batch-drop span { font: 10px var(--sans); color: var(--ink-soft); }
.batch-drop input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer; }
.batch-drop:focus-within { outline: 2px solid var(--gold); outline-offset: 3px; }
.batch-preview { margin: 16px 0 2px; flex-shrink: 0; }
.batch-preview-image { position: relative; display: grid; place-items: center; height: clamp(130px, 23vh, 240px); background: #243c32; border-radius: 6px; overflow: hidden; color: #e2e6da; font: 12px var(--sans); }
.batch-preview-image img { display: block; width: 100%; height: 100%; min-height: 0; object-fit: contain; }
.batch-preview-number { position: absolute; bottom: 8px; right: 8px; background: #142b23cc; border: 1px solid #ffffff30; border-radius: 3px; padding: 4px 7px; font: 10px var(--sans); letter-spacing: .08em; }
.batch-preview figcaption { display: grid; gap: 4px; padding: 10px 1px; min-width: 0; }
.batch-preview figcaption strong { overflow: hidden; white-space: nowrap; text-overflow: ellipsis; font: 12px var(--sans); }
.batch-preview figcaption > span { color: var(--ink-soft); font: 11px var(--sans); }
.batch-queue-tools { display: flex; align-items: center; gap: 6px; padding: 10px 0; font: 11px var(--sans); border-top: 1px solid var(--line); }
.batch-queue-tools span { flex: 1; }.batch-queue-tools button, .batch-remove { background: none; border: 0; color: inherit; padding: 5px; cursor: pointer; }
.batch-items { list-style: none; padding: 0; margin: 0; overflow: auto; flex: 1; min-height: 70px; }
.batch-item { display: flex; align-items: center; gap: 7px; padding: 9px 7px; border: 1px solid transparent; border-radius: 5px; margin-bottom: 5px; }
.batch-item.is-active { border-color: #a0b098; background: #dde5d8; box-shadow: inset 3px 0 var(--moss); }.batch-item.is-saved { background: #ffffff55; }
.batch-item > input { flex: 0 0 auto; width: 14px; height: 14px; margin: 0; accent-color: var(--moss); }
.batch-photo-button { display: flex; align-items: center; gap: 9px; min-width: 0; flex: 1; text-align: left; border: 0; background: none; padding: 0; color: inherit; cursor: pointer; }
.batch-photo-button img, .batch-invalid-photo { width: 42px; height: 46px; object-fit: cover; flex-shrink: 0; border-radius: 3px; }
.batch-photo-button > span { min-width: 0; }.batch-photo-button strong { display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font: 11px var(--sans); }
.batch-photo-button small { display: flex; align-items: center; gap: 5px; margin-top: 6px; font: 10px/1.4 var(--sans); color: var(--ink-soft); }
.batch-photo-button i { width: 5px; height: 5px; border-radius: 50%; background: #b38c53; flex-shrink: 0; }
.batch-item[data-tone="ready"] i, .batch-item[data-tone="saved"] i { background: #557b50; }.batch-item[data-tone="error"] i { background: var(--rust); }
.batch-invalid-photo { display: grid; place-content: center; background: #e4d1c8; color: #963d30; }
.batch-session-note { font: 10px/1.8 var(--sans); color: var(--ink-soft); margin: 10px 0 0; }
.batch-editor { display: flex; flex-direction: column; min-width: 0; min-height: 0; padding: 0; }
.batch-editor-top { padding: 18px 26px 0; border-bottom: 1px solid var(--line); background: #fafaf3; flex-shrink: 0; }
.batch-photo-heading { display: flex; align-items: center; gap: 14px; justify-content: space-between; margin-bottom: 15px; }.batch-photo-heading > div { min-width: 0; }.batch-photo-heading h3 { font-size: 20px; margin: 0; }
.batch-status { font: 11px/1.5 var(--sans); padding: 5px 9px; border-radius: 4px; background: #eee7d6; color: #7c613c; }
.batch-status[data-tone="ready"], .batch-status[data-tone="saved"] { background: #e4ebdf; color: #41643d; }.batch-status[data-tone="error"] { background: #f1e2dc; color: var(--rust); }
.batch-section-nav { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; padding-bottom: 12px; }
.batch-section-nav button { display: flex; gap: 7px; align-items: center; justify-content: center; border: 1px solid var(--line); border-radius: 4px; padding: 9px 5px; background: transparent; color: var(--ink); font: 12px var(--sans); cursor: pointer; }
.batch-section-nav button:hover { background: #e7ecdf; border-color: #a1b197; }.batch-section-nav button span { font: 10px Georgia, serif; color: #809176; }
.batch-editor-scroll { overflow: auto; min-height: 0; padding: 20px 26px 30px; scrollbar-gutter: stable; }
.batch-apply { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px 14px; padding: 14px 16px; border: 1px solid #d5dece; border-radius: 6px; background: #edf1e7; margin-bottom: 16px; }
.batch-apply > strong { grid-column: 1 / -1; font: 13px var(--sans); }.batch-apply > div { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }.batch-apply label { display: flex; align-items: center; gap: 6px; font: 11px var(--sans); }.batch-apply input { width: 14px; height: 14px; accent-color: var(--moss); }
.batch-apply p { grid-column: 1 / -1; margin: 0; font: 10px/1.7 var(--sans); color: var(--ink-soft); }.batch-apply > button { grid-column: 2; grid-row: 2; padding: 8px 10px; font: 11px var(--sans); }
.batch-issues { padding: 12px 14px; border: 1px solid #e1d6ba; border-radius: 5px; background: #f8f3e7; font: 11px/1.8 var(--sans); margin-bottom: 18px; color: #81663e; }
.batch-issues strong { font-weight: 600; }.batch-issues ul { display: flex; flex-wrap: wrap; gap: 2px 18px; margin: 5px 0 0; padding-left: 15px; }
.batch-entry-form { display: block !important; max-height: none !important; }.batch-entry-form :deep(fieldset) { min-width: 0; scroll-margin-top: 8px; }.batch-entry-form :deep(fieldset:focus) { outline: none; }.batch-entry-form :deep(fieldset:focus-visible) { outline: 2px solid var(--gold); outline-offset: 3px; }.batch-entry-form :deep(fieldset:first-of-type) { margin-top: 0; }
.batch-error { padding: 12px; background: #f1e2dc; color: var(--rust); font: 12px/1.7 var(--sans); }
.batch-empty, .batch-result { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 36px; min-height: 300px; }
.batch-empty-art { width: 156px; height: 125px; stroke: #839775; stroke-width: 1.4; margin-bottom: 22px; }.batch-empty-art rect { fill: #f8f8ee; }.batch-empty h3, .batch-result h3 { margin: 10px 0; font-size: 24px; }.batch-empty > p:not(.eyebrow), .batch-result p { font: 12px/1.8 var(--sans); color: var(--ink-soft); }
.batch-empty-steps { display: flex; gap: 26px; padding: 25px 0 0; margin: 22px 0 0; list-style: none; border-top: 1px solid var(--line); text-align: left; }
.batch-empty-steps li { display: flex; gap: 10px; }.batch-empty-steps b { color: #8e9c7d; font: 18px Georgia, serif; }.batch-empty-steps span { display: grid; gap: 7px; font: 12px var(--sans); }.batch-empty-steps small { color: var(--ink-soft); font-size: 10px; }
.batch-result-mark { display: grid; place-items: center; width: 56px; height: 56px; border: 1px solid #adbda1; border-radius: 50%; color: var(--moss); font-size: 28px; margin: 20px; }.batch-result a { color: var(--moss); margin-top: 14px; font: 13px var(--sans); }
.batch-trip { display: flex; align-items: end; gap: 14px; padding: 12px 26px; border-top: 1px solid var(--line); flex-wrap: wrap; background: var(--paper); flex-shrink: 0; max-height: 22dvh; overflow: auto; }.batch-trip label { display: grid; gap: 6px; font: 11px var(--sans); }.batch-trip select { min-width: 160px; }.batch-trip span { font: 11px var(--sans); flex: 1; min-width: 180px; }.batch-trip span:empty { display: none; }
.batch-footer { gap: 18px; padding: 14px 26px !important; flex-shrink: 0; border-top: 1px solid var(--line); }.batch-footer > span { font: 11px/1.7 var(--sans); flex: 1; }.batch-footer > button { flex-shrink: 0; font-size: 13px; }
@media (min-width: 761px) {
  .batch-queue { overflow: auto; }
  .batch-queue:has(.batch-preview) { display: grid; grid-template-rows: auto minmax(0, 1.15fr) auto minmax(84px, 1fr) auto; }
  .batch-preview { display: flex; flex-direction: column; min-height: 0; }
  .batch-preview-image { height: auto; min-height: 0; flex: 1; }
  .batch-preview figcaption { flex-shrink: 0; }
  .batch-items { min-height: 0; }
}
@media (min-width: 761px) and (max-height: 800px) {
  .batch-preview figcaption { display: none; }
  .batch-session-note { font-size: 9px; margin-top: 6px; }
}
@media (max-width: 1000px) { .batch-overview { gap: 15px; }.batch-apply { grid-template-columns: 1fr; }.batch-apply > button { grid-column: 1; grid-row: auto; justify-self: start; }.batch-empty-steps { gap: 16px; flex-wrap: wrap; }.batch-section-nav button { font-size: 11px; gap: 4px; } }
@media (max-width: 760px) {
  .batch-import { height: 94dvh; }.batch-import .dialog-header { padding: 14px 16px; gap: 10px; flex-wrap: wrap; }.batch-import .dialog-header > div:first-child { flex: 1; }.batch-import .dialog-header h2 { font-size: 22px; }.batch-intro { font-size: 10px; }.batch-overview { order: 3; flex-basis: 100%; justify-content: flex-start; gap: 18px; }.batch-overview span { display: flex; align-items: baseline; gap: 6px; }.batch-overview b { font-size: 18px; }
  .batch-workspace { display: block; overflow: auto; }.batch-queue { border-right: 0; border-bottom: 1px solid var(--line); padding: 12px 14px; }.batch-drop { padding: 10px; }.batch-preview { display: flex; gap: 12px; margin: 12px 0 4px; }.batch-preview-image { height: 100px; width: 130px; flex-shrink: 0; }.batch-preview figcaption { justify-content: center; }.batch-preview-number { font-size: 8px; padding: 3px 4px; }.batch-session-note { display: none; }.batch-items { display: flex; gap: 8px; min-height: 0; flex: none; overflow-x: auto; }.batch-item { flex: 0 0 205px; min-width: 0; margin-bottom: 2px; border: 1px solid var(--line); }
  .batch-editor-top { padding: 16px 14px 0; }.batch-photo-heading h3 { font-size: 18px; }.batch-section-nav { gap: 4px; }.batch-section-nav button { flex-direction: column; padding: 8px 4px; gap: 4px; }.batch-editor-scroll { overflow: visible; padding: 16px 14px 24px; }.batch-empty, .batch-result { min-height: 260px; padding: 28px 18px; }.batch-empty h3, .batch-result h3 { font-size: 21px; }.batch-empty-steps { flex-direction: column; width: 100%; gap: 18px; }.batch-empty-art { width: 120px; height: 95px; margin-bottom: 12px; }
  .batch-trip { padding: 10px 16px; gap: 8px; }.batch-trip select { min-width: 0; width: 100%; }.batch-trip button { padding: 9px 12px; font-size: 11px; }.batch-footer { flex-wrap: wrap; padding: 10px 16px !important; gap: 8px; }.batch-footer > span { flex-basis: 100%; font-size: 10px; }.batch-footer > button { width: 100%; padding: 11px; }
}
</style>
