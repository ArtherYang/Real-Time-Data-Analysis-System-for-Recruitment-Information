<template>
  <div class="city-analysis">
    <h2 style="margin-bottom: 16px; color: #303133">
      <el-icon :size="20"><MapLocation /></el-icon>
      城市分布分析
    </h2>

    <FilterPanel @filter-change="onFilterChange" />

    <!-- 中国地图 -->
    <ChinaMap style="margin-bottom: 20px" />

    <!-- 补充图表 -->
    <div class="chart-grid">
      <div class="chart-card">
        <div class="chart-title">城市岗位 TOP 15</div>
        <div class="chart-container tall">
          <v-chart :option="barOption" autoresize />
        </div>
      </div>
      <div class="chart-card">
        <div class="chart-title">区域分布</div>
        <div class="chart-container tall">
          <v-chart :option="regionPieOption" autoresize />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { use } from "echarts/core";
import { BarChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { MapLocation } from "@element-plus/icons-vue";
import { useAnalysisStore } from "../stores/analysis";
import FilterPanel from "../components/FilterPanel.vue";
import ChinaMap from "../components/ChinaMap.vue";
import { CITY_METADATA } from "../assets/cityCoordinates";

use([BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

onMounted(async () => {
  await Promise.all([
    store.fetchFilterOptions(),
    store.fetchCityMetadata(),
    store.fetchCityDist(100),
    store.fetchSalaryDist("city"),
  ]);
});

async function onFilterChange() {
  await Promise.all([
    store.fetchCityDist(100),
    store.fetchSalaryDist("city"),
  ]);
}

// ---- 柱状图：城市 TOP 15 ----
const barOption = computed(() => {
  const items = [...store.cityDist].slice(0, 15).reverse();
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
    },
    grid: { left: 60, right: 40, top: 10, bottom: 20 },
    xAxis: { type: "value", name: "岗位数" },
    yAxis: {
      type: "category",
      data: items.map(i => {
        const icon = CITY_METADATA[i.city]?.icon || "";
        return `${icon} ${i.city}`;
      }),
      axisLabel: { fontSize: 12 },
    },
    series: [{
      type: "bar",
      data: items.map(i => ({
        value: i.count,
        itemStyle: {
          color: {
            type: "linear", x: 0, y: 0, x2: 1, y2: 0,
            colorStops: [
              { offset: 0, color: "#409EFF" },
              { offset: 1, color: "#67C23A" },
            ],
          },
          borderRadius: [0, 4, 4, 0],
        },
      })),
      barWidth: 16,
    }],
  };
});

// ---- 饼图：区域分布（东部/中部/西部） ----
const regionPieOption = computed(() => {
  const regionCount = { 东部: 0, 中部: 0, 西部: 0 };
  for (const item of store.cityDist) {
    const region = CITY_METADATA[item.city]?.region;
    if (region && regionCount[region] !== undefined) {
      regionCount[region] += item.count;
    }
  }
  return {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} 个岗位 ({d}%)",
    },
    legend: { bottom: 0 },
    color: ["#409EFF", "#67C23A", "#E6A23C"],
    series: [{
      type: "pie",
      radius: ["45%", "75%"],
      center: ["50%", "45%"],
      label: { formatter: "{b}\n{d}%" },
      data: [
        { name: "东部", value: regionCount.东部 },
        { name: "中部", value: regionCount.中部 },
        { name: "西部", value: regionCount.西部 },
      ],
    }],
  };
});
</script>
