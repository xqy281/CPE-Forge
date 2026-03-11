/**
 * CPE-Forge API 客户端 — axios 封装层
 * 
 * 1:1 映射后端 16 个 REST 端点，统一错误处理。
 */
import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 300000, // LLM 分析可能耗时较长，设置 5 分钟超时
  headers: { 'Content-Type': 'application/json' },
})

// 响应拦截器 — 统一错误处理
http.interceptors.response.use(
  (res) => res.data,
  (error) => {
    const data = error.response?.data
    const err = new Error(data?.error || error.message || '网络请求失败')
    err.needConfig = data?.need_config || false
    err.status = error.response?.status
    return Promise.reject(err)
  }
)

export default {
  // ============ 数据查询 GET ============

  /** 获取数据清洗报告 */
  getCleaningReport() {
    return http.get('/cleaning-report')
  },

  /** 获取所有员工列表 */
  getEmployees() {
    return http.get('/employees')
  },

  /** 获取指定员工可用的周报时间范围 */
  getRanges(email) {
    return http.get(`/employees/${encodeURIComponent(email)}/ranges`)
  },

  /** 获取所有 LLM 模型配置 */
  getModels() {
    return http.get('/models')
  },

  /** 获取单个模型配置详情 */
  getModelDetail(modelId) {
    return http.get(`/models/${modelId}`)
  },

  // ============ 分析结果 GET ============

  /** 获取最新分析结果 */
  getLatestAnalysis(email) {
    return http.get(`/analysis/${encodeURIComponent(email)}/latest`)
  },

  /** 获取历史分析文件列表 */
  getAnalysisHistory(email) {
    return http.get(`/analysis/${encodeURIComponent(email)}/history`)
  },

  /** 根据文件名加载特定历史分析结果 */
  getAnalysisByFile(email, filename) {
    return http.get(`/analysis/${encodeURIComponent(email)}/file/${encodeURIComponent(filename)}`)
  },

  /** 全员缓存状态 */
  getAnalysisStatus() {
    return http.get('/analysis/status')
  },

  /** 全员聚合结果（团队大盘） */
  getAllAnalysis() {
    return http.get('/analysis/all')
  },

  // ============ 分析触发 POST ============

  /** Token 预估（不调用 LLM） */
  estimateTokens(email, rangeIds, modelId) {
    return http.post('/estimate-tokens', {
      email,
      range_ids: rangeIds,
      model_id: modelId,
    })
  },

  /** 完整分析（画像 + 成长） */
  runFullAnalysis(email, rangeIds, modelId) {
    return http.post('/analysis/full', {
      email,
      range_ids: rangeIds,
      model_id: modelId,
    })
  },

  /** 仅画像提取 */
  runProfileOnly(email, rangeIds, modelId) {
    return http.post('/analysis/profile', {
      email,
      range_ids: rangeIds,
      model_id: modelId,
    })
  },

  /** 仅成长分析 */
  runGrowthOnly(email, rangeIds, modelId) {
    return http.post('/analysis/growth', {
      email,
      range_ids: rangeIds,
      model_id: modelId,
    })
  },

  // ============ 模型配置 PUT ============

  /** 更新模型配置 */
  updateModel(modelId, updates) {
    return http.put(`/models/${modelId}`, updates)
  },

  // ============ FAQ 对话 ============

  /** 创建对话会话 */
  startChat(email, rangeIds, modelId) {
    return http.post('/chat/start', {
      email,
      range_ids: rangeIds,
      model_id: modelId,
    })
  },

  /** 发送消息 */
  sendChatMessage(sessionId, message) {
    return http.post('/chat/send', {
      session_id: sessionId,
      message,
    })
  },

  /** 获取对话历史 */
  getChatHistory(sessionId) {
    return http.get(`/chat/${encodeURIComponent(sessionId)}/history`)
  },
}
