<script setup lang="ts">
import { computed, ref } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type { IntegrationSummary } from "@/api/types";

const props = defineProps<{ config: IntegrationSummary | null }>();
const emit = defineEmits<{ updated: [config: IntegrationSummary] }>();

const dialog = ref<HTMLDialogElement>();
const provider = ref<"local" | "openai_compatible">("local");
const amapKey = ref("");
const clearAmap = ref(false);
const baseUrl = ref("");
const model = ref("");
const llmKey = ref("");
const clearLlm = ref(false);
const amapStatus = ref("");
const llmStatus = ref("");
const amapBusy = ref(false);
const llmBusy = ref(false);

const external = computed(() => provider.value === "openai_compatible");

function fill(config: IntegrationSummary): void {
  provider.value = config.llm.provider;
  baseUrl.value = config.llm.base_url ?? "";
  model.value = config.llm.model ?? "";
  amapKey.value = "";
  llmKey.value = "";
  clearAmap.value = false;
  clearLlm.value = false;
}

async function open(): Promise<void> {
  dialog.value?.showModal();
  amapStatus.value = "正在读取配置…";
  llmStatus.value = "";
  try {
    const config = await api<IntegrationSummary>("/api/integrations");
    emit("updated", config);
    fill(config);
    amapStatus.value = "密钥不会在页面中回显。";
  } catch (error) {
    amapStatus.value = errorMessage(error);
  }
}

function close(): void {
  dialog.value?.close();
}

async function saveAmap(): Promise<void> {
  amapBusy.value = true;
  amapStatus.value = "正在保存…";
  try {
    const config = await api<IntegrationSummary>("/api/integrations/amap", jsonRequest("PUT", {
      api_key: amapKey.value || null,
      clear_api_key: clearAmap.value,
    }));
    emit("updated", config);
    fill(config);
    amapStatus.value = "地图配置已加密保存。";
  } catch (error) {
    amapStatus.value = errorMessage(error);
  } finally {
    amapBusy.value = false;
  }
}

async function saveLlm(): Promise<void> {
  llmBusy.value = true;
  llmStatus.value = "正在保存…";
  try {
    const config = await api<IntegrationSummary>("/api/integrations/llm", jsonRequest("PUT", {
      provider: provider.value,
      base_url: baseUrl.value || null,
      model: model.value || null,
      api_key: llmKey.value || null,
      clear_api_key: clearLlm.value,
    }));
    emit("updated", config);
    fill(config);
    document.dispatchEvent(new CustomEvent("feather:reload-status"));
    llmStatus.value = "飞羽精灵的对话模型配置已保存。";
  } catch (error) {
    llmStatus.value = errorMessage(error);
  } finally {
    llmBusy.value = false;
  }
}

async function testService(kind: "amap" | "llm"): Promise<void> {
  const status = kind === "amap" ? amapStatus : llmStatus;
  status.value = "正在测试…";
  try {
    const result = await api<{ message: string }>(`/api/integrations/${kind}/test`, { method: "POST" });
    status.value = result.message;
  } catch (error) {
    status.value = errorMessage(error);
  }
}

defineExpose({ open, close });
</script>

<template>
  <dialog ref="dialog" class="v2-home-cover-dialog v2-api-dialog" @click.self="close">
    <header>
      <div><p class="v2-kicker">ARCANE CONNECTIONS</p><h2>API 与模型配置册</h2></div>
      <button type="button" aria-label="关闭" @click="close">×</button>
    </header>
    <div class="v2-api-dialog-body">
      <p class="v2-api-security-note"><strong>本机安全说明</strong>API Key 使用跨平台本地配置文件保存，页面只显示末四位。配置文件包含明文密钥，请依赖本机账户与目录权限保护，并且不要公开分享。启用外部模型时，精灵对话内容及回答该问题所需的最小馆藏摘要会发送到你配置的服务商。</p>

      <section class="v2-api-config-card">
        <div class="v2-api-config-title">
          <span>01 · MAP SERVICE</span><h3>高德地图</h3>
          <small>{{ config?.amap.configured ? `当前密钥：${config.amap.key_hint}（${config.amap.source === "environment" ? "环境配置" : "配置册"}）` : "当前未配置 Key" }}</small>
        </div>
        <div class="v2-api-fields">
          <label class="v2-api-wide"><span>Web 服务 API Key</span><input v-model="amapKey" type="password" maxlength="200" autocomplete="new-password" spellcheck="false" placeholder="留空则保留当前密钥" /></label>
          <label class="v2-api-check"><input v-model="clearAmap" type="checkbox" /><span>清除已保存的 Key</span></label>
        </div>
        <div class="v2-api-actions">
          <button class="v2-button v2-button-primary" type="button" :disabled="amapBusy" @click="saveAmap">{{ amapBusy ? "正在保存…" : "保存地图配置" }}</button>
          <button class="v2-button v2-api-secondary" type="button" @click="testService('amap')">测试连接</button>
          <p role="status">{{ amapStatus }}</p>
        </div>
      </section>

      <section class="v2-api-config-card">
        <div class="v2-api-config-title">
          <span>02 · FEATHER CHAT MODEL</span><h3>飞羽精灵对话模型</h3>
          <small v-if="config?.llm.provider === 'openai_compatible'">当前模型：{{ config.llm.model || "未填写" }} · Key：{{ config.llm.api_key_hint || "未配置" }}</small>
          <small v-else>当前使用 {{ config?.local_model.model }}（{{ config?.local_model.base_url }}）</small>
        </div>
        <div class="v2-api-fields">
          <label><span>模型提供方</span><select v-model="provider"><option value="local">本地 Ollama</option><option value="openai_compatible">外部 OpenAI 兼容服务</option></select></label>
          <label><span>模型名称</span><input v-model="model" type="text" maxlength="200" spellcheck="false" placeholder="例如 qwen-plus" :disabled="!external" /></label>
          <label class="v2-api-wide"><span>Base URL</span><input v-model="baseUrl" type="url" maxlength="500" spellcheck="false" placeholder="例如 https://api.example.com/v1" :disabled="!external" /></label>
          <label class="v2-api-wide"><span>API Key</span><input v-model="llmKey" type="password" maxlength="1000" autocomplete="new-password" spellcheck="false" placeholder="留空则保留当前密钥" :disabled="!external" /></label>
          <label class="v2-api-check"><input v-model="clearLlm" type="checkbox" :disabled="!external" /><span>清除已保存的 Key</span></label>
        </div>
        <p class="v2-api-routing-note">外部模型用于开放式“精灵对话”和田野查询；物种字段提取和页面说明仍由本地模型处理。</p>
        <div class="v2-api-actions">
          <button class="v2-button v2-button-primary" type="button" :disabled="llmBusy" @click="saveLlm">{{ llmBusy ? "正在保存…" : "保存模型配置" }}</button>
          <button class="v2-button v2-api-secondary" type="button" :disabled="!external" @click="testService('llm')">测试外部连接</button>
          <p role="status">{{ llmStatus }}</p>
        </div>
      </section>

      <section class="v2-api-future"><span>FUTURE SLOTS</span><p>以后接入的天气、物种名录或其他服务，也会统一收纳在这本配置册中。</p></section>
    </div>
  </dialog>
</template>
