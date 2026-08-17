import apiClient from './client'

// 简历解析为耗时操作（文件保存 → 文本提取 → LLM 调用 → 存储），
// 单文件可能超过默认的 30s，这里单独放宽到 5 分钟。
const UPLOAD_TIMEOUT = 5 * 60 * 1000

export default {
  upload: (formData) => apiClient.post('/resume/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT,
  }),
  batchUpload: (formData) => apiClient.post('/resume/upload/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT,
  }),
  listResumes: (params) => apiClient.get('/resume/', { params }),
  getResume: (id) => apiClient.get(`/resume/${id}`),
  deleteResume: (id) => apiClient.delete(`/resume/${id}`),
  searchResumes: (params) => apiClient.get('/resume/search', { params }),
}
