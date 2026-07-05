<template>
  <v-chart :option="option" autoresize style="height:350px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

const option = computed(() => {
  const items = [...store.hotJobs].reverse();
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: "{b}: {c} 个岗位",
    },
    grid: { left: 140, right: 40, top: 10, bottom: 20 },
    xAxis: {
      type: "value",
      name: "岗位数量",
    },
    yAxis: {
      type: "category",
      data: items.map((i) => i.name),
      axisLabel: { fontSize: 12 },
    },
    series: [
      {
        type: "bar",
        data: items.map((i) => i.count),
        itemStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 1,
            y2: 0,
            colorStops: [
              { offset: 0, color: "#409EFF" },
              { offset: 1, color: "#67C23A" },
            ],
          },
          borderRadius: [0, 4, 4, 0],
        },
        barWidth: 18,
      },
    ],
  };
});
</script>
