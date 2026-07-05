<template>
  <div class="big-screen">
    <!-- 动态粒子背景 -->
    <div class="particles-bg"></div>

    <!-- ====== 顶部：标题 + 时钟 ====== -->
    <header class="screen-header">
      <div class="header-left">
        <span class="header-decor">▎</span>
        <h1>招聘数据实时监控中心</h1>
        <span class="header-decor">▎</span>
      </div>
      <div class="header-center">
        <span class="pulse-dot"></span>
        <span class="live-text">系统运行中</span>
      </div>
      <div class="header-right">
        <span class="clock-date">{{ dateStr }}</span>
        <span class="clock-time">{{ timeStr }}</span>
      </div>
    </header>

    <!-- ====== 主体：三栏布局 ====== -->
    <div class="screen-body">
      <!-- 左栏：数字卡片 + 经验学历 -->
      <aside class="side-left">
        <div class="dark-card">
          <div class="card-title">📊 核心指标</div>
          <div class="stat-rows">
            <div class="stat-row" v-for="s in stats" :key="s.label">
              <span class="stat-label">{{ s.label }}</span>
              <span class="stat-value" ref="countEls">{{ s.display }}</span>
            </div>
          </div>
        </div>

        <div class="dark-card">
          <div class="card-title">📚 学历要求</div>
          <v-chart :option="eduPieOption" autoresize style="height:160px" />
        </div>

        <div class="dark-card">
          <div class="card-title">🎓 经验要求</div>
          <v-chart :option="expPieOption" autoresize style="height:160px" />
        </div>
      </aside>

      <!-- 中栏：中国地图 -->
      <main class="center-map">
        <div class="dark-card map-card">
          <div class="card-title">🗺️ 全国岗位分布热力</div>
          <v-chart :option="mapOption" autoresize style="height:100%"
            @click="onMapClick" />
        </div>
      </main>

      <!-- 右栏：排行榜 + 技能 -->
      <aside class="side-right">
        <div class="dark-card">
          <div class="card-title">🔥 热门岗位 TOP8</div>
          <div class="rank-list">
            <div class="rank-item" v-for="(j, idx) in topJobs" :key="j.name"
              :class="{ 'rank-top3': idx < 3 }">
              <span class="rank-no">{{ idx + 1 }}</span>
              <span class="rank-name">{{ j.name }}</span>
              <span class="rank-bar">
                <span class="rank-bar-inner" :style="{ width: (j.count / maxJobCount * 100) + '%' }"></span>
              </span>
              <span class="rank-val">{{ j.count }}</span>
            </div>
          </div>
        </div>

        <div class="dark-card">
          <div class="card-title">💡 热门技能 TOP8</div>
          <div class="rank-list">
            <div class="rank-item" v-for="(s, idx) in topSkills" :key="s.name"
              :class="{ 'rank-top3': idx < 3 }">
              <span class="rank-no">{{ idx + 1 }}</span>
              <span class="rank-name">{{ s.name }}</span>
              <span class="rank-bar">
                <span class="rank-bar-inner skill-bar" :style="{ width: (s.count / maxSkillCount * 100) + '%' }"></span>
              </span>
              <span class="rank-val">{{ s.count }}</span>
            </div>
          </div>
        </div>
      </aside>
    </div>

    <!-- ====== 底部：滚动消息条 ====== -->
    <footer class="screen-footer">
      <div class="ticker-wrap">
        <div class="ticker">
          <span v-for="(msg, i) in tickerMessages" :key="i" class="ticker-item">
            🔔 {{ msg }}<span class="ticker-sep"> ║ </span>
          </span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from "vue";
