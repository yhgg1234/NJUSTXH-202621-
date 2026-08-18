import apiClient from './client'

// 抽取含 LLM 调用，首次还会触发嵌入模型下载，放宽到 3 分钟
const TIMEOUT = 3 * 60 * 1000

export default {
  extract: (data) => apiClient.post('/extraction/extract', data, { timeout: TIMEOUT }),
  fromCleaning: (limit) => apiClient.post('/extraction/from-cleaning', null, { params: { limit }, timeout: TIMEOUT }),
  initRag: () => apiClient.post('/extraction/init-rag', null, { timeout: TIMEOUT }),
}
