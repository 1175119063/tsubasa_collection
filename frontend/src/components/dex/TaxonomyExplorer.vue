<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import TaxonomyNodeView from "@/components/dex/TaxonomyNode.vue";
import type {
  PersonalTaxonomyTree,
  TaxonomyNode,
  TaxonomyNodeKey,
} from "@/components/dex/taxonomy-model";
import { taxonomyPath, taxonomyRankLabel } from "@/components/dex/taxonomy-model";

const props = defineProps<{
  tree: PersonalTaxonomyTree;
  currentKey: TaxonomyNodeKey;
}>();

const emit = defineEmits<{
  select: [key: TaxonomyNodeKey];
  openSpecies: [speciesId: number];
  viewObservations: [speciesId: number];
  editTaxonomy: [key: TaxonomyNodeKey];
}>();

const stage = ref<HTMLElement>();
const capacity = ref(5);
const windowStart = ref(0);
const motionDirection = ref<-1 | 1>(1);
const isAnimating = ref(false);
let resizeObserver: ResizeObserver | null = null;
let pointerStartX: number | null = null;
let motionTimer: number | null = null;
let wheelQuietTimer: number | null = null;
let wheelAccumulator = 0;
let wheelGestureLocked = false;
let reduceMotion = false;

const current = computed(() => props.tree.nodes[props.currentKey] || props.tree.nodes[props.tree.rootKey]);
const parent = computed(() => current.value.parentKey ? props.tree.nodes[current.value.parentKey] : null);
const children = computed(() => current.value.childKeys.map((key) => props.tree.nodes[key]).filter(Boolean));
const maxWindowStart = computed(() => Math.max(0, children.value.length - capacity.value));
const visibleChildren = computed(() => children.value.slice(windowStart.value, windowStart.value + capacity.value));
const path = computed(() => taxonomyPath(props.tree, current.value.key));
const hasOverflow = computed(() => children.value.length > capacity.value);
const visibleRange = computed(() => {
  if (!children.value.length) return "";
  const start = String(windowStart.value + 1).padStart(2, "0");
  const end = String(Math.min(children.value.length, windowStart.value + capacity.value)).padStart(2, "0");
  const total = String(children.value.length).padStart(2, "0");
  return `${start}—${end} / ${total}`;
});

interface Point { x: number; y: number }
interface Line { x1: number; y1: number; x2: number; y2: number }

const currentPoint = computed<Point>(() => {
  return { x: 50, y: 50 };
});

const parentPoint = computed<Point>(() => {
  return { x: 50, y: 82 };
});

const childPoints = computed<Point[]>(() => {
  const count = visibleChildren.value.length;
  if (count === 0) return [];
  const pointSets: Record<number, Point[]> = {
    1: [{ x: 50, y: 15 }],
    2: [{ x: 29, y: 21 }, { x: 71, y: 21 }],
    3: [{ x: 23, y: 27 }, { x: 50, y: 15 }, { x: 77, y: 27 }],
    4: [
      { x: 17, y: 30 }, { x: 38, y: 18 },
      { x: 62, y: 18 }, { x: 83, y: 30 },
    ],
    5: [
      { x: 14, y: 31 }, { x: 31, y: 19 }, { x: 50, y: 14 },
      { x: 69, y: 19 }, { x: 86, y: 31 },
    ],
  };
  return pointSets[count] ?? pointSets[5];
});

function insetLine(from: Point, to: Point, fromInset: number, toInset: number): Line {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  return {
    x1: from.x + dx * fromInset,
    y1: from.y + dy * fromInset,
    x2: to.x - dx * toInset,
    y2: to.y - dy * toInset,
  };
}

const childLines = computed<Line[]>(() => childPoints.value.map(
  (point) => insetLine(currentPoint.value, point, 0.18, 0.18),
));
const parentLine = computed<Line | null>(() => parent.value
  ? insetLine(currentPoint.value, parentPoint.value, 0.22, 0.22)
  : null);

const currentChildLabel = computed(() => {
  if (!children.value.length) return "分类末端";
  return `下辖 ${children.value.length} 个${taxonomyRankLabel(children.value[0].rank)}`;
});

function select(key: TaxonomyNodeKey): void {
  if (key !== current.value.key) emit("select", key);
}

function clearMotion(): void {
  if (motionTimer !== null) window.clearTimeout(motionTimer);
  motionTimer = null;
  isAnimating.value = false;
}