import { use } from "echarts/core";
import { GeoComponent } from "echarts/components";
import { ScatterChart, MapChart, EffectScatterChart, PieChart } from "echarts/charts";
import { TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import * as echarts from "echarts/core";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";
import { CITY_METADATA } from "../assets/cityCoordinates";

use([GeoComponent, ScatterChart, MapChart, EffectScatterChart, PieChart,
  TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

// ---- 时钟 ----
const dateStr = ref("");
const timeStr = ref("");
let clockTimer = null;

function updateClock() {
  const now = new Date();
  dateStr.value = now.toLocaleDateString("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", weekday: "short",
  });
  timeStr.value = now.toLocaleTimeString("zh-CN", { hour12: false });
}
onMounted(() => { updateClock(); clockTimer = setInterval(updateClock, 1000); });
onUnmounted(() => clearInterval(clockTimer));

// ---- 数据加载 ----
const cityData = ref([]);
const mapReady = ref(false);

onMounted(async () => {
  // Load GeoJSON
  try {
    const geoModule = await import("../assets/china.json");
    echarts.registerMap("china", geoModule.default || geoModule);
  } catch (e) {
    console.warn("Map GeoJSON load failed, trying fallback...");
  }
  mapReady.value = true;

  // Load all data
  await Promise.all([
    store.fetchSummary(),
    store.fetchHotJobs(8),
    store.fetchCityDist(30),
    store.fetchSkillRanking(8),
    store.fetchSalaryDist("job_category"),
  ]);

  // Map city data
  cityData.value = (store.cityDist || []).map(item => {
    const meta = CITY_METADATA[item.city];
    return {
      city: item.city, count: item.count, percentage: item.percentage,
      lng: meta?.lng || 0, lat: meta?.lat || 0,
      icon: meta?.icon || "📍", province: meta?.province || "",
      region: meta?.region || "",
    };
  });
});

// ---- 核心指标 ----
const stats = computed(() => [
  { label: "岗位总数", display: store.summary.total_jobs?.toLocaleString() || "0" },
  { label: "本周新增", display: store.summary.new_this_week?.toLocaleString() || "0" },
  { label: "覆盖城市", display: store.summary.city_count || "0" },
  { label: "薪资中位数", display: "¥" + ((store.summary.avg_salary || 0) / 1000).toFixed(1) + "K" },
]);

// ---- 排行榜 ----
const topJobs = computed(() => store.hotJobs.slice(0, 8));
const topSkills = computed(() => store.skillRanking.slice(0, 8));
const maxJobCount = computed(() => Math.max(1, ...topJobs.value.map(j => j.count)));
const maxSkillCount = computed(() => Math.max(1, ...topSkills.value.map(s => s.count)));

// ---- 学历饼图（暗色主题） ----
const DARK_PIE_COLORS = ["#409EFF", "#67C23A", "#E6A23C", "#F56C6C", "#9b59b6"];
const textStyle = { color: "#a8c0e0", fontSize: 11 };

const eduPieOption = computed(() => ({
  tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
  legend: { bottom: 0, textStyle },
  color: DARK_PIE_COLORS,
  series: [{
    type: "pie", radius: ["45%", "70%"], center: ["50%", "42%"],
    label: { color: "#a8c0e0", fontSize: 10, formatter: "{b}\n{d}%" },
    data: store.experienceEdu.education.map(e => ({ name: e.name, value: e.count })),
  }],
}));

const expPieOption = computed(() => ({
  tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
  legend: { bottom: 0, textStyle },
  color: DARK_PIE_COLORS,
  series: [{
    type: "pie", radius: ["45%", "70%"], center: ["50%", "42%"],
    label: { color: "#a8c0e0", fontSize: 10, formatter: "{b}\n{d}%" },
    data: store.experienceEdu.experience.map(e => ({ name: e.name, value: e.count })),
  }],
}));

// ---- 中国地图（暗色主题） ----
const mapOption = computed(() => {
  const cities = cityData.value;
  if (cities.length === 0) return {};
  const maxCount = Math.max(...cities.map(c => c.count), 1);

  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(10,20,50,0.9)",
      borderColor: "#1e80ff",
      textStyle: { color: "#e0e8f0" },
      formatter: (p) => {
        if (p.seriesType === "effectScatter") {
          const d = cities.find(c => c.city === p.name);
          if (!d) return p.name;
          return `<b>${d.icon} ${d.city}</b><br/>
            岗位：<b>${d.count}</b> 个<br/>
            占比：<b>${d.percentage}%</b><br/>
            区域：${d.province}`;
        }
        return p.name;
      },
    },
    geo: {
      map: "china", roam: true, zoom: 1.2, center: [104.5, 36],
      aspectScale: 0.85, layoutCenter: ["50%", "52%"], layoutSize: "100%",
      itemStyle: {
        areaColor: "#0a1628", borderColor: "#1a3550", borderWidth: 1,
        shadowColor: "rgba(0,100,255,0.15)", shadowBlur: 8,
      },
      emphasis: {
        itemStyle: { areaColor: "#122545", borderColor: "#409EFF", borderWidth: 1.5 },
        label: { show: true, color: "#c0d8f0", fontSize: 11 },
      },
    },
    series: [
      {
        type: "scatter", coordinateSystem: "geo", zlevel: 1,
        symbol: "none", symbolSize: 1,
        data: cities.map(c => ({
          name: c.city, value: [c.lng, c.lat, c.count],
        })),
        label: {
          show: true,
          formatter: (p) => {
            const city = cities.find(c => c.city === p.name);
            return city ? `${city.icon} ${city.name}` : p.name;
          },
          position: "right", distance: 6, fontSize: 10, fontWeight: "bold",
          color: "#a0c0e0",
        },
      },
      {
        type: "effectScatter", coordinateSystem: "geo", zlevel: 2,
        rippleEffect: { brushType: "stroke", scale: 2.5, period: 6 },
        symbolSize: (val) => Math.max(8, Math.min(24, 6 + (val[2] / maxCount) * 18)),
        data: cities.map(c => ({
          name: c.city, value: [c.lng, c.lat, c.count],
        })),
        itemStyle: {
          color: "#1e80ff",
          shadowBlur: 12, shadowColor: "rgba(30,128,255,0.6)",
        },
        emphasis: {
          scale: 2.5,
          itemStyle: { color: "#ff6b6b", shadowColor: "rgba(255,107,107,0.7)" },
        },
      },
    ],
  };
});

