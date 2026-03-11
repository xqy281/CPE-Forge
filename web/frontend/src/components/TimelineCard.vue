<script setup>
/**
 * TimelineCard — 技术攻坚故事线卡片
 */
import { Clock, CheckCircle, AlertCircle, Tag } from 'lucide-vue-next'

const props = defineProps({
  issue: { type: Object, required: true },
  isLast: { type: Boolean, default: false },
})

const statusConfig = {
  resolved: { label: '已解决', class: 'badge--success', icon: CheckCircle },
  open: { label: '进行中', class: 'badge--warning', icon: AlertCircle },
}

const getStatus = (status) => statusConfig[status] || statusConfig.open
</script>

<template>
  <div class="timeline-item">
    <!-- 时间轴节点 -->
    <div class="timeline-item__node">
      <div
        class="timeline-item__dot"
        :class="{ 'timeline-item__dot--resolved': issue.status === 'resolved' }"
      ></div>
      <div v-if="!isLast" class="timeline-item__line"></div>
    </div>

    <!-- 内容卡片 -->
    <div class="timeline-item__content card">
      <div class="timeline-item__header">
        <h4 class="timeline-item__title">{{ issue.title || '未命名问题' }}</h4>
        <span class="badge" :class="getStatus(issue.status).class">
          {{ getStatus(issue.status).label }}
        </span>
      </div>

      <div class="timeline-item__meta">
        <span v-if="issue.first_appeared" class="timeline-item__date">
          <Clock :size="13" :stroke-width="1.8" />
          {{ issue.first_appeared }}
          <template v-if="issue.resolved_date"> → {{ issue.resolved_date }}</template>
        </span>
        <span v-if="issue.duration_weeks" class="timeline-item__duration">
          {{ issue.duration_weeks }} 周持续追踪
        </span>
      </div>

      <!-- 根因 & 解法 -->
      <div v-if="issue.root_cause" class="timeline-item__detail">
        <span class="timeline-item__label">根因</span>
        <p>{{ issue.root_cause }}</p>
      </div>

      <div v-if="issue.solution" class="timeline-item__detail">
        <span class="timeline-item__label">解法</span>
        <p>{{ issue.solution }}</p>
      </div>

      <!-- 标签 -->
      <div v-if="issue.tags && issue.tags.length" class="timeline-item__tags">
        <span v-for="tag in issue.tags" :key="tag" class="badge badge--neutral">
          <Tag :size="10" :stroke-width="2" />
          {{ tag }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-item {
  display: flex;
  gap: var(--space-5);
  position: relative;
}

.timeline-item__node {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: var(--space-6);
}

.timeline-item__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-border);
  border: 2px solid var(--color-bg);
  box-shadow: 0 0 0 2px var(--color-border);
  flex-shrink: 0;
  z-index: 1;
}

.timeline-item__dot--resolved {
  background: var(--color-success);
  box-shadow: 0 0 0 2px var(--color-success);
}

.timeline-item__line {
  width: 1px;
  flex: 1;
  background: var(--color-border);
  margin-top: var(--space-2);
}

.timeline-item__content {
  flex: 1;
  margin-bottom: var(--space-5);
}

.timeline-item__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.timeline-item__title {
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--color-text);
  line-height: 1.4;
}

.timeline-item__meta {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
}

.timeline-item__date {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.timeline-item__detail {
  margin-bottom: var(--space-3);
}

.timeline-item__label {
  display: inline-block;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-1);
}

.timeline-item__detail p {
  font-size: var(--text-base);
  color: var(--color-text);
  line-height: 1.6;
}

.timeline-item__tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}
</style>
