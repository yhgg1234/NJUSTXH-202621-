import apiClient from './client'

// 清洗流水线为耗时操作（去重/标注/划分），放宽到 5 分钟
const TASK_TIMEOUT = 5 * 60 * 1000

export default {
  getPipelineDefaults: () => apiClient.get('/data-cleaning/pipeline/defaults'),
  createTask: (formData) => apiClient.post('/data-cleaning/tasks', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: TASK_TIMEOUT,
  }),
  createTaskFromCollection: () => apiClient.post('/data-cleaning/tasks/from-collection', null, {
    timeout: TASK_TIMEOUT,
  }),
  listTasks: (params) => apiClient.get('/data-cleaning/tasks', { params }),
  getTask: (id) => apiClient.get(`/data-cleaning/tasks/${id}`),
  listQualityItems: (params) => apiClient.get('/data-cleaning/quality-check', { params }),
  submitReview: (data) => apiClient.post('/data-cleaning/quality-review', data),
  listDatasets: (params) => apiClient.get('/data-cleaning/datasets', { params }),
  getDatasetItem: (id) => apiClient.get(`/data-cleaning/datasets/${id}`),
  deleteDatasetItem: (id) => apiClient.delete(`/data-cleaning/datasets/${id}`),
}
