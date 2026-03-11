<script setup>
/**
 * AppLayout — 极简侧栏 + 主内容区布局
 * 设计灵感：Jony Ive / Apple 风格，精简导航，大量留白
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  TerminalSquare,
  BarChart3,
  Users,
  Settings,
  Flame,
  FileSearch,
} from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const navItems = [
  { path: '/console', label: '调度台', icon: TerminalSquare },
  { path: '/cleaning', label: '数据清洗', icon: FileSearch },
  { path: '/dashboard', label: '团队大盘', icon: BarChart3 },
  { path: '/roster', label: '英雄榜', icon: Users },
  { path: '/settings', label: '模型配置', icon: Settings },
]

const isActive = (path) => {
  if (path === '/roster') {
    return route.path === '/roster' || route.path.startsWith('/player/')
  }
  return route.path === path
}
</script>

<template>
  <div class="layout">
    <!-- 侧栏 -->
    <aside class="sidebar">
      <!-- Logo -->
      <div class="sidebar__logo" @click="router.push('/console')">
        <Flame class="sidebar__logo-icon" :size="22" :stroke-width="2.5" />
        <span class="sidebar__logo-text">CPE-Forge</span>
      </div>

      <!-- 导航 -->
      <nav class="sidebar__nav">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ 'nav-link--active': isActive(item.path) }"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.8" />
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <!-- 底部版本 -->
      <div class="sidebar__footer">
        <span class="sidebar__version">v2.0 · Vue</span>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main">
      <div class="main__inner">
        <router-view v-slot="{ Component }">
          <transition name="slide-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
}

/* ── 侧栏 ── */
.sidebar {
  width: var(--sidebar-width);
  background: var(--color-bg);
  border-right: 1px solid var(--color-border);
  padding: var(--space-6) var(--space-4);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  height: 100vh;
  z-index: 100;
}

.sidebar__logo {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  margin-bottom: var(--space-8);
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.sidebar__logo:hover {
  opacity: 0.7;
}

.sidebar__logo-icon {
  color: var(--color-primary);
}

.sidebar__logo-text {
  font-family: var(--font-display);
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--color-text);
  letter-spacing: -0.02em;
}

.sidebar__nav {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  font-size: var(--text-base);
  font-weight: 500;
  transition: all var(--transition-fast);
  text-decoration: none;
}

.nav-link:hover {
  color: var(--color-text);
  background: var(--color-surface);
}

.nav-link--active {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.nav-link--active:hover {
  color: var(--color-primary);
  background: var(--color-primary-light);
}

.sidebar__footer {
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-light);
}

.sidebar__version {
  font-size: var(--text-xs);
  color: var(--color-text-tertiary);
  padding: 0 var(--space-3);
}

/* ── 主内容 ── */
.main {
  flex: 1;
  margin-left: var(--sidebar-width);
  background: var(--color-surface);
  min-height: 100vh;
}

.main__inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--space-10) var(--space-10);
}

/* ── 响应式 ── */
@media (max-width: 768px) {
  .sidebar {
    position: relative;
    width: 100%;
    height: auto;
    flex-direction: row;
    align-items: center;
    padding: var(--space-3) var(--space-4);
    border-right: none;
    border-bottom: 1px solid var(--color-border);
  }

  .sidebar__logo {
    margin-bottom: 0;
    margin-right: var(--space-6);
  }

  .sidebar__nav {
    flex-direction: row;
    gap: var(--space-1);
    overflow-x: auto;
  }

  .sidebar__footer {
    display: none;
  }

  .main {
    margin-left: 0;
  }

  .main__inner {
    padding: var(--space-6) var(--space-4);
  }
}
</style>
