<template>
  <div class="data-import-button">
    <button
      class="import-btn"
      :class="{ importing: isImporting, done: isDone, error: isError }"
      :disabled="isImporting"
      @click="startImport"
    >
      <span class="btn-icon">{{ isImporting ? '⏳' : isDone ? '✅' : isError ? '❌' : '📂' }}</span>
      {{ buttonText }}
    </button>

    <!-- 进度提示 -->
    <div v-if="isImporting" class="import-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
      </div>
      <div class="progress-text">{{ statusText }}</div>
    </div>

    <!-- 完成提示 -->
    <div v-if="showResult" class="result-toast" :class="{ fade: fadeResult }">
      🎉 {{ resultMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const emit = defineEmits(['import-complete'])

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1'

const isImporting = ref(false)
const isDone = ref(false)
const isError = ref(false)
const progressPct = ref(0)
const statusText = ref('')
const resultMessage = ref('')
const showResult = ref(false)
const fadeResult = ref(false)

let progressTimer = null
let fadeTimer = null

const buttonText = computed(() => {
  if (isImporting.value) return '导入中...'
  if (isDone.value) return '导入完成'
  if (isError.value) return '导入失败，重试'
  return '📂 导入公开数据集'
})

async function startImport() {
  isImporting.value = true
  isDone.value = false
  isError.value = false
  progressPct.value = 0
  showResult.value = false

  // 模拟进度（因为导入很快，加个进度动画）
  statusText.value = '正在读取 大模型岗位信息.csv（5,333 条）...'
  progressPct.value = 10

  progressTimer = setInterval(() => {
    if (progressPct.value < 90) {
      progressPct.value += Math.random() * 20 + 5
      if (progressPct.value > 30) {
        statusText.value = '正在解析字段并写入数据库...'
      }
      if (progressPct.value > 60) {
        statusText.value = '正在建立索引...'
      }
    }
  }, 300)

  try {
    const resp = await fetch(`${API_BASE}/data/import-csv`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ batch_size: 500 }),
    })
    const result = await resp.json()

    clearInterval(progressTimer)
    progressPct.value = 100
    isImporting.value = false

    if (result.code === 200) {
      isDone.value = true
      const d = result.data || result
      resultMessage.value = `导入完成！${d.imported || 0} 条数据，耗时 ${d.time_seconds || '?'} 秒`
      showResult.value = true
      emit('import-complete')
    } else {
      isError.value = true
      resultMessage.value = '导入失败：' + (result.message || '未知错误')
      showResult.value = true
    }

    fadeTimer = setTimeout(() => { fadeResult.value = true }, 4000)
    setTimeout(() => { showResult.value = false; isDone.value = false; isError.value = false }, 5000)
  } catch (e) {
    clearInterval(progressTimer)
    isImporting.value = false
    isError.value = true
    resultMessage.value = '请求失败: ' + e.message
    showResult.value = true
    fadeTimer = setTimeout(() => { fadeResult.value = true }, 4000)
  }
}

onBeforeUnmount(() => {
  clearInterval(progressTimer)
  clearTimeout(fadeTimer)
})
</script>

<style scoped>
.data-import-button {
  display: inline-flex;
  flex-direction: column;
  gap: 8px;
  align-items: flex-start;
}

.import-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 22px;
  border: 2px solid #10b981;
  border-radius: 10px;
  background: linear-gradient(135deg, #10b981, #059669);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.35);
}

.import-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(16, 185, 129, 0.5);
}

.import-btn.importing {
  background: linear-gradient(135deg, #f59e0b, #f97316);
  border-color: #f59e0b;
  cursor: wait;
}

.import-btn.done {
  background: linear-gradient(135deg, #10b981, #34d399);
  border-color: #10b981;
}

.import-btn.error {
  background: linear-gradient(135deg, #ef4444, #f87171);
  border-color: #ef4444;
}

.btn-icon {
  font-size: 18px;
}

.import-progress {
  width: 300px;
}

.progress-bar {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-text {
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
