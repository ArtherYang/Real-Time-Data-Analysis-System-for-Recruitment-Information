<template>
  <v-chart :option="option" autoresize style="height:320px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent, LegendComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

const option = computed(() => {
  const groups = store.salaryDist;
  const maxVal = groups.length > 0 ? Math.max(...groups.map(g => g.p75 || 0)) * 1.3 : 50000;
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const i = params[0]?.dataIndex;
        const d = groups[i];
        if (!d) return "";
        return `<b>${d.group}</b>（${d.count}个岗位）<br/>
          <span style="display:inline-block;width:10px;height:10px;background:#91cc75;border-radius:2px;margin-right:4px"></span>P25: ¥${(d.p25/1000).toFixed(1)}K<br/>
          <span style="display:inline-block;width:10px;height:10px;background:#409EFF;border-radius:2px;margin-right:4px"></span>中位数: ¥${(d.median/1000).toFixed(1)}K<br/>
          <span style="display:inline-block;width:10px;height:10px;background:#ee6666;border-radius:2px;margin-right:4px"></span>P75: ¥${(d.p75/1000).toFixed(1)}K`;
      },
    },
    legend: {
      data: ["P25（25分位）", "中位数（50分位）", "P75（75分位）"],
      top: 0,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 90, right: 20, top: 45, bottom: 30 },
    xAxis: {
      type: "category",
      data: groups.map((g) => g.group),
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: "value",
      name: "月薪(K)",
      max: Math.ceil(maxVal / 10000) * 10000,
      interval: Math.ceil(maxVal / 50000) * 10000 || 10000,
      axisLabel: { formatter: (v) => (v / 1000).toFixed(0) + "K" },
    },
    series: [
      {
        name: "P25（25分位）",
        type: "bar",
        barGap: "10%",
        barWidth: "25%",
        data: groups.map((g) => g.p25),
        label: { show: true, position: "top", fontSize: 9,
          formatter: (p) => p.value > 0 ? (p.value/1000).toFixed(0)+"K" : "" },
        itemStyle: { color: "#91cc75", borderRadius: [3,3,0,0] },
      },
      {
        name: "中位数（50分位）",
        type: "bar",
        barWidth: "25%",
        data: groups.map((g) => g.median),
        label: { show: true, position: "top", fontSize: 9,
          formatter: (p) => p.value > 0 ? (p.value/1000).toFixed(0)+"K" : "" },
        itemStyle: { color: "#409EFF", borderRadius: [3,3,0,0] },
      },
      {
        name: "P75（75分位）",
        type: "bar",
        barWidth: "25%",
        data: groups.map((g) => g.p75),
        label: { show: true, position: "top", fontSize: 9,
          formatter: (p) => p.value > 0 ? (p.value/1000).toFixed(0)+"K" : "" },
        itemStyle: { color: "#ee6666", borderRadius: [3,3,0,0] },
      },
    ],
  };
});
</script>
