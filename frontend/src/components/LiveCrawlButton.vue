<template>
  <div class="live-crawl-button">
    <button
      class="crawl-btn"
      :class="{ running: isRunning, completed: isCompleted, failed: isFailed }"
      :disabled="isRunning"
      @click="startCrawl"
    >
      <span class="btn-icon">{{ isRunning ? '⏳' : isCompleted ? '✅' : isFailed ? '❌' : '🔄' }}</span>
      {{ buttonText }}
    </button>

    <div v-if="isRunning" class="progress-bar-wrap">
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: progressPct + '%' }"
        ></div>
      </div>
      <div class="progress-detail">
        {{ progressPct }}% —
        关键词: {{ currentKeyword || '...' }} ({{ currentPage || 0 }}/{{ totalPages }}页)
        — {{ completedKeywords }}/{{ totalKeywords }} 完成
      </div>
    </div>

    <div v-if="lastResult" class="result-toast" :class="{ fade: fadeToast }">
      🎉 采集完成！
      新增 {{ lastResult.total_saved }} 条，
      有效率 {{ cleanRate }}%
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const emit = defineEmits(['refresh-complete'])

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

const isRunning = ref(false)
const isCompleted = ref(false)
const isFailed = ref(false)
const progressPct = ref(0)
const currentKeyword = ref('')
const currentPage = ref(0)
const totalPages = ref(3)
const completedKeywords = ref(0)
const totalKeywords = ref(5)
const lastResult = ref(null)
const fadeToast = ref(false)

let pollTimer = null
let fadeTimer = null

const buttonText = computed(() => {
  if (isRunning.value) return '采集中...'
  if (isCompleted.value) return '采集完成'
  if (isFailed.value) return '采集失败，重试'
  return '实时采集数据'
})

const cleanRate = computed(() => {
  if (!lastResult.value) return 0
  const { total_crawled, total_valid } = lastResult.value
  return total_crawled > 0 ? Math.round((total_valid / total_crawled) * 100) : 0
})

async function startCrawl() {
  isRunning.value = true
  isCompleted.value = false
  isFailed.value = false
  progressPct.value = 0
  lastResult.value = null
  fadeToast.value = false

  try {
    const resp = await fetch(`${API_BASE}/data/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pages: totalPages.value }),
    })
    const { data } = await resp.json()
    if (!data?.task_id) throw new Error('未获取到 task_id')

    pollProgress(data.task_id)
  } catch (e) {
    isRunning.value = false
    isFailed.value = true
    console.error('采集启动失败:', e)
  }
}

async function pollProgress(taskId) {
  try {
    const resp = await fetch(`${API_BASE}/data/refresh/${taskId}/progress`)
    const { data } = await resp.json()
    if (!data) return

    progressPct.value = data.progress_pct || 0
    currentKeyword.value = data.current_keyword || ''
    currentPage.value = data.current_page || 0
    totalPages.value = data.pages || 3
    totalKeywords.value = data.keywords?.length || 5
    completedKeywords.value = data.result?.completed_keywords?.length || 0

    if (data.status === 'completed') {
      isRunning.value = false
      isCompleted.value = true
      lastResult.value = data.result
      showToast()
      emit('refresh-complete')
      return
    }

    if (data.status === 'failed') {
      isRunning.value = false
      isFailed.value = true
      console.error('采集失败:', data.error)
      return
    }

    // 继续轮询
    pollTimer = setTimeout(() => pollProgress(taskId), 1000)
  } catch (e) {
    console.error('进度轮询失败:', e)
    pollTimer = setTimeout(() => pollProgress(taskId), 2000)
  }
}

function showToast() {
  fadeToast.value = false
  fadeTimer = setTimeout(() => {
    fadeToast.value = true
  }, 5000)

  setTimeout(() => {
    lastResult.value = null
    isCompleted.value = false
  }, 8000)
}

onBeforeUnmount(() => {
  clearTimeout(pollTimer)
  clearTimeout(fadeTimer)
})
</script>

<style scoped>
.live-crawl-button {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.crawl-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px;
  border: 2px solid #6366f1;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.35);
}

.crawl-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(99, 102, 241, 0.5);
}

.crawl-btn.running {
  background: linear-gradient(135deg, #f59e0b, #f97316);
  border-color: #f59e0b;
  cursor: wait;
  animation: pulse 1.5s ease-in-out infinite;
}

.crawl-btn.completed {
  background: linear-gradient(135deg, #10b981, #34d399);
  border-color: #10b981;
}

.crawl-btn.failed {
  background: linear-gradient(135deg, #ef4444, #f87171);
  border-color: #ef4444;
}

.btn-icon {
  font-size: 18px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.75; }
}

.progress-bar-wrap {
  width: 320px;
}

.progress-bar {
  height: 10px;
  background: #e2e8f0;
  border-radius: 5px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 5px;
  transition: width 0.4s ease;
}

.progress-detail {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}

.result-toast {
  padding: 10px 16px;
  background: #ecfdf5;
  border: 1px solid #10b981;
  border-radius: 8px;
  color: #065f46;
  font-size: 14px;
  font-weight: 500;
  transition: opacity 1s ease;
}

.result-toast.fade {
  opacity: 0;
}
</style>
