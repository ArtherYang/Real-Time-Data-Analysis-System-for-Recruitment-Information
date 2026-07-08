<!--
  ChinaMap.vue — 中国地图组件
  ============================

  ## china_map_render（地图渲染）
  1. GeoJSON 加载 → echarts.registerMap("china", geoJSON)
  2. 城市数据获取 → store.fetchCityDist(100)
  3. 坐标映射 → CITY_METADATA[cityName] → {lng, lat, icon, province}
  4. ECharts 三层叠加：
     - Layer 0: geo 中国底图（省份边界 + 浅蓝底色）
     - Layer 1: scatter 文本标签（emoji + 城市名，Canvas fillText 原生支持 emoji）
     - Layer 2: effectScatter 涟漪圆点（大小按岗位数缩放，蓝色脉冲）
  5. 点击事件 → 右侧面板展示城市岗位统计

  ## city_icon_match（图标匹配）
  1. 后端 /cities/metadata 返回 30 城市的 {name, lng, lat, icon, province}
  2. 前端 cityCoordinates.js 本地镜像（离线兜底）
  3. 匹配链路：API 数据 city 字段 → CITY_METADATA[city] → 取 icon
  4. emoji 通过 label.formatter 直接拼入文本（Canvas fillText 兼容）
  5. tooltip 使用 HTML 渲染，emoji 100% 兼容
  6. 无匹配 → 兜底 icon "📍"
-->
<template>
  <div class="china-map-wrapper">
    <!-- 状态：加载中 -->
    <div v-if="loading" class="map-status">
      <el-icon :size="40" class="spin"><Loading /></el-icon>
      <p>{{ statusText }}</p>
    </div>

    <!-- 状态：错误 -->
    <div v-else-if="loadError" class="map-status">
      <el-result icon="warning" title="地图加载失败" :sub-title="loadError">
        <template #extra>
          <el-button type="primary" @click="initMap">重试</el-button>
        </template>
      </el-result>
    </div>

    <!-- 正常：地图 + 侧边面板 -->
    <template v-else>
      <div class="map-container" ref="mapContainer">
        <v-chart
          :option="mapOption"
          :key="chartKey"
          autoresize
          style="height: 100%"
          @click="onCityClick"
          @finished="onChartReady"
        />
      </div>

      <div class="city-panel" v-if="!compact">
        <!-- 未选中 -->
        <div v-if="!selectedCity" class="panel-empty">
          <el-icon :size="44" color="#c0c4cc"><MapLocation /></el-icon>
          <p>👆 点击地图上的城市</p>
          <p class="sub">查看该城市岗位统计详情</p>
        </div>

        <!-- 已选中城市 -->
        <template v-else>
          <div class="panel-head">
            <span class="city-emoji">{{ cityMeta?.icon || '📍' }}</span>
            <div>
              <h3>{{ selectedCity }}</h3>
              <span class="city-province">{{ cityMeta?.province || '' }} · {{ cityMeta?.region || '' }}</span>
            </div>
          </div>

          <el-divider />

          <div class="stat-grid">
            <div class="stat-cell">
              <span class="stat-num">{{ selectedData?.count || 0 }}</span>
              <span class="stat-desc">岗位总数</span>
            </div>
            <div class="stat-cell">
              <span class="stat-num">{{ selectedData?.percentage || 0 }}%</span>
              <span class="stat-desc">全国占比</span>
            </div>
          </div>

          <el-divider />

          <div class="section-title">🔥 热门岗位 TOP5</div>
          <div v-if="cityTopJobs.length" class="job-list">
            <div v-for="(j, i) in cityTopJobs" :key="i" class="job-row">
              <span class="job-idx">{{ ['🥇','🥈','🥉','4','5'][i] }}</span>
              <span class="job-title">{{ j.name }}</span>
              <span class="job-num">{{ j.count }}</span>
            </div>
          </div>
          <p v-else class="no-data">暂无该城市的热门岗位数据</p>
        </template>
      </div>
    </template>
  </div>
</template>

<script setup>
/**
 * china_map_render + city_icon_match
 * ==================================
 * 地图渲染管线：GeoJSON → registerMap → 数据映射 → ECharts option → 渲染
 * 图标匹配管线：城市名 → CITY_METADATA 查询 → icon/province/region → label/tooltip
 */
