<template>
  <v-chart :option="option" autoresize style="height:280px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

const store = useAnalysisStore();

const option = computed(() => {
  const trend = store.salaryTrend;
  return {
    tooltip: {
      trigger: "axis",
      formatter: (params) => {
        const period = params[0]?.axisValue || "";
        let html = `<b>${period}</b><br/>`;
        params.forEach((p) => {
          if (p.seriesName === "环比增长") {
            html += `${p.marker} ${p.seriesName}: ${p.value != null ? p.value + "%" : "-"}<br/>`;
          } else {
            html += `${p.marker} ${p.seriesName}: ${p.value} 个<br/>`;
          }
        });
        return html;
      },
    },
    legend: {
      data: ["岗位数量", "环比增长"],
      bottom: 0,
      itemWidth: 10, itemHeight: 10,
      textStyle: { fontSize: 10 },
    },
    grid: { left: 50, right: 50, top: 30, bottom: 35 },
    xAxis: {
      type: "category",
      data: trend.map((t) => t.date),
      axisLabel: { fontSize: 10 },
    },
    yAxis: [
      {
        type: "value",
        name: "岗位数",
        nameTextStyle: { fontSize: 9 },
        axisLabel: { fontSize: 9 },
      },
      {
        type: "value",
        name: "增长率(%)",
        nameTextStyle: { fontSize: 9 },
        axisLabel: { fontSize: 9, formatter: "{value}%" },
      },
    ],
    series: [
      {
        name: "岗位数量",
        type: "bar",
        data: trend.map((t) => t.job_count),
        label: {
          show: true,
          position: "top",
          fontSize: 10,
          color: "#303133",
        },
        itemStyle: {
          color: {
            type: "linear",
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: "#409EFF" },
              { offset: 1, color: "#79bbff" },
            ],
          },
          borderRadius: [4, 4, 0, 0],
        },
        barWidth: 18,
      },
      {
        name: "环比增长",
        type: "line",
        yAxisIndex: 1,
        data: trend.map((t) => t.growth_rate),
        label: {
          show: true,
          formatter: "{c}%",
          fontSize: 9,
          color: "#67C23A",
        },
        smooth: true,
        itemStyle: { color: "#67C23A" },
        lineStyle: { width: 2, type: "dashed" },
        symbol: "circle",
        symbolSize: 8,
      },
    ],
  };
});
</script>
