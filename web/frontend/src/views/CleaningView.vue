<script setup>
/**
 * CleaningView — 数据清洗状态总览
 * 展示清洗管线的运行结果、员工周报分布、加密文件清单
 */
import { ref, computed, onMounted } from 'vue'
import api from '@/api'
import {
  FileSearch,
  Lock,
  ChevronDown,
  ChevronRight,
  FileWarning,
  CheckCircle,
  AlertTriangle,
} from 'lucide-vue-next'

const report = ref(null)
const loading = ref(true)
const error = ref('')

/** 加密文件折叠状态 { email: boolean } */
const expandedEncrypted = ref({})

onMounted(async () => {
  try {
    report.value = await api.getCleaningReport()
  } catch (e) {
    error.value = e.message || '加载清洗报告失败'
  } finally {
    loading.value = false
  }
})

/** 概览统计卡片数据 */
const statCards = computed(() => {
  if (!report.value) return []
  const r = report.value
  return [
    { label: '总文件数', value: r.total_files, note: '原始 Excel 附件' },
    { label: '有效文件', value: r.valid_files, note: `已过滤 ${r.filtered_files} 份` },
    { label: '去重后 Sheet 数', value: r.deduplicated_sheets, note: `去重率 ${r.dedup_rate}` },
    { label: '加密文件', value: r.encrypted_files, note: '无法读取', danger: r.encrypted_files > 0 },
  ]
})

/** 所有员工的最大/最小/中位数周报数 */
const reportStats = computed(() => {
  if (!report.value?.employees?.length) return null
  const counts = report.value.employees.map((e) => e.report_count)
  const sorted = [...counts].sort((a, b) => a - b)
  const max = sorted[sorted.length - 1]
  const min = sorted[0]
  const mid = sorted[Math.floor(sorted.length / 2)]
  return { max, min, mid }
})

/**
 * 根据周报数量返回状态标签
 *  - 中位数 ×0.6 以下 → 严重缺失
 *  - 中位数 ×0.8 以下 → 偏少
 *  - 否则 → 正常
 */
function getStatusBadge(count) {
  const stats = reportStats.value
  if (!stats) return { label: '—', cls: 'badge--neutral' }
  if (count <= stats.mid * 0.6) return { label: '严重缺失', cls: 'badge--danger' }
  if (count <= stats.mid * 0.8) return { label: '偏少', cls: 'badge--warning' }
  return { label: '正常', cls: 'badge--success' }
}

/** 计算某员工的加密文件数 */
function encryptedCount(email) {
  return report.value?.encrypted_by_employee?.[email]?.length || 0
}

/** 切换加密文件折叠 */
function toggleEncrypted(email) {
  expandedEncrypted.value[email] = !expandedEncrypted.value[email]
}

/** 加密分组的邮箱列表（有数据的优先展示） */
const encryptedEmails = computed(() => {
  if (!report.value?.encrypted_by_employee) return []
  return Object.keys(report.value.encrypted_by_employee).sort()
})

/** 从文件名中提取简短的日期区间 */
function extractDateFromFilename(filename) {
  const match = filename.match(/\d{4}年\d{1,2}月\d{1,2}日?[~\-—至]*\d{4}年\d{1,2}月\d{1,2}日?/)
  return match ? match[0] : filename
}
</script>

