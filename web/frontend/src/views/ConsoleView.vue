<script setup>
/**
 * ConsoleView — 数据调度台
 * 选择员工 → 时间范围 → 模型 → Token 预检 → 触发分析
 */
import { ref, watch, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import {
  Play,
  Gauge,
  AlertTriangle,
  CheckCircle,
  ArrowRight,
  Zap,
} from 'lucide-vue-next'

const router = useRouter()
const store = useAppStore()

const selectedEmail = ref('')
const ranges = ref([])
const selectedRanges = ref([])
const selectedModel = ref('')
const tokenEstimate = ref(null)
const analyzing = ref(false)
const analysisError = ref('')
const loadingRanges = ref(false)
const loadingTokens = ref(false)

onMounted(async () => {
  await Promise.all([store.fetchEmployees(), store.fetchModels()])
  if (store.enabledModels.length > 0) {
    selectedModel.value = store.enabledModels[0].model_id
  }
})

// 员工切换时加载时间范围
watch(selectedEmail, async (email) => {
  ranges.value = []
  selectedRanges.value = []
  tokenEstimate.value = null
  analysisError.value = ''
  if (!email) return

  loadingRanges.value = true
  try {
    ranges.value = await api.getRanges(email)
    // 默认全选
    selectedRanges.value = ranges.value.map((r) => r.id)
  } catch (e) {
    analysisError.value = `加载时间范围失败: ${e.message}`
  } finally {
    loadingRanges.value = false
  }
})

// 全选/取消全选
const allSelected = computed(() =>
  ranges.value.length > 0 && selectedRanges.value.length === ranges.value.length,
)

function toggleAll() {
  if (allSelected.value) {
    selectedRanges.value = []
  } else {
    selectedRanges.value = ranges.value.map((r) => r.id)
  }
}

/**
 * 按时间段快速筛选周报（近 N 个月）
 * 根据 range.end 日期与当前日期比较实现
 */
const quickFilters = [
  { label: '近一季度', months: 3 },
  { label: '近两季度', months: 6 },
  { label: '近三季度', months: 9 },
  { label: '近一年', months: 12 },
]

function selectByMonths(months) {
  const now = new Date()
  const cutoff = new Date(now)
  cutoff.setMonth(cutoff.getMonth() - months)
  const cutoffStr = cutoff.toISOString().slice(0, 10)

  selectedRanges.value = ranges.value
    .filter((r) => r.end >= cutoffStr)
    .map((r) => r.id)
  tokenEstimate.value = null
}

function toggleRange(id) {
  const idx = selectedRanges.value.indexOf(id)
  if (idx >= 0) {
    selectedRanges.value.splice(idx, 1)
  } else {
    selectedRanges.value.push(id)
  }
  tokenEstimate.value = null
}

// Token 预估
async function estimateTokens() {
  if (!selectedEmail.value || selectedRanges.value.length === 0) return
  loadingTokens.value = true
  tokenEstimate.value = null
  try {
    tokenEstimate.value = await api.estimateTokens(
      selectedEmail.value,
      selectedRanges.value,
      selectedModel.value,
    )
  } catch (e) {
    analysisError.value = `Token 预估失败: ${e.message}`
  } finally {
    loadingTokens.value = false
  }
}

// 执行分析
async function runAnalysis() {
  if (!selectedEmail.value || selectedRanges.value.length === 0) return
  analyzing.value = true
  analysisError.value = ''

  try {
    const result = await api.runFullAnalysis(
      selectedEmail.value,
      selectedRanges.value,
      selectedModel.value,
    )
    store.setCurrentAnalysis(result)
    router.push(`/player/${encodeURIComponent(selectedEmail.value)}`)
  } catch (e) {
    if (e.needConfig) {
      analysisError.value = `需要配置 API Key，请前往「模型配置」页面设置。`
    } else {
      analysisError.value = `分析失败: ${e.message}`
    }
  } finally {
    analyzing.value = false
  }
}

// Token 水位线颜色
const tokenLevelClass = computed(() => {
  if (!tokenEstimate.value) return ''
  const level = tokenEstimate.value.level
  if (level === 'green') return 'badge--success'
  if (level === 'yellow') return 'badge--warning'
  return 'badge--danger'
})
</script>

<template>
  <div class="console">
    <!-- 全屏加载遮罩 -->
    <LoadingOverlay
      v-if="analyzing"
      fullscreen
      message="AIGC 深度分析中，请稍候片刻..."
    />

    <div class="page-header">
      <h1 class="page-header__title">数据调度台</h1>
      <p class="page-header__subtitle">选择员工与周报时段，触发 AIGC 画像分析</p>
    </div>

    <!-- 配置表单 -->
    <div class="console__form card">
      <!-- 员工选择 -->
      <div class="form-group">
        <label class="form-label">选择员工</label>
        <select v-model="selectedEmail" class="form-select">
          <option value="" disabled>请选择...</option>
          <option
            v-for="emp in store.employees"
            :key="emp.email"
            :value="emp.email"
          >
            {{ emp.name }} ({{ emp.email }})
          </option>
        </select>
      </div>

      <!-- 模型选择 -->
      <div class="form-group">
        <label class="form-label">分析模型</label>
        <select v-model="selectedModel" class="form-select">
          <option
            v-for="model in store.enabledModels"
            :key="model.model_id"
            :value="model.model_id"
          >
            {{ model.display_name || model.model_id }}
            {{ model.api_key ? '' : '(未配置 Key)' }}
          </option>
        </select>
      </div>

      <!-- 时间范围 -->
      <div v-if="selectedEmail" class="form-group">
        <div class="console__range-header">
          <label class="form-label" style="margin-bottom: 0">
            周报时段
            <span class="console__range-count" v-if="ranges.length">
              {{ selectedRanges.length }} / {{ ranges.length }}
            </span>
          </label>
          <div v-if="ranges.length" class="console__quick-btns">
            <button
              class="btn btn--ghost btn--sm"
              @click="toggleAll"
            >
              {{ allSelected ? '取消全选' : '全选' }}
            </button>
            <button
              v-for="qf in quickFilters"
              :key="qf.months"
              class="btn btn--ghost btn--sm"
              @click="selectByMonths(qf.months)"
            >
              {{ qf.label }}
            </button>
          </div>
        </div>

        <div v-if="loadingRanges" style="padding: 16px 0;">
          <div class="spinner"></div>
        </div>

        <div v-else-if="ranges.length" class="console__ranges">
          <label
            v-for="r in ranges"
            :key="r.id"
            class="console__range-item"
            :class="{ 'console__range-item--selected': selectedRanges.includes(r.id) }"
          >
            <input
              type="checkbox"
              :value="r.id"
              :checked="selectedRanges.includes(r.id)"
              @change="toggleRange(r.id)"
            />
            <span>{{ r.start }} ~ {{ r.end }}</span>
          </label>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="console__actions">
        <button
          class="btn btn--secondary"
          :disabled="!selectedEmail || selectedRanges.length === 0 || loadingTokens"
          @click="estimateTokens"
        >
          <Gauge :size="16" :stroke-width="2" />
          {{ loadingTokens ? '预估中...' : 'Token 预检' }}
        </button>

        <button
          class="btn btn--primary btn--lg"
          :disabled="!selectedEmail || selectedRanges.length === 0 || analyzing"
          @click="runAnalysis"
        >
          <Zap :size="16" :stroke-width="2" />
          启动分析
          <ArrowRight :size="16" :stroke-width="2" />
        </button>
      </div>

      <!-- Token 预估结果 -->
      <div v-if="tokenEstimate" class="console__token-result card">
        <div class="console__token-row">
          <span class="console__token-label">Token 数量</span>
          <span class="console__token-value">
            {{ tokenEstimate.token_count?.toLocaleString() }}
          </span>
        </div>
        <div class="console__token-row">
          <span class="console__token-label">模型上限</span>
          <span class="console__token-value">
            {{ tokenEstimate.model_limit?.toLocaleString() }}
          </span>
        </div>
        <div class="console__token-row">
          <span class="console__token-label">使用率</span>
          <span class="badge" :class="tokenLevelClass">
            {{ tokenEstimate.utilization_pct }}%
            {{ tokenEstimate.level_label }}
          </span>
        </div>
      </div>

      <!-- 错误提示 -->
      <div v-if="analysisError" class="console__error">
        <AlertTriangle :size="16" :stroke-width="2" />
        {{ analysisError }}
        <button
          v-if="analysisError.includes('API Key')"
          class="btn btn--sm btn--ghost"
          @click="router.push('/settings')"
        >
          前往配置 →
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.console__form {
  max-width: 640px;
}

.console__range-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.console__range-count {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  font-weight: 400;
  margin-left: var(--space-2);
}

.console__quick-btns {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.console__ranges {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-2);
  max-height: 280px;
  overflow-y: auto;
  padding: var(--space-1);
}

.console__range-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.console__range-item:hover {
  border-color: var(--color-primary-subtle);
}

.console__range-item--selected {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
}

.console__range-item input[type="checkbox"] {
  accent-color: var(--color-primary);
}

.console__actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-6);
  padding-top: var(--space-6);
  border-top: 1px solid var(--color-border-light);
}

.console__token-result {
  margin-top: var(--space-5);
  background: var(--color-surface);
  padding: var(--space-4);
}

.console__token-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-2) 0;
}

.console__token-row + .console__token-row {
  border-top: 1px solid var(--color-border-light);
}

.console__token-label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.console__token-value {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: var(--text-base);
}

.console__error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
  background: var(--color-danger-light);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
}
</style>
