<template>
  <div class="toolbar">
    <!-- CSV 导入 -->
    <input ref="csvInput" type="file" accept=".csv" style="display:none" @change="onCsvSelected" />
    <el-button type="primary" :icon="Upload" :loading="importing" @click="$refs.csvInput.click()">
      📂 {{ importing ? '导入中...' : '导入 CSV 数据' }}
    </el-button>

    <!-- 导入爬虫程序 -->
    <input ref="pyInput" type="file" accept=".py" style="display:none" @change="onPySelected" />
    <el-button type="success" :icon="Upload" :loading="crawling" @click="$refs.pyInput.click()">
      🕷️ {{ crawling ? '执行中...' : '导入爬虫程序 (.py)' }}
    </el-button>

    <!-- 进度 -->
    <span v-if="importing || crawling" class="progress-text">{{ statusMsg }}</span>
    <el-progress v-if="importing || crawling" :percentage="progress" :stroke-width="6" style="width:200px" />

    <!-- 结果提示 -->
    <el-alert v-if="done" :title="alertTitle" :type="alertType" show-icon closable @close="done=false" style="margin-left:12px;flex:1" />
  </div>
</template>

<script setup>
import { ref } from "vue";
import { Upload, Refresh } from "@element-plus/icons-vue";
import api from "../api";

const emit = defineEmits(["data-changed"]);
const csvInput = ref(null);

const importing = ref(false);
const crawling = ref(false);
const progress = ref(0);
const statusMsg = ref("");
const done = ref(false);
const alertTitle = ref("");
const alertType = ref("success");

// ===== CSV 导入 =====
async function onCsvSelected(e) {
  const file = e.target.files[0];
  if (!file) return;

  importing.value = true; progress.value = 5; done.value = false;
  statusMsg.value = `读取 ${file.name}...`;

  try {
    const csvText = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error("读取失败"));
      reader.readAsText(file, "UTF-8");
    });

    progress.value = 20;
    statusMsg.value = "正在解析并导入...";

    const res = await api.post("/data/import-csv", { csv_content: csvText, file_name: file.name });
    const taskId = res.task_id;

    // 轮询进度
    const poll = setInterval(async () => {
      try {
        const data = await api.get(`/data/import-csv/${taskId}/progress`);
        progress.value = Math.min(data.progress || progress.value + 5, 99);
        statusMsg.value = data.status || "";

        if (data.state === "SUCCESS") {
          clearInterval(poll);
          progress.value = 100; importing.value = false; done.value = true;
          const n = data.result?.imported || data.collected_so_far || 0;
          alertTitle.value = `✅ CSV 导入完成：新增 ${n} 条（已自动去重）`;
          alertType.value = "success";
          emit("data-changed");
          csvInput.value.value = "";
        } else if (data.state?.includes("失败")) {
          clearInterval(poll);
          importing.value = false; done.value = true;
          alertTitle.value = "导入失败";
          alertType.value = "error";
        }
      } catch { clearInterval(poll); importing.value = false; }
    }, 800);
  } catch (e) {
    importing.value = false; done.value = true;
    alertTitle.value = "导入失败: " + e.message;
    alertType.value = "error";
  }
}

// ===== 导入爬虫程序 =====
async function onPySelected(e) {
  const file = e.target.files[0];
  if (!file) return;

  crawling.value = true; progress.value = 5; done.value = false;
  statusMsg.value = `读取 ${file.name}...`;

  try {
    const pyCode = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target.result);
      reader.onerror = () => reject(new Error("读取失败"));
      reader.readAsText(file, "UTF-8");
    });

    progress.value = 20;
    statusMsg.value = "正在执行爬虫脚本...";

    const res = await api.post("/data/run-crawler", { script: pyCode, file_name: file.name });
    const taskId = res.task_id;

    const poll = setInterval(async () => {
      try {
        const data = await api.get(`/data/run-crawler/${taskId}/progress`);
        progress.value = Math.min(data.progress || progress.value + 5, 99);
        statusMsg.value = data.status || "";

        if (data.state === "SUCCESS") {
          clearInterval(poll);
          progress.value = 100; crawling.value = false; done.value = true;
          const n = data.result?.saved || data.collected_so_far || 0;
          alertTitle.value = `✅ 爬虫执行完成：新增 ${n} 条数据`;
          alertType.value = "success";
          emit("data-changed");
          pyInput.value.value = "";
        } else if (data.state?.includes("失败")) {
          clearInterval(poll);
          crawling.value = false; done.value = true;
          alertTitle.value = "执行失败: " + (data.error || "");
          alertType.value = "error";
        }
      } catch { clearInterval(poll); crawling.value = false; }
    }, 800);
  } catch (e) {
    crawling.value = false; done.value = true;
    alertTitle.value = "失败: " + e.message;
    alertType.value = "error";
  }
}
</script>

<style scoped>
.toolbar { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:12px; }
.progress-text { font-size:12px; color:#909399; white-space:nowrap; }
</style>