function moveWindow(direction: -1 | 1): boolean {
  if (isAnimating.value) return false;
  const nextStart = Math.min(maxWindowStart.value, Math.max(0, windowStart.value + direction));
  if (nextStart === windowStart.value) return false;

  motionDirection.value = direction;
  isAnimating.value = true;
  windowStart.value = nextStart;
  motionTimer = window.setTimeout(clearMotion, reduceMotion ? 0 : 560);
  return true;
}

function onKeydown(event: KeyboardEvent): void {
  if (!hasOverflow.value || event.repeat || !["ArrowLeft", "ArrowRight"].includes(event.key)) return;
  event.preventDefault();
  moveWindow(event.key === "ArrowRight" ? 1 : -1);
}

function clearWheelGesture(): void {
  if (wheelQuietTimer !== null) window.clearTimeout(wheelQuietTimer);
  wheelQuietTimer = null;
  wheelAccumulator = 0;
  wheelGestureLocked = false;
}

function onWheel(event: WheelEvent): void {
  if (!hasOverflow.value || !stage.value) return;
  const bounds = stage.value.getBoundingClientRect();
  if (event.clientY > bounds.top + bounds.height * 0.48) return;

  const rawDelta = Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY;
  if (!rawDelta) return;
  const scale = event.deltaMode === WheelEvent.DOM_DELTA_LINE
    ? 16
    : event.deltaMode === WheelEvent.DOM_DELTA_PAGE ? bounds.height : 1;
  const delta = rawDelta * scale;
  const direction: -1 | 1 = delta > 0 ? 1 : -1;
  const canMove = direction > 0 ? windowStart.value < maxWindowStart.value : windowStart.value > 0;

  // 到达首尾后把滚轮还给页面，避免光标进入舞台便锁住纵向滚动。
  if (!canMove && !wheelGestureLocked) {
    wheelAccumulator = 0;
    return;
  }
  event.preventDefault();

  if (wheelQuietTimer !== null) window.clearTimeout(wheelQuietTimer);
  wheelQuietTimer = window.setTimeout(clearWheelGesture, 190);
  if (wheelGestureLocked || isAnimating.value) return;

  if (wheelAccumulator && Math.sign(wheelAccumulator) !== Math.sign(delta)) wheelAccumulator = 0;
  wheelAccumulator += delta;
  if (Math.abs(wheelAccumulator) < 32) return;

  wheelGestureLocked = true;
  wheelAccumulator = 0;
  moveWindow(direction);
}

function pointerDown(event: PointerEvent): void {
  pointerStartX = event.clientX;
}

function pointerUp(event: PointerEvent): void {
  const start = pointerStartX;
  pointerStartX = null;
  if (start === null || !hasOverflow.value) return;
  const distance = event.clientX - start;
  if (Math.abs(distance) > 45) moveWindow(distance < 0 ? 1 : -1);
}

function updateCapacity(width: number): void {
  capacity.value = width < 520 ? 2 : width < 900 ? 3 : 5;
  windowStart.value = Math.min(windowStart.value, maxWindowStart.value);
}

watch(() => props.currentKey, () => {
  clearMotion();
  clearWheelGesture();
  windowStart.value = 0;
});
watch(capacity, () => { windowStart.value = Math.min(windowStart.value, maxWindowStart.value); });

onMounted(() => {
  if (!stage.value) return;
  reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  updateCapacity(stage.value.clientWidth);
  resizeObserver = new ResizeObserver(([entry]) => updateCapacity(entry.contentRect.width));
  resizeObserver.observe(stage.value);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  clearMotion();
  clearWheelGesture();
});
</script>

