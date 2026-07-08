<template>
  <v-chart :option="option" autoresize style="height:280px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { PieChart } from "echarts/charts";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([PieChart, TooltipComponent, CanvasRenderer]);

const store = useAnalysisStore();

const COLORS = ["#3ba272", "#5470c6", "#fac858", "#ee6666", "#9b59b6"];

const option = computed(() => {
  const data = store.experienceEdu.education
    .filter(e => e.count > 0)
    .map(e => ({ name: e.name, value: e.count }));
  const total = data.reduce((s, i) => s + i.value, 0);

  return {
    tooltip: {
      trigger: "item",
      backgroundColor: "#fff",
      borderColor: "#e8e8e8",
      padding: [12, 16],
      textStyle: { color: "#333", fontSize: 13 },
      formatter: (p) => `
        <div style="font-size:14px;font-weight:600;margin-bottom:4px">${p.name}</div>
        <div style="color:#666">岗位数 <b style="color:#303133">${p.value}</b> 个</div>
        <div style="color:#666">占比 <b style="color:#303133">${p.percent}%</b></div>
      `,
    },
    color: COLORS,
    series: [{
      type: "pie",
      radius: ["55%", "80%"],
      center: ["50%", "48%"],
      padAngle: 2,
      itemStyle: {
        borderRadius: 6,
        borderColor: "#fff",
        borderWidth: 3,
      },
      label: { show: false },
      emphasis: {
        scaleSize: 10,
        itemStyle: { shadowBlur: 20, shadowColor: "rgba(0,0,0,0.15)" },
      },
      data,
    }],
    graphic: total > 0 ? [
      { type: "text", left: "center", top: "38%",
        style: { text: `${total}`, fontSize: 24, fontWeight: "bold", fill: "#303133", textAlign: "center" } },
      { type: "text", left: "center", top: "50%",
        style: { text: "个岗位", fontSize: 12, fill: "#909399", textAlign: "center" } },
    ] : [],
  };
});
</script>
