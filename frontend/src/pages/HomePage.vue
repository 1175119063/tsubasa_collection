<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type {
  HomepageFeature,
  IntegrationSummary,
  ObservationSummary,
  SpeciesSummary,
  Stats,
  UpdateDownload,
  UpdateStatus,
} from "@/api/types";
import DiscoveryCard from "@/components/DiscoveryCard.vue";
import ApiManagerDialog from "@/components/home/ApiManagerDialog.vue";
import BackupDialog from "@/components/home/BackupDialog.vue";
import HomeCoverDialog from "@/components/home/HomeCoverDialog.vue";

const router = useRouter();
const stats = ref<Stats | null>(null);
const species = ref<SpeciesSummary[]>([]);
const feature = ref<HomepageFeature | null>(null);
const observations = ref<ObservationSummary[]>([]);
const integrations = ref<IntegrationSummary | null>(null);
const integrationError = ref("");
const loadError = ref("");
const coverLoading = ref(false);
const coverStatus = ref("");
const updateBusy = ref(false);

const homeCoverDialog = ref<InstanceType<typeof HomeCoverDialog>>();
const backupDialog = ref<InstanceType<typeof BackupDialog>>();
const apiManagerDialog = ref<InstanceType<typeof ApiManagerDialog>>();

const latestSpecies = computed(() => [...species.value].sort((a, b) => b.id - a.id).slice(0, 4));
const featuredObservation = computed(() => feature.value?.observation ?? null);
const featuredId = computed(() => feature.value?.selection_mode === "manual" ? featuredObservation.value?.id ?? null : null);
const featuredLabel = computed(() => feature.value?.selection_mode === "manual" ? "指定馆藏" : "最新记录");

async function loadHome(): Promise<void> {
  loadError.value = "";
  try {
    const [statsResult, speciesResult, featureResult] = await Promise.all([
      api<Stats>("/api/stats"),
      api<SpeciesSummary[]>("/api/species"),
      api<HomepageFeature>("/api/home/cover"),
    ]);
    stats.value = statsResult;
    species.value = speciesResult;
    feature.value = featureResult;
  } catch (error) {
    loadError.value = errorMessage(error);
  }
}

async function loadIntegrations(): Promise<void> {
  integrationError.value = "";
  try {
    integrations.value = await api<IntegrationSummary>("/api/integrations");
  } catch (error) {
    integrationError.value = errorMessage(error);
  }
}

async function loadCoverChoices(): Promise<void> {
  coverLoading.value = true;
  coverStatus.value = "";
  try {
    observations.value = await api<ObservationSummary[]>("/api/observations");
  } catch (error) {
    coverStatus.value = errorMessage(error);
  } finally {
    coverLoading.value = false;
  }
}

async function selectHomepageFeature(observationId: number | null): Promise<void> {
  coverLoading.value = true;
  coverStatus.value = "正在保存首页封面……";
  try {
    feature.value = await api<HomepageFeature>("/api/home/cover", jsonRequest("PUT", {
      observation_id: observationId,
    }));
    homeCoverDialog.value?.close();
  } catch (error) {
    coverStatus.value = errorMessage(error);
  } finally {
    coverLoading.value = false;
  }
}

async function checkUpdate(): Promise<void> {
  updateBusy.value = true;
  try {
    const status = await api<UpdateStatus>("/api/updates/status");
    if (!status.update_available) {
      window.alert(status.message);
      return;
    }
    if (!window.confirm(`${status.message}\n${status.notes || ""}\n\n现在下载经过 SHA-256 校验的安装包吗？`)) return;
    const result = await api<UpdateDownload>("/api/updates/download", { method: "POST" });
    const link = document.createElement("a");
    link.href = result.download_url;
    link.download = result.filename;
    link.click();
    window.alert(`${result.message}\n安装包：${result.filename}`);
  } catch (error) {
    window.alert(errorMessage(error));
  } finally {
    updateBusy.value = false;
  }
}

onMounted(() => {
  void loadHome();
  void loadIntegrations();
});
</script>

