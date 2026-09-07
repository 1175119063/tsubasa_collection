<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { api, ApiError, errorMessage, jsonRequest } from "@/api/client";
import { taxonomyPath, taxonomyRankLabel, type PersonalTaxonomyTree, type TaxonomyNode, type TaxonomyNodeKey } from "./taxonomy-model";

const props = defineProps<{ tree: PersonalTaxonomyTree; nodeKey: TaxonomyNodeKey }>();
const emit = defineEmits<{ close: []; saved: [] }>();
const dialog = ref<HTMLDialogElement>();
const node = computed(() => props.tree.nodes[props.nodeKey]!);
const ranks = ['order', 'family', 'genus', 'species'] as const;
const level = computed(() => ranks.indexOf(node.value.rank as typeof ranks[number]));
const action = ref<'rename' | 'move'>('rename');
const chineseName = ref(node.value.chineseName);
const scientificName = ref(node.value.scientificName);
const createParent = ref(false);
const depth = ref(1);
const parentId = ref('');
const search = ref('');
const names = ref(Array.from({ length: 3 }, () => ({ chinese_name: '', scientific_name: '' })));
const ancestorLevel = computed(() => level.value - (createParent.value ? depth.value : 0) - 1);
const ancestorRank = computed(() => ranks[ancestorLevel.value]);
function pathLabel(item: TaxonomyNode): string {
  return taxonomyPath(props.tree, item.key).map(value => `${value.chineseName} (${value.scientificName})`).join(' → ');
}
const candidates = computed(() => {
  const terms = search.value.normalize('NFKC').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return Object.values(props.tree.nodes).filter(item => item.rank === ancestorRank.value
    && terms.every(term => pathLabel(item).normalize('NFKC').toLocaleLowerCase().includes(term)));
});
const parent = computed(() => Object.values(props.tree.nodes).find(item => item.rank === ancestorRank.value && item.sourceId === parentId.value));
const newNames = computed(() => names.value.slice(0, depth.value));
const payload = computed(() => action.value === 'rename'
  ? { action: 'rename', name: { chinese_name: chineseName.value, scientific_name: scientificName.value } }
  : { action: 'move', parent_id: ancestorLevel.value >= 0 && parentId.value ? Number(parentId.value) : null, new_parents: createParent.value ? newNames.value : [] });
type Path = { rank: string; id: number | null; chinese_name: string; scientific_name: string }[];
interface Preview { before: Path; after: Path; species: { id: number; chinese_name: string; scientific_name: string }[]; species_count: number; observation_count: number; preview_token: string }
const preview = ref<Preview | null>(null);
const impact = ref<HTMLElement>();
const busy = ref(false);
const status = ref('');
let revision = 0;
watch(payload, () => { preview.value = null; status.value = ''; revision++; }, { deep: true });
watch([createParent, depth], () => { parentId.value = ''; search.value = ''; });
const endpoint = computed(() => `/api/taxonomy/${node.value.rank}/${node.value.sourceId}`);
function taxonomyError(caught: unknown): string {
  if (caught instanceof ApiError && caught.status === 404 && caught.message === 'Not Found') {
    return '当前后台尚未加载分类修改接口。请重启本地服务，再点击“预览修改影响”；已填写的内容会保留。';
  }
  return errorMessage(caught);
}
async function showPreview(): Promise<void> {
  if (action.value === 'move' && ancestorLevel.value >= 0 && !parent.value) { status.value = '请在搜索结果中选择上级分类'; return; }
  const version = revision;
  busy.value = true; status.value = ''; preview.value = null;
  try {
    const result = await api<Preview>(`${endpoint.value}/preview`, jsonRequest('POST', payload.value));
    if (version === revision) {
      preview.value = result;
      await nextTick();
      impact.value?.scrollIntoView({ block: 'nearest' });
      impact.value?.focus({ preventScroll: true });
    }
  } catch (caught) { status.value = taxonomyError(caught); }
  finally { busy.value = false; }
}
async function save(): Promise<void> {
  if (!preview.value || busy.value) return;
  busy.value = true; status.value = '';
  try {
    await api(endpoint.value, jsonRequest('PUT', { ...payload.value, preview_token: preview.value.preview_token }));
    emit('saved');
  } catch (caught) { preview.value = null; status.value = taxonomyError(caught); }
  finally { busy.value = false; }
}
function close(): void { if (!busy.value) emit('close'); }
onMounted(() => dialog.value?.showModal());
</script>

