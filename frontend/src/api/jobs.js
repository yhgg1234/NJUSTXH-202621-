import apiClient from './client'

export default {
  discoverNewJobs: (data) => apiClient.post('/jobs/discover-new', data),
  getDiscoverStats: () => apiClient.get('/jobs/discover-new/stats'),
  getDiscoverCandidate: (id) => apiClient.get(`/jobs/discover-new/${id}`),
  editCandidate: (id, data) => apiClient.put(`/jobs/discover-new/${id}`, data),
  adoptCandidate: (id, data) => apiClient.post(`/jobs/discover-new/${id}/adopt`, data),
  rejectCandidate: (id, data) => apiClient.post(`/jobs/discover-new/${id}/reject`, data),
  batchAdopt: (data) => apiClient.post('/jobs/discover-new/batch/adopt', data),
  batchReject: (data) => apiClient.post('/jobs/discover-new/batch/reject', data),
  getAdoptionHistory: () => apiClient.get('/jobs/discover-new/history'),
  analyzeAbilityChanges: (data) => apiClient.post('/jobs/ability-changes/analyze', data),
  listAbilityChanges: (params) => apiClient.get('/jobs/ability-changes', { params }),
  reviewAbilityChange: (id, data) => apiClient.put(`/jobs/ability-changes/${id}/review`, data),
  analyzeEvolution: (data) => apiClient.post('/jobs/evolution', data),
  getEvolutionTimeline: (id, params) => apiClient.get(`/jobs/${id}/evolution-timeline`, { params }),
}
