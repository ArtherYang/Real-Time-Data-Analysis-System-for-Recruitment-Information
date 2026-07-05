<template>
  <v-chart :option="option" autoresize style="height:260px" />
</template>

<script setup>
import { computed } from "vue";
import { use } from "echarts/core";
import { TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import "echarts-wordcloud";
import VChart from "vue-echarts";
import { useAnalysisStore } from "../stores/analysis";

use([TooltipComponent, CanvasRenderer]);

const store = useAnalysisStore();

const option = computed(() => {
  const items = store.skillRanking;
  const maxCount = items.length > 0 ? items[0].count : 1;
  return {
    tooltip: {
      show: true,
      formatter: "{b}: {c} 次",
    },
    series: [
      {
        type: "wordCloud",
        shape: "circle",
        left: "center",
        top: "center",
        width: "90%",
        height: "90%",
        sizeRange: [14, 48],
        rotationRange: [-45, 45],
        rotationStep: 15,
        gridSize: 8,
        drawOutOfBound: false,
        textStyle: {
          fontFamily: "Microsoft YaHei, sans-serif",
          fontWeight: "normal",
          color: () => {
            const colors = [
              "#409EFF", "#67C23A", "#E6A23C", "#F56C6C",
              "#9b59b6", "#1abc9c", "#3498db", "#e74c3c",
            ];
            return colors[Math.floor(Math.random() * colors.length)];
          },
        },
        emphasis: {
          textStyle: {
            shadowBlur: 10,
            shadowColor: "#333",
          },
        },
        data: items.map((i) => ({
          name: i.name,
          value: i.count,
        })),
      },
    ],
  };
});
</script>
