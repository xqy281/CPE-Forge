<script setup>
/**
 * ContributorCard — 贡献者技术维度卡片
 *
 * 精简版打分卡片，用于团队大盘页面展示每位贡献者的技术维度打分：
 * - 头部：员工姓名 + 邮箱
 * - 5 维度精力占比条 + 深度点阵
 * - 不含工程素养基石部分（证据链在大盘页面不适合展示）
 */
import { computed } from 'vue'
import { User } from 'lucide-vue-next'

const props = defineProps({
  name: { type: String, required: true },
  email: { type: String, required: true },
  outerData: { type: Object, default: () => ({}) },
})

const DIM_LABELS = {
  system_platform: '系统平台',
  driver_development: '底层驱动',
  application_software: '上层应用',
  wireless_communication: '无线通信',
  sqa_quality: 'SQA质量',
}

// 按 proportion 降序排列
const sortedDims = computed(() => {
  const outer = props.outerData || {}
  return Object.entries(DIM_LABELS)
    .map(([key, label]) => {
      const val = outer[key] || { proportion: 0, depth: 0 }
      return { key, label, proportion: val.proportion || 0, depth: val.depth || 0 }
    })
    .sort((a, b) => b.proportion - a.proportion)
})

const emit = defineEmits(['click-name'])
</script>

<template>
  <div class="contributor-card">
    <!-- 头部 -->
    <div class="contributor-card__header">
      <div class="contributor-card__avatar">
        <User :size="16" :stroke-width="2" />
      </div>
      <div class="contributor-card__info">
        <span
          class="contributor-card__name"
          @click="emit('click-name', email)"
        >{{ name }}</span>
        <span class="contributor-card__email">{{ email }}</span>
      </div>
    </div>

    <!-- 技术维度打分 -->
    <div class="contributor-card__dims">
      <div
        v-for="dim in sortedDims"
        :key="dim.key"
        class="contributor-card__dim"
      >
        <span class="contributor-card__dim-label">{{ dim.label }}</span>
        <!-- 精力占比条 -->
        <div
          class="contributor-card__bar-wrapper"
          :title="`精力占比 ${(dim.proportion * 100).toFixed(1)}%`"
        >
          <div
            class="contributor-card__bar"
            :style="{ width: `${Math.min(dim.proportion * 100 * 5, 100)}%` }"
          ></div>
          <span class="contributor-card__bar-value">
            {{ (dim.proportion * 100).toFixed(0) }}%
          </span>
        </div>
        <!-- 深度点阵 -->
        <div class="contributor-card__depth" :title="`投入深度 ${dim.depth}/5`">
          <span
            v-for="i in 5"
            :key="i"
            class="contributor-card__depth-dot"
            :class="{ 'contributor-card__depth-dot--filled': i <= dim.depth }"
          ></span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.contributor-card {
  background: var(--color-surface-elevated);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  padding: var(--space-4) var(--space-5);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.contributor-card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

/* ── 头部 ── */
.contributor-card__header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--color-border-light);
}

.contributor-card__avatar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-primary-light);
  color: var(--color-primary);
  flex-shrink: 0;
}

.contributor-card__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.contributor-card__name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--color-text);
  cursor: pointer;
  transition: color 0.15s;
}

.contributor-card__name:hover {
  color: var(--color-primary);
}

.contributor-card__email {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 技术维度 ── */
.contributor-card__dims {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.contributor-card__dim {
  display: grid;
  grid-template-columns: 64px 1fr 76px;
  align-items: center;
  gap: var(--space-2);
}

.contributor-card__dim-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.contributor-card__bar-wrapper {
  position: relative;
  height: 16px;
  background: var(--color-surface);
  border-radius: 8px;
  overflow: hidden;
}

.contributor-card__bar {
  height: 100%;
  border-radius: 8px;
  background: linear-gradient(90deg, #689F38, #8BC34A);
  transition: width 0.5s ease;
}

.contributor-card__bar-value {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  font-weight: 600;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.contributor-card__depth {
  display: flex;
  align-items: center;
  gap: 2px;
  justify-content: flex-end;
}

.contributor-card__depth-dot {
  width: 11px;
  height: 11px;
  border-radius: 2px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  transition: all 0.3s ease;
}

.contributor-card__depth-dot--filled {
  background: #E65100;
  border-color: #E65100;
}
</style>
