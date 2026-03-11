<script setup>
/**
 * RosterView — 英雄榜
 * 卡片网格展示全员 + 缓存状态 + 历史版本
 */
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import LoadingOverlay from '@/components/LoadingOverlay.vue'
import {
  User,
  CheckCircle2,
  Clock,
  ChevronDown,
  FileText,
} from 'lucide-vue-next'

const router = useRouter()
const store = useAppStore()

const loading = ref(true)
const historyMap = ref({}) // { email: [{filename, generated_at, model_id, ...}] }
const expandedEmail = ref('')

onMounted(async () => {
  await Promise.all([
    store.fetchEmployees(),
    store.fetchAnalysisStatus(),
  ])

  // 预加载有缓存的员工的历史版本列表
  for (const emp of store.employees) {
    if (store.hasCache(emp.email)) {
      try {
        historyMap.value[emp.email] = await api.getAnalysisHistory(emp.email)
      } catch { /* 静默忽略 */ }
    }
  }
  loading.value = false
})

function goToPlayer(email) {
  router.push(`/player/${encodeURIComponent(email)}`)
}

function toggleHistory(email, event) {
  event.stopPropagation()
  expandedEmail.value = expandedEmail.value === email ? '' : email
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  return dateStr.replace('T', ' ').substring(0, 16)
}

/** 将 date_range_ids 压缩为起止日期摘要 */
function compressDateRanges(rangeIds) {
  if (!rangeIds || rangeIds.length === 0) return ''
  const allDates = []
  rangeIds.forEach((id) => {
    const parts = id.split('_')
    if (parts.length >= 2) {
      allDates.push(parts[0], parts[parts.length - 1])
    }
  })
  allDates.sort()
  return `${allDates[0]} ~ ${allDates[allDates.length - 1]} · ${rangeIds.length}周`
}

/** 点击历史版本，带 filename query 参数跳转到 PlayerView */
function goToHistoryVersion(email, filename, event) {
  event.stopPropagation()
  router.push({
    path: `/player/${encodeURIComponent(email)}`,
    query: { file: filename },
  })
}
</script>

<template>
  <div class="roster">
    <div class="page-header">
      <h1 class="page-header__title">英雄榜</h1>
      <p class="page-header__subtitle">
        {{ store.employees.length }} 位团队成员 ·
        {{ Object.values(store.analysisStatus).filter(Boolean).length }} 位已分析
      </p>
    </div>

    <LoadingOverlay v-if="loading" message="加载团队数据..." />

    <div v-else class="roster__grid">
      <div
        v-for="emp in store.employees"
        :key="emp.email"
        class="roster__card card card--interactive"
        @click="store.hasCache(emp.email) ? goToPlayer(emp.email) : null"
        :class="{ 'roster__card--cached': store.hasCache(emp.email) }"
      >
        <!-- 头部 -->
        <div class="roster__card-header">
          <div class="roster__avatar">
            <User :size="20" :stroke-width="1.8" />
          </div>
          <div class="roster__info">
            <h3 class="roster__name">{{ emp.name }}</h3>
            <p class="roster__email">{{ emp.email }}</p>
          </div>
          <CheckCircle2
            v-if="store.hasCache(emp.email)"
            :size="18"
            :stroke-width="2"
            class="roster__check"
          />
        </div>

        <!-- 状态 -->
        <div class="roster__status">
          <span
            class="badge"
            :class="store.hasCache(emp.email) ? 'badge--success' : 'badge--neutral'"
          >
            {{ store.hasCache(emp.email) ? '已分析' : '未分析' }}
          </span>

          <!-- 历史版本按钮 -->
          <button
            v-if="historyMap[emp.email]?.length > 0"
            class="btn btn--ghost btn--sm"
            @click="toggleHistory(emp.email, $event)"
          >
            <FileText :size="13" :stroke-width="1.8" />
            {{ historyMap[emp.email].length }} 份
            <ChevronDown
              :size="13"
              :stroke-width="2"
              :class="{ 'rotate-180': expandedEmail === emp.email }"
              style="transition: transform 0.2s;"
            />
          </button>
        </div>

        <!-- 历史版本列表 -->
        <Transition name="slide-fade">
          <div
            v-if="expandedEmail === emp.email && historyMap[emp.email]?.length > 0"
            class="roster__history"
          >
            <div
              v-for="h in historyMap[emp.email]"
              :key="h.filename"
              class="roster__history-item roster__history-item--clickable"
              @click="goToHistoryVersion(emp.email, h.filename, $event)"
              :title="`查看 ${h.filename}`"
            >
              <div class="roster__history-row">
                <Clock :size="12" :stroke-width="1.8" />
                <span>{{ formatDate(h.generated_at) }}</span>
                <span class="roster__history-model">{{ h.model_id?.split('/').pop() }}</span>
                <span class="roster__history-time">{{ h.elapsed_seconds?.toFixed(0) }}s</span>
              </div>
              <div v-if="h.date_range_ids?.length" class="roster__history-range">
                {{ compressDateRanges(h.date_range_ids) }}
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.roster__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--space-5);
}

.roster__card {
  transition: all var(--transition-base);
}

.roster__card:not(.roster__card--cached) {
  opacity: 0.6;
  cursor: default;
}

.roster__card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.roster__avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-lg);
  background: var(--color-surface);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.roster__card--cached .roster__avatar {
  background: var(--color-primary-light);
  color: var(--color-primary);
}

.roster__info {
  flex: 1;
  min-width: 0;
}

.roster__name {
  font-size: var(--text-base);
  font-weight: 600;
}

.roster__email {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.roster__check {
  color: var(--color-success);
  flex-shrink: 0;
}

.roster__status {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.roster__history {
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.roster__history-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
}

.roster__history-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.roster__history-item--clickable {
  cursor: pointer;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast);
}

.roster__history-item--clickable:hover {
  background: var(--color-primary-light);
  color: var(--color-primary);
}

.roster__history-model {
  margin-left: auto;
  font-family: var(--font-mono);
  font-size: 11px;
}

.roster__history-time {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.roster__history-range {
  font-size: 10px;
  color: var(--color-text-tertiary);
  padding-left: 20px;
  font-family: var(--font-mono);
}

.rotate-180 {
  transform: rotate(180deg);
}
</style>
