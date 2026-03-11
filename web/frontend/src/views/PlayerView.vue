<script setup>
/**
 * PlayerView — 个人能力画像
 * 3D 统一图谱 + 打分面板 + 总评 + 故事线 + FAQ Chat
 */
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import AbilityChart3D from '@/components/AbilityChart3D.vue'
import ScorePanel from '@/components/ScorePanel.vue'
import TimelineCard from '@/components/TimelineCard.vue'
import ChatWidget from '@/components/ChatWidget.vue'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import {
  ArrowLeft,
  TrendingUp,
  AlertCircle,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()
const store = useAppStore()

const loading = ref(true)
const error = ref('')
const data = ref(null)

const email = computed(() => decodeURIComponent(route.params.email))

onMounted(async () => {
  try {
    const queryFile = route.query.file

    if (queryFile) {
      data.value = await api.getAnalysisByFile(email.value, queryFile)
    } else if (store.currentAnalysis?.employee_email === email.value) {
      data.value = store.currentAnalysis
    } else {
      data.value = await api.getLatestAnalysis(email.value)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const name = computed(() => data.value?.employee_name || email.value.split('@')[0])
const profile = computed(() => data.value?.profile || {})
const growth = computed(() => data.value?.growth || {})
const outerRadar = computed(() => profile.value.radar_outer || {})
const innerRadar = computed(() => profile.value.radar_inner || {})
const issues = computed(() => growth.value.closed_loop_issues || [])
const recursiveLogic = computed(() => growth.value.growth_analysis?.recursive_logic || [])

/** 日期范围压缩显示 */
function compressDateRanges(rangeIds) {
  if (!rangeIds || rangeIds.length === 0) return '无'
  const allDates = []
  rangeIds.forEach((id) => {
    const parts = id.split('_')
    if (parts.length >= 2) {
      allDates.push(parts[0], parts[parts.length - 1])
    }
  })
  allDates.sort()
  return `${allDates[0]} ~ ${allDates[allDates.length - 1]}（共 ${rangeIds.length} 份周报）`
}
</script>

<template>
  <div class="player">
    <LoadingOverlay v-if="loading" :message="`正在加载 ${email} 的档案...`" />

    <!-- 错误状态 -->
    <div v-else-if="error" class="player__error card">
      <AlertCircle :size="24" :stroke-width="1.8" class="player__error-icon" />
      <h3>加载失败</h3>
      <p>{{ error }}</p>
      <button class="btn btn--primary" @click="router.push('/console')">
        返回调度台
      </button>
    </div>

    <!-- 正常内容 -->
    <template v-else-if="data">
      <!-- 顶部导航 -->
      <div class="player__nav">
        <button class="btn btn--ghost" @click="router.push('/roster')">
          <ArrowLeft :size="16" :stroke-width="2" />
          返回英雄榜
        </button>
      </div>

      <!-- 页面标题 -->
      <div class="page-header">
        <h1 class="page-header__title">{{ name }}</h1>
        <p class="page-header__subtitle">
          {{ compressDateRanges(data.date_range_ids) }}
          <span v-if="data.model_id" class="player__model-tag">
            · {{ data.model_id.split('/').pop() }}
          </span>
        </p>
      </div>

      <!-- 3D 统一能力图谱 -->
      <div class="card player__chart-card">
        <h3 class="player__section-title">统一能力图谱</h3>
        <p class="player__chart-hint">拖拽旋转视角 · 悬停查看数值 · 中心三层浮岛为工程素养基石</p>
        <AbilityChart3D
          :outer-data="outerRadar"
          :inner-data="innerRadar"
        />
      </div>

      <!-- 打分解释面板 -->
      <ScorePanel
        :outer-data="outerRadar"
        :inner-data="innerRadar"
      />

      <!-- 执行力总评 -->
      <div class="card" v-if="profile.summary">
        <h3 class="player__section-title">执行力总评</h3>
        <p class="player__summary">
          {{ profile.summary }}
        </p>
      </div>

      <!-- 技术攻坚故事线 -->
      <div class="player__section" v-if="issues.length > 0">
        <h2 class="player__section-heading">
          <TrendingUp :size="20" :stroke-width="2" />
          技术攻坚故事线
          <span class="player__section-count">{{ issues.length }}</span>
        </h2>

        <div class="player__timeline">
          <TimelineCard
            v-for="(issue, idx) in issues"
            :key="idx"
            :issue="issue"
            :is-last="idx === issues.length - 1"
          />
        </div>
      </div>

      <!-- 成长递进分析 -->
      <div class="player__section" v-if="recursiveLogic.length > 0">
        <h2 class="player__section-heading">成长递进分析</h2>
        <div class="player__growth-list">
          <div
            v-for="(item, idx) in recursiveLogic"
            :key="idx"
            class="card player__growth-item"
          >
            <div class="player__growth-header">
              <h4>{{ item.task_name }}</h4>
              <span class="badge badge--primary">{{ item.label }}</span>
            </div>
            <p v-if="item.evidence_period" class="player__growth-period">
              {{ item.evidence_period }}
            </p>
            <ul v-if="item.reasoning_chain?.length" class="player__growth-chain">
              <li v-for="(step, i) in item.reasoning_chain" :key="i">{{ step }}</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- FAQ Chat 浮窗 -->
      <ChatWidget
        :employee-name="name"
        :employee-email="data.employee_email"
        :date-range-ids="data.date_range_ids || []"
        :model-id="data.model_id || ''"
      />
    </template>
  </div>
</template>

<style scoped>
.player__nav {
  margin-bottom: var(--space-4);
}

.player__model-tag {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
}

.player__section-title {
  font-size: var(--text-md);
  font-weight: 600;
  margin-bottom: var(--space-5);
  color: var(--color-text);
}

.player__chart-card {
  overflow: hidden;
  padding: 0;
}

.player__chart-card .player__section-title {
  padding: var(--space-4) var(--space-5) 0;
}

.player__chart-hint {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: calc(-1 * var(--space-3));
  margin-bottom: var(--space-3);
}

/* ── 总评 ── */
.player__summary {
  font-size: var(--text-base);
  color: var(--color-text);
  line-height: 1.8;
  background: var(--color-surface);
  padding: var(--space-4);
  border-radius: var(--radius-md);
}

/* ── 故事线区域 ── */
.player__section {
  margin-top: var(--space-10);
}

.player__section-heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-xl);
  font-weight: 600;
  margin-bottom: var(--space-6);
  color: var(--color-text);
}

.player__section-count {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-tertiary);
  margin-left: var(--space-1);
}

.player__timeline {
  max-width: 800px;
}

/* ── 成长递进 ── */
.player__growth-list {
  display: grid;
  gap: var(--space-4);
}

.player__growth-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.player__growth-header h4 {
  font-size: var(--text-base);
  font-weight: 600;
}

.player__growth-period {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.player__growth-chain {
  padding-left: var(--space-5);
  list-style: decimal;
}

.player__growth-chain li {
  font-size: var(--text-base);
  color: var(--color-text);
  line-height: 1.6;
  margin-bottom: var(--space-1);
}

/* ── 错误状态 ── */
.player__error {
  max-width: 480px;
  margin: var(--space-16) auto;
  text-align: center;
  padding: var(--space-10);
}

.player__error-icon {
  color: var(--color-danger);
  margin-bottom: var(--space-4);
}

.player__error h3 {
  font-size: var(--text-lg);
  margin-bottom: var(--space-2);
}

.player__error p {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-6);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .player__profile {
    grid-template-columns: 1fr;
  }
}
</style>
