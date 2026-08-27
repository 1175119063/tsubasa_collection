<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";

type PageName = "home" | "observations" | "dex" | "locations" | "trips" | "map";
type Role = "assistant" | "user";

interface Message {
  id: number;
  role: Role;
  text: string;
  pending?: boolean;
  failed?: boolean;
}

interface AssistantStatus {
  available: boolean;
  message: string;
}

interface ChatResult {
  answer: string;
  suggestions: string[];
}

interface SearchResult {
  answer: string;
  interpretation: string;
  warnings: string[];
  [key: string]: unknown;
}

const props = defineProps<{ page: PageName }>();

const pageNames: Record<PageName, string> = {
  home: "探索营地",
  observations: "田野记录",
  dex: "鸟类调查册",
  locations: "区域档案",
  map: "探索地图",
  trips: "远征日志",
};

const examples: Record<PageName, string[]> = {
  home: ["首页可以做什么？", "如何选择首页封面？", "怎样备份全部资料？"],
  observations: ["如何记录一张照片中的多个物种？", "删除一笔观察会发生什么？", "怎样修改物种信息？"],
  dex: ["鸟类调查册收录哪些物种？", "怎样修改图鉴资料？", "如何设置物种封面？"],
  locations: ["如何通过地图新增地点？", "区域档案会展示哪些记录？", "地点如何关联远征？"],
  map: ["探索地图会显示什么？", "地图为什么需要联网？", "怎样建立区域档案？"],
  trips: ["如何建立包含多个地点的远征？", "怎样更换远征封面？", "删除远征会删除观察吗？"],
};

const panelOpen = ref(false);
const available = ref(false);
const status = ref("正在确认本地模型状态…");
const mode = ref<"chat" | "search">("chat");
const input = ref("");
const messages = ref<Message[]>([]);
const suggestions = ref<string[]>([]);
const history = ref<Array<{ role: Role; content: string }>>([]);
const chatLog = ref<HTMLElement>();
let messageId = 0;
let previousGreeting = -1;

const modeNote = computed(() => mode.value === "search"
  ? "描述日期、多个物种、目科属种、地点、远征或同框关系，我会查询并展示实际命中的记录。"
  : `可以自由聊天；涉及本项目功能时会参考${pageNames[props.page]}的说明。`);

const quickReplies = computed(() => suggestions.value.length
  ? suggestions.value.slice(0, 4)
  : mode.value === "search"
    ? ["查询最近的多物种照片", "查看2024年4月5日的全部记录", "查询鸦科的所有记录"]
    : examples[props.page]);

function nextGreeting(): string {
  const greetings = [
    "探险家，你终于来了！今天想从哪一页飞羽见闻开始？",
    "飞羽精灵已醒来。探险家，要检索记录，还是一起翻阅调查手册？",
    "我听见档案页在轻轻振翅——探险家，今天有什么新发现？",
    "欢迎回到营地，探险家！把要整理的线索交给我吧。",
    `探险家，${pageNames[props.page]}的书页已经展开。需要我做些什么？`,
  ];
  let index = Math.floor(Math.random() * greetings.length);
  if (greetings.length > 1 && index === previousGreeting) index = (index + 1) % greetings.length;
  previousGreeting = index;
  return greetings[index];
}

async function scrollChat(): Promise<void> {
  await nextTick();
  if (chatLog.value) chatLog.value.scrollTop = chatLog.value.scrollHeight;
}

function addMessage(role: Role, text: string, pending = false): Message {
  const message = { id: ++messageId, role, text, pending };
  messages.value.push(message);
  void scrollChat();
  return message;
}

function setPanel(open: boolean): void {
  panelOpen.value = open;
  document.body.classList.toggle("feather-panel-open", open);
  if (open) addMessage("assistant", nextGreeting());
}

async function loadStatus(): Promise<void> {
  try {
    const result = await api<AssistantStatus>("/api/assistant/status");
    available.value = result.available;
    status.value = result.message;
  } catch (error) {
    available.value = false;
    status.value = errorMessage(error);
  }
}

function switchMode(nextMode: "chat" | "search"): void {
  mode.value = nextMode;
  suggestions.value = [];
}

