<template>
  <div class="skill-analysis">
    <h2 style="margin-bottom: 16px; color: #303133">技能需求分析</h2>

    <FilterPanel @filter-change="onFilterChange" />

    <div class="chart-grid">
      <SkillWordCloud />
      <HotJobsChart />
    </div>

    <!-- 技能排行表 -->
    <div class="chart-card" style="margin-bottom: 20px">
      <div class="chart-title">技能需求排行 TOP 30</div>
      <el-table :data="store.skillRanking" stripe max-height="500" size="small">
        <el-table-column type="index" label="#" width="60" />
        <el-table-column prop="name" label="技能名称" />
        <el-table-column prop="count" label="出现次数" width="120" sortable />
        <el-table-column label="热度" width="180">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.count / maxCount) * 100)"
              :stroke-width="12"
              :color="progressColor"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";
import FilterPanel from "../components/FilterPanel.vue";
import SkillWordCloud from "../components/SkillWordCloud.vue";
import HotJobsChart from "../components/HotJobsChart.vue";

const store = useAnalysisStore();

const maxCount = computed(() =>
  store.skillRanking.length > 0 ? store.skillRanking[0].count : 1
);

const progressColor = [
  { color: "#67C23A", percentage: 30 },
  { color: "#409EFF", percentage: 60 },
  { color: "#E6A23C", percentage: 80 },
  { color: "#F56C6C", percentage: 100 },
];

onMounted(async () => {
  await store.fetchFilterOptions();
  await store.fetchSkillRanking(30);
  await store.fetchHotJobs();
});

async function onFilterChange() {
  await Promise.all([store.fetchSkillRanking(30), store.fetchHotJobs()]);
}
</script>
