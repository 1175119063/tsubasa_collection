<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import { api, errorMessage, jsonRequest } from "@/api/client";
import type {
  CollectionPlanDetail,
  CollectionTemplateKind,
} from "@/api/types";

const props = defineProps<{
  plan: CollectionPlanDetail | null;
}>();
const emit = defineEmits<{
  close: [];
  saved: [plan: CollectionPlanDetail];
}>();

const form = reactive({
  name: "",
  introduction: "",
  templateKind: "none" as CollectionTemplateKind,
  customLabels: [""],
});
const status = ref("");
const saving = ref(false);

watch(() => props.plan, (plan) => {
  form.name = plan?.name ?? "";
  form.introduction = plan?.introduction ?? "";
  form.templateKind = plan?.template_kind ?? "none";
  form.customLabels = plan?.template_kind === "custom" ? [...plan.subitems] : [""];
  status.value = "";
}, { immediate: true });

function addLabel(): void {
  if (form.customLabels.length < 8) form.customLabels.push("");
}
function removeLabel(index: number): void {
  form.customLabels.splice(index, 1);
  if (!form.customLabels.length) form.customLabels.push("");
}
async function save(): Promise<void> {
  saving.value = true;
  status.value = "正在装订收集计划…";
  const payload = {
    name: form.name,
    introduction: form.introduction || null,
    template_kind: form.templateKind,
    subitems: form.templateKind === "custom" ? form.customLabels : [],
  };
  try {
    const url = props.plan ? `/api/collections/${props.plan.id}` : "/api/collections";
    const method = props.plan ? "PUT" : "POST";
    const saved = await api<CollectionPlanDetail>(url, jsonRequest(method, payload));
    emit("saved", saved);
  } catch (caught) {
    status.value = errorMessage(caught);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <form class="collection-form" @submit.prevent="save">
    <header class="dialog-header">
      <div><p class="eyebrow">COLLECTION PLAN</p><h2>{{ plan ? "修改收集计划" : "创建收集计划" }}</h2></div>
      <button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">×</button>
    </header>
    <div class="form-scroll collection-form-scroll">
      <section class="form-section">
        <label>计划名称<input v-model="form.name" required maxlength="180" placeholder="例如：鸲类收集" /></label>
        <label>观察记录简介<textarea v-model="form.introduction" rows="5" maxlength="10000" placeholder="写下这些鸟种的来历、渊源或你的收集目标。"></textarea></label>
      </section>
      <section class="form-section">
        <div class="section-heading"><div><p class="eyebrow">UNIFORM TEMPLATE</p><h3>全计划统一子项</h3></div></div>
        <p class="section-note">这里选择的结构会应用到计划内每一个物种，不能为单个物种另设模板。</p>
        <div class="collection-template-grid">
          <label><input v-model="form.templateKind" type="radio" value="none" /><span><b>无子项</b><small>每种鸟只有一个槽位</small></span></label>
          <label><input v-model="form.templateKind" type="radio" value="plumage" /><span><b>繁殖羽</b><small>br. / non br.</small></span></label>
          <label><input v-model="form.templateKind" type="radio" value="sex_age" /><span><b>性别与年龄</b><small>♂ / ♀ / juv.</small></span></label>
          <label><input v-model="form.templateKind" type="radio" value="custom" /><span><b>自定义</b><small>最多八个固定子项</small></span></label>
        </div>
        <div v-if="form.templateKind === 'custom'" class="collection-label-editor">
          <div v-for="(_, index) in form.customLabels" :key="index">
            <input v-model="form.customLabels[index]" required maxlength="80" :placeholder="`子项 ${index + 1}`" />
            <button type="button" @click="removeLabel(index)">移除</button>
          </div>
          <button type="button" :disabled="form.customLabels.length >= 8" @click="addLabel">＋ 增加子项</button>
        </div>
      </section>
    </div>
    <footer class="dialog-footer"><span>{{ status }}</span><button class="primary-button" type="submit" :disabled="saving">{{ saving ? "保存中…" : "保存计划" }}</button></footer>
  </form>
</template>
