<template>
  <div class="import-section">
    <!-- 隐藏的文件选择器 -->
    <input
      ref="fileInput"
      type="file"
      accept=".csv"
      style="display: none"
      @change="onFileSelected"
    />

    <el-button type="primary" :loading="importing" @click="openFileDialog">
      📂 {{ importing ? '导入中...' : '导入本地 CSV 数据集' }}
    </el-button>

    <div v-if="importing" style="margin-top: 8px">
      <el-progress :percentage="progress" :stroke-width="8" :color="progressColor" />
      <p style="font-size: 12px; color: #909399; margin-top: 4px">
        {{ statusMsg }}
      </p>
    </div>

    <el-alert
      v-if="done"
      :title="alertTitle"
      :type="alertType"
      show-icon
      closable
      @close="done = false"
      style="margin-top: 8px"
    />
  </div>
</template>

<script setup>
import { ref, computed } from "vue";
import axios from "axios";

const emit = defineEmits(["import-complete"]);
const fileInput = ref(null);
const importing = ref(false);
const progress = ref(0);
const statusMsg = ref("");
const done = ref(false);
const alertTitle = ref("");
const alertType = ref("success");
const progressColor = computed(() => (progress.value < 100 ? "#409eff" : "#67c23a"));

function openFileDialog() {
  fileInput.value.click();
}

async function onFileSelected(e) {
  const file = e.target.files[0];
  if (!file) return;

  importing.value = true;
  progress.value = 0;
  done.value = false;
  statusMsg.value = `正在读取 ${file.name}（${formatSize(file.size)}）...`;
  progress.value = 10;

  try {
    // 1. 用 FileReader 读取 CSV 内容
    const csvText = await readFileAsText(file);
    progress.value = 30;
    statusMsg.value = "正在解析 CSV 字段...";

    // 2. 发给后端处理
    progress.value = 50;
    statusMsg.value = "正在导入数据库...";

    const res = await axios.post("/api/v1/data/import-csv", {
      csv_content: csvText,
      file_name: file.name,
    });

    if (res.data && res.data.code === 202) {
      const taskId = res.data.data.task_id;
      // 3. 轮询进度
      const poll = setInterval(async () => {
        try {
          const { data: progressData } = await axios.get(
            `/api/v1/data/import-csv/${taskId}/progress`
          );
          const d = progressData.data;
          progress.value = Math.min(d.progress || progress.value + 5, 99);
          statusMsg.value = d.status || "正在处理...";

          if (d.state === "SUCCESS") {
            clearInterval(poll);
            progress.value = 100;
            importing.value = false;
            done.value = true;
            alertTitle.value = `导入完成！${d.result?.imported || d.collected_so_far || 0} 条数据，耗时 ${d.result?.time_seconds || "?"} 秒`;
            alertType.value = "success";
            statusMsg.value = "";
            emit("import-complete");
            // 重置 input 让同一个文件可再次选择
            fileInput.value.value = "";
          } else if (d.state === "FAILURE" || d.state?.includes("失败")) {
            clearInterval(poll);
            importing.value = false;
            done.value = true;
            alertTitle.value = "导入失败: " + (d.error || "未知错误");
            alertType.value = "error";
          }
        } catch {
          clearInterval(poll);
          importing.value = false;
          done.value = true;
          alertTitle.value = "进度查询失败";
          alertType.value = "error";
        }
      }, 1000);
    } else {
      throw new Error("后端返回异常");
    }
  } catch (err) {
    importing.value = false;
    done.value = true;
    alertTitle.value = "导入失败: " + (err.message || "请检查文件格式");
    alertType.value = "error";
  }
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = () => reject(new Error("文件读取失败"));
    reader.readAsText(file, "UTF-8");
  });
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1048576).toFixed(1) + " MB";
}
</script>
