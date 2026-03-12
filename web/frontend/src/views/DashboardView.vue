<script setup>
/**
 * DashboardView — 团队大盘
 * 聚合所有已分析员工的统计数据、能力均值和贡献者卡片
 *
 * 交互：
 * - 默认展示全部贡献者的技术维度卡片
 * - 点击维度筛选按钮后，仅展示该方向 proportion > 0 的贡献者
 * - 再次点击同一按钮取消筛选
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/api'
import RadarChart from '@/components/RadarChart.vue'
import ContributorCard from '@/components/ContributorCard.vue'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import {
  Users,
  BarChart3,
  Clock,
  TrendingUp,
  Filter,
} from 'lucide-vue-next'

const loading = ref(true)
const dashData = ref(null)
const selectedDim = ref(null)  // 当前选中的技术维度 key（null = 显示全部）
const router = useRouter()

// 维度标签映射
const DIM_LABELS = {
  system_platform: '系统平台',
  driver_development: '底层驱动',
  application_software: '上层应用',
  wireless_communication: '无线通信',
  sqa_quality: 'SQA质量',
}

onMounted(async () => {
  try {
    dashData.value = await api.getAllAnalysis()
  } catch (e) {
    console.error('团队大盘加载失败:', e)
  } finally {
    loading.value = false
  }
})

// 有 profile 数据的员工列表
const contributors = computed(() => {
  if (!dashData.value) return []
  return (dashData.value.results || []).filter((r) => r.profile?.radar_outer)
})

// 聚合统计
const stats = computed(() => {
  if (!dashData.value) return null
  const results = dashData.value.results || []

  let totalIssues = 0
  let totalResolvedIssues = 0
  results.forEach((r) => {
    const issues = r.growth?.closed_loop_issues || []
    totalIssues += issues.length
    totalResolvedIssues += issues.filter((i) => i.status === 'resolved').length
  })

  return {
    totalEmployees: dashData.value.total_employees,
    analyzedCount: dashData.value.analyzed_count,
    totalIssues,
    totalResolvedIssues,
  }
})

// 聚合雷达图数据（基于 filteredContributors 取均值）
const avgProfile = computed(() => {
  const source = filteredContributors.value
  if (!source || source.length === 0) return null

  const dims = Object.keys(DIM_LABELS)

  const sumProportion = {}
  const sumDepth = {}
  dims.forEach((d) => {
    sumProportion[d] = 0
    sumDepth[d] = 0
  })

  let count = 0
  source.forEach((r) => {
    const outer = r.profile?.radar_outer
    if (!outer) return
    count++
    dims.forEach((d) => {
      if (outer[d]) {
        sumProportion[d] += outer[d].proportion || 0
        sumDepth[d] += outer[d].depth || 0
      }
    })
  })

  if (count === 0) return null

  const radarOuter = {}
  dims.forEach((d) => {
    radarOuter[d] = {
      proportion: sumProportion[d] / count,
      depth: Math.round(sumDepth[d] / count),
    }
  })

  return { radar_outer: radarOuter }
})

// 按选中维度筛选并排序贡献者（按该维度 proportion 降序）
const filteredContributors = computed(() => {
  if (!selectedDim.value) return contributors.value
  const dim = selectedDim.value
  return contributors.value
    .filter((r) => {
      const val = r.profile?.radar_outer?.[dim]
      return val && (val.proportion || 0) > 0
    })
    .sort((a, b) => {
      const pa = a.profile?.radar_outer?.[dim]?.proportion || 0
      const pb = b.profile?.radar_outer?.[dim]?.proportion || 0
      return pb - pa
    })
})

// 筛选状态描述
const filterLabel = computed(() => {
  const total = contributors.value.length
  const filtered = filteredContributors.value.length
  if (!selectedDim.value) {
    return `全部贡献者（${total} 人）`
  }
  return `${DIM_LABELS[selectedDim.value]}方向贡献者（${filtered} 人 / 共 ${total} 人）`
})

// 点击维度筛选按钮
function toggleDim(dimKey) {
  selectedDim.value = selectedDim.value === dimKey ? null : dimKey
}

// 点击贡献者姓名跳转个人画像
function goToPlayer(email) {
  router.push(`/player/${encodeURIComponent(email)}`)
}
</script>

<template>
  <div class="dashboard">
    <div class="page-header">
      <h1 class="page-header__title">团队大盘</h1>
      <p class="page-header__subtitle">全员能力画像聚合分析</p>
    </div>

    <LoadingOverlay v-if="loading" message="加载团队聚合数据..." />

    <template v-else-if="dashData">
      <!-- 统计卡片 -->
      <div class="grid grid--4">
        <div class="card stat-card">
          <div class="stat-card__label">
            <Users :size="14" :stroke-width="2" style="display: inline; vertical-align: middle;" />
            团队成员
          </div>
          <div class="stat-card__value">{{ stats?.totalEmployees || 0 }}</div>
        </div>

        <div class="card stat-card">
          <div class="stat-card__label">
            <BarChart3 :size="14" :stroke-width="2" style="display: inline; vertical-align: middle;" />
            已分析
          </div>
          <div class="stat-card__value">{{ stats?.analyzedCount || 0 }}</div>
          <div class="stat-card__note">
            覆盖率 {{ stats ? Math.round(stats.analyzedCount / stats.totalEmployees * 100) : 0 }}%
          </div>
        </div>

        <div class="card stat-card">
          <div class="stat-card__label">
            <TrendingUp :size="14" :stroke-width="2" style="display: inline; vertical-align: middle;" />
            技术攻坚
          </div>
          <div class="stat-card__value">{{ stats?.totalIssues || 0 }}</div>
          <div class="stat-card__note">闭环问题总数</div>
        </div>

        <div class="card stat-card">
          <div class="stat-card__label">
            <Clock :size="14" :stroke-width="2" style="display: inline; vertical-align: middle;" />
            已解决
          </div>
          <div class="stat-card__value">{{ stats?.totalResolvedIssues || 0 }}</div>
          <div class="stat-card__note">
            解决率 {{ stats?.totalIssues ? Math.round(stats.totalResolvedIssues / stats.totalIssues * 100) : 0 }}%
          </div>
        </div>
      </div>

      <!-- 聚合雷达图 + 维度筛选 -->
      <div v-if="avgProfile" class="dashboard__radar card" style="margin-top: var(--space-8);">
        <h3 class="player__section-title" style="margin-bottom: var(--space-4);">
          团队平均能力雷达
        </h3>

        <!-- 维度筛选按钮组 -->
        <div class="dashboard__dim-filters">
          <Filter :size="14" :stroke-width="2" style="color: var(--color-text-tertiary); flex-shrink: 0;" />
          <button
            v-for="(label, key) in DIM_LABELS"
            :key="key"
            class="dashboard__dim-pill"
            :class="{ 'dashboard__dim-pill--active': selectedDim === key }"
            @click="toggleDim(key)"
          >
            {{ label }}
          </button>
          <button
            v-if="selectedDim"
            class="dashboard__dim-pill dashboard__dim-pill--clear"
            @click="selectedDim = null"
          >
            清除筛选
          </button>
        </div>

        <div style="max-width: 500px; margin: 0 auto;">
          <RadarChart :profile-data="avgProfile" />
        </div>
      </div>

      <!-- 贡献者卡片网格 -->
      <div v-if="contributors.length > 0" class="dashboard__contributors" style="margin-top: var(--space-8);">
        <div class="dashboard__contributors-header">
          <h3 class="player__section-title">{{ filterLabel }}</h3>
          <p class="dashboard__contributors-hint">
            以下贡献者的数据构成了上方团队聚合雷达图
          </p>
        </div>

        <transition-group
          name="card-fade"
          tag="div"
          class="dashboard__contributors-grid"
        >
          <ContributorCard
            v-for="c in filteredContributors"
            :key="c.employee_email"
            :name="c.employee_name"
            :email="c.employee_email"
            :outer-data="c.profile?.radar_outer || {}"
            @click-name="goToPlayer"
          />
        </transition-group>

        <!-- 筛选无结果 -->
        <div v-if="filteredContributors.length === 0 && selectedDim" class="dashboard__no-result">
          <p>该方向暂无贡献者数据</p>
          <button class="dashboard__dim-pill" @click="selectedDim = null">
            显示全部
          </button>
        </div>
      </div>

      <!-- 无数据 -->
      <div v-else class="empty-state" style="margin-top: var(--space-8);">
        <BarChart3 class="empty-state__icon" :size="48" :stroke-width="1" />
        <h3 class="empty-state__title">暂无分析数据</h3>
        <p>请前往调度台对至少一位成员发起 AIGC 分析</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard__radar {
  padding: var(--space-8);
}

/* ── 维度筛选按钮组 ── */
.dashboard__dim-filters {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
  flex-wrap: wrap;
}

.dashboard__dim-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 14px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-secondary);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.dashboard__dim-pill:hover {
  border-color: var(--color-primary);
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.dashboard__dim-pill--active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: #ffffff;
}

.dashboard__dim-pill--active:hover {
  background: #A0360A;
  border-color: #A0360A;
  color: #ffffff;
}

.dashboard__dim-pill--clear {
  border-style: dashed;
  color: var(--color-text-tertiary);
}

/* ── 贡献者区域 ── */
.dashboard__contributors-header {
  margin-bottom: var(--space-5);
}

.dashboard__contributors-hint {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-top: var(--space-1);
}

.dashboard__contributors-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: var(--space-5);
}

.dashboard__no-result {
  text-align: center;
  padding: var(--space-8) 0;
  color: var(--color-text-tertiary);
}

.dashboard__no-result p {
  margin-bottom: var(--space-3);
}

/* ── 卡片动画 ── */
.card-fade-enter-active,
.card-fade-leave-active {
  transition: all 0.3s ease;
}

.card-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.card-fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

.card-fade-move {
  transition: transform 0.3s ease;
}
</style>
