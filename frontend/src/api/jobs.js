import apiClient from './client'

export default {
  listJobs: (params) => apiClient.get('/jobs/', { params }),
  createJob: (data) => apiClient.post('/jobs/', data),
  getJob: (id) => apiClient.get(`/jobs/${id}`),
  updateJob: (id, data) => apiClient.put(`/jobs/${id}`, data),
  deleteJob: (id) => apiClient.delete(`/jobs/${id}`),
  discoverNewJobs: (data) => apiClient.post('/jobs/discover-new', data),
  analyzeEvolution: (data) => apiClient.post('/jobs/evolution', data),
  getEvolutionTimeline: (id, params) => apiClient.get(`/jobs/${id}/evolution-timeline`, { params }),
  getHotSkills: () => apiClient.get('/jobs/skills/hot'),
  getSkillTrend: (name) => apiClient.get(`/jobs/skills/${name}/trend`),
}
