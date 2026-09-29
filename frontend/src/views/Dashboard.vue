<template>
  <div class="dashboard">
    <!-- 顶部操作栏 -->
    <div class="dash-top">
      <div class="top-left">
        <span class="live-clock">🕐 {{ timeStr }}</span>
        <span class="live-dot"></span>
        <span class="live-label">实时</span>
      </div>
      <div class="top-right">
        <el-button size="small" @click="toggleDark" circle>
          {{ isDark ? '☀️' : '🌙' }}
        </el-button>
      </div>
    </div>

    <!-- 工具栏：筛选 + 数据操作 -->
    <div class="toolbar">
      <FilterPanel @filter-change="onFilterChange" />
      <div class="toolbar-actions">
        <ToolBar @data-changed="onRefreshComplete" />
      </div>
    </div>

    <!-- 三列网格 -->
    <div class="dash-grid">
      <!-- 左列 -->
      <aside class="dash-col dash-left">
        <SummaryCards />
        <div class="chart-card left-trend">
          <div class="card-title">📈 岗位需求趋势</div>
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
import { ref, onMounted, onUnmounted } from "vue";
import { useAnalysisStore } from "../stores/analysis";
import FilterPanel from "../components/FilterPanel.vue";
import SummaryCards from "../components/SummaryCards.vue";
import HotJobsChart from "../components/HotJobsChart.vue";
import SalaryTrendChart from "../components/SalaryTrendChart.vue";
import SkillWordCloud from "../components/SkillWordCloud.vue";
import ExperiencePieChart from "../components/ExperiencePieChart.vue";
import EducationPieChart from "../components/EducationPieChart.vue";
import ChinaMap from "../components/ChinaMap.vue";
import ToolBar from "../components/ToolBar.vue";

const store = useAnalysisStore();

// Dark mode toggle
const isDark = ref(false);
function toggleDark() {
  isDark.value = !isDark.value;
  document.documentElement.setAttribute("data-theme", isDark.value ? "dark" : "");
}

// Live clock
const timeStr = ref("");
let clockTimer = null;
function tick() { timeStr.value = new Date().toLocaleTimeString("zh-CN", { hour12: false }); }

onMounted(async () => {
  tick(); clockTimer = setInterval(tick, 1000);
  await Promise.all([store.refreshAll(), store.fetchHotJobs(10, 'title')]);
});
onUnmounted(() => { clearInterval(clockTimer); });
async function onFilterChange() {
  await Promise.all([store.refreshAll(), store.fetchHotJobs(10, 'title')]);
}
async function onRefreshComplete() {
  await Promise.all([store.refreshAll(), store.fetchHotJobs(10, 'title')]);
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  padding-bottom: 20px;
}

.dash-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 0; margin-bottom: 8px;
}
.top-left { display: flex; align-items: center; gap: 8px; }
.live-clock { font-family: "Courier New",monospace; font-size: 15px; color: #303133; }
.live-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 6px #22c55e; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
.live-label { font-size: 12px; color: #22c55e; font-weight: 600; letter-spacing: 1px; }
.top-right { display: flex; gap: 6px; }

.toolbar { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
.toolbar-actions { display: flex; gap: 8px; flex-shrink: 0; padding-top: 4px; }

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 0;
}

.toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
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
