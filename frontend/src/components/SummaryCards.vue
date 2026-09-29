<template>
  <div class="summary-cards">
    <div class="summary-card" v-for="card in cards" :key="card.label">
      <span class="card-emoji">{{ card.emoji }}</span>
      <div class="card-content">
        <div class="card-label">{{ card.label }}</div>
        <div class="card-value">{{ card.display }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from "vue";
import { useAnalysisStore } from "../stores/analysis";

const store = useAnalysisStore();

// countUp：首次加载从 0 滚，后续数据变化直接显示
function animateTo(target, dur = 1200) {
  const disp = ref("0");
  let raf;
  function run() {
    const t = target();
    if (!t) { disp.value = "0"; return; }
    const start = performance.now();
    cancelAnimationFrame(raf);
    function step(now) {
      const p = Math.min((now - start) / dur, 1);
      const e = 1 - Math.pow(2, -10 * p);
      const v = Math.round(t * e);
      disp.value = t >= 1000 ? v.toLocaleString() : String(v);
      if (p < 1) raf = requestAnimationFrame(step);
      else disp.value = t >= 1000 ? t.toLocaleString() : String(t);
    }
    raf = requestAnimationFrame(step);
  }
  run();
  // 监听数据变化，重新动画
  watch(target, () => run(), { immediate: false });
  return disp;
}

const c1 = animateTo(() => store.summary.total_jobs, 1500);
const c2 = animateTo(() => store.summary.new_this_week, 1200);
const c3 = animateTo(() => store.summary.city_count, 1000);
const c4 = computed(() => "¥" + ((store.summary.avg_salary || 0) / 1000).toFixed(1) + "K");

const cards = computed(() => [
  { label: "岗位总数", emoji: "📋", display: c1.value },
  { label: "本周新增", emoji: "🆕", display: c2.value },
  { label: "覆盖城市", emoji: "🏙️", display: c3.value },
  { label: "薪资中位数", emoji: "💰", display: c4.value },
]);
</script>

<style scoped>
.summary-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.summary-card { background: #fff; border-radius: 8px; padding: 14px 12px; display: flex; align-items: center; gap: 10px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); transition: transform 0.2s; }
.summary-card:hover { transform: translateY(-2px); }
.card-emoji { font-size: 28px; flex-shrink: 0; }
.card-content { flex: 1; }
.card-label { font-size: 13px; color: #909399; margin-bottom: 4px; }
.card-value { font-size: 22px; font-weight: 700; color: #303133; font-family: "Courier New",monospace; }
@media (min-width: 1600px) { .summary-cards { grid-template-columns: repeat(4, 1fr); } }
@media (max-width: 768px) { .summary-cards { grid-template-columns: 1fr; } }
</style>
