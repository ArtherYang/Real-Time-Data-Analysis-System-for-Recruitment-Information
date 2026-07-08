<template>
  <div style="display: flex; gap: 8px">
    <el-button type="primary" size="small" @click="exportCSV">
      📄 导出 CSV
    </el-button>
    <el-button type="success" size="small" @click="exportExcel">
      📊 导出 Excel
    </el-button>
  </div>
</template>

<script setup>
import { useAnalysisStore } from "../stores/analysis";

const store = useAnalysisStore();

function buildExportUrl(format) {
  const params = new URLSearchParams();
  for (const [key, val] of Object.entries(store.filters)) {
    if (val !== "" && val !== null) {
      params.append(key, val);
    }
  }
  return `/api/v1/export/${format}?${params.toString()}`;
}

function exportCSV() {
  window.open(buildExportUrl("csv"), "_blank");
}

function exportExcel() {
  window.open(buildExportUrl("excel"), "_blank");
}
</script>