<template>
  <section class="v2-taxonomy-browser" data-taxonomy-browser>
    <div class="v2-taxonomy-toolbar">
    <nav class="v2-taxonomy-breadcrumb" data-taxonomy-breadcrumb aria-label="当前分类路径">
      <template v-for="(node, index) in path" :key="node.key">
        <button type="button" :aria-current="node.key === current.key ? 'page' : undefined" @click="select(node.key)">
          <span>{{ taxonomyRankLabel(node.rank) }}</span>{{ node.chineseName }}
        </button>
        <i v-if="index < path.length - 1" aria-hidden="true">/</i>
      </template>
    </nav>
    <button v-if="current.rank !== 'class'" class="v2-taxonomy-edit-button" type="button" @click="emit('editTaxonomy', current.key)">修改分类</button>
    </div>

    <div class="v2-taxonomy-context">
      <span>{{ currentChildLabel }}</span>
      <span v-if="hasOverflow">{{ visibleRange }}</span>
    </div>

    <section
      ref="stage"
      class="v2-taxonomy-stage"
      data-taxonomy-child-track
      :data-taxonomy-motion="isAnimating ? (motionDirection > 0 ? 'forward' : 'backward') : 'idle'"
      :data-taxonomy-window-start="windowStart"
      :style="{
        '--taxon-focus-x': `${currentPoint.x}%`,
        '--taxon-focus-y': `${currentPoint.y}%`,
      }"
      tabindex="0"
      aria-label="子分类节点；使用左右方向键切换更多节点"
      @keydown="onKeydown"
      @wheel="onWheel"
      @pointerdown="pointerDown"
      @pointerup="pointerUp"
      @pointercancel="pointerStartX = null"
    >
      <svg class="v2-taxonomy-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        <line
          v-for="(line, index) in childLines"
          :key="index"
          data-taxonomy-child-line
          :x1="line.x1"
          :y1="line.y1"
          :x2="line.x2"
          :y2="line.y2"
        />
        <line
          v-if="parentLine"
          data-taxonomy-parent-line
          :x1="parentLine.x1"
          :y1="parentLine.y1"
          :x2="parentLine.x2"
          :y2="parentLine.y2"
        />
      </svg>

      <div v-if="!children.length" class="v2-taxonomy-leaf-note">
        <span>TERMINAL SPECIES</span>
        <strong>已经抵达分类树末端</strong>
        <p>种是本视图的末端节点；亚种仍保留在物种档案与每笔观察中。</p>
      </div>

      <button v-if="hasOverflow" class="v2-taxonomy-page-button is-previous" type="button" :disabled="windowStart === 0" aria-label="上一组子节点" @click="moveWindow(-1)">‹</button>
      <button v-if="hasOverflow" class="v2-taxonomy-page-button is-next" type="button" :disabled="windowStart === maxWindowStart" aria-label="下一组子节点" @click="moveWindow(1)">›</button>

      <TransitionGroup
        tag="div"
        name="v2-taxonomy-arc"
        :css="isAnimating"
        class="v2-taxonomy-child-layer"
        :class="motionDirection > 0 ? 'is-forward' : 'is-backward'"
        data-taxonomy-window
      >
        <div
          v-for="(node, index) in visibleChildren"
          :key="node.key"
          class="v2-taxonomy-node-position is-child"
          :style="{ '--taxon-x': `${childPoints[index].x}%`, '--taxon-y': `${childPoints[index].y}%` }"
        >
          <TaxonomyNodeView :node="node" role="child" @select="select" />
        </div>
      </TransitionGroup>

      <div
        class="v2-taxonomy-node-position is-current"
        :style="{ '--taxon-x': `${currentPoint.x}%`, '--taxon-y': `${currentPoint.y}%` }"
      >
        <TaxonomyNodeView :node="current" role="current" @select="select" />
      </div>

      <div
        v-if="parent"
        class="v2-taxonomy-node-position is-parent"
        :style="{ '--taxon-x': `${parentPoint.x}%`, '--taxon-y': `${parentPoint.y}%` }"
      >
        <TaxonomyNodeView :node="parent" role="parent" @select="select" />
      </div>
      <div v-else class="v2-taxonomy-root-note">
        <span>ROOT OF YOUR ARCHIVE</span>
        <p>这里是由全部个人观察共同生长出的根节点。</p>
      </div>
    </section>

    <footer class="v2-taxonomy-summary">
      <div><span>当前层级</span><strong>{{ taxonomyRankLabel(current.rank) }}</strong><small>{{ current.scientificName }}</small></div>
      <div><span>后代物种</span><strong>{{ current.speciesCount }}</strong><small>SPECIES</small></div>
      <div><span>观察条目</span><strong>{{ current.observationCount }}</strong><small>OBSERVATION ENTRIES</small></div>
    </footer>
      <div v-if="current.rank === 'species' && current.speciesId" class="v2-taxonomy-leaf-actions">
        <button type="button" @click="emit('openSpecies', current.speciesId)">打开物种档案</button>
        <button type="button" @click="emit('viewObservations', current.speciesId)">查看田野记录</button>
      </div>
  </section>
</template>