// ---- 滚动消息 ----
const tickerMessages = computed(() => {
  const msgs = [];
  const jobs = store.hotJobs.slice(0, 5);
  for (const j of jobs) {
    msgs.push(`最新岗位：${j.name} 需求 ${j.count} 个，占比 ${j.percentage || "?"}%`);
  }
  msgs.push(`系统覆盖 ${store.filterOptions.cities?.length || 30} 个城市，${store.filterOptions.platforms?.length || 4} 个招聘平台`);
  return msgs.length ? msgs : ["正在加载数据..."];
});

// ---- 地图点击 ----
function onMapClick(params) {
  if (params.seriesType === "effectScatter" && params.name) {
    console.log("Selected city:", params.name);
  }
}
</script>

<style scoped>
/* ============================================================
 * 全屏数据大屏 — 深色科技蓝主题
 * ============================================================ */
.big-screen {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(135deg, #0a0e1a 0%, #0d1a2d 30%, #0a1620 60%, #0c1020 100%);
  color: #c0d8f0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
}

/* 粒子背景 */
.particles-bg {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background:
    radial-gradient(1px 1px at 10% 15%, rgba(30,128,255,0.4), transparent),
    radial-gradient(1px 1px at 25% 35%, rgba(30,128,255,0.3), transparent),
    radial-gradient(2px 2px at 40% 20%, rgba(0,200,255,0.4), transparent),
    radial-gradient(1px 1px at 55% 45%, rgba(30,128,255,0.3), transparent),
    radial-gradient(2px 2px at 70% 30%, rgba(0,200,255,0.35), transparent),
    radial-gradient(1px 1px at 85% 25%, rgba(30,128,255,0.4), transparent),
    radial-gradient(1px 1px at 15% 60%, rgba(30,128,255,0.3), transparent),
    radial-gradient(2px 2px at 35% 70%, rgba(0,200,255,0.35), transparent),
    radial-gradient(1px 1px at 60% 65%, rgba(30,128,255,0.3), transparent),
    radial-gradient(1px 1px at 80% 55%, rgba(30,128,255,0.4), transparent),
    radial-gradient(2px 2px at 90% 75%, rgba(0,200,255,0.3), transparent),
    radial-gradient(1px 1px at 50% 85%, rgba(30,128,255,0.3), transparent),
    radial-gradient(1px 1px at 20% 80%, rgba(30,128,255,0.25), transparent);
  pointer-events: none;
  z-index: 0;
}

/* ====== 顶部 ====== */
.screen-header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 32px;
  background: linear-gradient(180deg, rgba(10,30,60,0.95) 0%, rgba(10,20,40,0.6) 100%);
  border-bottom: 1px solid rgba(30,128,255,0.2);
  flex-shrink: 0;
}

