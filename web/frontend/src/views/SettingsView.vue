<script setup>
/**
 * SettingsView — 模型配置
 * LLM 模型列表 + 编辑表单（API Key / Temperature / Top P）
 */
import { ref, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import api from '@/api'
import {
  Key,
  Thermometer,
  Check,
  X,
  Edit3,
  Shield,
  Cpu,
} from 'lucide-vue-next'

const store = useAppStore()

const editingModel = ref(null)
const editForm = ref({ api_key: '', temperature: 0.7, top_p: 0.9 })
const saving = ref(false)
const saveSuccess = ref('')
const saveError = ref('')

onMounted(() => {
  store.fetchModels()
})

function startEdit(model) {
  editingModel.value = model.model_id
  editForm.value = {
    api_key: '', // 不预填 key，留空表示不修改
    temperature: model.temperature ?? 0.7,
    top_p: model.top_p ?? 0.9,
  }
  saveSuccess.value = ''
  saveError.value = ''
}

function cancelEdit() {
  editingModel.value = null
}

async function saveModel() {
  saving.value = true
  saveSuccess.value = ''
  saveError.value = ''

  try {
    const updates = {
      temperature: parseFloat(editForm.value.temperature),
      top_p: parseFloat(editForm.value.top_p),
    }
    // 仅在用户输入了新 key 时才传递
    if (editForm.value.api_key.trim()) {
      updates.api_key = editForm.value.api_key.trim()
    }

    await api.updateModel(editingModel.value, updates)
    await store.fetchModels()
    saveSuccess.value = '保存成功'
    editingModel.value = null
  } catch (e) {
    saveError.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="settings">
    <div class="page-header">
      <h1 class="page-header__title">模型配置</h1>
      <p class="page-header__subtitle">管理 LLM 模型的 API Key、Temperature 和 Top P 参数</p>
    </div>

    <!-- 成功提示 -->
    <div v-if="saveSuccess" class="settings__toast settings__toast--success">
      <Check :size="16" :stroke-width="2" />
      {{ saveSuccess }}
    </div>

    <!-- 模型列表 -->
    <div class="settings__list">
      <div
        v-for="model in store.models"
        :key="model.model_id"
        class="settings__item card"
      >
        <!-- 模型信息 -->
        <div class="settings__item-header">
          <div class="settings__item-info">
            <Cpu :size="16" :stroke-width="1.8" class="settings__item-icon" />
            <div>
              <h3 class="settings__item-name">{{ model.display_name || model.model_id }}</h3>
              <p class="settings__item-id">{{ model.model_id }}</p>
            </div>
          </div>

          <div class="settings__item-badges">
            <span
              class="badge"
              :class="model.api_key ? 'badge--success' : 'badge--danger'"
            >
              <Key :size="10" :stroke-width="2" />
              {{ model.api_key ? 'Key 已配置' : '未配置' }}
            </span>
            <span
              class="badge"
              :class="model.enabled ? 'badge--info' : 'badge--neutral'"
            >
              {{ model.enabled ? '已启用' : '已禁用' }}
            </span>
          </div>
        </div>

        <!-- 参数摘要 -->
        <div class="settings__item-params" v-if="editingModel !== model.model_id">
          <span class="settings__param">
            <Thermometer :size="13" :stroke-width="1.8" />
            Temperature: <strong>{{ model.temperature ?? '—' }}</strong>
          </span>
          <span class="settings__param">
            Top P: <strong>{{ model.top_p ?? '—' }}</strong>
          </span>
          <span v-if="model.api_key_preview" class="settings__param">
            <Shield :size="13" :stroke-width="1.8" />
            Key: ****{{ model.api_key_preview }}
          </span>
        </div>

        <!-- 编辑按钮 -->
        <button
          v-if="editingModel !== model.model_id"
          class="btn btn--secondary btn--sm settings__edit-btn"
          @click="startEdit(model)"
        >
          <Edit3 :size="14" :stroke-width="2" />
          编辑
        </button>

        <!-- 编辑表单 -->
        <div v-if="editingModel === model.model_id" class="settings__form">
          <div class="form-group">
            <label class="form-label">API Key（留空则不修改）</label>
            <input
              v-model="editForm.api_key"
              type="password"
              class="form-input"
              placeholder="sk-..."
              autocomplete="off"
            />
          </div>

          <div class="settings__form-row">
            <div class="form-group" style="flex: 1;">
              <label class="form-label">Temperature</label>
              <input
                v-model.number="editForm.temperature"
                type="number"
                class="form-input"
                min="0"
                max="2"
                step="0.1"
              />
            </div>

            <div class="form-group" style="flex: 1;">
              <label class="form-label">Top P</label>
              <input
                v-model.number="editForm.top_p"
                type="number"
                class="form-input"
                min="0"
                max="1"
                step="0.05"
              />
            </div>
          </div>

          <div v-if="saveError" class="settings__form-error">
            {{ saveError }}
          </div>

          <div class="settings__form-actions">
            <button
              class="btn btn--primary btn--sm"
              :disabled="saving"
              @click="saveModel"
            >
              <Check :size="14" :stroke-width="2" />
              {{ saving ? '保存中...' : '保存' }}
            </button>
            <button
              class="btn btn--ghost btn--sm"
              @click="cancelEdit"
            >
              <X :size="14" :stroke-width="2" />
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings__list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 720px;
}

.settings__item-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-3);
}

.settings__item-info {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.settings__item-icon {
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.settings__item-name {
  font-size: var(--text-base);
  font-weight: 600;
}

.settings__item-id {
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.settings__item-badges {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.settings__item-params {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-3);
}

.settings__param {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.settings__param strong {
  color: var(--color-text);
  font-family: var(--font-mono);
}

.settings__edit-btn {
  margin-top: var(--space-1);
}

/* ── 编辑表单 ── */
.settings__form {
  margin-top: var(--space-4);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-light);
}

.settings__form-row {
  display: flex;
  gap: var(--space-4);
}

.settings__form-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.settings__form-error {
  font-size: var(--text-sm);
  color: var(--color-danger);
  margin-bottom: var(--space-3);
}

/* ── 提示 ── */
.settings__toast {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  font-size: var(--text-sm);
  font-weight: 500;
  margin-bottom: var(--space-6);
}

.settings__toast--success {
  background: var(--color-success-light);
  color: var(--color-success);
}
</style>
