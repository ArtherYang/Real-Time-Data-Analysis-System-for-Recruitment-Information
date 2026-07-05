<template>
  <div class="chart-card">
    <div class="chart-title">城市岗位分布</div>
    <div class="chart-container tall">
      <v-chart :option="option" autoresize />
    </div>
  </div>
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

const option = computed(() => {
  const items = store.cityDist;
  const total = items.reduce((s, i) => s + i.count, 0);
  return {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} 个岗位 ({d}%)",
    },
    legend: {
      type: "scroll",
      orient: "vertical",
      right: 10,
      top: 20,
      bottom: 20,
    },
    series: [
      {
        type: "pie",
        radius: ["40%", "70%"],
        center: ["40%", "50%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: "#fff",
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: "{b}: {d}%",
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: "bold",
          },
        },
        data: items.map((i) => ({
          name: i.city,
          value: i.count,
        })),
      },
    ],
  };
});
</script>
