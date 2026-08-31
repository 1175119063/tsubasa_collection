<script setup lang="ts">
import { reactive, ref } from "vue";
import { api, errorMessage } from "@/api/client";
import type { SpeciesDetail } from "@/components/dex/SpeciesDossier.vue";

const props = defineProps<{ detail: SpeciesDetail }>();
const emit = defineEmits<{ close: []; saved: [] }>();
const form = reactive({ title: "", recorded_at: "", locality: "", notes: "" });
const file = ref<File | null>(null); const status = ref(""); const busy = ref(false);
function chooseFile(event: Event): void { file.value = (event.target as HTMLInputElement).files?.[0] || null; }
async function submit(): Promise<void> {
  if (!file.value) { status.value = "请选择 MP3 录音。"; return; }
  busy.value = true; status.value = "正在保存录音…";
  const body = new FormData(); body.append("audio", file.value); body.append("payload", JSON.stringify({ title: form.title || null, recorded_at: form.recorded_at || null, locality: form.locality || null, notes: form.notes || null }));
  try { await api(`/api/species/${props.detail.id}/audio`, { method: "POST", body }); emit("saved"); }
  catch (caught) { status.value = errorMessage(caught); }
  finally { busy.value = false; }
}
</script>

<template>
  <form @submit.prevent="submit"><header class="dialog-header"><div><p class="eyebrow">FIELD RECORDING</p><h2>添加物种录音</h2></div><button type="button" class="icon-button" aria-label="关闭" @click="emit('close')">×</button></header><div class="form-scroll"><fieldset><legend><span>01</span> 录音资料</legend><div class="form-grid"><label class="full-field file-field">MP3 录音<input type="file" accept="audio/mpeg,.mp3" required @change="chooseFile" /></label><label>标题<input v-model="form.title" maxlength="160" placeholder="例如：晨鸣" /></label><label>录制时间<input v-model="form.recorded_at" type="datetime-local" step="60" /></label><label class="full-field">录制地点<input v-model="form.locality" maxlength="240" /></label><label class="full-field">备注<textarea v-model="form.notes" rows="4"></textarea></label></div></fieldset></div><footer class="dialog-footer"><span role="status">{{ status }}</span><button type="submit" class="primary-button" :disabled="busy">{{ busy ? "正在保存…" : "保存录音" }}</button></footer></form>
</template>
