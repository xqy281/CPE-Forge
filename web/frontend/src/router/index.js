/**
 * Vue Router 路由配置
 */
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/console',
  },
  {
    path: '/console',
    name: 'Console',
    component: () => import('@/views/ConsoleView.vue'),
    meta: { title: '数据调度台' },
  },
  {
    path: '/cleaning',
    name: 'Cleaning',
    component: () => import('@/views/CleaningView.vue'),
    meta: { title: '数据清洗' },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { title: '团队大盘' },
  },
  {
    path: '/roster',
    name: 'Roster',
    component: () => import('@/views/RosterView.vue'),
    meta: { title: '英雄榜' },
  },
  {
    path: '/player/:email',
    name: 'Player',
    component: () => import('@/views/PlayerView.vue'),
    meta: { title: '个人画像' },
    props: true,
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsView.vue'),
    meta: { title: '模型配置' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// 路由守卫 — 设置页面标题
router.afterEach((to) => {
  document.title = `${to.meta.title || 'CPE-Forge'} · CPE-Forge`
})

export default router
