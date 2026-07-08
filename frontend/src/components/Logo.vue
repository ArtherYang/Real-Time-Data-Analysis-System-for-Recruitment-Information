<template>
  <!-- 完整品牌 Logo：图标 + 艺术字 -->
  <svg v-if="showText" class="zhiyan-logo-text" :width="textWidth" height="40" viewBox="0 0 130 40" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="textGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#409EFF" />
        <stop offset="50%" stop-color="#5b8def" />
        <stop offset="100%" stop-color="#36cfc9" />
      </linearGradient>
      <linearGradient id="barGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#409EFF" />
        <stop offset="100%" stop-color="#36cfc9" />
      </linearGradient>
      <linearGradient id="barGrad2" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0%" stop-color="#1890ff" />
        <stop offset="100%" stop-color="#722ed1" />
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="1.5" result="blur" />
        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>
    <!-- 图标 -->
    <rect x="0" y="2" width="36" height="36" rx="9" fill="url(#barGrad)" />
    <rect x="4" y="4" width="28" height="28" rx="5" fill="#fff" opacity="0.95" />
    <rect x="10" y="22" width="3" height="6" rx="1.5" fill="#409EFF" />
    <rect x="15" y="16" width="3" height="12" rx="1.5" fill="#1890ff" />
    <rect x="20" y="10" width="3" height="18" rx="1.5" fill="url(#barGrad2)" />
    <circle cx="11.5" cy="20" r="1.2" fill="#722ed1" opacity="0.5"/>
    <circle cx="21.5" cy="8" r="1.2" fill="#36cfc9" opacity="0.7"/>
    <!-- 艺术字 "职" -->
    <text x="44" y="30" font-size="26" font-weight="900" fill="url(#textGrad)" filter="url(#glow)"
      font-family="'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif"
      letter-spacing="2">职</text>
    <!-- 艺术字 "言" -->
    <text x="76" y="30" font-size="26" font-weight="900" fill="url(#textGrad)" filter="url(#glow)"
      font-family="'Microsoft YaHei','PingFang SC','Noto Sans SC',sans-serif"
      letter-spacing="2">言</text>
  </svg>

  <!-- 仅图标（小尺寸使用） -->
  <svg v-else class="zhiyan-logo-icon" :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="iconGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#409EFF" />
        <stop offset="100%" stop-color="#36cfc9" />
      </linearGradient>
      <linearGradient id="iconGrad2" x1="0" y1="1" x2="1" y2="0">
        <stop offset="0%" stop-color="#1890ff" />
        <stop offset="100%" stop-color="#722ed1" />
      </linearGradient>
    </defs>
    <rect x="2" y="2" width="44" height="44" rx="10" fill="url(#iconGrad)" />
    <rect x="7" y="7" width="34" height="34" rx="6" fill="#fff" opacity="0.95" />
    <rect x="14" y="28" width="4" height="8" rx="2" fill="#409EFF" />
    <rect x="20" y="22" width="4" height="14" rx="2" fill="#1890ff" />
    <rect x="26" y="16" width="4" height="20" rx="2" fill="url(#iconGrad2)" />
    <circle cx="16" cy="26" r="1.5" fill="#722ed1" opacity="0.6"/>
    <circle cx="28" cy="14" r="1.5" fill="#36cfc9" opacity="0.8"/>
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 36 },
  showText: { type: Boolean, default: false },
  textWidth: { type: [Number, String], default: 130 },
});
</script>

<style scoped>
.zhiyan-logo-text,
.zhiyan-logo-icon {
  display: block;
  flex-shrink: 0;
}
</style>
