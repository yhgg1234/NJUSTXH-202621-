import apiClient from './client'

export default {
  getSubgraph: (params) => apiClient.get('/graph/subgraph', { params }),
  getFilterOptions: () => apiClient.get('/graph/filter-options'),
  getStats: () => apiClient.get('/graph/stats'),
  importGraph: (data) => apiClient.post('/graph/import', data),
  initializeSchema: () => apiClient.post('/graph/schema'),
  upsertNode: (id, data) => apiClient.put(`/graph/nodes/${id}`, data),
  upsertRelationship: (id, data) => apiClient.put(`/graph/relationships/${id}`, data),
}
