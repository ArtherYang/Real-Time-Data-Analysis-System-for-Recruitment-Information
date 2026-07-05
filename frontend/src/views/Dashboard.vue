<template>
  <div class="dashboard">
    <!-- 筛选栏 -->
    <FilterPanel @filter-change="onFilterChange" />

    <!-- 三列网格 -->
    <div class="dash-grid">
      <!-- 左列 -->
      <aside class="dash-col dash-left">
        <SummaryCards />
        <div class="chart-card left-trend">
          <div class="card-title">📈 薪资趋势</div>
          <div class="card-body"><SalaryTrendChart /></div>
        </div>
      </aside>

      <!-- 中列 -->
      <main class="dash-col dash-center">
        <div class="chart-card">
          <div class="card-title">🔥 岗位热度 TOP10</div>
          <div class="card-body"><HotJobsChart /></div>
        </div>
        <div class="chart-card map-card">
          <div class="card-title">🗺️ 城市分布</div>
          <div class="card-body map-body">
            <ChinaMap :compact="true" />
          </div>
        </div>
      </main>

      <!-- 右列 -->
      <aside class="dash-col dash-right">
        <div class="chart-card">
          <div class="card-title">💡 技能需求</div>
          <div class="card-body"><SkillWordCloud /></div>
        </div>
        <div class="chart-card">
          <div class="card-title">🎓 经验 & 学历</div>
          <div class="card-body row-2">
            <ExperiencePieChart />
            <EducationPieChart />
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";
import FilterPanel from "../components/FilterPanel.vue";
import SummaryCards from "../components/SummaryCards.vue";
import HotJobsChart from "../components/HotJobsChart.vue";
import SalaryTrendChart from "../components/SalaryTrendChart.vue";
import SkillWordCloud from "../components/SkillWordCloud.vue";
import ExperiencePieChart from "../components/ExperiencePieChart.vue";
import EducationPieChart from "../components/EducationPieChart.vue";
import ChinaMap from "../components/ChinaMap.vue";

const store = useAnalysisStore();
onMounted(() => store.refreshAll());
async function onFilterChange() { await store.refreshAll(); }
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 20px;
}

.dash-grid {
  display: grid;
  grid-template-columns: 300px 1fr 300px;
  gap: 14px;
  min-height: 800px;
}

.dash-col {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chart-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  display: flex;
  flex-direction: column;
}

.map-card { flex: 1; min-height: 350px; }

.card-title {
  font-size: 14px; font-weight: 600; color: #303133;
  padding-bottom: 10px; margin-bottom: 10px;
  border-bottom: 1px solid #ebeef5;
  flex-shrink: 0;
}

/* 固定各图表高度，防止重叠 */
.card-body {
  flex: 1;
  min-height: 200px;
  overflow: visible;
}

.left-trend .card-body { min-height: 280px; }
.dash-center .chart-card .card-body { min-height: 320px; }
.map-body { min-height: 320px; }
.right-skills .card-body { min-height: 260px; }
.right-exp .card-body { min-height: 260px; }

.row-2 {
  display: flex;
  gap: 10px;
}
.row-2 > * {
  flex: 1;
  min-width: 0;
  min-height: 200px;
}

@media (max-width: 1400px) {
  .dash-grid { grid-template-columns: 1fr; min-height: auto; }
  .dash-col { display: grid; grid-template-columns: 1fr 1fr; }
  .chart-card { min-height: 280px; }
}
</style>
