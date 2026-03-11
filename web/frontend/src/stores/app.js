/**
 * Pinia 全局状态管理
 */
import { defineStore } from 'pinia'
import api from '@/api'

export const useAppStore = defineStore('app', {
  state: () => ({
    // 员工列表
    employees: [],
    // 当前选中的分析结果
    currentAnalysis: null,
    // 全员缓存状态 { email: true/false }
    analysisStatus: {},
    // LLM 模型列表
    models: [],
    // 全局加载状态
    loading: false,
    // 全局错误信息
    error: null,
  }),

  getters: {
    /** 获取已启用的模型列表 */
    enabledModels: (state) => state.models.filter((m) => m.enabled),

    /** 指定员工是否有缓存 */
    hasCache: (state) => (email) => !!state.analysisStatus[email],
  },

  actions: {
    /** 加载员工列表 */
    async fetchEmployees() {
      try {
        this.employees = await api.getEmployees()
      } catch (e) {
        console.error('加载员工列表失败:', e)
      }
    },

    /** 加载模型列表 */
    async fetchModels() {
      try {
        this.models = await api.getModels()
      } catch (e) {
        console.error('加载模型列表失败:', e)
      }
    },

    /** 加载全员缓存状态 */
    async fetchAnalysisStatus() {
      try {
        this.analysisStatus = await api.getAnalysisStatus()
      } catch (e) {
        console.error('加载缓存状态失败:', e)
      }
    },

    /** 设置当前分析结果 */
    setCurrentAnalysis(data) {
      this.currentAnalysis = data
    },

    /** 清除错误 */
    clearError() {
      this.error = null
    },
  },
})
