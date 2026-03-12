<script setup>
/**
 * ScorePanel — 打分解释面板
 *
 * 3D 图谱下方的结构化数据面板：
 * 1. 技术维度打分表（精力占比 + 投入深度进度条）
 * 2. 工程素养基石（递进层叠进度条 + 等级 + 证据链）
 */
import { computed } from 'vue'
import {
  Layers,
  Flame,
  ChevronRight,
  Plus,
  Minus,
} from 'lucide-vue-next'

const props = defineProps({
  outerData: { type: Object, required: true },
  innerData: { type: Object, required: true },
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

// 基石层（固定顺序：求真→务实→严谨）
const INNER_LAYERS = [
  { key: 'truth_seeking', label: '求真', role: '基石', desc: '溯源行为：根因定位、手册阅读、底层排查', color: '#7C2D12' },
  { key: 'pragmatic', label: '务实', role: '框架', desc: '交付行为：任务闭环、按时交付、方案替代', color: '#C2410C' },
  { key: 'rigorous', label: '严谨', role: '附着', desc: '质量行为：边界测试、代码重构、自动化脚本', color: '#EA580C' },
]

const innerLayers = computed(() => {
  const inner = props.innerData || {}
  return INNER_LAYERS.map((layer) => {
    const val = inner[layer.key] || { level: 0, evidence: [] }
    return { ...layer, level: val.level || 0, evidence: val.evidence || [] }
  })
})

/** 判断证据极性 */
function getEvidencePolarity(ev) {
  const trimmed = (ev || '').trim()
  if (trimmed.startsWith('[-]') || trimmed.startsWith('[-]')) return 'negative'
  if (trimmed.startsWith('[+]') || trimmed.startsWith('[+]')) return 'positive'
  return 'neutral'
}

/** 去掉 [+]/[-] 前缀，保留正文 */
function stripPrefix(ev) {
  return (ev || '').replace(/^\[[-+]\]\s*/, '').replace(/^【/, '【')
}
</script>

<template>
  <div class="score-panel">
    <!-- 技术维度打分 -->
    <div class="score-panel__section">
      <h4 class="score-panel__heading">
        <Layers :size="16" :stroke-width="2" />
        技术维度打分
      </h4>
      <div class="score-panel__dim-list">
        <div
          v-for="dim in sortedDims"
          :key="dim.key"
          class="score-panel__dim"
        >
          <span class="score-panel__dim-label">{{ dim.label }}</span>
          <!-- 精力占比条 -->
          <div class="score-panel__bar-wrapper" :title="`精力占比 ${(dim.proportion * 100).toFixed(1)}%`">
            <div
              class="score-panel__bar score-panel__bar--proportion"
              :style="{ width: `${dim.proportion * 100 * 5}%` }"
            ></div>
            <span class="score-panel__bar-value">{{ (dim.proportion * 100).toFixed(1) }}%</span>
          </div>
          <!-- 深度条 -->
          <div class="score-panel__depth" :title="`投入深度 ${dim.depth}/5`">
            <span
              v-for="i in 5"
              :key="i"
              class="score-panel__depth-dot"
              :class="{ 'score-panel__depth-dot--filled': i <= dim.depth }"
            ></span>
            <span class="score-panel__depth-label">{{ dim.depth }}</span>
          </div>
        </div>
      </div>
      <div class="score-panel__legend">
        <span class="score-panel__legend-item">
          <span class="score-panel__legend-dot score-panel__legend-dot--proportion"></span>
          精力占比
        </span>
        <span class="score-panel__legend-item">
          <span class="score-panel__legend-dot score-panel__legend-dot--depth"></span>
          投入深度 (0-5)
        </span>
      </div>
    </div>

    <!-- 工程素养基石 -->
    <div class="score-panel__section">
      <h4 class="score-panel__heading">
        <Flame :size="16" :stroke-width="2" />
        工程素养基石
        <span class="score-panel__heading-hint">递进关系：求真 → 务实 → 严谨</span>
      </h4>
      <div class="score-panel__foundation">
        <div
          v-for="(layer, idx) in innerLayers"
          :key="layer.key"
          class="score-panel__layer"
        >
          <div class="score-panel__layer-header">
            <span
              class="score-panel__layer-badge"
              :style="{ background: layer.color }"
            >
              {{ layer.label }}
            </span>
            <span class="score-panel__layer-role">{{ layer.role }}</span>
            <span class="score-panel__layer-level">Lv.{{ layer.level }}</span>
          </div>
          <!-- 等级进度条 -->
          <div class="score-panel__level-bar">
            <div
              class="score-panel__level-fill"
              :style="{
                width: `${(layer.level / 5) * 100}%`,
                background: layer.color,
              }"
            ></div>
          </div>
          <p class="score-panel__layer-desc">{{ layer.desc }}</p>
          <!-- 证据链（全部显示，正负向颜色区分） -->
          <ul v-if="layer.evidence.length > 0" class="score-panel__evidence">
            <li
              v-for="(ev, i) in layer.evidence"
              :key="i"
              :class="{
                'score-panel__evidence--positive': getEvidencePolarity(ev) === 'positive',
                'score-panel__evidence--negative': getEvidencePolarity(ev) === 'negative',
              }"
            >
              <span v-if="getEvidencePolarity(ev) === 'positive'" class="score-panel__ev-icon score-panel__ev-icon--pos">
                <Plus :size="10" :stroke-width="3" />
              </span>
              <span v-else-if="getEvidencePolarity(ev) === 'negative'" class="score-panel__ev-icon score-panel__ev-icon--neg">
                <Minus :size="10" :stroke-width="3" />
              </span>
              <ChevronRight v-else :size="12" :stroke-width="2" />
              {{ stripPrefix(ev) }}
            </li>
          </ul>
          <!-- 递进箭头 -->
          <div v-if="idx < innerLayers.length - 1" class="score-panel__arrow">
            ↑ 为上层提供支撑
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.score-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-6);
}