<template>
  <div class="cleaning">
    <div class="page-header">
      <h1 class="page-header__title">数据清洗状态</h1>
      <p class="page-header__subtitle">管线清洗结果总览，快速定位周报缺失与加密异常</p>
    </div>

    <!-- 加载 -->
    <div v-if="loading" class="loading-center">
      <div class="spinner spinner--lg"></div>
    </div>

    <!-- 错误 -->
    <div v-else-if="error" class="cleaning__error">
      <AlertTriangle :size="18" :stroke-width="2" />
      {{ error }}
    </div>

    <!-- 内容 -->
    <template v-else-if="report">
      <!-- 概览统计卡片 -->
      <div class="grid grid--4 cleaning__stats">
        <div
          v-for="(stat, i) in statCards"
          :key="i"
          class="card stat-card fade-in"
          :style="{ animationDelay: `${i * 80}ms` }"
        >
          <div class="stat-card__label">{{ stat.label }}</div>
          <div
            class="stat-card__value"
            :class="{ 'stat-card__value--danger': stat.danger }"
          >
            {{ stat.value }}
          </div>
          <div class="stat-card__note">{{ stat.note }}</div>
        </div>
      </div>

      <!-- 管线指标条 -->
      <div class="card cleaning__pipeline-bar fade-in" style="animation-delay: 320ms">
        <div class="cleaning__pipeline-item">
          <span class="cleaning__pipeline-label">Sheet 总数</span>
          <span class="cleaning__pipeline-value">{{ report.total_sheets }}</span>
        </div>
        <div class="cleaning__pipeline-sep"></div>
        <div class="cleaning__pipeline-item">
          <span class="cleaning__pipeline-label">重复组</span>
          <span class="cleaning__pipeline-value">{{ report.duplicate_groups }}</span>
        </div>
        <div class="cleaning__pipeline-sep"></div>
        <div class="cleaning__pipeline-item">
          <span class="cleaning__pipeline-label">去重率</span>
          <span class="badge badge--primary">{{ report.dedup_rate }}</span>
        </div>
        <div class="cleaning__pipeline-sep"></div>
        <div class="cleaning__pipeline-item">
          <span class="cleaning__pipeline-label">损坏文件</span>
          <span
            class="badge"
            :class="report.corrupted_files > 0 ? 'badge--danger' : 'badge--success'"
          >
            {{ report.corrupted_files }}
          </span>
        </div>
      </div>

      <!-- 员工周报明细表 -->
      <div class="card cleaning__table-card fade-in" style="animation-delay: 400ms">
        <h2 class="cleaning__section-title">
          <FileSearch :size="18" :stroke-width="2" />
          员工周报分布
        </h2>
        <p class="cleaning__section-desc">
          中位数为 {{ reportStats?.mid ?? '—' }} 篇，低于
          {{ reportStats ? Math.round(reportStats.mid * 0.8) : '—' }} 篇标记为偏少
        </p>

        <table class="cleaning__table">
          <thead>
            <tr>
              <th>员工</th>
              <th>邮箱</th>
              <th class="text-right">去重后周报</th>
              <th class="text-right">加密文件</th>
              <th class="text-center">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="emp in report.employees"
              :key="emp.email"
              class="cleaning__table-row"
            >
              <td class="cleaning__name-cell">{{ emp.name }}</td>
              <td class="cleaning__email-cell">{{ emp.email }}</td>
              <td class="text-right">
                <span class="cleaning__count-value">{{ emp.report_count }}</span>
              </td>
              <td class="text-right">
                <span
                  v-if="encryptedCount(emp.email) > 0"
                  class="badge badge--warning"
                >
                  <Lock :size="11" :stroke-width="2.5" />
                  {{ encryptedCount(emp.email) }}
                </span>
                <span v-else class="cleaning__zero">0</span>
              </td>
              <td class="text-center">
                <span class="badge" :class="getStatusBadge(emp.report_count).cls">
                  {{ getStatusBadge(emp.report_count).label }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 加密文件清单 -->
      <div
        v-if="encryptedEmails.length > 0"
        class="card cleaning__encrypted-card fade-in"
        style="animation-delay: 480ms"
      >
        <h2 class="cleaning__section-title">
          <Lock :size="18" :stroke-width="2" />
          加密文件清单
          <span class="cleaning__section-count badge badge--warning">
            共 {{ report.encrypted_files }} 份
          </span>
        </h2>
        <p class="cleaning__section-desc">
          以下文件因加密保护无法读取，周报数据可能不完整
        </p>

        <div
          v-for="email in encryptedEmails"
          :key="email"
          class="cleaning__enc-group"
        >
          <button
            class="cleaning__enc-header"
            @click="toggleEncrypted(email)"
          >
            <component
              :is="expandedEncrypted[email] ? ChevronDown : ChevronRight"
              :size="16"
              :stroke-width="2"
            />
            <span class="cleaning__enc-email">{{ email }}</span>
            <span class="badge badge--neutral">
              {{ report.encrypted_by_employee[email].length }} 份
            </span>
          </button>

          <ul
            v-if="expandedEncrypted[email]"
            class="cleaning__enc-list"
          >
            <li
              v-for="(fname, fi) in report.encrypted_by_employee[email]"
              :key="fi"
              class="cleaning__enc-item"
            >
              <FileWarning :size="14" :stroke-width="2" />
              <span class="cleaning__enc-filename">{{ extractDateFromFilename(fname) }}</span>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cleaning__stats {
  margin-bottom: var(--space-6);
}

.stat-card__value--danger {
  color: var(--color-danger);
}

.loading-center {
  display: flex;
  justify-content: center;
  padding: var(--space-16) 0;
}

.cleaning__error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4) var(--space-5);
  background: var(--color-danger-light);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: var(--text-base);
}

