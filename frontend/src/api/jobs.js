import apiClient from './client'

export default {
  listJobs: (params) => apiClient.get('/jobs/', { params }),
  createJob: (data) => apiClient.post('/jobs/', data),
  getJob: (id) => apiClient.get(`/jobs/${id}`),
  updateJob: (id, data) => apiClient.put(`/jobs/${id}`, data),
  deleteJob: (id) => apiClient.delete(`/jobs/${id}`),
  discoverNewJobs: (data) => apiClient.post('/jobs/discover-new', data),
  getDiscoverStats: () => apiClient.get('/jobs/discover-new/stats'),
  getDiscoverCandidate: (id) => apiClient.get(`/jobs/discover-new/${id}`),
  adoptCandidate: (id, createGraphNodes = true) => apiClient.post(`/jobs/discover-new/${id}/adopt`, null, { params: { create_graph_nodes: createGraphNodes } }),
  rejectCandidate: (id) => apiClient.post(`/jobs/discover-new/${id}/reject`),
  batchAdopt: (data) => apiClient.post('/jobs/discover-new/batch/adopt', data),
  batchReject: (data) => apiClient.post('/jobs/discover-new/batch/reject', data),
  getAdoptionHistory: () => apiClient.get('/jobs/discover-new/history'),
  analyzeEvolution: (data) => apiClient.post('/jobs/evolution', data),
  getEvolutionTimeline: (id, params) => apiClient.get(`/jobs/${id}/evolution-timeline`, { params }),
  getHotSkills: () => apiClient.get('/jobs/skills/hot'),
  getSkillTrend: (name) => apiClient.get(`/jobs/skills/${name}/trend`),
}
