<template>
  <div class="filter-panel">
    <el-select
      v-model="store.filters.city"
      placeholder="城市"
      clearable
      @change="onFilterChange"
    >
      <el-option
        v-for="c in store.filterOptions.cities"
        :key="c"
        :label="c"
        :value="c"
      />
    </el-select>

    <el-select
      v-model="store.filters.job_category"
      placeholder="岗位类型"
      clearable
      @change="onFilterChange"
    >
      <el-option
        v-for="c in store.filterOptions.job_categories"
        :key="c"
        :label="c"
        :value="c"
      />
    </el-select>

    <el-select
      v-model="store.filters.platform"
      placeholder="数据来源"
      clearable
      @change="onFilterChange"
    >
      <el-option
        v-for="p in store.filterOptions.platforms"
        :key="p"
        :label="p"
        :value="p"
      />
    </el-select>

    <el-select
      v-model="store.filters.experience"
      placeholder="经验要求"
      clearable
      @change="onFilterChange"
    >
      <el-option
        v-for="e in store.filterOptions.experiences"
        :key="e"
        :label="e"
        :value="e"
      />
    </el-select>

    <el-select
      v-model="store.filters.education"
      placeholder="学历要求"
      clearable
      @change="onFilterChange"
    >
      <el-option
        v-for="e in store.filterOptions.educations"
        :key="e"
        :label="e"
        :value="e"
      />
    </el-select>

    <div class="filter-actions">
      <el-button type="primary" @click="onFilterChange">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
      <el-button @click="onReset">
        <el-icon><Delete /></el-icon>
        重置
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";

const store = useAnalysisStore();
const emit = defineEmits(["filter-change"]);

onMounted(async () => {
  await store.fetchFilterOptions();
});

function onFilterChange() {
  emit("filter-change");
}

function onReset() {
  store.resetFilters();
  emit("filter-change");
}
</script>

<style scoped>
.filter-panel {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
}

.filter-panel :deep(.el-select) {
  width: 150px;
}

.filter-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .filter-panel {
    flex-direction: column;
    align-items: stretch;
  }
  .filter-panel :deep(.el-select) {
    width: 100%;
  }
  .filter-actions {
    margin-left: 0;
  }
}
</style>
