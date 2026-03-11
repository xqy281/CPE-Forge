<script setup>
/**
 * ChatWidget — FAQ 智能对话浮窗
 * 固定在页面右下角，支持多轮对话
 */
import { ref, nextTick } from 'vue'
import { X, Send, MessageCircle, Loader2 } from 'lucide-vue-next'
import api from '@/api'

const props = defineProps({
  employeeName: { type: String, required: true },
  employeeEmail: { type: String, required: true },
  dateRangeIds: { type: Array, default: () => [] },
  modelId: { type: String, default: '' },
})

const isOpen = ref(false)
const sessionId = ref(null)
const messages = ref([])
const inputText = ref('')
const sending = ref(false)
const connecting = ref(false)
const messagesContainer = ref(null)

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

async function openChat() {
  isOpen.value = true
  if (sessionId.value) return

  connecting.value = true
  try {
    const res = await api.startChat(
      props.employeeEmail,
      props.dateRangeIds,
      props.modelId,
    )
    sessionId.value = res.session_id
    messages.value = [
      {
        role: 'assistant',
        content: `你好！我已经读取了 ${props.employeeName} 在该时间段内的全部周报。可以向我提出任何细节追问。`,
      },
    ]
  } catch (e) {
    messages.value = [
      { role: 'system', content: `对话启动失败: ${e.message}` },
    ]
  } finally {
    connecting.value = false
    scrollToBottom()
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !sessionId.value || sending.value) return

  inputText.value = ''
  messages.value.push({ role: 'user', content: text })
  scrollToBottom()

  sending.value = true
  try {
    const reply = await api.sendChatMessage(sessionId.value, text)
    messages.value.push({
      role: 'assistant',
      content: reply.content || reply.text || '没有回答内容。',
    })
  } catch (e) {
    messages.value.push({
      role: 'system',
      content: `发送失败: ${e.message}`,
    })
  } finally {
    sending.value = false
    scrollToBottom()
  }
}

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}
</script>

<template>
  <!-- 触发按钮 -->
  <button
    v-if="!isOpen"
    class="chat-trigger"
    @click="openChat"
    title="发起智能对话"
  >
    <MessageCircle :size="22" :stroke-width="2" />
  </button>

  <!-- 对话面板 -->
  <Transition name="chat-slide">
    <div v-if="isOpen" class="chat-panel">
      <!-- 顶栏 -->
      <div class="chat-panel__header">
        <div>
          <span class="chat-panel__title">智能助手</span>
          <span class="chat-panel__subtitle">· {{ employeeName }}</span>
        </div>
        <button class="chat-panel__close" @click="isOpen = false">
          <X :size="18" :stroke-width="2" />
        </button>
      </div>

      <!-- 消息区域 -->
      <div ref="messagesContainer" class="chat-panel__messages">
        <!-- 连接中 -->
        <div v-if="connecting" class="chat-msg chat-msg--system">
          <Loader2 :size="14" class="chat-msg__spinner" />
          正在建立连接...
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="chat-msg"
          :class="{
            'chat-msg--user': msg.role === 'user',
            'chat-msg--assistant': msg.role === 'assistant',
            'chat-msg--system': msg.role === 'system',
          }"
        >
          <div class="chat-msg__bubble">{{ msg.content }}</div>
        </div>

        <!-- 回复等待 -->
        <div v-if="sending" class="chat-msg chat-msg--assistant">
          <div class="chat-msg__bubble chat-msg__typing">
            <span></span><span></span><span></span>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="chat-panel__input">
        <input
          v-model="inputText"
          class="form-input"
          :disabled="!sessionId || sending"
          placeholder="输入你的问题..."
          @keydown="handleKeydown"
        />
        <button
          class="btn btn--primary btn--sm"
          :disabled="!inputText.trim() || !sessionId || sending"
          @click="handleSend"
        >
          <Send :size="15" :stroke-width="2" />
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.chat-trigger {
  position: fixed;
  right: var(--space-8);
  bottom: var(--space-8);
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition-fast);
  z-index: 1000;
  cursor: pointer;
}

.chat-trigger:hover {
  background: var(--color-primary-hover);
  transform: scale(1.05);
}

/* ── 对话面板 ── */
.chat-panel {
  position: fixed;
  right: var(--space-8);
  bottom: var(--space-8);
  width: 400px;
  height: 520px;
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  z-index: 1001;
  overflow: hidden;
}

.chat-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--color-border);
}

.chat-panel__title {
  font-weight: 600;
  font-size: var(--text-base);
  color: var(--color-text);
}

.chat-panel__subtitle {
  font-size: var(--text-sm);
  color: var(--color-text-secondary);
  margin-left: var(--space-1);
}

.chat-panel__close {
  color: var(--color-text-secondary);
  padding: var(--space-1);
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
  cursor: pointer;
}

.chat-panel__close:hover {
  background: var(--color-surface);
  color: var(--color-text);
}

/* ── 消息区域 ── */
.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  background: var(--color-surface);
}

.chat-msg {
  display: flex;
}

.chat-msg--user {
  justify-content: flex-end;
}

.chat-msg--system {
  justify-content: center;
  font-size: var(--text-sm);
  color: var(--color-text-tertiary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.chat-msg__bubble {
  max-width: 80%;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-lg);
  font-size: var(--text-base);
  line-height: 1.5;
  word-break: break-word;
}

.chat-msg--user .chat-msg__bubble {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: var(--radius-sm);
}

.chat-msg--assistant .chat-msg__bubble {
  background: var(--color-bg);
  color: var(--color-text);
  border: 1px solid var(--color-border);
  border-bottom-left-radius: var(--radius-sm);
}

.chat-msg__spinner {
  animation: spin 1s linear infinite;
}

/* 输入中动画 */
.chat-msg__typing {
  display: flex;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
}

.chat-msg__typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  animation: typing-dots 1.4s infinite;
}

.chat-msg__typing span:nth-child(2) { animation-delay: 0.2s; }
.chat-msg__typing span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing-dots {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-3px); }
}

/* ── 输入区域 ── */
.chat-panel__input {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border);
  background: var(--color-bg);
}

.chat-panel__input .form-input {
  flex: 1;
}

/* ── 过渡 ── */
.chat-slide-enter-active { transition: all 0.25s ease; }
.chat-slide-leave-active { transition: all 0.2s ease; }
.chat-slide-enter-from { opacity: 0; transform: translateY(20px) scale(0.95); }
.chat-slide-leave-to { opacity: 0; transform: translateY(20px) scale(0.95); }
</style>
