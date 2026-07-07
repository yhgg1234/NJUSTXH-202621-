import apiClient from './client'

export default {
  getPipelineDefaults: () => apiClient.get('/data-cleaning/pipeline/defaults'),
  createTask: (data) => apiClient.post('/data-cleaning/tasks', data),
  listTasks: (params) => apiClient.get('/data-cleaning/tasks', { params }),
  getTask: (id) => apiClient.get(`/data-cleaning/tasks/${id}`),
  listQualityItems: (params) => apiClient.get('/data-cleaning/quality-check', { params }),
  submitReview: (data) => apiClient.post('/data-cleaning/quality-review', data),
  listDatasets: (params) => apiClient.get('/data-cleaning/datasets', { params }),
  getDatasetItem: (id) => apiClient.get(`/data-cleaning/datasets/${id}`),
  deleteDatasetItem: (id) => apiClient.delete(`/data-cleaning/datasets/${id}`),
}