import { ref, computed, watch, nextTick } from "vue";
import { use } from "echarts/core";
import { GeoComponent } from "echarts/components";
import { EffectScatterChart, ScatterChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import * as echarts from "echarts/core";
import VChart from "vue-echarts";
import { MapLocation, Loading } from "@element-plus/icons-vue";
import { useAnalysisStore } from "../stores/analysis";
import { CITY_METADATA } from "../assets/cityCoordinates";

// ---- ECharts 模块注册 ----
use([GeoComponent, EffectScatterChart, ScatterChart, TooltipComponent, CanvasRenderer]);

const props = defineProps({
  compact: { type: Boolean, default: false },  // true = 只显示地图，隐藏侧边面板
});

const store = useAnalysisStore();

// ---- 状态 ----
const loading = ref(true);
const loadError = ref("");
const statusText = ref("正在加载地图数据...");
const chartKey = ref(0);
const selectedCity = ref("");
const cityData = ref([]);

// ============================================================
// china_map_render — 地图渲染管线
// ============================================================

/** Step 1: 加载 GeoJSON + 城市数据 */
async function initMap() {
  loading.value = true;
  loadError.value = "";
  statusText.value = "正在加载中国地图 GeoJSON...";

  try {
    // 动态 import — Vite 处理路径，生成独立 chunk
    const mod = await import("../assets/china.json");
    const geo = mod.default || mod;
    echarts.registerMap("china", geo);
  } catch (e) {
    console.error("GeoJSON import failed:", e.message);
    // 兜底：fetch from public
    try {
      statusText.value = "正在从备用源加载...";
      const r = await fetch("/assets/china.json");
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      echarts.registerMap("china", await r.json());
    } catch (e2) {
      loadError.value = `地图数据加载失败：${e2.message}`;
      loading.value = false;
      return;
    }
  }

  // Step 2: 拉取城市岗位分布数据
  statusText.value = "正在获取城市数据...";
  await store.fetchCityDist(100);
  buildCityData();

  loading.value = false;
  chartKey.value++; // 强制重建 chart 确保 registerMap 生效
  await nextTick();
}

/** Step 2b: 构建地图所需城市数据 */
function buildCityData() {
  cityData.value = (store.cityDist || [])
    .map(item => {
      const meta = CITY_METADATA[item.city];        // city_icon_match
      if (!meta) return null;                        // 未收录城市跳过
      return {
        city: item.city,
        count: item.count || 0,
        percentage: item.percentage || 0,
        lng: meta.lng,
        lat: meta.lat,
        icon: meta.icon,
        province: meta.province,
        region: meta.region,
      };
    })
    .filter(Boolean);
}

// 数据变更时自动重建
watch(() => store.cityDist, buildCityData, { deep: true });

// ============================================================
// city_icon_match — 图标匹配
// ============================================================

/**
 * 根据城市名获取元数据（图标、坐标、省份、区域）
 * 查找链：CITY_METADATA[cityName]（O(1) 哈希查找）
 * 未匹配 → 返回 null，调用方使用 "📍" 兜底
 */
function matchCity(cityName) {
  return CITY_METADATA[cityName] || null;
}

// ============================================================
// ECharts option 构建
// ============================================================

const mapOption = computed(() => {
  const cities = cityData.value;
  if (!cities.length) {
    return {
      title: {
        text: "暂无城市数据", left: "center", top: "center",
        textStyle: { color: "#909399", fontSize: 15 },
      },
    };
  }

  const maxCount = Math.max(...cities.map(c => c.count), 1);

  return {
    backgroundColor: "#fafbfc",

    tooltip: {
      trigger: "item",
      backgroundColor: "#fff",
      borderColor: "#d0d8e0",
      textStyle: { color: "#303133", fontSize: 13 },
      formatter(params) {
        if (params.seriesType !== "effectScatter") return params.name;
        const d = cities.find(c => c.city === params.name);
        if (!d) return params.name;
        // HTML tooltip — emoji 100% 兼容
        return `
          <div style="padding:2px 4px">
            <b style="font-size:15px">${d.icon} ${d.city}</b><br/>
            <span style="color:#666">岗位数</span> <b>${d.count}</b> 个 &nbsp;
            <span style="color:#666">占比</span> <b>${d.percentage}%</b><br/>
            <span style="color:#999;font-size:12px">${d.province} · ${d.region}</span>
          </div>`;
      },
    },

    // Layer 0: 中国底图
    geo: {
      map: "china",
      roam: true,
      zoom: 1.2,
      center: [104.5, 36],
      aspectScale: 0.85,
      layoutCenter: ["50%", "52%"],
      layoutSize: "100%",
      itemStyle: {
        areaColor: "#f0f5ff",
        borderColor: "#bcd0e8",
        borderWidth: 1,
      },
      emphasis: {
        itemStyle: { areaColor: "#dce8fc", borderColor: "#409eff", borderWidth: 1.5 },
        label: { show: true, color: "#303133", fontSize: 12 },
      },
    },

    series: [
      // Layer 1: 城市标签（emoji + 名称，Canvas fillText 原生支持 emoji）
      {
        type: "scatter",
        coordinateSystem: "geo",
        zlevel: 1,
        symbol: "none",
        symbolSize: 1,
        data: cities.map(c => ({
          name: c.city,
          value: [c.lng, c.lat, c.count],
        })),
        label: {
          show: true,
          formatter(p) {
            const city = matchCity(p.name);           // city_icon_match
            return city ? `${city.icon} ${p.name}` : `📍 ${p.name}`;
          },
          position: "right",
          distance: 10,
          fontSize: 11,
          fontWeight: "bold",
          color: "#303133",
          fontFamily: "'Microsoft YaHei','PingFang SC','Segoe UI Emoji',sans-serif",
        },
      },

      // Layer 2: 涟漪标记点（视觉焦点 + 点击热区）
      {
        type: "effectScatter",
        coordinateSystem: "geo",
        zlevel: 2,
        rippleEffect: { brushType: "stroke", scale: 2.5, period: 6 },
        symbolSize(val) {
          // sqrt 缩放：20条→12px, 100条→20px, 500条→30px, 1000条→36px
          return Math.max(10, Math.min(38, 8 + Math.sqrt(val[2]) * 0.9));
        },
        data: cities.map(c => ({
          name: c.city,
          value: [c.lng, c.lat, c.count],
        })),
        itemStyle: {
          color: "#409eff",
          shadowBlur: 8,
          shadowColor: "rgba(64,158,255,0.5)",
        },
        emphasis: {
          scale: 2.2,
          itemStyle: { color: "#f56c6c", shadowColor: "rgba(245,108,108,0.6)" },
        },
      },
    ],
  };
});

// ============================================================
// 交互
// ============================================================

function onCityClick(params) {
  if (params.seriesType === "effectScatter" && params.name) {
    selectedCity.value = params.name;
  }
}

function onChartReady() {
  console.log("[ChinaMap] chart rendered, cities:", cityData.value.length);
}

// ---- 选中城市数据 ----
const cityMeta = computed(() => matchCity(selectedCity.value));

const selectedData = computed(() => {
  if (!selectedCity.value) return null;
  return cityData.value.find(c => c.city === selectedCity.value) || null;
});

const cityTopJobs = computed(() => {
  if (!selectedCity.value) return [];
  // 模拟：取全局热门岗位 TOP5（实际可按城市筛选）
  return (store.hotJobs || []).slice(0, 5).map(j => ({
    name: j.name,
    count: j.count,
  }));
});

// ============================================================
// 生命周期
// ============================================================

initMap();
</script>

<style scoped>
.china-map-wrapper {
  display: flex;
  height: 340px;
  gap: 16px;
}

.map-status {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  color: #909399;
  gap: 10px;
}

.spin { animation: spin 1.5s linear infinite; color: #409eff; }
@keyframes spin { to { transform: rotate(360deg); } }

.map-container {
  flex: 7;
  min-width: 0;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  overflow: hidden;
}

/* 右侧面板 */
.city-panel {
  flex: 3;
  min-width: 270px;
  max-width: 350px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
  padding: 20px;
  overflow-y: auto;
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  text-align: center;
  gap: 8px;
}
.panel-empty p { margin: 0; font-size: 14px; }
.panel-empty .sub { font-size: 12px; color: #c0c4cc; }

.panel-head { display: flex; align-items: center; gap: 10px; }
.city-emoji { font-size: 32px; line-height: 1; }
.panel-head h3 { margin: 0; font-size: 20px; color: #303133; }
.city-province { font-size: 12px; color: #909399; }

.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 4px 0; }
.stat-cell { text-align: center; padding: 10px 6px; background: #f5f7fa; border-radius: 6px; }
.stat-num { display: block; font-size: 22px; font-weight: 700; color: #303133; }
.stat-desc { display: block; font-size: 12px; color: #909399; margin-top: 2px; }

.section-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; }

.job-list { display: flex; flex-direction: column; gap: 3px; }
.job-row { display: flex; align-items: center; padding: 3px 0; font-size: 13px; }
.job-idx {
  width: 20px; height: 20px; line-height: 20px; text-align: center;
  background: #ecf5ff; color: #409eff; border-radius: 4px;
  font-size: 11px; font-weight: 700; margin-right: 8px; flex-shrink: 0;
}
.job-title { flex: 1; color: #303133; }
.job-num { color: #909399; font-size: 12px; flex-shrink: 0; }
.no-data { color: #c0c4cc; font-size: 13px; text-align: center; }

@media (max-width: 1024px) {
  .china-map-wrapper { flex-direction: column; }
  .map-container { flex: none; height: 380px; }
  .city-panel { flex: none; max-width: none; }
}
</style>