.score-panel__section {
  padding: var(--space-5);
  background: var(--color-surface-elevated);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border-light);
}

.score-panel__heading {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-base);
  font-weight: 600;
  margin-bottom: var(--space-4);
  color: var(--color-text);
}

.score-panel__heading-hint {
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--color-text-tertiary);
  margin-left: auto;
}

/* ── 技术维度 ── */
.score-panel__dim-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.score-panel__dim {
  display: grid;
  grid-template-columns: 80px 1fr 100px;
  align-items: center;
  gap: var(--space-3);
}

.score-panel__dim-label {
  font-size: var(--text-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.score-panel__bar-wrapper {
  position: relative;
  height: 20px;
  background: var(--color-surface);
  border-radius: 10px;
  overflow: hidden;
}

.score-panel__bar {
  height: 100%;
  border-radius: 10px;
  transition: width 0.6s ease;
}

.score-panel__bar--proportion {
  background: linear-gradient(90deg, #689F38, #8BC34A);
}

.score-panel__bar-value {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.score-panel__depth {
  display: flex;
  align-items: center;
  gap: 3px;
}

.score-panel__depth-dot {
  width: 14px;
  height: 14px;
  border-radius: 3px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  transition: all 0.3s ease;
}

.score-panel__depth-dot--filled {
  background: #E65100;
  border-color: #E65100;
}

.score-panel__depth-label {
  font-size: 12px;
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
  margin-left: 4px;
}

.score-panel__legend {
  display: flex;
  gap: var(--space-4);
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border-light);
}

.score-panel__legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
}

.score-panel__legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 3px;
}

.score-panel__legend-dot--proportion {
  background: linear-gradient(90deg, #689F38, #8BC34A);
}

.score-panel__legend-dot--depth {
  background: #E65100;
}

/* ── 工程素养基石 ── */
.score-panel__foundation {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.score-panel__layer {
  padding: var(--space-3) var(--space-4);
  border-left: 3px solid var(--color-border-light);
}

.score-panel__layer:first-child {
  border-left-color: #7C2D12;
}

.score-panel__layer:nth-child(2) {
  border-left-color: #C2410C;
}

.score-panel__layer:last-child {
  border-left-color: #EA580C;
}

.score-panel__layer-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.score-panel__layer-badge {
  display: inline-flex;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  color: #FFFFFF;
  font-size: var(--text-sm);
  font-weight: 600;
}

.score-panel__layer-role {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  padding: 1px 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.score-panel__layer-level {
  font-size: var(--text-sm);
  font-weight: 600;
  font-family: var(--font-mono);
  color: var(--color-text);
  margin-left: auto;
}

.score-panel__level-bar {
  height: 6px;
  background: var(--color-surface);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: var(--space-2);
}

.score-panel__level-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.6s ease;
}

.score-panel__layer-desc {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-2);
}

.score-panel__evidence {
  list-style: none;
  padding: 0;
  margin: 0;
}

.score-panel__evidence li {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--color-text-secondary);
  line-height: 1.6;
  padding: var(--space-1) 0;
  border-radius: var(--radius-sm);
}

/* 正向证据 */
.score-panel__evidence--positive {
  color: #2E7D32;
  background: rgba(46, 125, 50, 0.06);
  padding: var(--space-1) var(--space-2) !important;
  margin-bottom: 2px;
}

/* 负向证据 */
.score-panel__evidence--negative {
  color: #C62828;
  background: rgba(198, 40, 40, 0.06);
  padding: var(--space-1) var(--space-2) !important;
  margin-bottom: 2px;
}

/* 证据极性图标 */
.score-panel__ev-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 2px;
}

.score-panel__ev-icon--pos {
  background: #2E7D32;
  color: #fff;
}

.score-panel__ev-icon--neg {
  background: #C62828;
  color: #fff;
}

.score-panel__arrow {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-tertiary);
  padding: var(--space-1) 0;
  letter-spacing: 2px;
}
</style>