.header-left { display: flex; align-items: center; gap: 16px; }
.header-left h1 {
  font-size: 22px; font-weight: 600; letter-spacing: 4px;
  background: linear-gradient(90deg, #60a5fa, #38bdf8, #60a5fa);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header-decor { color: #1e80ff; font-size: 20px; opacity: 0.7; }

.header-center { display: flex; align-items: center; gap: 8px; }
.pulse-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #22c55e;
  box-shadow: 0 0 8px #22c55e;
  animation: pulse-dot 2s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(1.6); }
}
.live-text { color: #22c55e; font-size: 13px; letter-spacing: 2px; }

.header-right { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; }
.clock-date { font-size: 13px; color: #7a9ec0; }
.clock-time { font-size: 26px; font-weight: 700; font-family: "Courier New", monospace; color: #e0f0ff; letter-spacing: 3px; }

/* ====== 主体三栏 ====== */
.screen-body {
  position: relative; z-index: 1;
  flex: 1; display: flex; gap: 12px; padding: 12px;
  min-height: 0;
}

.dark-card {
  background: rgba(10,25,50,0.7);
  border: 1px solid rgba(30,128,255,0.15);
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 10px;
  backdrop-filter: blur(4px);
}
.card-title {
  font-size: 14px; font-weight: 600; color: #7ab8f5;
  margin-bottom: 10px; padding-bottom: 6px;
  border-bottom: 1px solid rgba(30,128,255,0.15);
}

/* 左栏 */
.side-left {
  width: 260px; flex-shrink: 0; overflow-y: auto;
}
.stat-rows { display: flex; flex-direction: column; gap: 8px; }
.stat-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px; background: rgba(30,128,255,0.08); border-radius: 4px;
  border-left: 3px solid #1e80ff;
}
.stat-label { font-size: 13px; color: #7a9ec0; }
.stat-value {
  font-size: 22px; font-weight: 700; color: #38bdf8;
  font-family: "Courier New", monospace;
}

/* 中栏 */
.center-map { flex: 1; min-width: 0; }
.map-card { height: 100%; display: flex; flex-direction: column; }
.map-card > :last-child { flex: 1; }

/* 右栏 */
.side-right {
  width: 280px; flex-shrink: 0; overflow-y: auto;
}

.rank-list { display: flex; flex-direction: column; gap: 4px; }
.rank-item {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 6px; border-radius: 3px;
  transition: background 0.2s;
}
.rank-item:hover { background: rgba(30,128,255,0.1); }
.rank-no {
  width: 20px; height: 20px; line-height: 20px; text-align: center;
  background: rgba(30,128,255,0.2); color: #7ab8f5;
  border-radius: 3px; font-size: 11px; font-weight: 700;
}
.rank-top3 .rank-no { background: #1e80ff; color: #fff; }
.rank-name { flex: 1; font-size: 13px; color: #c0d8f0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rank-bar { width: 60px; height: 5px; background: rgba(30,128,255,0.15); border-radius: 3px; overflow: hidden; flex-shrink: 0; }
.rank-bar-inner { height: 100%; background: #1e80ff; border-radius: 3px; transition: width 0.6s ease; }
.skill-bar { background: #22c55e; }
.rank-val { width: 28px; text-align: right; font-size: 12px; font-weight: 600; color: #e0f0ff; font-family: "Courier New", monospace; }

/* ====== 底部滚动条 ====== */
.screen-footer {
  position: relative; z-index: 1;
  flex-shrink: 0; height: 36px;
  background: rgba(10,25,50,0.8);
  border-top: 1px solid rgba(30,128,255,0.2);
  overflow: hidden;
}
.ticker-wrap { height: 100%; display: flex; align-items: center; overflow: hidden; }
.ticker {
  display: flex; gap: 32px; white-space: nowrap;
  animation: ticker-scroll 40s linear infinite;
}
.ticker-item { font-size: 13px; color: #7a9ec0; }
.ticker-sep { color: rgba(30,128,255,0.3); margin: 0 8px; }
@keyframes ticker-scroll {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}
</style>
