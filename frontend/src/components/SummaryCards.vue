<template>
  <div class="summary-cards">
    <div class="summary-card" v-for="card in cards" :key="card.label">
      <div class="card-icon" :class="card.color">{{ card.emoji }}</div>
      <div class="card-content">
        <div class="card-label">{{ card.label }}</div>
        <div class="card-value">{{ card.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue";
import { useAnalysisStore } from "../stores/analysis";

const store = useAnalysisStore();

const cards = computed(() => [
  { label: "岗位总数", value: store.summary.total_jobs.toLocaleString(), emoji: "📋", color: "blue" },
  { label: "本周新增", value: store.summary.new_this_week.toLocaleString(), emoji: "🆕", color: "green" },
  { label: "覆盖城市", value: store.summary.city_count, emoji: "🏙️", color: "orange" },
  { label: "薪资中位数", value: "¥" + (store.summary.avg_salary / 1000).toFixed(1) + "K", emoji: "💰", color: "purple" },
]);
</script>

<style scoped>
.summary-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.summary-card {
  background: #fff;
  border-radius: 8px;
  padding: 14px 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: pointer;
}

.summary-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
}

.card-icon {
  width: 40px; height: 40px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; flex-shrink: 0;
}

.card-icon.blue   { background: linear-gradient(135deg, #409eff, #337ecc); }
.card-icon.green  { background: linear-gradient(135deg, #67c23a, #529b2e); }
.card-icon.orange { background: linear-gradient(135deg, #e6a23c, #c98d31); }
.card-icon.purple { background: linear-gradient(135deg, #9b59b6, #7d3c98); }

.card-content { flex: 1; }
.card-label { font-size: 13px; color: #909399; margin-bottom: 4px; }
.card-value { font-size: 22px; font-weight: 700; color: #303133; }

@media (min-width: 1600px) {
  .summary-cards { grid-template-columns: repeat(4, 1fr); }
}
@media (max-width: 768px) {
  .summary-cards { grid-template-columns: 1fr; }
  .card-value { font-size: 18px; }
}
</style>
