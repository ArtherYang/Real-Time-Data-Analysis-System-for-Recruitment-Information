<template>
  <div class="salary-analysis">
    <h2 style="margin-bottom: 16px; color: #303133">薪资分析</h2>

    <FilterPanel @filter-change="onFilterChange" />

    <SummaryCards />

    <div class="chart-grid single">
      <SalaryDistChart />
    </div>

    <div class="chart-grid">
      <SalaryTrendChart />
      <div class="chart-card">
        <div class="chart-title">薪资分组切换</div>
        <div style="padding: 16px">
          <el-radio-group v-model="groupBy" @change="onGroupByChange">
            <el-radio-button value="job_category">按岗位类型</el-radio-button>
            <el-radio-button value="city">按城市</el-radio-button>
            <el-radio-button value="experience">按经验</el-radio-button>
          </el-radio-group>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";
import FilterPanel from "../components/FilterPanel.vue";
import SummaryCards from "../components/SummaryCards.vue";
import SalaryDistChart from "../components/SalaryDistChart.vue";
import SalaryTrendChart from "../components/SalaryTrendChart.vue";

const store = useAnalysisStore();
const groupBy = ref("job_category");

onMounted(async () => {
  await store.fetchFilterOptions();
  await store.fetchSummary();
  await store.fetchSalaryDist(groupBy.value);
  await store.fetchSalaryTrend();
});

async function onFilterChange() {
  await store.fetchSummary();
  await store.fetchSalaryDist(groupBy.value);
  await store.fetchSalaryTrend();
}

async function onGroupByChange(val) {
  await store.fetchSalaryDist(val);
}
</script>
