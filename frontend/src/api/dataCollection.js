import apiClient from './client'

export default {
  // 数据源
  listSources: (params) => apiClient.get('/data-collection/sources', { params }),
  createSource: (data) => apiClient.post('/data-collection/sources', data),
  getSource: (id) => apiClient.get(`/data-collection/sources/${id}`),
  updateSource: (id, data) => apiClient.put(`/data-collection/sources/${id}`, data),
  deleteSource: (id) => apiClient.delete(`/data-collection/sources/${id}`),
  // 采集任务
  listTasks: (params) => apiClient.get('/data-collection/tasks', { params }),
  createTask: (data) => apiClient.post('/data-collection/tasks', data),
  getTask: (id) => apiClient.get(`/data-collection/tasks/${id}`),
  cancelTask: (id) => apiClient.post(`/data-collection/tasks/${id}/cancel`),
  // 原始数据
  listRawData: (params) => apiClient.get('/data-collection/raw-data', { params }),
  getRawData: (id) => apiClient.get(`/data-collection/raw-data/${id}`),
}