async function send(rawText = input.value): Promise<void> {
  const text = rawText.trim();
  if (!available.value || !text) return;
  addMessage("user", text);
  input.value = "";
  const pending = addMessage("assistant", mode.value === "search" ? "正在追踪这些田野线索…" : "正在翻阅随身手册…", true);
  try {
    if (mode.value === "search") {
      const result = await api<SearchResult>("/api/assistant/search-parse", jsonRequest("POST", { query: text }));
      document.dispatchEvent(new CustomEvent("feather:apply-observation-search", { detail: result }));
      const warnings = result.warnings.length ? `\n${result.warnings.join("\n")}` : "";
      pending.text = `${result.answer}\n${result.interpretation}${warnings}`;
    } else {
      history.value.push({ role: "user", content: text });
      history.value = history.value.slice(-12);
      const result = await api<ChatResult>("/api/assistant/chat", jsonRequest("POST", {
        page: props.page,
        messages: history.value,
      }));
      history.value.push({ role: "assistant", content: result.answer });
      history.value = history.value.slice(-12);
      pending.text = result.answer;
      suggestions.value = result.suggestions ?? [];
    }
  } catch (error) {
    pending.text = `这条线索暂时没有回应：${errorMessage(error)}`;
    pending.failed = true;
    if (mode.value === "chat" && history.value.at(-1)?.role === "user") history.value.pop();
  } finally {
    pending.pending = false;
    void scrollChat();
  }
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void send();
  }
}

watch(() => props.page, () => {
  mode.value = "chat";
  suggestions.value = [];
});

onMounted(() => {
  void loadStatus();
  document.addEventListener("feather:reload-status", loadStatus);
});

onBeforeUnmount(() => {
  document.body.classList.remove("feather-panel-open");
  document.removeEventListener("feather:reload-status", loadStatus);
});
</script>

<template>
  <button
    class="feather-launch"
    :class="{ 'is-offline': !available }"
    type="button"
    aria-controls="feather-panel"
    :aria-expanded="panelOpen"
    @click="setPanel(!panelOpen)"
  >
    <img :src="'/static/assets/feather-spirit-avatar.png?v=20260825-1'" alt="" />
    <span>飞羽精灵</span>
  </button>
  <aside v-show="panelOpen" id="feather-panel" class="feather-panel">
    <header class="feather-panel-header">
      <div class="feather-identity">
        <span class="feather-avatar"><img :src="'/static/assets/feather-spirit-avatar.png?v=20260825-1'" alt="飞羽精灵头像" /></span>
        <div><p>ARCANE FIELD COMPANION</p><h2>飞羽精灵</h2><small>探险家的飞羽向导</small></div>
      </div>
      <button class="feather-panel-close" type="button" aria-label="关闭" @click="setPanel(false)">×</button>
    </header>
    <div class="feather-status" :class="{ 'is-online': available }">{{ status }}</div>
    <nav class="feather-chat-modes" aria-label="飞羽精灵对话模式">
      <button :class="{ 'is-active': mode === 'chat' }" type="button" @click="switchMode('chat')">精灵对话</button>
      <button v-if="page === 'observations'" :class="{ 'is-active': mode === 'search' }" type="button" @click="switchMode('search')">检索田野记录</button>
    </nav>
    <section class="feather-chat-stage">
      <div ref="chatLog" class="feather-chat-log" aria-live="polite">
        <article
          v-for="message in messages"
          :key="message.id"
          class="feather-message"
          :class="[`is-${message.role}`, { 'is-pending': message.pending, 'is-error': message.failed }]"
        >
          <img v-if="message.role === 'assistant'" :src="'/static/assets/feather-spirit-avatar.png?v=20260825-1'" alt="" />
          <div><small>{{ message.role === "assistant" ? "飞羽精灵" : "探险家" }}</small><p>{{ message.text }}</p></div>
        </article>
      </div>
      <p class="feather-mode-note">{{ modeNote }}</p>
      <div class="feather-quick-replies">
        <button v-for="item in quickReplies" :key="item" type="button" @click="send(item)">{{ item }}</button>
      </div>
    </section>
    <form class="feather-composer" @submit.prevent="send()">
      <textarea
        v-model="input"
        maxlength="500"
        rows="2"
        :placeholder="mode === 'search' ? '例如：查询2024年4月5日拍到的白头鹎和灰喜鹊' : '给飞羽精灵发送消息…'"
        @keydown="handleKeydown"
      ></textarea>
      <button class="feather-action" type="submit" :disabled="!available || !input.trim()" aria-label="发送消息">发送</button>
    </form>
  </aside>
</template>