/* ── 管线指标条 ── */
.cleaning__pipeline-bar {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-4) var(--space-6);
  margin-bottom: var(--space-6);
}

.cleaning__pipeline-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.cleaning__pipeline-label {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.cleaning__pipeline-value {
  font-weight: 600;
  font-family: var(--font-mono);
  font-size: var(--text-base);
  color: var(--color-text);
}

.cleaning__pipeline-sep {
  width: 1px;
  height: 20px;
  background: var(--color-border);
}

/* ── 分段标题 ── */
.cleaning__section-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-lg);
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--space-1);
}

.cleaning__section-count {
  margin-left: var(--space-2);
  font-weight: 500;
}

.cleaning__section-desc {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-5);
}

/* ── 员工表格 ── */
.cleaning__table-card {
  margin-bottom: var(--space-6);
}

.cleaning__table {
  width: 100%;
  border-collapse: collapse;
}

.cleaning__table thead th {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: var(--space-2) var(--space-3);
  border-bottom: 2px solid var(--color-border);
  text-align: left;
}

.cleaning__table tbody td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--color-border-light);
  font-size: var(--text-base);
}

.cleaning__table-row {
  transition: background var(--transition-fast);
}

.cleaning__table-row:hover {
  background: var(--color-primary-light);
}

.cleaning__name-cell {
  font-weight: 600;
  color: var(--color-text);
}

.cleaning__email-cell {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
}

.cleaning__count-value {
  font-family: var(--font-mono);
  font-weight: 600;
  font-size: var(--text-md);
}

.cleaning__zero {
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.text-right {
  text-align: right;
}

.text-center {
  text-align: center;
}

/* ── 加密文件区域 ── */
.cleaning__encrypted-card {
  margin-bottom: var(--space-6);
}

.cleaning__enc-group {
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.cleaning__enc-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-3) var(--space-4);
  background: var(--color-surface);
  border: none;
  cursor: pointer;
  font-size: var(--text-base);
  color: var(--color-text);
  transition: background var(--transition-fast);
}

.cleaning__enc-header:hover {
  background: var(--color-primary-light);
}

.cleaning__enc-email {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  flex: 1;
  text-align: left;
}

.cleaning__enc-list {
  list-style: none;
  margin: 0;
  padding: var(--space-2) var(--space-6);
  background: var(--color-bg);
}

.cleaning__enc-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  border-bottom: 1px solid var(--color-border-light);
}

.cleaning__enc-item:last-child {
  border-bottom: none;
}

.cleaning__enc-filename {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .cleaning__pipeline-bar {
    flex-wrap: wrap;
  }

  .cleaning__table {
    font-size: var(--text-sm);
  }
}
</style>
