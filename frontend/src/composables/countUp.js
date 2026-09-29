import { ref, onMounted } from "vue";

export function useCountUp(getTarget, duration = 1500) {
  const display = ref("0");

  function fmt(v) {
    if (v >= 1000) return v.toLocaleString();
    return String(Math.floor(v));
  }

  function animate() {
    const target = getTarget();
    if (!target) { display.value = "0"; return; }
    const start = performance.now();
    function step(now) {
      const t = Math.min((now - start) / duration, 1);
      const eased = t === 1 ? 1 : 1 - Math.pow(2, -10 * t);
      display.value = fmt(Math.round(target * eased));
      if (t < 1) requestAnimationFrame(step);
      else display.value = fmt(target);
    }
    requestAnimationFrame(step);
  }

  onMounted(animate);
  return { display, animate };
}