<template>
  <main class="v2-home">
    <section class="v2-camp-hero">
      <div
        class="v2-hero-photo"
        aria-hidden="true"
        :style="featuredObservation ? { backgroundImage: `url(&quot;${featuredObservation.photo_url}&quot;)` } : undefined"
      ></div>
      <div class="v2-hero-shade"></div>
      <div class="v2-hero-copy">
        <p class="v2-kicker">PERSONAL EXPEDITION ARCHIVE · 个人探索档案</p>
        <h1>记录只属于你的探索<br /><em>收集每一支散落的飞羽</em></h1>
        <p>每次相遇都是一页新情报。把照片、足迹与时间装订成一本持续生长的自然调查手册。</p>
        <div class="v2-hero-actions">
          <RouterLink class="v2-button v2-button-primary" to="/dex">打开鸟类调查册</RouterLink>
          <RouterLink class="v2-button v2-button-ghost" to="/observations?new=1">登记新发现</RouterLink>
          <button class="v2-button v2-button-ghost" type="button" @click="homeCoverDialog?.open()">选择首页封面</button>
          <button class="v2-button v2-button-ghost" type="button" @click="backupDialog?.open()">完整备份资料库</button>
          <button class="v2-button v2-button-ghost" type="button" :disabled="updateBusy" @click="checkUpdate">
            {{ updateBusy ? "正在检查…" : "检查软件更新" }}
          </button>
        </div>
      </div>
      <aside class="v2-featured-tag">
        <template v-if="featuredObservation">
          <span>{{ featuredLabel }} · {{ featuredObservation.catalog_number }} · OBSERVATION {{ featuredObservation.id }}</span>
          <strong>{{ featuredObservation.species_name }}</strong>
          <i>{{ featuredObservation.species_scientific_name }}</i>
        </template>
        <template v-else>
          <span>调查册尚未启用</span><strong>登记第一笔观察</strong><i>从一张照片开始你的探索</i>
        </template>
      </aside>
    </section>

    <section class="v2-camp-board" aria-label="探索概览">
      <div class="v2-board-heading">
        <div><p class="v2-kicker">CAMP NOTICE BOARD</p><h2>探索者营地</h2></div>
        <p>从这里继续未完的调查，或翻阅已经装订成册的足迹。</p>
      </div>
      <div class="v2-stat-strip">
        <article><span>已确认物种</span><strong>{{ stats?.species_count ?? "—" }}</strong><small>SPECIES</small></article>
        <article><span>田野记录</span><strong>{{ stats?.observation_count ?? "—" }}</strong><small>RECORDS</small></article>
        <article><span>照片凭证</span><strong>{{ stats?.photo_count ?? "—" }}</strong><small>PHOTOS</small></article>
        <article><span>声音标本</span><strong>{{ stats?.audio_count ?? "—" }}</strong><small>AUDIO</small></article>
      </div>
      <div class="v2-board-grid">
        <RouterLink class="v2-quest-card v2-quest-primary" to="/dex">
          <span class="v2-card-rune">Ⅰ</span><p>FIELD GUIDE</p><h3>鸟类调查册</h3>
          <small>翻阅已确认物种、生态画像与照片凭证</small><b>进入调查册 →</b>
        </RouterLink>
        <RouterLink class="v2-quest-card" to="/observations">
          <span class="v2-card-rune">Ⅱ</span><p>FIELD NOTES</p><h3>田野记录</h3>
          <small>按时间回看每一次相遇与拍摄详情</small><b>翻阅记录 →</b>
        </RouterLink>
        <RouterLink class="v2-quest-card" to="/locations">
          <span class="v2-card-rune">Ⅲ</span><p>REGION MAP</p><h3>区域档案</h3>
          <small>整理反复到访的湿地、森林与城市角落</small><b>查看区域 →</b>
        </RouterLink>
        <RouterLink class="v2-quest-card" to="/trips">
          <span class="v2-card-rune">Ⅳ</span><p>EXPEDITION LOG</p><h3>远征日志</h3>
          <small>把同一次外出中的发现编入一段旅程</small><b>查看远征 →</b>
        </RouterLink>
        <RouterLink class="v2-quest-card" to="/collections">
          <span class="v2-card-rune">Ⅴ</span><p>COLLECTION PLAN</p><h3>收集计划</h3>
          <small>把相似鸟种与不同形态编成自己的专题收藏</small><b>查看收藏 →</b>
        </RouterLink>
      </div>
    </section>

    <section class="v2-latest-section">
      <div class="v2-section-title"><div><p class="v2-kicker">LATEST DISCOVERIES</p><h2>最近装订的图鉴页</h2></div><RouterLink to="/dex">查看全部</RouterLink></div>
      <div class="v2-discovery-row">
        <DiscoveryCard
          v-for="item in latestSpecies"
          :key="item.id"
          :species="item"
          compact
          @click="router.push({ path: '/dex', query: { species: item.id } })"
        />
        <p v-if="loadError" class="v2-loading">{{ loadError }}</p>
        <p v-else-if="stats && !latestSpecies.length" class="v2-loading">尚无已确认物种。</p>
        <p v-else-if="!stats" class="v2-loading">正在整理调查手记…</p>
      </div>
    </section>

    <section class="v2-api-section" aria-labelledby="vue-api-section-title">
      <div class="v2-api-heading">
        <div><p class="v2-kicker">ARCANE CONNECTIONS</p><h2 id="vue-api-section-title">API 管理</h2></div>
        <p>集中保管地图与飞羽精灵使用的外部服务。密钥不会显示在页面中，也不会写入备份。</p>
      </div>
      <div class="v2-api-overview">
        <article><span>地图服务</span><strong>高德地图</strong><small>{{ integrationError || (integrations?.amap.configured ? `已配置 · ${integrations.amap.key_hint || "密钥已隐藏"}` : "尚未配置") }}</small></article>
        <article><span>精灵对话</span><strong>{{ integrations?.llm.provider === "openai_compatible" ? "外部大模型" : "本地 Ollama" }}</strong><small>{{ integrationError || (integrations?.llm.provider === "openai_compatible" ? `${integrations.llm.model || "模型未填写"}${integrations.llm.api_key_hint ? ` · ${integrations.llm.api_key_hint}` : " · Key 未配置"}` : `${integrations?.local_model.model || "正在检查"} · 对话留在本机`) }}</small></article>
        <button class="v2-api-manage" type="button" @click="apiManagerDialog?.open()"><span>配置册</span><strong>管理 API 与模型</strong><small>打开安全配置界面 →</small></button>
      </div>
    </section>
  </main>

  <HomeCoverDialog
    ref="homeCoverDialog"
    :observations="observations"
    :featured-id="featuredId"
    :loading="coverLoading"
    :status="coverStatus"
    @open="loadCoverChoices"
    @select="selectHomepageFeature"
  />
  <BackupDialog ref="backupDialog" />
  <ApiManagerDialog ref="apiManagerDialog" :config="integrations" @updated="integrations = $event" />
</template>