<template>
  <dialog ref="dialog" class="taxonomy-edit-dialog" @cancel.prevent="close" @click.self="close">
    <form @submit.prevent="showPreview">
      <header><div><small>TAXONOMY EDIT</small><h2>修改分类 · {{ node.chineseName }}</h2></div><button type="button" aria-label="关闭分类修改" :disabled="busy" @click="close">×</button></header>
      <div class="taxonomy-edit-body">
        <p class="taxonomy-current-path">{{ pathLabel(node) }}</p>
        <fieldset :disabled="busy">
          <legend>修改方式</legend>
          <label>操作<select v-model="action"><option value="rename">修改名称</option><option v-if="level > 0" value="move">修改归属</option></select></label>
          <div v-if="action === 'rename'" class="form-grid">
            <label>中文名<input v-model="chineseName" required maxlength="120" /></label>
            <label>拉丁学名<input v-model="scientificName" required maxlength="120" /></label>
          </div>
          <template v-else>
            <p>{{ node.rank === 'species' ? '只调整当前物种的所属属，其他物种保持原归属。' : '整个分支会随当前节点一起移动，下面的物种保持原有身份。' }}</p>
            <label>目标分类<select v-model="createParent"><option :value="false">选择已有分类</option><option :value="true">补建缺少的分类</option></select></label>
            <label v-if="createParent">补建层级<select v-model="depth"><option v-for="count in level" :key="count" :value="count">{{ ranks.slice(level - count, level).map(taxonomyRankLabel).join(' → ') }}</option></select></label>
            <template v-if="ancestorLevel >= 0">
              <label>搜索上级分类（{{ taxonomyRankLabel(ancestorRank!) }}）<input v-model="search" type="search" placeholder="中文名、拉丁名或分类路径" /></label>
              <ul class="taxonomy-parent-results" aria-label="可选上级分类">
                <li v-for="item in candidates" :key="item.key"><button type="button" :aria-pressed="parentId === item.sourceId" @click="parentId = item.sourceId">{{ pathLabel(item) }}</button></li>
              </ul>
              <p v-if="!candidates.length">没有匹配的上级分类，可修改搜索词或补建缺少的层级。</p>
              <p>已选：{{ parent ? pathLabel(parent) : '尚未选择' }}</p>
            </template>
            <p v-else>上级分类：鸟纲 Aves</p>
            <section v-for="(item, index) in (createParent ? newNames : [])" :key="index" class="taxonomy-new-parent">
              <h3>新增{{ taxonomyRankLabel(ranks[level - depth + index]!) }}</h3>
              <div class="form-grid"><label>中文名<input v-model="item.chinese_name" required maxlength="120" /></label><label>拉丁学名<input v-model="item.scientific_name" required maxlength="120" /></label></div>
            </section>
          </template>
          <button class="secondary-button" type="submit">预览修改影响</button>
        </fieldset>
        <section v-if="preview" ref="impact" class="taxonomy-impact" aria-label="修改影响预览" tabindex="-1">
          <h3>修改影响预览</h3>
          <p><strong>修改前：</strong>{{ preview.before.map(item => `${item.chinese_name} (${item.scientific_name})`).join(' → ') }}</p>
          <p><strong>修改后：</strong>{{ preview.after.map(item => `${item.chinese_name} (${item.scientific_name})`).join(' → ') }}</p>
          <p>涉及 {{ preview.species_count }} 个物种、{{ preview.observation_count }} 笔观察。</p>
          <details><summary>查看受影响物种</summary><ul><li v-for="item in preview.species" :key="item.id">{{ item.chinese_name }} · {{ item.scientific_name }}</li></ul></details>
          <p>物种编号、照片、录音和观察内容保持不变。归属调整后，没有物种的旧分支会自动清理。</p>
        </section>
        <p v-if="status" role="alert">{{ status }}</p>
      </div>
      <footer><button class="secondary-button" type="button" :disabled="busy" @click="close">取消</button><button class="primary-button" type="button" :disabled="busy || !preview" @click="save">{{ busy ? '正在处理…' : '确认保存分类' }}</button></footer>
    </form>
  </dialog>
</template>

<style scoped>
.taxonomy-edit-dialog { width: min(820px, 94vw); max-height: 92vh; padding: 0; color: var(--ink); background: var(--paper-light); border: 1px solid var(--line); }
.taxonomy-edit-dialog::backdrop { background: rgba(10,25,19,.65); backdrop-filter: blur(4px); }
form { display: flex; flex-direction: column; max-height: 90vh; margin: 0; padding: 0; border: 0; }
header, footer { display: flex; align-items: center; gap: 12px; padding: 18px 24px; flex-shrink: 0; }
header { justify-content: space-between; background: #1f362c; color: var(--paper-light); }
header small { color: var(--gold-light); letter-spacing: .14em; } header h2 { margin: 6px 0 0; font-size: 24px; }
header button { color: inherit; background: none; border: 0; font-size: 28px; }
footer { justify-content: flex-end; border-top: 1px solid var(--line); }
.taxonomy-edit-body { padding: 18px 24px; overflow-y: auto; min-height: 0; }
fieldset { margin: 18px 0; padding: 16px; } label { display: block; margin: 8px 0; }
.taxonomy-current-path, .taxonomy-edit-body p { font: 13px/1.8 var(--sans); overflow-wrap: anywhere; }
.taxonomy-parent-results { position: static; list-style: none; padding: 0; margin: 10px 0; max-height: 180px; overflow-y: auto; border: 1px solid var(--line); }
.taxonomy-parent-results button { width: 100%; padding: 10px; text-align: left; border: 0; border-bottom: 1px solid var(--line); background: transparent; color: var(--ink); font: 13px/1.6 var(--sans); }
.taxonomy-parent-results button:hover, .taxonomy-parent-results button[aria-pressed=true] { background: var(--paper); }
.taxonomy-impact, .taxonomy-new-parent { margin-top: 14px; padding: 14px; background: var(--paper); border: 1px solid var(--line); }
.taxonomy-impact ul { max-height: 180px; overflow: auto; }
</style>
