<script setup lang="ts">
import { ref } from "vue";
import { api, errorMessage } from "@/api/client";
import type { BackupResult, RestoreResult } from "@/api/types";

const dialog = ref<HTMLDialogElement>();
const backupStatus = ref("准备创建备份。");
const restoreStatus = ref("尚未选择备份。");
const restoreFile = ref<File | null>(null);
const backupBusy = ref(false);
const restoreBusy = ref(false);
const download = ref<BackupResult | null>(null);

function open(): void {
  backupStatus.value = "准备创建备份。备份期间请不要关闭软件。";
  download.value = null;
  dialog.value?.showModal();
}

function close(): void {
  dialog.value?.close();
}

function chooseRestoreFile(event: Event): void {
  const input = event.target as HTMLInputElement;
  restoreFile.value = input.files?.[0] ?? null;
  restoreStatus.value = restoreFile.value ? `已选择：${restoreFile.value.name}` : "尚未选择备份。";
}

async function createBackup(): Promise<void> {
  backupBusy.value = true;
  backupStatus.value = "正在生成一致性数据库快照并归档媒体文件……";
  try {
    const result = await api<BackupResult>("/api/backups", { method: "POST" });
    download.value = result;
    backupStatus.value = `备份完成：${result.filename}（${(result.size_bytes / 1024 / 1024).toFixed(1)} MB）`;
  } catch (error) {
    backupStatus.value = errorMessage(error);
  } finally {
    backupBusy.value = false;
  }
}

async function restoreBackup(): Promise<void> {
  if (!restoreFile.value) {
    restoreStatus.value = "请先选择 ZIP 备份。";
    return;
  }
  if (!window.confirm("恢复会用备份中的数据库和媒体替换当前资料。程序会先自动备份当前状态，确定继续吗？")) return;
  restoreBusy.value = true;
  restoreStatus.value = "正在校验数据库、文件哈希和媒体引用，请不要关闭软件……";
  try {
    const body = new FormData();
    body.append("backup", restoreFile.value);
    const result = await api<RestoreResult>("/api/backups/restore", { method: "POST", body });
    restoreStatus.value = `${result.message} 当前状态的安全备份：${result.safety_backup.filename}`;
    window.setTimeout(() => window.location.reload(), 1200);
  } catch (error) {
    restoreStatus.value = errorMessage(error);
  } finally {
    restoreBusy.value = false;
  }
}

defineExpose({ open, close });
</script>

<template>
  <dialog ref="dialog" class="v2-home-cover-dialog" @click.self="close">
    <header>
      <div><p class="v2-kicker">ARCHIVE SAFETY COPY</p><h2>资料库完整备份</h2></div>
      <button type="button" aria-label="关闭" @click="close">×</button>
    </header>
    <div class="v2-home-cover-toolbar">
      <p>备份包含一致性数据库快照、全部照片、缩略图和录音。文件保存在程序旁的 backups 目录中。</p>
      <p>{{ backupStatus }}</p>
      <hr />
      <p><strong>恢复完整备份</strong></p>
      <p>恢复前会自动保存当前资料库的安全备份。所选备份通过数据库、文件哈希和媒体引用校验后才会替换当前资料。</p>
      <label class="file-field">选择 ZIP 备份<input type="file" accept="application/zip,.zip" @change="chooseRestoreFile" /></label>
      <p>{{ restoreStatus }}</p>
    </div>
    <footer>
      <button class="v2-button v2-button-danger" type="button" :disabled="restoreBusy || backupBusy" @click="restoreBackup">
        {{ restoreBusy ? "正在恢复…" : "校验并恢复备份" }}
      </button>
      <button class="v2-button v2-button-primary" type="button" :disabled="backupBusy || restoreBusy" @click="createBackup">
        {{ backupBusy ? "正在备份…" : "立即创建完整备份" }}
      </button>
      <a
        v-if="download"
        class="v2-button v2-button-ghost"
        :href="download.download_url"
        :download="download.filename"
      >下载备份</a>
    </footer>
  </dialog>
</template>
