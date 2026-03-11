<script setup>
/**
 * DashboardView — 团队大盘
 * 聚合所有已分析员工的统计数据和能力均值
 */
import { ref, onMounted, computed } from 'vue'
import api from '@/api'
import RadarChart from '@/components/RadarChart.vue'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import {
  Users,
  BarChart3,
  Clock,
  TrendingUp,
} from 'lucide-vue-next'

const loading = ref(true)
const dashData = ref(null)

onMounted(async () => {
  try {
    dashData.value = await api.getAllAnalysis()
  } catch (e) {
    console.error('团队大盘加载失败:', e)
  } finally {
    loading.value = false
  }
})

// 聚合统计
const stats = computed(() => {
  if (!dashData.value) return null
  const results = dashData.value.results || []

  // 总闭环问题数
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

// 聚合雷达图数据（取均值）
const avgProfile = computed(() => {
  if (!dashData.value) return null
  const results = dashData.value.results || []
  if (results.length === 0) return null

  const dims = [
    'system_platform', 'driver_development',
    'application_software', 'wireless_communication', 'sqa_quality',
  ]

  const sumProportion = {}
  const sumDepth = {}
  dims.forEach((d) => {
    sumProportion[d] = 0
    sumDepth[d] = 0
  })

  let count = 0
  results.forEach((r) => {
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

      <!-- 聚合雷达图 -->
      <div v-if="avgProfile" class="dashboard__radar card" style="margin-top: var(--space-8);">
        <h3 class="player__section-title" style="margin-bottom: var(--space-5);">
          团队平均能力雷达
        </h3>
        <div style="max-width: 500px; margin: 0 auto;">
          <RadarChart :profile-data="avgProfile" />
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
</style>
