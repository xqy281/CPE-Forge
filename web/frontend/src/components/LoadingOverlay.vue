<script setup>
/**
 * LoadingOverlay — 加载遮罩组件
 * 可用于全屏或局部遮罩
 */
defineProps({
  message: { type: String, default: '正在加载...' },
  fullscreen: { type: Boolean, default: false },
})
</script>

<template>
  <div class="loading" :class="{ 'loading--fullscreen': fullscreen }">
    <div class="loading__content">
      <div class="spinner spinner--lg"></div>
      <p class="loading__text">{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-16) 0;
}

.loading--fullscreen {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(4px);
  z-index: 999;
  padding: 0;
}

.loading__content {
  text-align: center;
}

.loading__text {
  margin-top: var(--space-4);
  font-size: var(--text-base);
  color: var(--color-text-secondary);
  font-weight: 500;
}
</style>
