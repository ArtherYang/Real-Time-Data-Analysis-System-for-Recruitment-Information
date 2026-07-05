<template>
  <v-chart :option="option" autoresize style="height:240px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { PieChart } from "echarts/charts";
import {
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([PieChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

const COLORS = ["#409EFF", "#67C23A", "#E6A23C", "#F56C6C", "#909399", "#9b59b6"];

const option = computed(() => ({
  tooltip: {
    trigger: "item",
    formatter: "{b}: {c} 个岗位 ({d}%)",
  },
  color: COLORS,
  series: [
    {
      type: "pie",
      radius: ["45%", "78%"],
      center: ["50%", "55%"],
      label: {
        show: true,
        position: "outside",
        formatter: "{b} {d}%",
        fontSize: 11,
        color: "#606266",
      },
      labelLine: { length: 15, length2: 25, lineStyle: { width: 1 } },
      emphasis: {
        label: { fontSize: 15, fontWeight: "bold" },
      },
      data: store.experienceEdu.experience.map((e) => ({
        name: e.name,
        value: e.count,
      })),
    },
  ],
}));
</script>
